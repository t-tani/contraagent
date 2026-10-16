"""omp RPC backend: one `omp --mode rpc --no-session` process per task.

Same isolation as `-p` (one process per launch), but the wire gives
what text mode cannot: the agent events `--mode json` prints (read by the
same `TraceReader`), and `abort` for `Limits` deadlines instead of SIGKILL.
Only the exchange differs from the omp backend (`OmpRpcBackend.exchange`):
the rest of a launch is `Backend.run`'s, as for every agent.

Protocol: NDJSON over stdin/stdout (docs: https://omp.sh/docs/rpc).
`ready` handshake, immediate v2 negotiate (rpc_chunk reassembly),
one `prompt`, completion at terminal `agent_end` (isTerminal != false)
or `prompt_result`/`response` with `agentInvoked: false`.
`@file` CLI args are rejected in RPC mode, so the agent .md rides
inside the message text, not context_files.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

from contraagent._internal.backends import live_processes
from contraagent._internal.backends.launch import Launch, Stop
from contraagent._internal.backends.omp import wire as omp_wire
from contraagent._internal.backends.omp.backend import OmpBackend, isolation_args, plugin_extension_args, prompt_args, session_args
from contraagent._internal.backends.omp.wire import TraceReader
from contraagent._internal.backends.process import LaunchError
from contraagent._internal.backends.refusal import FAILED_STOPS, Signals
from contraagent._internal.backends.wire import EventFold, LimitsWatch, positive_int
from contraagent._internal.platform.commands import commands
from contraagent._internal.platform.groups import groups

#: The id of the post-turn `get_state` request (`OmpRpcBackend._harvest_state`).
STATE_REQUEST = "harvest-state"

#: Frames of the RPC protocol itself, around the agent events: read here or ignored,
#: never counted as unread agent events.
RPC_FRAMES = {
    "ready",
    "response",
    "prompt_result",
    "rpc_chunk",
    "session_stats",
    "stats",
    "extension_ui_request",
    "available_commands_update",
}


class RpcReader(TraceReader):
    """omp's agent events over RPC (`TraceReader`), with the protocol's own frames read
    first: chunks, responses, the terminal `agent_end` (`done`)."""

    def __init__(self, prompt_id: str = "p1") -> None:
        super().__init__()
        #: The id of the launch's `prompt` request.
        self.prompt_id = prompt_id
        self.chunks: dict[str, dict] = {}
        #: The turn is over.
        self.done = False
        #: The `get_state` response arrived.
        self.state_seen = False

    def feed(self, ev: dict) -> Stop | None:
        """Absorb one frame; `done` turns True on the terminal one."""
        typ = ev.get("type")
        if typ == "rpc_chunk":
            self._chunk(ev)
        elif typ not in RPC_FRAMES:
            super().feed(ev)
            # A nested turn's end (a subagent's) says isTerminal false: the prompt goes on.
            if typ == "agent_end" and ev.get("isTerminal") is not False:
                self.done = True
        elif typ == "response":
            data = ev.get("data") or {}
            if ev.get("id") == STATE_REQUEST:
                self.state_seen = True
                self.apply_state(data if isinstance(data, dict) else {})
                return None
            if ev.get("success") is False and isinstance(ev.get("error"), str):
                self._error({"errorMessage": ev["error"]})
            if isinstance(data, dict) and data.get("agentInvoked") is False and ev.get("id") == self.prompt_id:
                self.done = True
        elif typ == "prompt_result":
            if ev.get("id") == self.prompt_id and ev.get("agentInvoked") is False:
                self.done = True
        elif typ in ("session_stats", "stats"):
            data = ev.get("data")
            data = data if isinstance(data, dict) else ev
            if data.get("sessionId"):
                self.session_id = str(data["sessionId"])
        return None

    def _chunk(self, frame: dict) -> None:
        """Reassemble v2 rpc_chunk sequences, then feed the logical frame."""
        cid = str(frame.get("chunkId") or "")
        try:
            idx = int(frame.get("index", -1))
            count = int(frame.get("count", 0))
        except (TypeError, ValueError):
            return
        slot = self.chunks.setdefault(cid, {"parts": {}, "count": count})
        slot["count"] = count
        try:
            slot["parts"][idx] = base64.b64decode(str(frame.get("data") or ""))
        except (TypeError, ValueError):
            return
        if len(slot["parts"]) != count:
            return
        try:
            logical = json.loads(b"".join(slot["parts"][i] for i in range(count)))
        except (ValueError, KeyError):
            return
        finally:
            del self.chunks[cid]
        if isinstance(logical, dict):
            self.feed(logical)

    def apply_state(self, data: dict) -> None:
        """The session id and the model's context window (`model.contextWindow`) from a
        post-turn `get_state` (tokens and cost come from each assistant `message_end`)."""
        if data.get("sessionId"):
            self.session_id = str(data["sessionId"])
        model = data.get("model")
        window = positive_int(model.get("contextWindow")) if isinstance(model, dict) else None
        if window is not None:
            self.context_window = window


class OmpRpcBackend(OmpBackend):
    """RPC variant of the omp backend: argv and the exchange its own, the rest shared."""

    name = "omp-rpc"
    # The RPC wire is JSON frames only.
    plaintext_stream = False
    # No exit status to weigh: a process that ended before any agent event is a launch
    # failure, and a quota refusal it printed on stderr makes it `rate_limited`.
    signals: Signals = dataclasses.replace(omp_wire.SIGNALS, stderr_stops=FAILED_STOPS | {Stop.LAUNCH_FAILED})

    def argv(self, launch: Launch) -> list[str]:
        a = [self.binary, "--mode", "rpc"]
        # Ephemeral unless the run may resume this session: then it is
        # saved under the launch's own session_dir.
        a += session_args(launch) if launch.session_dir is not None or launch.resume else ["--no-session"]
        for plug in self._loaded_plugin_dirs(launch):
            a += ["--plugin-dir", plug]
        a += plugin_extension_args(launch.plugin_dirs)
        # Same neutral effort as the omp backend: the launch value wins
        # over the constructor default so a per-task effort reaches the CLI.
        a += ["--thinking", launch.effort or self.thinking, "--approval-mode", "yolo", *isolation_args()]
        a += prompt_args(launch)
        if launch.limits.timeout_s:
            # CLI-side backstop behind the loop's own abort: the process
            # dies even if our abort frame is lost.
            a += ["--max-time", str(int(launch.limits.timeout_s))]
        if launch.model:
            a += ["--model", launch.model]
        a += self.bind_credential(launch.credential, launch.model, label=launch.label).args
        return a

    def fold(self, launch: Launch) -> EventFold:
        return RpcReader(launch.label or "p1")

    def exchange(
        self, launch: Launch, argv: list[str], env: dict[str, str], fold: EventFold, watch: LimitsWatch
    ) -> tuple[bytes, str, int | None, Stop | None]:
        """One RPC process: the handshake, the prompt, its frames to `fold` until the terminal
        one, then `get_state`. A limit (`watch`, the deadline) sends `abort`. No process exit
        to weigh: the exit status is None."""
        assert isinstance(fold, RpcReader)
        since = live_processes.epoch()
        try:
            proc = subprocess.Popen(
                commands.resolve(argv, env.get("PATH")),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(launch.cwd),
                env=env,
                **groups.popen_options(),
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise LaunchError(str(exc)) from exc
        live_processes.register(proc, since=since)
        stderr: list[str] = []
        try:
            frames = self._start_readers(proc, launch, stderr)
            killed, why = self._converse(proc, frames, launch, fold, watch)
        finally:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except (OSError, BrokenPipeError):
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                groups.kill(proc)
                proc.wait()
            live_processes.unregister(proc)
            # The process is gone; its readers are at EOF or take a closed pipe as one.
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe:
                        pipe.close()
                except OSError:
                    pass
        tail = "\n".join(x for x in (why, "".join(stderr)[-2000:].strip()) if x)
        return b"", tail, None, killed

    # --- exchange -----------------------------------------------------

    def _start_readers(self, proc: subprocess.Popen, launch: Launch, stderr: list[str]) -> queue.Queue:
        """Threads that put each stdout line on the returned queue (and on the stream file)
        and keep the tail of stderr in `stderr`."""
        assert proc.stdout is not None and proc.stderr is not None
        stdout, errout = proc.stdout, proc.stderr
        frames: queue.Queue = queue.Queue()

        def read() -> None:
            try:
                for line in stdout:
                    # This backend drives its own process, not `run_process`, so it writes
                    # the stream file itself.
                    if launch.stream_path is not None:
                        try:
                            with open(launch.stream_path, "a", encoding="utf-8", newline="\n") as f:
                                f.write(line)
                        except OSError:
                            pass
                    frames.put(("line", line))
            except (OSError, ValueError):
                pass
            finally:
                frames.put(("eof", ""))

        def drain() -> None:
            """stderr is diagnostics: kept as a tail, never read as frames."""
            try:
                for line in errout:
                    stderr.append(line)
                    if len(stderr) > 200:
                        del stderr[:100]
            except (OSError, ValueError):
                pass

        threading.Thread(target=read, daemon=True).start()
        threading.Thread(target=drain, daemon=True).start()
        return frames

    def _converse(
        self, proc: subprocess.Popen, frames: queue.Queue, launch: Launch, fold: RpcReader, watch: LimitsWatch
    ) -> tuple[Stop | None, str]:
        """The handshake, the prompt and its frames. The kill reason and why, if one."""
        deadline = time.monotonic() + (launch.limits.timeout_s or 600.0)
        try:
            ready = self._next(frames, deadline, ("ready",))
        except TimeoutError:
            return Stop.TIMEOUT, "no ready frame"
        if ready.get("type") != "ready":
            raise LaunchError(f"expected ready, got {str(ready)[:120]}")
        if 2 in (ready.get("supportedProtocolVersions") or [1]):
            self._send(proc, {"id": "proto-1", "type": "negotiate_protocol", "protocolVersion": 2})
        self._send(proc, {"id": fold.prompt_id, "type": "prompt", "message": self._message(launch)})
        killed = self._drain_loop(proc, frames, fold, watch, deadline)
        if killed is None:
            self._harvest_state(proc, frames, fold, deadline)
        return killed, ""

    def _drain_loop(self, proc: subprocess.Popen, frames: queue.Queue, fold: RpcReader, watch: LimitsWatch, deadline: float) -> Stop | None:
        """Frames until the terminal one. The kill reason, or None."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._send(proc, {"id": f"{fold.prompt_id}-abort", "type": "abort"})
                return Stop.TIMEOUT
            try:
                kind, payload = frames.get(timeout=min(remaining, 5.0))
            except queue.Empty:
                continue
            if kind == "eof":
                return None
            fold.feed_line(payload.encode("utf-8"))
            if fold.done:
                return None
            stop = watch()
            if stop is not None:
                self._send(proc, {"id": f"{fold.prompt_id}-abort", "type": "abort"})
                return stop

    def _harvest_state(self, proc: subprocess.Popen, frames: queue.Queue, fold: RpcReader, deadline: float) -> None:
        """get_state after the turn: the session id and the model's context window. Best-effort:
        frames that arrive before its response (late events, a chunked response) go to the
        reader; waits at most 10 s, never past the launch's deadline."""
        self._send(proc, {"id": STATE_REQUEST, "type": "get_state"})
        until = min(deadline, time.monotonic() + 10.0)
        while not fold.state_seen:
            remaining = until - time.monotonic()
            if remaining <= 0:
                return
            try:
                kind, payload = frames.get(timeout=remaining)
            except queue.Empty:
                return
            if kind == "eof":
                return
            fold.feed_line(payload.encode("utf-8"))

    def _message(self, launch: Launch) -> str:
        """Prompt plus the agent .md inline (RPC rejects `@file` args)."""
        parts = []
        if launch.preamble:
            parts.append(launch.preamble)
        for f in launch.context_files:
            try:
                parts.append(Path(f).read_text(encoding="utf-8")[:60_000])
            except (OSError, ValueError):
                continue
        parts.append(launch.prompt)
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _send(proc: subprocess.Popen, obj: dict) -> None:
        assert proc.stdin is not None
        try:
            proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except (OSError, BrokenPipeError, ValueError):
            pass  # the process is gone; its frames say how it ended

    @staticmethod
    def _next(frames: queue.Queue, deadline: float, want: tuple[str, ...]) -> dict:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("rpc wait expired")
            try:
                kind, payload = frames.get(timeout=min(remaining, 5.0))
            except queue.Empty:
                continue
            if kind == "eof":
                raise TimeoutError("rpc stdout closed")
            try:
                frame = json.loads(payload)
            except ValueError:
                continue
            if isinstance(frame, dict) and (not want or frame.get("type") in want):
                return frame
