"""opencode's event wire: `EventReader`, the reader of what `opencode run --format json`
prints, the monitor's view of those events (`normalize_event`), and the reader of
opencode's own log on stderr (`refusal_in_log`).

`opencode run --format json` prints one event per line, each with the session id
(`sessionID`) and one part of the session (`part`): `step_start` and `step_finish`
around each API call (the call's tokens and cost on `step_finish`, and why the call
ended: `reason`, `stop` when it ended the turn), `text` once a
piece of the answer is complete, `reasoning` (with `--thinking`), `tool_use` once a
tool call has ended (its input and output together), and `error` when the session
ends on an error. A provider refusal that opencode retries (a 429) prints nothing
here: opencode only logs it, so `--print-logs` puts that log on stderr.

Tested on recordings of a real opencode (`tests/fixtures/opencode/<version>/`).
"""

from __future__ import annotations

import re

from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, Stop
from contraagent._internal.backends.refusal import QUOTA_RE, Ending, Signals, quota_refusal
from contraagent._internal.backends.wire import EventFold, first_text, tool_preview
from contraagent._internal.backends.wire import tokens as count

#: How opencode words a refusal: providers word a quota differently, and opencode passes
#: their words on. A refusal it only logs is read from its log (`refusal_in_log`).
SIGNALS = Signals(quota=QUOTA_RE, stderr_stops=frozenset())

#: The event types `opencode run --format json` prints (checked against opencode 1.19.0).
#: Another type is counted in `LaunchResult.unread_events`: a newer opencode sends it.
KNOWN_EVENTS = frozenset({"step_start", "step_finish", "text", "reasoning", "tool_use", "error"})
#: opencode's web search and web page tools; their inputs carry `query` and `url`.
WEB_SEARCH_TOOL = "websearch"
WEB_FETCH_TOOL = "webfetch"

# One line of opencode's log: `... message="stream error" ... error.error="AI_APICallError: ..."`.
_STREAM_ERROR_RE = re.compile(r'message="stream error".*?error\.error="([^"]*)"')


def refusal_in_log(line: str) -> str | None:
    """The provider's words when one line of opencode's log reports a quota refusal on an
    API call, else None. opencode retries such a call, waiting as long as the provider
    asks (days, for a blown weekly quota), and prints nothing on stdout meanwhile."""
    m = _STREAM_ERROR_RE.search(line)
    return m.group(1) if m and SIGNALS.quota_in(m.group(1)) else None


def _obj(d: dict, key: str) -> dict:
    """`d[key]` when it is an object, else an empty one."""
    value = d.get(key)
    return value if isinstance(value, dict) else {}


def _part(ev: dict) -> dict:
    return _obj(ev, "part")


def _state(part: dict) -> dict:
    return _obj(part, "state")


def call_usage(ev: dict, model: str) -> tuple[CallUsage, float | None] | None:
    """One `step_finish` event's API call: its tokens and cost (USD), or None for any other
    event. opencode counts reasoning apart from output; both are output tokens here."""
    if ev.get("type") != "step_finish":
        return None
    part = _part(ev)
    tokens = part.get("tokens")
    if not isinstance(tokens, dict):
        return None
    cache = _obj(tokens, "cache")
    try:
        call = CallUsage(
            model=model,
            input=count(tokens, "input"),
            cache_read=count(cache, "read"),
            cache_creation=count(cache, "write"),
            output=count(tokens, "output", "reasoning"),
        )
    except (TypeError, ValueError):
        return None
    cost = part.get("cost")
    return call, (float(cost) if isinstance(cost, (int, float)) else None)


