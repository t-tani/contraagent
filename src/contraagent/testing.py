"""A stub coding agent for tests: a `Backend` that plays scripted replies instead of an LLM.

Only the coding agent is replaced. The runner, the output checks and the
fix-up rounds, failover, retries, the journal and the monitor all run as
they do in production, so a flow's wiring is tested without spending tokens:

    stub = StubAgent({
        "summarize": lambda launch: {"unit": launch.unit, "points": ["a", "b", "c"]},
        "review": [fails(), {"approved": True, "note": "ok"}],   # one reply per launch
        "summarize-beta": rate_limited(),                          # a task key outranks its kind
    })
    report = Pipeline("pipeline.toml", backends=stub.backends()).run(docs, units=["alpha", "beta"])
    assert [l.key for l in stub.launches if l.resumed] == []

A reply is one of:

* a value: the output to write (a pydantic model or a dict as JSON, a `str` as is), or for
  a task whose output is its final message (`output_from="message"`), the final message;
* `writes(value)`: the same, explicitly (a JSON list output needs it);
* `writes_smallest()`: the smallest value the output's schema accepts (`contracts.smallest`);
  a schema rule it cannot build (`pattern`) fails the launch and names the rule;
* `writes_nothing()`: the launch completes and leaves no file;
* `fails(stop, reason)`: the launch ends on `stop` (default `error`);
* `rate_limited(retry_after_s)`: a 429, which moves the task to its next hop;
* a callable `(StubLaunch) -> reply`: decided per launch;
* a list or tuple of replies: one per reply of that task in a run, the last one repeating.

Script keys are a task key (`summarize-beta`) or a kind (`summarize`); the key
wins. A task with no reply scripted gets `default` (`StubAgent(default=...)`); with
none, its launch ends `error` and says so.

A **stub run** (`Pipeline(stub=StubAgent(...))`, `contraagent run --stub`) plays the
Python tasks too: a Python task's function does not run, and its reply is its
return value (`writes_nothing()`: no output; `fails()`: it raises), from the same
script; a callable reply is given a `StubTask`. The kinds in `execute` run their
functions as in any run. Flow code runs in a stub run as in any run.

Under a name whose coding agent continues its turn when a stop hook objects
(Claude Code), the stub does what that agent does: once it has written its
output it runs the Stop hooks of the launch's plugins (their rendered
`hooks/hooks.json`, with the agent's working directory and environment), and
when one exits 2 it is sent the hook's message and replies again in the same
launch (`StubLaunch.in_turn`). Under omp's names it stops, as omp does.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contraagent import envvars
from contraagent.backends import Backend, ClaudeBackend, backend_class, known_agents
from contraagent.backends.claude.stream import feedback_errors
from contraagent.backends.credentials import CredentialBase, CredentialBinding
from contraagent.backends.launch import Launch, LaunchResult, RateLimit, Stop
from contraagent.backends.process import write_launch_marker
from contraagent.backends.streams import resolve_format
from contraagent.calls import CallFile
from contraagent.contracts import smallest

_UNSET: Any = object()
#: How many times a stop hook may send the output back within one launch.
_MAX_HOOK_OBJECTIONS = 5


@dataclass(frozen=True)
class Reply:
    """What the stub does on one launch. Build one with `writes`, `writes_nothing`, `fails`, `rate_limited`."""

    output: Any = _UNSET
    stop: Stop = Stop.COMPLETED
    reason: str = ""
    rate_limit: RateLimit | None = None
    cost_usd: float | None = None


def writes(value: Any, *, cost_usd: float | None = None) -> Reply:
    """Write `value` to the call's output file: a pydantic model or any JSON value as JSON, a `str` as is."""
    return Reply(output=value, cost_usd=cost_usd)


#: The output of `writes_smallest()`: built from the output's schema when it is played.
_SMALLEST: Any = object()


def writes_smallest() -> Reply:
    """Write the smallest value the output's schema accepts (`contraagent.contracts.smallest`):
    required fields only, the shortest lists and strings, numbers nearest zero. A text
    output is `stub`. A schema rule it cannot build (`pattern`) fails the reply and names it."""
    return Reply(output=_SMALLEST)


def writes_nothing() -> Reply:
    """Complete without writing the output file."""
    return Reply()


