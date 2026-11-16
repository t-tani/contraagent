"""agy's event wire (`agy -p --output-format stream-json`): the reader that folds it into a
`LaunchResult`, and the monitor's view of its events.

One JSON object per line, named by `event` (checked against agy 1.5.9 and the recordings in
`tests/fixtures/agy/`):

    {"event": "init", "conversation_id": ..., "init": {"model", "cwd", "tools", "permission_mode"}}
    {"event": "step_update", "step_update": {"conversation_id", "step_index", "state", "step_type", ...}}
    {"event": "result", "result": {"conversation_id", "status", "response", "num_turns", "usage"}}

A step of type `agent_response` is one response of the model, so one turn: updates in
state `ACTIVE` carry its text as it comes (`text_delta`), and its last update, `DONE`,
carries the tokens of that one API call (`usage`). A response that only calls tools arrives
as its `DONE` update alone, so a turn is counted at its end. A step of type `tool` is one
tool call: `ACTIVE` with its name and arguments (`tool_info`), then `DONE` with its output or
`ERROR` with why it failed.

What was measured on agy 1.5.9, on its Gemini, Claude and GPT models alike:

- `usage.input_tokens` is the input that was not cached and `cache_read_tokens` the input
  that was: one call's input is their sum (three calls of one session in a row gave
  4687 + 3624, 4189 + 4195 and 4891 + 3623).
- `usage.output_tokens` holds the `thinking_tokens` (a response of Gemini 3.8 Flash gave 2275
  of output, 2238 of them thinking, and a total of 9766 + 2275), and the model's thinking
  is not in the stream.
- The model's tools are `run_command`, `read_file`, `write_file`, `edit_file` and
  `search_web`, with the tools of the launch's MCP servers.
- The `result` event's `usage` and `num_turns` are the conversation's so far, the earlier
  launches of a resumed one included, and its `num_turns` counts the user's messages. The
  tokens and the turns of a launch are those of its steps.
- The `result` event's `response` joins the text of every response of the launch. A
  launch's answer is its last response that has text.
- `--conversation <id>` with an id agy does not find starts a new conversation and warns on
  stderr. The reader ends such a launch at its `init` event: it would answer without the
  session it was to continue.
- A refused quota is a `result` with status `ERROR` and the provider's words (`Individual
  quota reached. ... Resets in 144h6m29s.`), exit status 3, and on stderr a line `AGY_ERROR:
  {...}` with the provider's status (`"error_code":429`).
- A launch that cannot start (an unknown agent or model, an empty prompt) prints a `result`
  alone, with an empty `conversation_id`, and exits 1.
- A tool call that needs an approval ends the launch, since nobody can give one: the
  `result` has status `SUCCESS`, an empty `response` and `denied_actions` (`[{"action":
  "command", "display_name": "Bash"}]`), the exit status is 0, and stderr says that the
  permission was denied. In `auto` mode this is a command that asks to leave the sandbox
  and that agy's own review does not let through; its step ends `DONE` with no output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contraagent._internal.backends.agy import hooks as agy_hooks
from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, Limits, QuotaRefusal, Stop
from contraagent._internal.backends.refusal import QUOTA_RE, Ending, Signals
from contraagent._internal.backends.wire import EventFold, JsonType, feedback_errors, first_text, tokens, tool_preview

#: How agy words a refusal: a quota in Google's words (`Individual quota reached`,
#: `RESOURCE_EXHAUSTED`), a missing or refused login, and the provider's status where it
#: gives one (`(code 429)`, `"error_code":429`).
SIGNALS = Signals(
    quota=re.compile(f"{QUOTA_RE.pattern}|quota reached|RESOURCE_EXHAUSTED", re.IGNORECASE),
    auth=re.compile(r"authentication required|UNAUTHENTICATED|failed to retrieve token|API key not valid", re.IGNORECASE),
    status=re.compile(r"\(code (\d{3})\)|\"error_code\":\s*(\d{3})"),
)

#: The events agy sends; another is counted in `LaunchResult.unread_events`.
KNOWN_EVENTS = frozenset({"init", "step_update", "result"})
#: The fields `StreamReader` reads on every event of its type (`EventFold.read_fields`).
READ_FIELDS: dict[str, dict[str, JsonType]] = {
    "init": {"conversation_id": "string", "init": "object"},
    "step_update": {"step_update.step_type": "string", "step_update.state": "string"},
    "result": {"result.status": "string", "result.conversation_id": "string"},
}
#: The statuses of a `result` that end a launch stopped from outside.
ABORTED = ("CANCELED", "INTERRUPTED")
#: A tool call agy's permissions refused, in the words of its error.
DENIED_RE = re.compile(r"permission check failed|permission denied", re.IGNORECASE)
#: The cool-off a refused quota states (`Resets in 144h6m29s`), as Go writes a duration.
_RESETS_RE = re.compile(r"resets in ((?:\d+(?:\.\d+)?(?:ms|h|m|s))+)", re.IGNORECASE)
_DURATION_PART_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
#: agy's tools that search the web and read a page, and the arguments that name what.
WEB_SEARCH = "search_web"
WEB_FETCH = "read_url_content"


def resets_in(words: str) -> float | None:
    """The seconds until the quota returns, as a refusal states them (`Resets in 144h6m29s`);
    None when it states none."""
    m = _RESETS_RE.search(words or "")
    if not m:
        return None
    return sum(float(n) * _SECONDS[unit] for n, unit in _DURATION_PART_RE.findall(m.group(1)))


def tool_target(name: str, params: object) -> str:
    """What a tool call is about, in one line: the command, the file, the query or the URL
    its arguments name, else the arguments as JSON."""
    found = first_text(params, "CommandLine", "Path", "AbsolutePath", "TargetFile", "query", "Query", "Url", "url")
    if found:
        return found
    return json.dumps(params, ensure_ascii=False) if isinstance(params, dict) and params else ""


class StreamReader(EventFold):
    """Reads `agy -p --output-format stream-json`."""

    agent = "agy"
    known_events = KNOWN_EVENTS
    read_fields = READ_FIELDS
    signals = SIGNALS

    def __init__(self, limits: Limits | None = None, resume: str = "", hook_state: Path | None = None) -> None:
        super().__init__()
        self.limits = limits or Limits()
        #: The conversation the launch was to continue ('' for a new one), and whether agy
        #: started another one instead.
        self.resume = resume
        self.resume_missed = False
        #: Where the bridge keeps what the launch's hooks said (`hooks.STATE_ENV`).
        self.hook_state = hook_state
        self.init_model = ""
        self.init_tools = 0
        #: The final `result` payload, when one arrived.
        self.final: dict[str, Any] | None = None
        self.denied: list[dict[str, Any]] = []
        #: The latest tool call: its name and arguments, and whether the model has not
        #: responded since.
        self._last_tool: tuple[str, dict[str, Any]] = ("", {})
        self._ended_on_tool = False
        #: The text of each response, by its step.
        self._texts: dict[int, list[str]] = {}
        self._tools_seen: set[int] = set()

    def feed(self, ev: dict) -> Stop | None:
        self.saw_any = True
        typ = str(ev.get("event") or "")
        if self.unknown(typ):
            return None
        self.check_fields(typ, ev)
        if typ == "init":
            return self._init(ev)
        if typ == "step_update":
            step = ev.get("step_update")
            return self._step(step) if isinstance(step, dict) else None
        final = ev.get("result")
        if isinstance(final, dict):
            self.final = final
            self.session_id = self.session_id or str(final.get("conversation_id") or "")
        return None

    def _init(self, ev: dict) -> Stop | None:
        self.session_id = str(ev.get("conversation_id") or "")
        init = ev.get("init")
        if isinstance(init, dict):
            self.init_model = str(init.get("model") or "")
            self.init_tools = len(init.get("tools") or [])
        if self.resume and self.session_id != self.resume:
            self.resume_missed = True
            return Stop.ERROR
        return None

    def _step(self, step: dict) -> Stop | None:
        """One update of one step. A step of another conversation is a subagent's: no turn
        and no tool call of the launch."""
        if self.session_id and str(step.get("conversation_id") or self.session_id) != self.session_id:
            return None
        kind, state, index = step.get("step_type"), step.get("state"), step.get("step_index")
        if kind == "agent_response":
            delta = step.get("text_delta")
            if isinstance(delta, str) and isinstance(index, int):
                self._texts.setdefault(index, []).append(delta)
            self._ended_on_tool = False
            if state == "ACTIVE":
                self.begin_turn()
                return None
            usage = step.get("usage")
            if isinstance(usage, dict):
                self.add_call(call_usage(self.init_model, usage))
            self.end_turn()
            return None
        if kind != "tool":
            return None
        info = step.get("tool_info")
        info = info if isinstance(info, dict) else {}
        name = str(step.get("tool_name") or info.get("name") or "")
        params = info.get("parameters")
        self._last_tool = (name, params if isinstance(params, dict) else {})
        self._ended_on_tool = True
        if not isinstance(index, int) or index not in self._tools_seen:
            if isinstance(index, int):
                self._tools_seen.add(index)
            self.note_tool(name, params)
            if name == WEB_SEARCH:
                self.note_web_query(first_text(params, "query", "Query"))
        error = info.get("error")
        if isinstance(error, dict) and DENIED_RE.search(str(error.get("message") or "")):
            self.denied.append({"tool_name": name, "tool_input": params if isinstance(params, dict) else {}})
            if self.limits.max_denials is not None and len(self.denied) > self.limits.max_denials:
                return Stop.DENIED
        return None

    # --- the end ------------------------------------------------------------

    @property
    def status(self) -> str:
        return str((self.final or {}).get("status") or "")

    @property
    def error(self) -> str:
        return str((self.final or {}).get("error") or "")

    @property
    def unapproved(self) -> list[dict[str, Any]]:
        """The actions nobody could approve (`denied_actions`)."""
        actions = (self.final or {}).get("denied_actions")
        return [a for a in actions if isinstance(a, dict)] if isinstance(actions, list) else []

    @property
    def ended_unapproved(self) -> bool:
        """Whether agy ended the launch on an approval nobody could give: the `result` names
        the action, and the model gave no response after its last tool call."""
        return bool(self.unapproved) and self._ended_on_tool

    def denials(self) -> list[dict[str, Any]]:
        """The tool calls agy's permissions refused: each one its error said so of, and the
        latest call when agy ended the launch on an approval nobody could give."""
        if not self.ended_unapproved or self.denied:
            return list(self.denied)
        name, params = self._last_tool
        first = self.unapproved[0]
        return [{"tool_name": name or str(first.get("display_name") or first.get("action") or ""), "tool_input": params}]

    def answer(self) -> str:
        """The launch's answer: its last response that has text, else what the `result` gives."""
        for index in sorted(self._texts, reverse=True):
            text = "".join(self._texts[index])
            if text.strip():
                return text
        return str((self.final or {}).get("response") or "")

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """The `result` decides: `SUCCESS` completes the launch, with or without text (a model
        that wrote its output file may end on an empty message). Any other status of a
        conversation that started is a failure, in the provider's words; one that never
        started (no `conversation_id`) is left to its exit status, and so is a process that
        ended with no `result`, whatever text it had sent. A launch agy ended on an approval
        nobody could give (`ended_unapproved`) is `denied`, whatever its status."""
        e = super().ending(exit_code=exit_code, killed=killed)
        if self.ended_unapproved:
            e.failed, e.capped = True, Stop.DENIED
            return e
        e.completed = self.status == "SUCCESS"
        e.text = self.answer() if e.completed else ""
        if not e.completed:
            e.error = self.error
            e.status = self.signals.status_in(self.error)
            e.failed = bool(self.final and self.session_id)
            e.aborted = self.status in ABORTED
        return e

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        final = self.final or {}
        stop = self.stop(exit_code=exit_code, killed=killed)
        said = self.error
        if self.resume_missed:
            said = f"agy did not find conversation {self.resume} and started {self.session_id}: the launch was ended"
        elif self.ended_unapproved:
            names = ", ".join(dict.fromkeys(str(a.get("display_name") or a.get("action") or "a tool") for a in self.unapproved))
            said = f"agy ended the launch: {names} needed an approval, and a headless session has nobody to give one"
        duration = final.get("duration_seconds")
        r = self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            model=launch.model or self.init_model,
            result_text=self.answer(),
            structured_output=final.get("structured_output"),
            duration_api_ms=round(duration * 1000) if isinstance(duration, (int, float)) and not isinstance(duration, bool) else None,
            permission_denials=self.denials(),
            raw_result={**final, "tool_args": dict(self.tool_args)},
            init_model=self.init_model,
            init_tools=self.init_tools,
            stderr_tail=said if stop is not Stop.COMPLETED else "",
            hook_errors=[feedback_errors(text) for text in agy_hooks.read_objections(self.hook_state)] if self.hook_state else [],
        )
        if stop is Stop.RATE_LIMITED:
            r.quota_refusal = QuotaRefusal(retry_after_s=resets_in(self.error))
        return r


