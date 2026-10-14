"""omp RPC backend: one `omp --mode rpc --no-session` process per task.

Same isolation as `-p` (one process per launch), but the wire gives
what text mode cannot: the agent events `--mode json` prints (read by the
same `TraceReader`), and `abort` for `Limits` deadlines instead of SIGKILL.

Protocol: NDJSON over stdin/stdout (docs: https://omp.sh/docs/rpc).
`ready` handshake, immediate v2 negotiate (rpc_chunk reassembly),
one `prompt`, completion at terminal `agent_end` (isTerminal != false)
or `prompt_result`/`response` with `agentInvoked: false`.
`@file` CLI args are rejected in RPC mode, so the agent .md rides
inside the message text, not context_files.
"""

from __future__ import annotations

import base64
import json
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from contraagent.backends import live_processes
from contraagent.backends.credentials import CredentialError
from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.backends.omp.backend import OmpBackend, isolation_args, plugin_extension_args, prompt_args, session_args
from contraagent.backends.omp.trace import TraceReader


class OmpRpcBackend(OmpBackend):
    """RPC variant of the omp backend. argv/env/parse surface shared."""

    name = "omp-rpc"

    def argv(self, launch: Launch) -> list[str]:
        a = [self.binary, "--mode", "rpc"]
        # Ephemeral unless the run may resume this session: then it is
        # saved under the launch's own session_dir.
        a += session_args(launch) if launch.session_dir is not None or launch.resume else ["--no-session"]
        for plug in launch.plugin_dirs:
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

    def parse(self, launch: Launch, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """Unused: `_launch` drives the event loop directly."""
        raise NotImplementedError("OmpRpcBackend._launch drives its own loop")

    def _launch(self, launch: Launch) -> LaunchResult:
        """One RPC process per launch. Rewards: tool_uses, usage, abort."""

        t0 = time.monotonic()
        try:
            argv = self.argv(launch)
            env = self.env(launch)
        except CredentialError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                credential=launch.credential.label,
                stderr_tail=f"credential: {exc}",
            )
        if not shutil.which(self.binary, path=self.base_path()):
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                argv=argv,
                stderr_tail=f"{self.binary} not on PATH",
            )
        since = live_processes.epoch()
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(launch.cwd),
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            # Same as every other backend: a launch that cannot start is a
            # result the router fails over on, not an exception.
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                argv=argv,
                credential=launch.credential.label,
                stderr_tail=str(exc),
                wall_s=time.monotonic() - t0,
            )
        live_processes.register(proc, since=since)
        try:
            launch_result = self._exchange(proc, launch, argv)
            launch_result.credential = launch.credential.label
        finally:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except (OSError, BrokenPipeError):
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            live_processes.unregister(proc)
        launch_result.wall_s = time.monotonic() - t0
        return launch_result

    # --- exchange -----------------------------------------------------

    def _exchange(self, proc: subprocess.Popen, launch: Launch, argv: list[str]) -> LaunchResult:
        assert proc.stdin is not None and proc.stdout is not None
        stdout = proc.stdout
        errors: queue.Queue = queue.Queue()

        def reader() -> None:
            try:
                for line in stdout:
                    # Mirrors run_process()'s raw passthrough to
                    # stream_path -- this backend drives its own loop
                    # instead of going through run_process(), so without
                    # this write here a task's stream file never existed
                    # at all (not malformed, just absent).
                    if launch.stream_path is not None:
                        try:
                            with open(launch.stream_path, "a") as f:
                                f.write(line)
                        except OSError:
                            pass
                    errors.put(("line", line))
            except (OSError, ValueError):
                pass
            finally:
                errors.put(("eof", ""))

        def drain() -> None:
            """stderr is diagnostics-only; never merge into the JSON parser."""
            assert proc.stderr is not None
            try:
                for _ in proc.stderr:
                    pass
            except (OSError, ValueError):
                pass

        th = threading.Thread(target=reader, daemon=True)
        th.start()
        th_err = threading.Thread(target=drain, daemon=True)
        th_err.start()

        deadline = time.monotonic() + (launch.limits.timeout_s or 600.0)
        try:
            ready = self._next(errors, deadline, ("ready",))
        except TimeoutError:
            return self._dead(launch, argv, Stop.TIMEOUT, "no ready frame")
        if ready.get("type") != "ready":
            return self._dead(launch, argv, Stop.LAUNCH_FAILED, f"expected ready, got {str(ready)[:120]}")
        versions = ready.get("supportedProtocolVersions") or [1]
        if 2 in versions:
            self._send(proc, {"id": "proto-1", "type": "negotiate_protocol", "protocolVersion": 2})
        message = self._message(launch)
        self._send(proc, {"id": launch.label or "p1", "type": "prompt", "message": message})
        acc = _Accumulator()
        pid = launch.label or "p1"
        killed = self._drain_loop(proc, errors, launch, argv, acc, pid, deadline)
        self._harvest_state(proc, errors, acc, deadline)
        return acc.launch_result(launch, self.name, argv, killed)

    def _drain_loop(
        self, proc: subprocess.Popen, errors: queue.Queue, launch: Launch, argv: list[str], acc: _Accumulator, pid: str, deadline: float
    ) -> Stop | None:
        """Event loop until the terminal frame. Killed reason or None."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._send(proc, {"id": f"{pid}-abort", "type": "abort"})
                return Stop.TIMEOUT
            try:
                kind, payload = errors.get(timeout=min(remaining, 5.0))
            except queue.Empty:
                continue
            if kind == "eof":
                return None
            try:
                frame = json.loads(payload)
            except ValueError:
                continue
            if not isinstance(frame, dict):
                continue
            done = acc.feed(frame, pid)
            if done:
                return None

    def _harvest_state(self, proc: subprocess.Popen, errors: queue.Queue, acc: _Accumulator, deadline: float) -> None:
        """get_state after the turn: the session id. Best-effort: frames that arrive
        before its response (late events, a chunked response) go through the
        accumulator; waits at most 10 s, never past the launch's deadline."""
        self._send(proc, {"id": STATE_REQUEST, "type": "get_state"})
        until = min(deadline, time.monotonic() + 10.0)
        while not acc.state_seen:
            remaining = until - time.monotonic()
            if remaining <= 0:
                return
            try:
                kind, payload = errors.get(timeout=remaining)
            except queue.Empty:
                return
            if kind == "eof":
                return
            try:
                frame = json.loads(payload)
            except ValueError:
                continue
            if isinstance(frame, dict):
                acc.feed(frame, "")

    def _message(self, launch: Launch) -> str:
        """Prompt plus the agent .md inline (RPC rejects `@file` args)."""
        parts = []
        if launch.preamble:
            parts.append(launch.preamble)
        for f in launch.context_files:
            try:
                parts.append(Path(f).read_text()[:60_000])
            except (OSError, ValueError):
                continue
        parts.append(launch.prompt)
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _send(proc: subprocess.Popen, obj: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    @staticmethod
    def _next(errors: queue.Queue, deadline: float, want: tuple[str, ...]) -> dict:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("rpc wait expired")
            try:
                kind, payload = errors.get(timeout=min(remaining, 5.0))
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

    def _dead(self, launch: Launch, argv: list[str], stop: Stop, err: str) -> LaunchResult:
        return LaunchResult(label=launch.label, agent=self.name, stop=stop, ok=False, model=launch.model, argv=argv, stderr_tail=err)


#: The id of the post-turn `get_state` request (`_harvest_state`).
STATE_REQUEST = "harvest-state"

#: Frames of the RPC protocol itself, around the agent events: read here or ignored,
#: never handed to the `TraceReader` (which would count them as unread).
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


class _Accumulator:
    """The RPC protocol's own frames (chunks, responses, the terminal `agent_end`);
    every agent event goes to the `TraceReader` both omp wires share."""

    def __init__(self) -> None:
        self.reader = TraceReader()
        self.chunks: dict[str, dict] = {}
        #: The `get_state` response arrived.
        self.state_seen = False

    @property
    def session_id(self) -> str:
        return self.reader.session_id

    def feed(self, frame: dict, pid: str) -> bool:
        """Absorb one frame. True when the turn is terminal."""
        typ = frame.get("type")
        if typ == "rpc_chunk":
            return self._chunk(frame, pid)
        if typ not in RPC_FRAMES:
            self.reader.feed(frame)
            # A nested turn's end (a subagent's) says isTerminal false: the prompt goes on.
            return typ == "agent_end" and frame.get("isTerminal") is not False
        if typ == "response":
            data = frame.get("data") or {}
            if frame.get("id") == STATE_REQUEST:
                self.state_seen = True
                self.apply_state(data if isinstance(data, dict) else {})
                return False
            if frame.get("success") is False and isinstance(frame.get("error"), str):
                self.reader._error({"errorMessage": frame["error"]})
            if isinstance(data, dict) and data.get("agentInvoked") is False and frame.get("id") == pid:
                return True
        elif typ == "prompt_result":
            return frame.get("id") == pid and frame.get("agentInvoked") is False
        elif typ in ("session_stats", "stats"):
            data = frame.get("data")
            data = data if isinstance(data, dict) else frame
            if data.get("sessionId"):
                self.reader.session_id = str(data["sessionId"])
        return False

    def _chunk(self, frame: dict, pid: str) -> bool:
        """Reassemble v2 rpc_chunk sequences, then feed the logical frame."""
        cid = str(frame.get("chunkId") or "")
        try:
            idx = int(frame.get("index", -1))
            count = int(frame.get("count", 0))
        except (TypeError, ValueError):
            return False
        slot = self.chunks.setdefault(cid, {"parts": {}, "count": count})
        slot["count"] = count
        try:
            slot["parts"][idx] = base64.b64decode(str(frame.get("data") or ""))
        except (TypeError, ValueError):
            return False
        if len(slot["parts"]) != count:
            return False
        try:
            logical = json.loads(b"".join(slot["parts"][i] for i in range(count)))
        except (ValueError, KeyError):
            return False
        finally:
            del self.chunks[cid]
        if isinstance(logical, dict):
            return self.feed(logical, pid)
        return False

    def apply_state(self, data: dict) -> None:
        """The session id from a post-turn `get_state` (tokens and cost come from each
        assistant `message_end`)."""
        if data.get("sessionId"):
            self.reader.session_id = str(data["sessionId"])

    def launch_result(self, launch: Launch, agent: str, argv: list[str], killed: Stop | None) -> LaunchResult:
        """Build the LaunchResult from folded frames. No process exit to weigh: `exit_code` None."""
        return self.reader.result(launch, agent, exit_code=None, killed=killed, argv=argv)
