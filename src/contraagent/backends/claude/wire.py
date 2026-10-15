"""Claude Code's wire (`--output-format stream-json --verbose`): `StreamReader`, which folds
it into a `LaunchResult`, and the monitor's view of its events (`normalize_event`).

One JSON event per line: `system` (`init`, `api_retry`, `permission_denied`, ...),
`assistant` (one content block per event, with the API call's usage), `user` (tool results,
a Stop hook's feedback), `rate_limit_event` (the subscription's utilization) and the final
`result`, which says how the session ended.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from contraagent.backends.launch import CallUsage, Launch, LaunchResult, Limits, Stop
from contraagent.backends.refusal import Ending, Signals
from contraagent.backends.wire import EventFold, first_text, tokens, tool_preview
from contraagent.dispatch.records import OtherModel, QuotaReading, QuotaWindow

#: A safety refusal in an error result's text (a result that is no error may say it in passing).
REFUSAL_RE = re.compile(r"safeguard|refus", re.I)
#: How Claude Code words a refusal. Usage-limit copy observed in result text (40 live
#: sightings, 2026-09); a refused credential's result starts `Failed to authenticate`; a
#: safety refusal is `REFUSAL_RE` in an error result. A process that printed nothing failed
#: to start when it exited nonzero; one that printed something but no result had no output.
SIGNALS = Signals(
    quota=re.compile(r"hit your (weekly|usage|session) limit|rate.?limit", re.I),
    auth=re.compile(r"^Failed to authenticate"),
    silence_is_startup=True,
    nonzero_exit_is_error=False,
    stderr_stops=frozenset({Stop.ERROR, Stop.NO_OUTPUT, Stop.API_ERROR, Stop.LAUNCH_FAILED}),
)
#: The event types Claude Code sends on its stream (its SDK's message types). Another is
#: counted in `LaunchResult.unread_events`.
KNOWN_EVENTS = frozenset(
    {
        *("system", "assistant", "user", "result", "rate_limit_event", "stream_event"),
        *("tool_progress", "tool_use_summary", "auth_status", "prompt_suggestion"),
    }
)
#: Claude Code's web search tool; its input carries `query`.
WEB_SEARCH_TOOL = "WebSearch"
#: Claude Code's web page tool; its input carries `url` and `prompt`.
WEB_FETCH_TOOL = "WebFetch"
# How Claude Code hands the agent what a Stop hook said: a user message starting so.
STOP_HOOK_FEEDBACK = "Stop hook feedback:"
# Hollow shape: <=1 turn, no tool use, raw tool-call text as the body.
_HOLLOW_RE = re.compile(r"\b(Bash|Read|Write|Edit|Skill|Agent|WebFetch|WebSearch)\(")


def stop_hook_feedback(ev: dict) -> str | None:
    """The text of a `user` event that carries a Stop hook's objection, else None."""
    if ev.get("type") != "user":
        return None
    content = (ev.get("message") or {}).get("content")
    blocks = [content] if isinstance(content, str) else content if isinstance(content, list) else []
    for b in blocks:
        text = b if isinstance(b, str) else b.get("text") if isinstance(b, dict) and b.get("type") == "text" else None
        if isinstance(text, str) and text.startswith(STOP_HOOK_FEEDBACK):
            return text
    return None


def feedback_errors(text: str) -> list[str]:
    """The errors a check's feedback lists (its `- ` lines outside code), else the text itself."""
    errors, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("- "):
            errors.append(line[2:])
    return errors or [text.strip()]


#: The fields of `rate_limit_info` a reading names; the rest go to `QuotaReading.extra`.
#: `resetsAt` and `utilization` are those of the `rateLimitType` window, in `windows`.
_READ_FIELDS = frozenset(
    {
        *("status", "resetsAt", "utilization", "rateLimitType", "surpassedThreshold"),
        *("overageStatus", "overageDisabledReason", "isUsingOverage", "unifiedWindows"),
    }
)


def _share_pct(u: object) -> float | None:
    return round(float(u) * 100, 1) if isinstance(u, (int, float)) and not isinstance(u, bool) else None


def _at(ts: object) -> str | None:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds") if isinstance(ts, (int, float)) and ts else None


