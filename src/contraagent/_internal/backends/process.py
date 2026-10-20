"""Subprocess loop shared by every headless CLI backend.

Runs argv to completion under the `Limits` deadline, streams stdout
through an optional capture file, and kills the whole process group on
timeout or stall. Knows nothing about claude vs omp output shapes.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
from typing import Protocol

from contraagent._internal.backends import live_processes
from contraagent._internal.backends.launch import STDIN_THRESHOLD, Launch, Stop
from contraagent._internal.errors import ContraagentError
from contraagent._internal.platform.commands import commands
from contraagent._internal.platform.groups import groups

_logger = logging.getLogger(__name__)

# How much of a (possibly very large, stdin-fed) prompt the launch marker
# records. The monitor renders it collapsed, so a generous cap still reads
# fine; anything past it is replaced by a "...(truncated N bytes)" note so a
# multi-megabyte prompt cannot bloat a looped task's stream file unbounded.
_MARKER_PROMPT_CAP = 200_000


def signal_of(exit_code: int | None) -> int | None:
    """The signal that ended a process, or None if it exited on its own.

    Popen reports a signal death as a negative returncode (-15 for SIGTERM).
    A shell wrapper reports the same death as 128+N, so both forms count.
    """
    if exit_code is None:
        return None
    if exit_code < 0:
        return -exit_code
    if exit_code >= 128:
        return exit_code - 128
    return None


class LaunchError(ContraagentError):
    """The child process could not be started (missing binary, bad cwd, ...)."""


class Sink(Protocol):
    """`sink(line)`: one line of a coding agent's output, its newline stripped, as it comes
    (`Backend.watch_stderr`). It returns a `Stop` to end the launch there, as a limit does,
    or None to read on."""

    def __call__(self, line: bytes, /) -> Stop | None: ...


def via_stdin(launch: Launch) -> bool:
    """Long prompts go over stdin. The per-argument limit is 128KB."""
    if launch.prompt_via_stdin is None:
        return len(launch.prompt) > STDIN_THRESHOLD
    return launch.prompt_via_stdin


def _feed(pipe, text: str) -> None:
    try:
        pipe.write(text.encode("utf-8"))
    except (OSError, BrokenPipeError):
        pass
    finally:
        try:
            pipe.close()
        except OSError:
            pass


def _drain(pipe, buf: list[str], sink: Sink | None = None, stops: list[Stop] | None = None) -> None:
    """Read stderr to its end into `buf`; with a `sink`, line by line, its first `Stop` in `stops`."""
    if sink is None:
        try:
            data = pipe.read()
        except OSError:
            return
        buf.append(data.decode("utf-8", "replace") if isinstance(data, bytes) else data)
        return
    try:
        for raw in iter(pipe.readline, b""):
            buf.append(raw.decode("utf-8", "replace"))
            if len(buf) > 200:  # only the tail is returned
                del buf[:100]
            if stops is not None and not stops:
                stop = sink(raw.rstrip(b"\n"))
                if stop is not None:
                    stops.append(stop)
    except (OSError, ValueError):
        return


def _terminate(proc: subprocess.Popen) -> None:
    """Stop the whole process group (`groups`): asked first, killed after 10s. The child
    itself is always waited for, so it is never left unreaped: with no group left to
    signal (on macOS, `killpg` refuses a group whose processes have all ended), the child
    has ended or is ended on its own."""
    try:
        if not groups.terminate(proc):
            if proc.poll() is None:
                proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            groups.kill(proc)
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass  # stuck in the kernel; the caller still gets its result
    finally:
        live_processes.unregister(proc)


def write_launch_marker(argv: list[str], launch: Launch) -> None:
    """Record one invocation's as-is command line + submitted prompt at the
    head of its stream append, so the monitor can split a looped task's
    single stream file into per-invocation tabs and show, for each, the
    exact argv it ran (ask: launch command line) and the prompt it was
    given (ask: submitted prompt — the stream's first `user` event is a
    `<tool_result>`, never the prompt, so it cannot be scraped back out).

    Best-effort: a looped task appends every round to the same
    `stream_path`, and each `run_process` call writes exactly one marker at
    its own append's head. The write never fails the launch — a stream file
    is a convenience transcript, not load-bearing — so an error is a warning
    of this module's logger.
    """
    if launch.stream_path is None:
        return
    try:
        prompt = launch.prompt or ""
        marker: dict = {
            "type": "launch",
            "ts": time.time(),
            "argv": list(argv),
            "cwd": str(launch.cwd),
            "prompt": prompt[:_MARKER_PROMPT_CAP],
        }
        if len(prompt) > _MARKER_PROMPT_CAP:
            marker["prompt_truncated"] = len(prompt) - _MARKER_PROMPT_CAP
        with open(launch.stream_path, "ab") as f:
            f.write((json.dumps(marker, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception as exc:  # a failed marker must never break a launch
        _logger.warning("[error] %s: launch marker not written: %r", launch.stream_path, exc)


def run_process(
    argv: list[str], env: dict[str, str], launch: Launch, sink: Sink | None = None, stderr_sink: Sink | None = None
) -> tuple[bytes, str, int | None, Stop | None]:
    """Run argv to completion under the launch's `Limits`. Returns stdout, stderr tail, exit, kill reason.

    `sink`, when given, is fed one newline-stripped stdout line at a time
    as it arrives, for a caller that needs live per-line inspection (e.g.
    claude's stream-json stop classification). It returning a `Stop` ends
    the run immediately, exactly like a limit timeout or stall. Line
    boundaries are tracked in a buffer kept separate from `stream_path`'s
    own writes, which stay exactly the raw bytes read off the fd — the
    sink's bookkeeping never touches what lands on disk.

    `stderr_sink` is the same for stderr, for a CLI that reports something
    only there (opencode logs a provider's refusal it keeps retrying, and
    prints nothing on stdout while it waits). Its `Stop` ends the run
    within a second.
    """
    started_wall = time.monotonic()
    if live_processes.launches_refused():
        raise LaunchError(live_processes.REFUSED)
    since = live_processes.epoch()
    try:
        proc = subprocess.Popen(
            commands.resolve(argv, env.get("PATH")),
            cwd=launch.cwd,
            env=env,
            stdin=subprocess.PIPE if via_stdin(launch) else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **groups.popen_options(),
        )
    except OSError as exc:
        raise LaunchError(str(exc)) from exc
    if not live_processes.register(proc, since=since):  # stopped already; waited for here
        _terminate(proc)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()
        raise LaunchError(live_processes.REFUSED)
    try:
        return _supervise(proc, argv, launch, sink, started_wall, stderr_sink)
    finally:
        live_processes.unregister(proc)


def _supervise(
    proc: subprocess.Popen, argv: list[str], launch: Launch, sink: Sink | None, started_wall: float, stderr_sink: Sink | None = None
) -> tuple[bytes, str, int | None, Stop | None]:
    # Head of this invocation's stream append: the as-is argv + submitted
    # prompt, before any of the child's own output lands. Written once per
    # run_process call, so a looped task's shared stream file carries one
    # marker per round -- the monitor's per-invocation boundary.
    write_launch_marker(argv, launch)
    if via_stdin(launch):
        threading.Thread(target=_feed, args=(proc.stdin, launch.prompt), daemon=True).start()
    stderr_buf: list[str] = []
    stderr_stops: list[Stop] = []
    assert proc.stderr is not None
    th = threading.Thread(target=_drain, args=(proc.stderr, stderr_buf, stderr_sink, stderr_stops), daemon=True)
    th.start()
    assert proc.stdout is not None
    chunks: queue.Queue[bytes] = queue.Queue()
    reader = threading.Thread(target=_read_chunks, args=(proc.stdout, chunks), daemon=True)
    reader.start()
    deadline = started_wall + launch.limits.timeout_s
    stall_s = launch.limits.stall_s
    last_line = started_wall
    # Chunks are collected and joined once: `bytes +=` copies the whole
    # transcript on every read, quadratic for a multi-megabyte stream.
    out: list[bytes] = []
    pending: list[bytes] = []  # sink-only: the unterminated tail line, never written to disk
    killed: Stop | None = None
    # Unbuffered so each chunk is on disk as soon as it is read: the monitor
    # tails this file while the agent runs.
    stream = open(launch.stream_path, "ab", buffering=0) if launch.stream_path is not None else None
    try:
        # A thread reads the pipe (no `select`, which on Windows takes sockets only) and
        # hands each chunk over as it comes; the wait for one is bounded below.
        while True:
            now = time.monotonic()
            if now >= deadline:
                killed = Stop.TIMEOUT
                break
            if stall_s and now - last_line > stall_s:
                killed = Stop.STALLED
                break
            if stderr_stops:
                killed = stderr_stops[0]
                break
            # Wake no later than the stall check is due, so a short stall_s
            # is enforced at its own resolution rather than the 1s poll's.
            wait = min(deadline - now, 1.0)
            if stall_s:
                wait = min(wait, max(0.0, last_line + stall_s - now) + 0.01)
            try:
                chunk = chunks.get(timeout=wait)
            except queue.Empty:
                continue
            if not chunk:
                break
            last_line = time.monotonic()
            out.append(chunk)
            if stream is not None:
                stream.write(chunk)
            if sink is not None:
                killed = _feed_sink(sink, pending, chunk)
                if killed is not None:
                    break
        if killed is None and sink is not None and pending:
            sink(b"".join(pending))
        if killed is None:
            # EOF on stdout is not exit: a child can close its stdout and
            # keep running, so the wait is still bounded by the deadline.
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                killed = Stop.TIMEOUT
    finally:
        if stream is not None:
            stream.close()
        if killed is not None or proc.poll() is None:
            _terminate(proc)
    exit_code = proc.returncode
    joined_by = time.monotonic() + 5
    for t in (th, reader):
        t.join(timeout=max(0.0, joined_by - time.monotonic()))
    _close_pipes(proc, stdout_read=not reader.is_alive(), stderr_read=not th.is_alive())
    return b"".join(out), "".join(stderr_buf)[-2000:], exit_code, killed


def _read_chunks(pipe, chunks: queue.Queue[bytes]) -> None:
    """Put each chunk read from `pipe` on `chunks` as it comes, then an empty one at its end."""
    fd = pipe.fileno()
    try:
        while chunk := os.read(fd, 1 << 16):
            chunks.put(chunk)
    except (OSError, ValueError):
        pass
    chunks.put(b"")


def _close_pipes(proc: subprocess.Popen, *, stdout_read: bool, stderr_read: bool) -> None:
    """Close the pipes this process read, so none is left for the garbage collector
    (a ResourceWarning). stdout and stderr only once their readers have finished: a
    grandchild that keeps one open would otherwise have its reader closed under it."""
    pipes = [proc.stdin] + ([proc.stdout] if stdout_read else []) + ([proc.stderr] if stderr_read else [])
    for pipe in pipes:
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass


def _feed_sink(sink: Sink, pending: list[bytes], chunk: bytes) -> Stop | None:
    """Hand `sink` every line `chunk` completes; keep the unterminated rest in `pending`.

    Only the new chunk is split, so a long line arriving in many chunks is
    joined once when its newline lands, not re-split on every read.
    """
    *lines, tail = chunk.split(b"\n")
    if lines:
        lines[0] = b"".join(pending) + lines[0]
        pending.clear()
    if tail:
        pending.append(tail)
    for raw in lines:
        stop_now = sink(raw)
        if stop_now is not None:
            return stop_now
    return None
