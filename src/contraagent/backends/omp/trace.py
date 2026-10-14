"""omp's event wire: `TraceReader`, the one reader of the agent events omp sends
in `--mode json` and over RPC, the monitor's view of those events
(`normalize_event`), and the rate-limit reading the text mode shares.

Tested on recordings of a real omp (`tests/fixtures/omp/<version>/`).
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

from contraagent.backends.launch import CallUsage, Launch, LaunchResult, RateLimit, Stop, Usage, note_web_query
from contraagent.backends.omp.classify import classify_text_result

_logger = logging.getLogger(__name__)
_warned: set[tuple[str, str]] = set()  # (agent, unread event type) already logged by this process

# omp surfaces a provider quota as a nonzero exit with a message, not as a
# structured status. Both the text path and the trace path need it, and
# both need the same copy: providers disagree on the wording.
_RATE_LIMIT_RE = re.compile(
    r"usage limit exceeded|rate[_ -]?limit|too many requests"
    r"|quota (?:exceeded|exhausted)|insufficient_quota",
    re.IGNORECASE,
)


def is_rate_limited(text: str) -> bool:
    return bool(_RATE_LIMIT_RE.search(text))


_RETRY_AFTER_RE = re.compile(r"retry-after-ms=(\d+)|retry[_ -]?after[\"':= ]+(\d+(?:\.\d+)?)", re.IGNORECASE)

#: omp's built-in web search tool; its arguments carry `query`.
WEB_SEARCH_TOOL = "web_search"

# Stream event types the monitor's live view renders; everything else on
# the wire (raw tool-call-argument deltas, internal bookkeeping frames,
# ...) is dropped before it reaches the shaping below.
STREAM_FWD = {
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "message_start",
    "message_end",
    "message_update",
    "tool_execution_start",
    "tool_execution_end",
    "tool_execution_update",
    "auto_retry_start",
    "auto_retry_end",
}


def normalize_text_line(line: str) -> dict:
    """Wrap one line of omp's plain-text stdout into the same
    message_update/text_delta shape a `--mode json` stream's text deltas
    render as.

    omp only emits structured `--mode json` events when launched with
    `--trace` (`OmpBackend.trace` defaults on, but `--no-trace`/explicit
    `trace=False` construction opts back into plain text). A non-JSON
    line on a `trace=False` task's stream is not malformed input -- it
    is the agent's own narration, and dropping it left every such
    task's monitor stream tab empty.
    """
    return {"type": "message_update", "ev": "text_delta", "delta": line[:2000] + "\n"}


def _preview(tool: object, args: object) -> dict:
    """A tool call's one-line preview (`cmd`); its query when it is a web search (`web_query`),
    its URL when it reads a web page (`web_fetch`: omp's `read` of an http(s) URL)."""
    args = args if isinstance(args, dict) else {}
    if tool == WEB_SEARCH_TOOL:
        query = str(args.get("query") or "")[:800]
        return {"cmd": query, "web_query": query}
    cmd = str(args.get("command", args.get("path", "")))[:800]
    if tool == "read" and cmd.startswith(("http://", "https://")):
        return {"cmd": cmd, "web_fetch": cmd}
    return {"cmd": cmd}


def normalize_event(e: dict) -> dict:
    """Trim one omp `--mode json` stream event to renderable fields (drop
    raw payloads), or `{"type": "skip"}` for one the monitor has nothing
    to show for: any type outside `STREAM_FWD`.
    """
    t = e.get("type")
    if t not in STREAM_FWD:
        return {"type": "skip"}
    if t == "message_update":
        ev = e.get("assistantMessageEvent", {})
        d = ev.get("delta", "")
        # toolcall_delta carries machine JSON fragments, not prose —
        # drop it (tool cards already show the call). thinking/text
        # deltas are human-readable; keep them tagged.
        kind = ev.get("type", "")
        if kind == "toolcall_delta":
            return {"type": "skip"}
        return {"type": t, "ev": kind, "delta": d[:500] if isinstance(d, str) else ""}
    if t in ("tool_execution_start", "tool_execution_update"):
        return {
            "type": t,
            "tool": e.get("toolName"),
            **_preview(e.get("toolName"), e.get("args")),
            "intent": str(e.get("intent", ""))[:200],
            "call": str(e.get("toolCallId", "")),
        }
    if t == "tool_execution_end":
        try:
            txt = e["result"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            txt = ""
        return {
            "type": t,
            "tool": e.get("toolName"),
            "out": str(txt)[:2000],
            "err": bool(e.get("isError")),
            "call": str(e.get("toolCallId", "")),
        }
    if t in ("message_start", "message_end"):
        m = e.get("message", {})
        role = m.get("role", "")
        try:
            c = m["content"][0]
        except (KeyError, IndexError, TypeError):
            return {"type": "skip"}
        if not isinstance(c, dict):
            return {"type": "skip"}
        ct = c.get("type", "")
        if ct == "toolCall":
            args = c.get("arguments", {}) or {}
            return {
                "type": "acall",
                "tool": c.get("name"),
                **_preview(c.get("name"), args),
                "call": str(c.get("id", "")),
                "intent": str(args.get("i", c.get("intent", "")))[:200],
            }
        if role == "toolResult":
            try:
                txt = c.get("text", "")[:2000]
            except AttributeError:
                txt = ""
            return {
                "type": "aresult",
                "tool": m.get("toolName"),
                "call": str(m.get("toolCallId", "")),
                "out": str(txt),
                "err": bool(m.get("isError")),
            }
        if role == "fileMention":
            return {"type": "skip"}
        if role == "custom":
            return {"type": "notice", "text": str(c.get("content", ""))[:800] if isinstance(c.get("content"), str) else str(c)[:800]}
        if ct == "thinking":
            th = c.get("thinking", "")
            if not th:
                return {"type": "skip"}
            return {"type": t, "text": "", "thinking": str(th)[:500]}
        txt = c.get("text", "")[:2000]
        return {"type": t, "role": role, "text": str(txt)}
    if t == "turn_end":
        try:
            c = e["message"]["content"][0]
        except (KeyError, IndexError, TypeError):
            return {"type": "skip"}
        if not isinstance(c, dict):
            return {"type": "skip"}
        if "arguments" in c:
            # Turn-level tool call echo (no thinking): fold into the
            # tool card stream as an acall so intent+command render.
            return {
                "type": "acall",
                "tool": c.get("name"),
                **_preview(c.get("name"), c.get("arguments")),
                "call": str(c.get("id", "")),
                "intent": str(c.get("intent", ""))[:200],
            }
        th = (c.get("thinking", "") or "")[:500]
        if not th:
            return {"type": "skip"}
        return {"type": t, "thinking": str(th)}
    if t == "auto_retry_start":
        return {"type": t, "attempt": e.get("attempt"), "err": str(e.get("errorMessage", ""))[:200]}
    return {"type": t}


def parse_retry_after(text: str) -> float | None:
    """The provider's own stated cool-off, in seconds.

    opencode-go answers a blown quota with `retry-after-ms=313534000` —
    three and a half days. Without it the router probes the primary on a
    timer and burns a launch per probe to learn the same thing; with it,
    one 429 buys a real schedule. Absent or unparsable: None, and the
    router falls back to its configured interval.
    """
    m = _RETRY_AFTER_RE.search(text)
    if not m:
        return None
    if m.group(1):
        return int(m.group(1)) / 1000.0
    try:
        return float(m.group(2))
    except (TypeError, ValueError):
        return None


def parse_trace(launch: Launch, agent: str, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
    """Parse `--mode json` event lines: tool calls, results, final text, tokens and cost."""
    reader = TraceReader()
    for raw in stdout.split(b"\n"):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            reader.feed(ev)
    return reader.result(launch, agent, exit_code=exit_code, killed=killed)


#: The event types omp sends in `--mode json` and on the RPC wire alike (its
#: `AgentEvent` and `AgentSessionEvent` unions and `session_settled`, which the RPC wire
#: sends once background work drains; checked against omp 18.9.1 and the recordings in
#: `tests/fixtures/omp/`). A type outside this set is counted in
#: `LaunchResult.unread_events`: a newer omp sends something this reader does not read.
KNOWN_EVENTS = STREAM_FWD | {
    "session",
    "error",
    "advisor_cost_changed",
    "auto_compaction_start",
    "auto_compaction_end",
    "goal_updated",
    "irc_message",
    "model_changed",
    "notice",
    "retry_fallback_applied",
    "retry_fallback_succeeded",
    "session_settled",
    "thinking_level_changed",
    "todo_auto_clear",
    "todo_reminder",
    "ttsr_triggered",
}
#: `message_update` kinds (`assistantMessageEvent.type`), from omp's `AssistantMessageEvent`.
KNOWN_UPDATES = {
    "start",
    "done",
    "error",
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "toolcall_start",
    "toolcall_delta",
    "toolcall_end",
    "image_end",
}


def web_query(update: dict) -> str | None:
    """The query of a `toolcall_end` update that calls `web_search`, else None."""
    if update.get("type") != "toolcall_end":
        return None
    call = update.get("toolCall") or {}
    args = call.get("arguments") if isinstance(call, dict) else None
    if call.get("name") != WEB_SEARCH_TOOL or not isinstance(args, dict):
        return None
    return str(args.get("query") or "")


def message_usage(raw: bytes) -> tuple[CallUsage, float | None] | None:
    """One event line's API call: the tokens and cost (USD) of an assistant
    `message_end`, or None for any other line."""
    try:
        ev = json.loads(raw)
    except ValueError:
        return None
    return event_usage(ev) if isinstance(ev, dict) else None


def event_usage(ev: dict) -> tuple[CallUsage, float | None] | None:
    """One event's API call: the tokens and cost (USD) of an assistant `message_end`,
    or None for any other event."""
    message = ev.get("message") if ev.get("type") == "message_end" else None
    if not isinstance(message, dict) or message.get("role") != "assistant" or not isinstance(message.get("usage"), dict):
        return None
    usage = message["usage"]
    try:
        call = CallUsage(
            model=str(message.get("model") or ""),
            input=int(usage.get("input") or 0),
            cache_read=int(usage.get("cacheRead") or 0),
            cache_creation=int(usage.get("cacheWrite") or 0),
            output=int(usage.get("output") or 0),
        )
    except (TypeError, ValueError):
        return None
    total = usage["cost"].get("total") if isinstance(usage.get("cost"), dict) else None
    return call, (float(total) if isinstance(total, (int, float)) else None)


class TraceReader:
    """Folds omp's agent events into a `LaunchResult`: the one reader of that wire.

    `--mode json` prints the events one per line; the RPC wire carries the same
    objects as frames (`OmpRpcBackend` reads its own frames first and hands the rest
    here). Each call ends twice on the wire, as `toolcall_end` and then as
    `tool_execution_end`; it is counted once, from the calls, or from the
    executions when no call was seen.
    """

    #: The coding agent whose wire this is, in the warning about an unread event.
    agent = "omp"
    #: The event types and `message_update` kinds this reader knows (`unread_events`: the rest).
    known_events = KNOWN_EVENTS
    known_updates = KNOWN_UPDATES

    def __init__(self) -> None:
        self.saw_any = False
        self.session_id = ""
        self.texts: list[str] = []
        self._text = ""
        self.tool_uses: Counter = Counter()
        self.executed: Counter = Counter()
        self.tool_args: dict[str, list[str]] = {}
        self.web_queries: list[str] = []
        self.calls: list[CallUsage] = []
        self.cost: float | None = None
        self.api_status: int | None = None
        self.api_error = ""
        self.unread: Counter = Counter()

    def feed(self, ev: dict) -> None:
        typ = str(ev.get("type") or "")
        if typ not in self.known_events:
            self.unread[typ or "<untyped>"] += 1
            return
        self.saw_any = True
        if typ == "session":
            self.session_id = str(ev.get("id") or "")
        elif typ == "message_update":
            self._update(ev.get("assistantMessageEvent") or {})
        elif typ == "tool_execution_end":
            name = str(ev.get("toolName") or "")
            if name:
                self.executed[name] += 1
        elif typ == "message_end":
            self._message_end(ev)
        elif typ == "error":
            err = ev.get("error")
            self._error(err if isinstance(err, dict) else ev)

    def _update(self, upd: dict) -> None:
        kind = str(upd.get("type") or "")
        if kind not in self.known_updates:
            self.unread[f"message_update/{kind}"] += 1
        elif kind == "toolcall_end":
            call = upd.get("toolCall") or {}
            name = str(call.get("name") or "") if isinstance(call, dict) else ""
            if name:
                self.tool_uses[name] += 1
                self._record_args(name, call.get("arguments"))
            query = web_query(upd)
            if query is not None:
                note_web_query(self.web_queries, query)
        elif kind == "text_start":
            self._text = ""
        elif kind == "text_delta":
            self._text += str(upd.get("delta") or "")
        elif kind == "text_end":
            self.texts.append(str(upd.get("content") or self._text))
            self._text = ""

    def _message_end(self, ev: dict) -> None:
        found = event_usage(ev)
        if found is not None:
            call, cost = found
            self.calls.append(call)
            if cost is not None:
                self.cost = (self.cost or 0.0) + cost
        message = ev.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            # The latest assistant message decides: an error omp retried past is not the outcome.
            self.api_status, self.api_error = None, ""
            self._error(message)

    def _error(self, frame: dict) -> None:
        """A provider refusal: `errorStatus`/`errorMessage` on an assistant message, or an `error` event."""
        status = frame.get("errorStatus", frame.get("status"))
        if status is not None and self.api_status is None:
            try:
                self.api_status = int(status)
            except (TypeError, ValueError):
                pass
        msg = str(frame.get("errorMessage") or (frame.get("message") if isinstance(frame.get("message"), str) else "") or "")
        if msg and msg not in self.api_error:
            self.api_error = f"{self.api_error} {msg}".strip()

    def _record_args(self, name: str, args: object) -> None:
        """A bounded sample of each tool's arguments (what did 138 bash calls run?)."""
        buf = self.tool_args.setdefault(name, [])
        if not isinstance(args, dict) or len(buf) >= 20:
            return
        try:
            buf.append(json.dumps(args, ensure_ascii=False)[:500])
        except (TypeError, ValueError):
            pass

    def classify(self, text: str, *, exit_code: int | None, killed: Stop | None) -> Stop:
        """How the launch ended, from its final text, its exit and what the provider said."""
        # Rate limit before the text/exit-code shape: a 429 is terminal. The status is
        # authoritative when present; the message is the fallback for providers that
        # only say "quota".
        rate_limited = self.api_status is None and is_rate_limited(self.api_error)
        return classify_text_result(
            text, saw_any=self.saw_any, exit_code=exit_code, killed=killed, rate_limited=rate_limited, api_status=self.api_status
        )

    def usage(self) -> tuple[Usage, float | None]:
        """The tokens of every API call and their summed cost (None when none reported one)."""
        return Usage(calls=list(self.calls), output_total=sum(c.output for c in self.calls)), (
            round(self.cost, 6) if self.cost is not None else None
        )

    def result(
        self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None, argv: list[str] | None = None
    ) -> LaunchResult:
        """How the launch ended, and everything read on the way. `exit_code` None: no
        process exit to weigh (the RPC wire)."""
        text = "\n".join(t for t in self.texts if t).strip()
        stop = self.classify(text, exit_code=exit_code, killed=killed)
        for typ in sorted(t for t in self.unread if (self.agent, t) not in _warned):
            _warned.add((self.agent, typ))
            _logger.warning(
                f"[{self.agent}] event {typ!r} is not one this contraagent reads; a newer {self.agent}? (LaunchResult.unread_events)"
            )
        usage, cost = self.usage()
        result_text = text
        if stop is Stop.RATE_LIMITED:
            result_text = text or self.api_error
        elif stop in (Stop.ERROR, Stop.LAUNCH_FAILED):
            result_text = ""
        return LaunchResult(
            label=launch.label,
            agent=agent,
            stop=stop,
            ok=stop is Stop.COMPLETED,
            exit_code=exit_code,
            model=launch.model,
            argv=list(argv or []),
            session_id=self.session_id,
            result_text=result_text,
            rate_limit=RateLimit(status="quota", retry_after_s=parse_retry_after(self.api_error)) if stop is Stop.RATE_LIMITED else None,
            tool_uses=dict(self.tool_uses or self.executed),
            web_queries=list(self.web_queries),
            usage=usage,
            cost_usd=cost,
            raw_result={"tool_args": dict(self.tool_args)},
            # The provider's own words, which omp puts on no stderr: the journal's reason.
            stderr_tail=self.api_error if stop is not Stop.COMPLETED else "",
            unread_events=dict(self.unread),
        )