class EventReader(EventFold):
    """Folds opencode's events into a `LaunchResult`.

    The answer is the text of the last assistant message: opencode prints the
    text of every step, and a step before a tool call says what it is about to do.
    A last step that ends the turn (`step_finish` with reason `stop`) completes the
    launch, with or without text: a model that has written its output file may end on
    an empty message.
    """

    agent = "opencode"
    known_events = KNOWN_EVENTS
    signals = SIGNALS

    def __init__(self, model: str = "") -> None:
        super().__init__()
        self.model = model
        self._texts: dict[str, list[str]] = {}  # message id -> its text parts, in order
        self._last_message = ""
        #: Why the last step ended (its `step_finish` `reason`); '' while a step runs.
        self._finish_reason = ""
        self.errors: list[dict] = []

    def feed(self, ev: dict) -> Stop | None:
        typ = str(ev.get("type") or "")
        if self.unknown(typ):
            return None
        self.saw_any = True
        self.session_id = self.session_id or str(ev.get("sessionID") or "")
        part = _part(ev)
        if typ == "step_start":
            self._finish_reason = ""
        elif typ == "text":
            message = str(part.get("messageID") or "")
            self._texts.setdefault(message, []).append(str(part.get("text") or ""))
            self._last_message = message
        elif typ == "tool_use":
            name = str(part.get("tool") or "")
            args = _state(part).get("input")
            self.note_tool(name, args)
            if name == WEB_SEARCH_TOOL:
                self.note_web_query((args if isinstance(args, dict) else {}).get("query"))
        elif typ == "step_finish":
            self._finish_reason = str(part.get("reason") or "")
            found = call_usage(ev, self.model)
            if found is not None:
                self.add_call(*found)
        elif typ == "error":
            err = ev.get("error")
            self.errors.append(err if isinstance(err, dict) else {"name": str(err)})
        return None

    @property
    def text(self) -> str:
        return "".join(self._texts.get(self._last_message, ())).strip()

    def error_text(self) -> str:
        """The errors' own words: each one's message, else its name."""
        words = []
        for err in self.errors:
            data = _obj(err, "data")
            words.append(str(data.get("message") or err.get("name") or "error"))
        return " | ".join(words)

    def _error_status(self) -> int | None:
        for err in self.errors:
            data = _obj(err, "data")
            if isinstance(data.get("statusCode"), int):
                return data["statusCode"]
        return None

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """An error event decides (its status, its words, its name: a refused credential, an
        abort); without one, a last step that ended the turn, then the exit and the answer."""
        names = {str(e.get("name") or "") for e in self.errors}
        return Ending(
            killed=killed,
            exit_code=exit_code,
            saw_any=self.saw_any,
            text=self.text,
            error=self.error_text(),
            status=self._error_status(),
            failed=bool(self.errors),
            auth="ProviderAuthError" in names,
            aborted="MessageAbortedError" in names,
            completed=self._finish_reason == "stop" and exit_code in (0, None),
        )

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        stop = self.stop(exit_code=exit_code, killed=killed)
        words = self.error_text()
        text = self.text
        return self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            result_text=text if stop is Stop.COMPLETED else (text or words if stop is Stop.RATE_LIMITED else ""),
            quota_refusal=quota_refusal(words) if stop is Stop.RATE_LIMITED else None,
            # The provider's own words, which opencode prints on stdout: the journal's reason.
            stderr_tail=words if stop is not Stop.COMPLETED else "",
        )


def _preview(tool: str, args: dict) -> dict:
    """A tool call's one-line preview (`cmd`); its query when it is a web search
    (`web_query`), its URL when it reads a web page (`web_fetch`)."""
    cmd = first_text(args, "command", "pattern", "filePath", "path", "url", "query", "name")
    return tool_preview(cmd, web_query=tool == WEB_SEARCH_TOOL, web_fetch=tool == WEB_FETCH_TOOL)


def normalize_event(e: dict) -> dict | list[dict]:
    """One opencode event as the monitor's renderable events, or `{"type": "skip"}`.

    A `tool_use` holds a finished call with its result, so it is two events: the
    call's start and its end, paired by `call`.
    """
    typ = e.get("type")
    part = _part(e)
    if typ == "text":
        text = str(part.get("text") or "")
        return {"type": "message_update", "ev": "text_delta", "delta": text + "\n"} if text else {"type": "skip"}
    if typ == "reasoning":
        text = str(part.get("text") or "")
        return {"type": "turn_end", "thinking": text[:4000]} if text else {"type": "skip"}
    if typ == "tool_use":
        tool = str(part.get("tool") or "")
        state = _state(part)
        args = _obj(state, "input")
        call = str(part.get("callID") or part.get("id") or "")
        failed = state.get("status") == "error"
        out = state.get("error") if failed else state.get("output")
        return [
            {
                "type": "tool_execution_start",
                "tool": tool,
                **_preview(tool, args),
                "intent": str(state.get("title") or "")[:200],
                "call": call,
            },
            {"type": "tool_execution_end", "tool": tool, "out": str(out or "")[:4000], "err": failed, "call": call},
        ]
    if typ == "error":
        err = _obj(e, "error")
        data = _obj(err, "data")
        return {"type": "notice", "text": f"error: {data.get('message') or err.get('name') or ''}"[:800]}
    return {"type": "skip"}