def fails(stop: Stop = Stop.ERROR, reason: str = "stub: scripted failure") -> Reply:
    """End the launch on `stop` without writing anything."""
    return Reply(stop=stop, reason=reason)


def rate_limited(retry_after_s: float | None = None) -> Reply:
    """A 429: the task moves to its next failover hop, if it has one."""
    return Reply(stop=Stop.RATE_LIMITED, reason="stub: 429 Too Many Requests", rate_limit=RateLimit(retry_after_s=retry_after_s))


@dataclass(frozen=True)
class StubLaunch:
    """One launch the stub received: what a reply callable is given, and what `StubAgent.launches` records."""

    run: str
    key: str
    kind: str
    unit: str
    params: dict[str, Any]
    #: The launch's LLM (the route's model on a failover hop).
    model: str
    role: str | None
    #: 1-based count of this task's replies in this run: fix-up rounds, retries, hops and replies in a turn all count.
    n: int
    #: True for a fix-up round: the same session, sent the failed checks.
    resumed: bool
    #: The launch's prompt, or for a reply within the turn what the stop hook said.
    prompt: str
    call: CallFile = field(repr=False)
    #: The `Launch` itself: its budget (`limits`), `env`, `plugin_dirs`, credential.
    launch: Launch = field(repr=False)
    #: True for a reply within the launch, after a stop hook sent the output back.
    in_turn: bool = False


@dataclass(frozen=True)
class StubTask:
    """One Python task a stub run played: what a reply callable is given, and what
    `StubAgent.played` records."""

    run: str
    key: str
    kind: str
    unit: str
    #: The function's arguments, upstream outputs resolved.
    params: dict[str, Any] = field(repr=False)
    #: 1-based count of this task's replies in this run.
    n: int


Script = Mapping[str, Any]


