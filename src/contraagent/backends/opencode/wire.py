"""opencode's event wire: `EventReader`, the reader of what `opencode run --format json`
prints, the monitor's view of those events (`normalize_event`), and the reader of
opencode's own log on stderr (`refusal_in_log`).

`opencode run --format json` prints one event per line, each with the session id
(`sessionID`) and one part of the session (`part`): `step_start` and `step_finish`
around each API call (the call's tokens and cost on `step_finish`), `text` once a
piece of the answer is complete, `reasoning` (with `--thinking`), `tool_use` once a
tool call has ended (its input and output together), and `error` when the session
ends on an error. A provider refusal that opencode retries (a 429) prints nothing
here: opencode only logs it, so `--print-logs` puts that log on stderr.

Tested on recordings of a real opencode (`tests/fixtures/opencode/<version>/`).
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

from contraagent.backends.launch import CallUsage, Launch, LaunchResult, RateLimit, Stop, Usage, note_web_query

_logger = logging.getLogger(__name__)
_warned: set[str] = set()  # unread event types already logged by this process

#: The event types `opencode run --format json` prints (checked against opencode 1.19.0).
#: Another type is counted in `LaunchResult.unread_events`: a newer opencode sends it.
KNOWN_EVENTS = frozenset({"step_start", "step_finish", "text", "reasoning", "tool_use", "error"})
#: opencode's web search and web page tools; their inputs carry `query` and `url`.
WEB_SEARCH_TOOL = "websearch"
WEB_FETCH_TOOL = "webfetch"

# Providers word a quota differently; opencode passes their words on.
_RATE_LIMIT_RE = re.compile(
    r"usage limit exceeded|rate[_ -]?limit|too many requests|quota (?:exceeded|exhausted)|insufficient_quota",
    re.IGNORECASE,
)
# One line of opencode's log: `... message="stream error" ... error.error="AI_APICallError: ..."`.
_STREAM_ERROR_RE = re.compile(r'message="stream error".*?error\.error="([^"]*)"')


def is_rate_limited(text: str) -> bool:
    return bool(_RATE_LIMIT_RE.search(text))


def refusal_in_log(line: str) -> str | None:
    """The provider's words when one line of opencode's log reports a quota refusal on an
    API call, else None. opencode retries such a call, waiting as long as the provider
    asks (days, for a blown weekly quota), and prints nothing on stdout meanwhile."""
    m = _STREAM_ERROR_RE.search(line)
    return m.group(1) if m and is_rate_limited(m.group(1)) else None


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
            input=int(tokens.get("input") or 0),
            cache_read=int(cache.get("read") or 0),
            cache_creation=int(cache.get("write") or 0),
            output=int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0),
        )
    except (TypeError, ValueError):
        return None
    cost = part.get("cost")
    return call, (float(cost) if isinstance(cost, (int, float)) else None)


def line_usage(raw: bytes, model: str) -> tuple[CallUsage, float | None] | None:
    """`call_usage` of one raw stdout line."""
    try:
        ev = json.loads(raw)
    except ValueError:
        return None
    return call_usage(ev, model) if isinstance(ev, dict) else None


class EventReader:
    """Folds opencode's events into a `LaunchResult`.

    The answer is the text of the last assistant message: opencode prints the
    text of every step, and a step before a tool call says what it is about to do.
    """

    def __init__(self, model: str = "") -> None:
        self.model = model
        self.saw_any = False
        self.session_id = ""
        self._texts: dict[str, list[str]] = {}  # message id -> its text parts, in order
        self._last_message = ""
        self.tool_uses: Counter = Counter()
        self.tool_args: dict[str, list[str]] = {}
        self.web_queries: list[str] = []
        self.calls: list[CallUsage] = []
        self.cost: float | None = None
        self.errors: list[dict] = []
        self.unread: Counter = Counter()

    def feed(self, ev: dict) -> None:
        typ = str(ev.get("type") or "")
        if typ not in KNOWN_EVENTS:
            self.unread[typ or "<untyped>"] += 1
            return
        self.saw_any = True
        self.session_id = self.session_id or str(ev.get("sessionID") or "")
        part = _part(ev)
        if typ == "text":
            message = str(part.get("messageID") or "")
            self._texts.setdefault(message, []).append(str(part.get("text") or ""))
            self._last_message = message
        elif typ == "tool_use":
            name = str(part.get("tool") or "")
            if name:
                self.tool_uses[name] += 1
                self._record_args(name, _state(part).get("input"))
            if name == WEB_SEARCH_TOOL:
                note_web_query(self.web_queries, (_state(part).get("input") or {}).get("query"))
        elif typ == "step_finish":
            found = call_usage(ev, self.model)
            if found is not None:
                call, cost = found
                self.calls.append(call)
                if cost is not None:
                    self.cost = (self.cost or 0.0) + cost
        elif typ == "error":
            err = ev.get("error")
            self.errors.append(err if isinstance(err, dict) else {"name": str(err)})

    def _record_args(self, name: str, args: object) -> None:
        """A bounded sample of each tool's arguments (what did 138 bash calls run?)."""
        buf = self.tool_args.setdefault(name, [])
        if not isinstance(args, dict) or len(buf) >= 20:
            return
        try:
            buf.append(json.dumps(args, ensure_ascii=False)[:500])
        except (TypeError, ValueError):
            pass

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

    def stop(self, exit_code: int | None, killed: Stop | None) -> Stop:
        """How the launch ended. Order: a limit the wrapper enforced, then an error event
        (rate limit, refused credential, abort, any other), then the exit and the answer."""
        if killed is not None:
            return killed
        if self.errors:
            status, words = self._error_status(), self.error_text()
            names = {str(e.get("name") or "") for e in self.errors}
            if status == 429 or is_rate_limited(words):
                return Stop.RATE_LIMITED
            if status in (401, 403) or "ProviderAuthError" in names:
                return Stop.AUTH_FAILED
            if "MessageAbortedError" in names:
                return Stop.ABORTED
            return Stop.API_ERROR
        if exit_code not in (0, None) and not self.text:
            return Stop.ERROR
        if not self.text:
            return Stop.NO_OUTPUT if self.saw_any else Stop.LAUNCH_FAILED
        return Stop.COMPLETED

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None, refusal: str = "") -> LaunchResult:
        """Everything read, as a `LaunchResult`. `refusal`: the provider's words when the
        launch was ended on a quota refusal opencode only logged."""
        stop = self.stop(exit_code, killed)
        for typ in sorted(set(self.unread) - _warned):
            _warned.add(typ)
            _logger.warning(f"[opencode] event {typ!r} is not one this contraagent reads; a newer opencode? (LaunchResult.unread_events)")
        words = self.error_text() or refusal
        return LaunchResult(
            label=launch.label,
            agent=agent,
            stop=stop,
            ok=stop is Stop.COMPLETED,
            exit_code=exit_code,
            model=launch.model,
            session_id=self.session_id,
            result_text=self.text if stop is Stop.COMPLETED else (self.text or words if stop is Stop.RATE_LIMITED else ""),
            rate_limit=RateLimit(status="quota") if stop is Stop.RATE_LIMITED else None,
            tool_uses=dict(self.tool_uses),
            web_queries=list(self.web_queries),
            usage=Usage(calls=list(self.calls), output_total=sum(c.output for c in self.calls)),
            cost_usd=round(self.cost, 6) if self.cost is not None else None,
            raw_result={"tool_args": dict(self.tool_args)},
            # The provider's own words, which opencode prints on stdout: the journal's reason.
            stderr_tail=words if stop is not Stop.COMPLETED else "",
            unread_events=dict(self.unread),
        )


def parse_events(launch: Launch, agent: str, stdout: bytes, exit_code: int | None, killed: Stop | None, refusal: str = "") -> LaunchResult:
    """Read every event line of one launch's stdout."""
    reader = EventReader(launch.model)
    for raw in stdout.split(b"\n"):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            reader.feed(ev)
    return reader.result(launch, agent, exit_code=exit_code, killed=killed, refusal=refusal)


def _preview(tool: str, args: dict) -> dict:
    """A tool call's one-line preview (`cmd`); its query when it is a web search
    (`web_query`), its URL when it reads a web page (`web_fetch`)."""
    cmd = str(
        args.get("command")
        or args.get("pattern")
        or args.get("filePath")
        or args.get("path")
        or args.get("url")
        or args.get("query")
        or args.get("name")
        or ""
    )[:800]
    if tool == WEB_SEARCH_TOOL:
        return {"cmd": cmd, "web_query": cmd}
    if tool == WEB_FETCH_TOOL:
        return {"cmd": cmd, "web_fetch": cmd}
    return {"cmd": cmd}


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