def _reading_from_event(ev: dict) -> QuotaReading:
    """Claude stream `rate_limit_event` to a `QuotaReading`: each window of `unifiedWindows` (and
    the `rateLimitType` window the status is about), the status and its threshold, the
    overage fields, and what else it carries as `extra`."""
    info = ev.get("rate_limit_info") or {}
    win = info.get("unifiedWindows") or {}
    windows = {
        str(name): QuotaWindow(pct=_share_pct(w.get("utilization")), resets_at=_at(w.get("resetsAt")))
        for name, w in win.items()
        if isinstance(w, dict)
    }
    kind = str(info.get("rateLimitType") or "")
    if kind and kind not in windows and ("utilization" in info or "resetsAt" in info):
        windows[kind] = QuotaWindow(pct=_share_pct(info.get("utilization")), resets_at=_at(info.get("resetsAt")))
    using = info.get("isUsingOverage")
    return QuotaReading.from_windows(
        windows,
        observed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        status=str(info.get("status", "")),
        status_window=kind,
        threshold_pct=_share_pct(info.get("surpassedThreshold")),
        overage_status=str(info.get("overageStatus") or ""),
        overage_disabled_reason=str(info.get("overageDisabledReason") or ""),
        using_overage=using if isinstance(using, bool) else None,
        extra={k: v for k, v in info.items() if k not in _READ_FIELDS},
    )


def other_models(model_usage: object, own: str) -> dict[str, OtherModel]:
    """The result's `modelUsage` (`{model: {"costUSD", "inputTokens", ...}}`) less the
    launch's own model (`own`, the session's model; else the one that wrote the most),
    as `LaunchResult.other_models`."""
    used = _model_usage(model_usage)
    own = _own_model(used, own)
    return {
        m: OtherModel(
            cost_usd=u.get("costUSD") if isinstance(u.get("costUSD"), (int, float)) else None,
            input=_int(u.get("inputTokens")),
            output=_int(u.get("outputTokens")),
            cache_read=_int(u.get("cacheReadInputTokens")),
            cache_creation=_int(u.get("cacheCreationInputTokens")),
        )
        for m, u in used.items()
        if m != own
    }


def context_window(model_usage: object, own: str) -> int | None:
    """The context window of the launch's own model (`own`, chosen as `other_models`
    chooses it): the result's `modelUsage[<model>].contextWindow`, as
    `LaunchResult.context_window`; None when the result reports none."""
    used = _model_usage(model_usage)
    window = used.get(_own_model(used, own), {}).get("contextWindow")
    return int(window) if isinstance(window, int) and not isinstance(window, bool) and window > 0 else None


def _model_usage(model_usage: object) -> dict[str, dict]:
    if not isinstance(model_usage, dict):
        return {}
    return {m: u for m, u in model_usage.items() if isinstance(u, dict)}


def _own_model(used: dict[str, dict], own: str) -> str:
    if own not in used and used:
        return max(used, key=lambda m: _int(used[m].get("outputTokens")))
    return own


def _int(v: object) -> int:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