def call_usage(model: str, usage: dict) -> CallUsage:
    """One API call's tokens, from a response's `usage`. `thinking_tokens` are added to the
    output when `total_tokens` counts them apart from `output_tokens`."""
    fresh = tokens(usage, "input_tokens")
    out = tokens(usage, "output_tokens")
    thinking = tokens(usage, "thinking_tokens")
    if thinking and tokens(usage, "total_tokens") == fresh + out + thinking:
        out += thinking
    return CallUsage(model=model, input=fresh, cache_read=tokens(usage, "cache_read_tokens"), cache_creation=0, output=out)


def normalize_event(e: dict) -> dict | list[dict]:
    """Map one `agy -p --output-format stream-json` event onto the monitor's renderable
    shapes (the ones `backends.claude.wire.normalize_event` produces), or `{"type": "skip"}`.

    A response's text arrives in pieces, each shown as it comes. A tool step opens its card
    when it starts and closes it when it ends, matched by its conversation and step."""
    typ = e.get("event")
    if typ == "init":
        return {"type": "notice", "text": f"session started: {e.get('conversation_id') or ''}"[:800]}
    if typ == "result":
        final = e.get("result") or {}
        if final.get("status") in (None, "SUCCESS"):
            return {"type": "skip"}
        return {"type": "notice", "text": f"{final.get('status')}: {final.get('error') or ''}"[:800]}
    step = e.get("step_update") if typ == "step_update" else None
    if not isinstance(step, dict):
        return {"type": "skip"}
    kind = step.get("step_type")
    if kind == "agent_response":
        delta = step.get("text_delta")
        return {"type": "message_update", "ev": "text_delta", "delta": delta} if isinstance(delta, str) and delta else {"type": "skip"}
    if kind != "tool":
        return {"type": "skip"}
    info = step.get("tool_info")
    info = info if isinstance(info, dict) else {}
    name = str(step.get("tool_name") or info.get("name") or "")
    call = f"{step.get('conversation_id') or ''}:{step.get('step_index')}"
    if step.get("state") == "ACTIVE":
        preview = tool_preview(tool_target(name, info.get("parameters")), web_query=name == WEB_SEARCH, web_fetch=name == WEB_FETCH)
        return {"type": "tool_execution_start", "tool": name, "intent": "", "call": call, **preview}
    error = info.get("error")
    out = error.get("message") if isinstance(error, dict) else info.get("output")
    failed = step.get("state") == "ERROR" or isinstance(error, dict)
    return {"type": "tool_execution_end", "tool": "", "out": str(out or "")[:4000], "err": failed, "call": call}