class StubAgent(Backend):
    """A coding agent that reads its call file and plays the reply scripted for the task.

    `script`: task key or kind -> reply (see the module docstring). `default`: the
    reply of a task with none scripted (`writes_smallest()` in `contraagent run --stub`).
    `execute`: in a stub run, the Python task kinds whose functions run instead of
    being played. `delay_s`: a pause per launch, for watching a stub run in the monitor.
    """

    name = "stub"
    binary = ""

    def __init__(self, script: Script | None = None, *, default: Any = _UNSET, execute: Iterable[str] = (), delay_s: float = 0.0) -> None:
        super().__init__(base_env={})
        self.script: dict[str, Any] = dict(script or {})
        self.default = default
        self.execute: frozenset[str] = frozenset(execute)
        self.delay_s = delay_s
        #: Every launch, in the order they arrived.
        self.launches: list[StubLaunch] = []
        #: Every Python task a stub run played, in the order they ran.
        self.played: list[StubTask] = []
        self._counts: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def backends(self, names: Iterable[str] | None = None) -> dict[str, StubAgent]:
        """This stub under every coding-agent name (default: every registered one, and `stub`),
        for `Pipeline(backends=...)`: a config's routes and failover hops all land on it.
        Each answers to its own name (the journal's `agent`) and shares this one's
        script and record of launches."""
        return {n: self._named(n) for n in (*(names if names is not None else known_agents()), self.name)}

    def _named(self, name: str) -> StubAgent:
        view = copy.copy(self)  # shallow: the script, the launches and the lock stay shared
        view.name = name
        return view

    def launches_of(self, key: str, run: str | None = None) -> list[StubLaunch]:
        """The launches of task `key`, of every run or of `run`."""
        return [launch for launch in self.launches if launch.key == key and run in (None, launch.run)]

    # --- Backend -----------------------------------------------------------

    def argv(self, launch: Launch) -> list[str]:
        return ["stub", "--model", launch.model or "-", "--agent", launch.role or "-"]

    def env(self, launch: Launch) -> dict[str, str]:
        return {}

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """Any credential: the stub makes no API call, so none is used in place of another."""
        return CredentialBinding(isolated=True, isolation="stub: no API calls")

    def resumable(self, launch: Launch) -> Launch:
        return launch  # the session id in each result is enough to resume

    def run(self, launch: Launch) -> LaunchResult:
        started = time.monotonic()
        call_path = launch.env.get(envvars.CALL)
        if not call_path:
            return self._result(launch, started, fails(reason="stub: no call file (an agent task without a call file)"))
        call = CallFile.read(Path(call_path))
        write_launch_marker(self.argv(launch), launch)
        self._tool(launch, f"{call.key}-read", "Read", call_path, json.dumps(call.params, ensure_ascii=False)[:2000])
        record = self._record(launch, call, prompt=launch.prompt, in_turn=False)
        message: list[str] = []  # the final message, for an output taken from it
        reply = self._play(launch, call, record, message)
        objections: list[list[str]] = []
        while reply.stop is Stop.COMPLETED and self._continues_on_stop_hook():
            said = self._stop_hooks(launch, active=bool(objections))
            if said is None or len(objections) >= _MAX_HOOK_OBJECTIONS:
                break
            objections.append(feedback_errors(said))
            self._text(launch, f"stop hook: {said}")
            reply = self._play(launch, call, self._record(launch, call, prompt=said, in_turn=True), message)
        self._text(launch, message[-1] if message else f"stub: {_describe(reply)}")
        result = self._result(launch, started, reply)
        result.hook_errors = objections
        result.result_text = message[-1] if message else ""
        return result

    def _record(self, launch: Launch, call: CallFile, *, prompt: str, in_turn: bool) -> StubLaunch:
        with self._lock:
            n = self._counts[call.run, call.key] = self._counts.get((call.run, call.key), 0) + 1
            record = StubLaunch(
                run=call.run,
                key=call.key,
                kind=call.kind,
                unit=call.unit,
                params=call.params,
                model=launch.model,
                role=launch.role,
                n=n,
                resumed=bool(launch.resume) and not in_turn,
                prompt=prompt,
                call=call,
                launch=launch,
                in_turn=in_turn,
            )
            self.launches.append(record)
        return record

    def _play(self, launch: Launch, call: CallFile, record: StubLaunch, message: list[str]) -> Reply:
        """The scripted reply to `record`, its output written: to the output file, or, for an
        output taken from the final message, to `message`."""
        reply = self._reply(record)
        if self.delay_s:
            time.sleep(self.delay_s)
        if reply.stop is Stop.COMPLETED and reply.output is not _UNSET:
            if call.output is None:
                if reply.output is _SMALLEST:
                    return writes_nothing()  # the smallest output of a task with none
                return fails(reason=f"stub: {call.key} declares no output, but its reply writes one")
            if reply.output is _SMALLEST:
                if record.resumed or record.in_turn:
                    # The same value again cannot pass: the checks that refused it are not the schema's.
                    return fails(reason=f"stub: the smallest output of {call.key} fails its checks; script a reply for it")
                value, problems = smallest(call.output.json_schema) if call.output.format == "json" else ("stub", [])
                if problems:
                    return fails(reason=f"stub: no smallest output for {call.key}: {'; '.join(problems)}")
                reply = writes(value, cost_usd=reply.cost_usd)
            text = _text_of(reply.output)
            if call.output.from_ == "message":
                message.append(text)
                return reply
            path = Path(call.output.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self._tool(launch, f"{call.key}-{record.n}-write", "Write", call.output.path, "ok")
        return reply

    def _continues_on_stop_hook(self) -> bool:
        """Whether the coding agent this stub plays continues its turn when a stop hook objects."""
        cls = backend_class(self.name)
        return cls is not None and issubclass(cls, ClaudeBackend)

    def _stop_hooks(self, launch: Launch, *, active: bool) -> str | None:
        """Run the launch's plugins' Stop hooks as Claude Code does; what the first one
        that objects (exit 2) says, or None when they all let the agent stop."""
        payload = json.dumps({"hook_event_name": "Stop", "stop_hook_active": active, "session_id": launch.label})
        for plugin_dir in launch.plugin_dirs:
            rendered = Path(plugin_dir) / "hooks" / "hooks.json"
            try:
                declared = json.loads(rendered.read_text()).get("hooks", {}).get("Stop", [])
            except (OSError, ValueError):
                continue
            env = {**os.environ, **launch.env, "CLAUDE_PLUGIN_ROOT": str(plugin_dir)}
            for command in (h.get("command", "") for group in declared for h in group.get("hooks", [])):
                proc = subprocess.run(
                    ["bash", "-c", command], input=payload, capture_output=True, text=True, cwd=launch.cwd, env=env, timeout=120
                )
                if proc.returncode == 2:
                    return proc.stderr.strip() or "the stop hook objected"
        return None

    # --- a stub run's Python tasks --------------------------------------------

    def plays(self, kind: str) -> bool:
        """Whether a stub run plays a Python task of `kind` (rather than running its function)."""
        return kind not in self.execute

    def play_python(self, run: str, key: str, kind: str, unit: str, params: dict[str, Any], json_schema: dict | None) -> tuple[bool, Any]:
        """A stub run's Python task: (whether it returns an output, the output). `json_schema`
        is its output's schema, None for a task with no output. A failure raises, as the
        function would."""
        with self._lock:
            n = self._counts[run, key] = self._counts.get((run, key), 0) + 1
            task = StubTask(run=run, key=key, kind=kind, unit=unit, params=params, n=n)
            self.played.append(task)
        reply = self._reply(task)
        if reply.stop is not Stop.COMPLETED:
            raise RuntimeError(reply.reason or f"stub: {reply.stop.value}")
        if reply.output is _UNSET:
            return False, None
        if reply.output is _SMALLEST:
            if json_schema is None:
                return False, None
            value, problems = smallest(json_schema)
            if problems:
                raise RuntimeError(f"stub: no smallest output for {key}: {'; '.join(problems)}")
            return True, value
        return True, reply.output

    # --- internals ---------------------------------------------------------

    def _reply(self, launch: StubLaunch | StubTask) -> Reply:
        entry = self.script.get(launch.key, self.script.get(launch.kind, self.default))
        if entry is _UNSET:
            scripted = ", ".join(sorted(self.script)) or "nothing"
            return fails(reason=f"stub: no reply scripted for {launch.key} (kind {launch.kind}); scripted: {scripted}")
        if isinstance(entry, (list, tuple)):
            if not entry:
                return fails(reason=f"stub: the reply list for {launch.key} is empty")
            entry = entry[min(launch.n, len(entry)) - 1]
        if callable(entry) and not isinstance(entry, type):
            entry = entry(launch)
        return entry if isinstance(entry, Reply) else writes(entry)

    # The transcript, in the stream format the monitor reads for this name (`claude`'s or `omp`'s).

    def _text(self, launch: Launch, text: str) -> None:
        if resolve_format(self.name) == "claude":
            self._emit(launch, {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
        else:
            self._emit(launch, {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": text + "\n"}})

    def _tool(self, launch: Launch, cid: str, name: str, path: str, output: str) -> None:
        if resolve_format(self.name) == "claude":
            self._emit(
                launch,
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": cid, "name": name, "input": {"file_path": path}}]},
                },
            )
            self._emit(launch, {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": cid, "content": output}]}})
        else:
            self._emit(launch, {"type": "tool_execution_start", "toolCallId": cid, "toolName": name.lower(), "args": {"path": path}})
            done = {"type": "tool_execution_end", "toolCallId": cid, "toolName": name.lower(), "isError": False}
            self._emit(launch, {**done, "result": {"content": [{"type": "text", "text": output}]}})

    def _emit(self, launch: Launch, event: dict) -> None:
        if launch.stream_path is None:
            return
        with open(launch.stream_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _result(self, launch: Launch, started: float, reply: Reply) -> LaunchResult:
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=reply.stop,
            ok=reply.stop is Stop.COMPLETED,
            model=launch.model,
            credential=launch.credential.label,
            wall_s=round(time.monotonic() - started, 3),
            session_id=launch.resume or f"stub-{launch.label}-{time.monotonic_ns()}",
            cost_usd=reply.cost_usd,
            rate_limit=reply.rate_limit,
            stderr_tail=reply.reason,
        )


def _text_of(value: Any) -> str:
    """An output as its file holds it: a model or a JSON value as JSON, a `str` as is."""
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _describe(reply: Reply) -> str:
    if reply.stop is not Stop.COMPLETED:
        return f"{reply.stop.value}: {reply.reason}"
    return "wrote the output" if reply.output is not _UNSET else "wrote nothing"


__all__ = [
    "Reply",
    "StubAgent",
    "StubLaunch",
    "StubTask",
    "fails",
    "rate_limited",
    "writes",
    "writes_nothing",
    "writes_smallest",
]
