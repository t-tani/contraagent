"""omp's event wire: `TraceReader`, the one reader of the agent events omp sends in
`--mode json` and over RPC, `TextReader` for its plain-text mode, and the monitor's view
of those events (`normalize_event`, `normalize_text_line`).

Tested on recordings of a real omp (`tests/fixtures/omp/<version>/`).
"""

from __future__ import annotations

from typing import Self

from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, Stop
from contraagent._internal.backends.refusal import QUOTA_RE, Ending, Signals, quota_refusal
from contraagent._internal.backends.wire import EventFold, feedback_errors, tokens, tool_preview

#: How omp words a refusal: a provider's quota in its own words (providers disagree on the
#: wording), read only when the wire gives no status; a status decides alone. omp reports
#: a quota refusal on stderr in text mode (`429 Go usage limit exceeded`), and nowhere else.
SIGNALS = Signals(quota=QUOTA_RE, status_decides=True)

#: omp's built-in web search tool; its arguments carry `query`.
WEB_SEARCH_TOOL = "web_search"
#: The `customType` of the message omp continues a session with when a `session_stop`
#: handler blocks the stop (a plugin's stop hook, `omp/index.ts`): its `content` is what the
#: hook said.
STOP_CONTINUATION = "session-stop-continuation"


def stop_hook_feedback(message: object) -> str | None:
    """What a stop hook said, when `message` is the one omp continues the session with, else None."""
    if not isinstance(message, dict) or message.get("role") != "custom" or message.get("customType") != STOP_CONTINUATION:
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


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
        return tool_preview(args.get("query"), web_query=True)
    cmd = str(args.get("command", args.get("path", "")))
    return tool_preview(cmd, web_fetch=tool == "read" and cmd.startswith(("http://", "https://")))


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
        if (said := stop_hook_feedback(m)) is not None:
            # Once, at its end, as Claude Code's transcript shows it.
            return {"type": "notice", "text": f"Stop hook feedback:\n{said}"[:4000]} if t == "message_end" else {"type": "skip"}
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
            input=tokens(usage, "input"),
            cache_read=tokens(usage, "cacheRead"),
            cache_creation=tokens(usage, "cacheWrite"),
            output=tokens(usage, "output"),
        )
    except (TypeError, ValueError):
        return None
    total = usage["cost"].get("total") if isinstance(usage.get("cost"), dict) else None
    return call, (float(total) if isinstance(total, (int, float)) else None)


class TraceReader(EventFold):
    """Folds omp's agent events into a `LaunchResult`: the one reader of that wire.

    `--mode json` prints the events one per line; the RPC wire carries the same
    objects as frames (`OmpRpcBackend` reads its own frames first and hands the rest
    here). Each call ends twice on the wire, as `toolcall_end` and then as
    `tool_execution_end`; it is counted once, from the calls, or from the
    executions when no call was seen.
    """

    agent = "omp"
    known_events = frozenset(KNOWN_EVENTS)
    #: The `message_update` kinds this reader knows (`unread_events`: the rest).
    known_updates = frozenset(KNOWN_UPDATES)
    signals = SIGNALS

    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []
        self._text = ""
        self.executed: dict[str, int] = {}
        self.api_status: int | None = None
        self.api_error = ""
        #: What the plugin's stop hook sent back within the launch, per objection.
        self.hook_errors: list[list[str]] = []

    def feed(self, ev: dict) -> Stop | None:
        typ = str(ev.get("type") or "")
        if self.unknown(typ):
            return None
        self.saw_any = True
        if typ == "session":
            self.session_id = str(ev.get("id") or "")
        elif typ == "message_update":
            self._update(ev.get("assistantMessageEvent") or {})
        elif typ == "tool_execution_end":
            name = str(ev.get("toolName") or "")
            if name:
                self.executed[name] = self.executed.get(name, 0) + 1
        elif typ == "message_end":
            self._message_end(ev)
        elif typ == "error":
            err = ev.get("error")
            self._error(err if isinstance(err, dict) else ev)
        return None

    def _update(self, upd: dict) -> None:
        kind = str(upd.get("type") or "")
        if kind not in self.known_updates:
            self.unread[f"message_update/{kind}"] += 1
        elif kind == "toolcall_end":
            call = upd.get("toolCall") or {}
            if isinstance(call, dict):
                self.note_tool(str(call.get("name") or ""), call.get("arguments"))
            query = web_query(upd)
            if query is not None:
                self.note_web_query(query)
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
            self.add_call(*found)
        message = ev.get("message")
        if (said := stop_hook_feedback(message)) is not None:
            self.hook_errors.append(feedback_errors(said))
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

    @property
    def text(self) -> str:
        """The answer: every text the agent ended, joined."""
        return "\n".join(t for t in self.texts if t).strip()

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """The final text, the exit and what the provider said (its status, else its words)."""
        return Ending(
            killed=killed, exit_code=exit_code, saw_any=self.saw_any, text=self.text, error=self.api_error, status=self.api_status
        )

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """How the launch ended, and everything read on the way. `exit_code` None: no
        process exit to weigh (the RPC wire)."""
        stop = self.stop(exit_code=exit_code, killed=killed)
        text = self.text
        if stop is Stop.RATE_LIMITED:
            text = text or self.api_error
        elif stop in (Stop.ERROR, Stop.LAUNCH_FAILED):
            text = ""
        return self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            result_text=text,
            quota_refusal=quota_refusal(self.api_error) if stop is Stop.RATE_LIMITED else None,
            tool_uses=dict(self.tool_uses or self.executed),
            hook_errors=list(self.hook_errors),
            # The provider's own words, which omp puts on no stderr: the journal's reason.
            stderr_tail=self.api_error if stop is not Stop.COMPLETED else "",
        )


class TextReader(EventFold):
    """omp's plain-text mode (`trace=False`): stdout is the answer, with no usage or cost.

    Stdout never holds a refusal: when the last assistant message ended on an error, omp
    18.9 prints nothing on stdout, writes the message's `errorMessage` on stderr and exits 1.
    The exit status decides, and `Backend.reclassify` reads the refusal on stderr."""

    agent = "omp"
    signals = SIGNALS

    def __init__(self) -> None:
        super().__init__()
        # Text mode has no "nothing ran at all" signal apart from "ran and said nothing":
        # empty text is no output, not a launch failure.
        self.saw_any = True
        self.lines: list[bytes] = []

    def feed_line(self, raw: bytes | str) -> Stop | None:
        self.lines.append(raw.encode() if isinstance(raw, str) else raw)
        return None

    def read(self, data: bytes) -> Self:
        self.lines = data.split(b"\n")
        return self

    @property
    def text(self) -> str:
        return b"\n".join(self.lines).decode("utf-8", "replace").strip()

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        return Ending(killed=killed, exit_code=exit_code, saw_any=True, text=self.text)

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        stop = self.stop(exit_code=exit_code, killed=killed)
        text = self.text
        return self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            result_text=text if stop in (Stop.COMPLETED, Stop.RATE_LIMITED) else "",
            quota_refusal=quota_refusal(text) if stop is Stop.RATE_LIMITED else None,
            raw_result={},
        )