class StreamReader(EventFold):
    """Claude Code's events, one at a time: per-call usage, tool use, rate limits, denials,
    retries, a Stop hook's objections, and the final result."""

    agent = "claude"
    known_events = KNOWN_EVENTS
    signals = SIGNALS

    def __init__(self, limits: Limits):
        super().__init__()
        self.limits = limits
        #: The quota readings of the stream, oldest first.
        self.quota: list[QuotaReading] = []
        #: The final `result` event, when one arrived.
        self.final: dict | None = None
        self.cli_version = ""
        self.api_key_source = ""
        self._seen_msg: set[str] = set()
        self.init_model = ""
        self.init_tools = 0
        self.init_errors: list[dict] = []
        self.api_retries = 0
        self.retry_errors: dict[str, int] = {}
        self.denied: list[dict] = []  # `permission_denied`, ahead of result
        self.hook_errors: list[list[str]] = []  # what a Stop hook sent back, per objection

    def feed(self, ev: dict) -> Stop | None:
        self.saw_any = True
        typ = str(ev.get("type") or "")
        if self.unknown(typ):
            return None
        if typ == "system" and ev.get("subtype") == "init":
            self.session_id = str(ev.get("session_id") or "")
            self.cli_version = str(ev.get("claude_code_version") or "")
            self.api_key_source = str(ev.get("apiKeySource") or "")
            self.init_model = str(ev.get("model") or "")
            self.init_tools = len(ev.get("tools") or [])
            for key in ("mcp_server_errors", "plugin_errors"):
                self.init_errors += [{"kind": key, **e} for e in (ev.get(key) or []) if isinstance(e, dict)]
        elif typ == "system" and ev.get("subtype") == "api_retry":
            # Auth failures never heal by waiting: a wrong Bearer loops
            # until timeout. Stop on the second one.
            self.api_retries += 1
            err = str(ev.get("error") or "unknown")
            self.retry_errors[err] = self.retry_errors.get(err, 0) + 1
            if err == "authentication_failed" and self.retry_errors[err] >= 2:
                return Stop.AUTH_FAILED
        elif typ == "system" and ev.get("subtype") == "permission_denied":
            self.denied.append({"tool_name": ev.get("tool_name"), "tool_input": ev.get("tool_input") or {}})
            if self.limits.max_denials is not None and len(self.denied) > self.limits.max_denials:
                return Stop.DENIED
        elif typ == "user" and (feedback := stop_hook_feedback(ev)) is not None:
            self.hook_errors.append(feedback_errors(feedback))
        elif typ == "rate_limit_event":
            self.quota.append(_reading_from_event(ev))
        elif typ == "assistant":
            self._assistant(ev.get("message") or {})
        elif typ == "result":
            self.final = ev
        return None

    def _assistant(self, msg: dict) -> None:
        for b in msg.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                # Claude Code's tool arguments are kept in its own result, not sampled here.
                self.tool_uses[str(b.get("name"))] += 1
                inp = b.get("input")
                if b.get("name") == WEB_SEARCH_TOOL and isinstance(inp, dict):
                    self.note_web_query(inp.get("query"))
        mid = str(msg.get("id") or "")
        u = msg.get("usage")
        if u and mid and mid not in self._seen_msg:
            self._seen_msg.add(mid)
            self.add_call(
                CallUsage(
                    model=str(msg.get("model") or ""),
                    input=tokens(u, "input_tokens"),
                    cache_read=tokens(u, "cache_read_input_tokens"),
                    cache_creation=tokens(u, "cache_creation_input_tokens"),
                    output=tokens(u, "output_tokens"),
                )
            )

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """The result event decides: its API status, its text (where a quota, a refused
        credential or a refusal is worded), its subtype and its reasons."""
        res = self.final or {}
        text = str(res.get("result") or "")
        subtype = str(res.get("subtype") or "")
        status = res.get("api_error_status")
        capped = Stop.MAX_TURNS if "max_turns" in subtype else Stop.BUDGET if "budget" in subtype else None
        e = Ending(
            killed=killed,
            exit_code=exit_code,
            saw_any=self.saw_any,
            error=text,
            status=status if isinstance(status, int) and not isinstance(status, bool) else None,
            auth=status in (401, 403),
            refused=res.get("stop_reason") == "refusal" or bool(res.get("is_error") and REFUSAL_RE.search(text)),
            aborted=str(res.get("terminal_reason") or "").startswith("aborted"),
            capped=capped,
        )
        if res:
            e.failed = bool(
                res.get("is_error")
                or (subtype and subtype != "success")
                or e.auth
                or SIGNALS.auth_in(text)
                or e.refused
                or e.aborted
                or capped
            )
            e.completed = not e.failed
        return e

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        res = self.final or {}
        stop = self.stop(exit_code=exit_code, killed=killed)
        text = str(res.get("result") or "")
        hollow = (res.get("num_turns") or 0) <= 1 and not self.tool_uses and bool(_HOLLOW_RE.search(text))
        usage = self.usage()
        usage.output_total = int((res.get("usage") or {}).get("output_tokens") or 0)
        own = self.init_model or launch.model
        return self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            ok=stop is Stop.COMPLETED and not hollow,
            cli_version=self.cli_version,
            api_key_source=self.api_key_source,
            session_id=str(res.get("session_id") or self.session_id or ""),
            num_turns=res.get("num_turns"),
            duration_api_ms=res.get("duration_api_ms"),
            result_text=text,
            structured_output=res.get("structured_output"),
            cost_usd=res.get("total_cost_usd"),
            usage=usage,
            other_models=other_models(res.get("modelUsage"), own),
            context_window=context_window(res.get("modelUsage"), own),
            quota=list(self.quota),
            permission_denials=list(res.get("permission_denials") or []) or list(self.denied),
            hollow=hollow,
            raw_result=res,
            init_model=self.init_model,
            init_tools=self.init_tools,
            init_errors=self.init_errors,
            api_retries=self.api_retries,
            retry_errors=dict(self.retry_errors),
            hook_errors=list(self.hook_errors),
        )


def _tool_result_text(block: dict) -> str:
    """The human-readable text of a claude `tool_result` block, whose
    `content` is either a plain string or a list of content segments
    ({type:text,text:...}); anything else degrades to ""."""
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for seg in c:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(str(seg.get("text") or ""))
            elif isinstance(seg, str):
                parts.append(seg)
        return "\n".join(parts)
    return ""


def normalize_event(e: dict) -> dict:
    """Map one claude `stream-json` event onto the same renderable shapes
    `backends.omp.wire.normalize_event` produces for the analogous omp events, or
    `{"type": "skip"}` for one the monitor has nothing to show for.

    Confirmed against a live `claude -p --output-format stream-json`
    capture: an `assistant` event's `message.content` list holds exactly one
    block per event (text, thinking, or tool_use — never fine-grained
    `content_block_delta` fragments), so reading `content[0]` is correct, not a
    simplification of something richer.

    Tool results: claude's wire format echoes a tool's result as a separate
    top-level `{"type": "user", ...}` event carrying `tool_use_id` +
    `content` (never the tool *name*). It is mapped here to the same
    `tool_execution_end` shape omp emits, keyed by `call` = `tool_use_id`.
    The name is left empty: the monitor matches a result to its originating
    `tool_execution_start` card by `call` id (not by name), so no
    stateful tool_use_id -> name cache is needed and this stays a pure
    one-event-in/one-event-out function.
    """
    typ = e.get("type")
    if typ == "assistant":
        msg = e.get("message") or {}
        blocks = msg.get("content") or []
        block = blocks[0] if blocks and isinstance(blocks[0], dict) else {}
        bt = block.get("type")
        if bt == "text":
            return {"type": "message_update", "ev": "text_delta", "delta": str(block.get("text") or "")}
        if bt == "thinking":
            return {"type": "message_update", "ev": "thinking_delta", "delta": str(block.get("thinking") or "")}
        if bt == "tool_use":
            inp = block.get("input")
            if not isinstance(inp, dict):
                inp = {}
            name = block.get("name")
            # First useful one-liner for the card preview: a Bash command, a
            # Grep/Glob pattern, a Read/Edit/Write path, a fetched URL or a search query.
            cmd = first_text(inp, "command", "pattern", "file_path", "path", "url", "query")
            return {
                "type": "tool_execution_start",
                "tool": name,
                **tool_preview(cmd, web_query=name == WEB_SEARCH_TOOL, web_fetch=name == WEB_FETCH_TOOL),
                # WebFetch's `prompt` (what to take from the page) is its intent.
                "intent": str(inp.get("prompt") or "")[:200] if name == WEB_FETCH_TOOL else "",
                "call": str(block.get("id") or ""),
            }
        return {"type": "skip"}
    if typ == "user" and (feedback := stop_hook_feedback(e)) is not None:
        return {"type": "notice", "text": feedback[:4000]}
    if typ == "user":
        # A tool_result block carried on a user event -> the matching tool
        # card's completion. content is a plain string or a list of
        # {type:text,text:...} blocks; is_error flags a failed tool.
        msg = e.get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    return {
                        "type": "tool_execution_end",
                        "tool": "",
                        "out": _tool_result_text(b)[:4000],
                        "err": bool(b.get("is_error")),
                        "call": str(b.get("tool_use_id") or ""),
                    }
        return {"type": "skip"}
    if typ == "system" and e.get("subtype") == "init":
        return {"type": "notice", "text": f"session init: model={e.get('model') or ''}"[:800]}
    if typ == "system" and e.get("subtype") == "api_retry":
        return {"type": "notice", "text": f"retrying after error: {e.get('error') or ''}"[:800]}
    if typ == "rate_limit_event":
        info = e.get("rate_limit_info") or {}
        return {"type": "notice", "text": f"rate limit status: {info.get('status', '')}"[:800]}
    return {"type": "skip"}
