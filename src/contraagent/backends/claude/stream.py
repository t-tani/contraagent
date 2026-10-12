"""Claude Code's `stream-json` wire format: per-line event folding and the
final result-to-Stop classifier.

Split out of `claude.py` so the wire-parsing concern (what shows up on the
NDJSON stream) stays separate from the Backend-contract concern (argv/env/
session lifecycle). `claude.py` is the only importer; nothing here imports
back into it.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime

from contraagent.backends.launch import (
    CallUsage,
    Limits,
    RateLimit,
    Stop,
    Usage,
    note_web_query,
)

# Usage-limit copy observed in result text (40 live sightings, 2026-09).
RATE_LIMIT_RE = re.compile(r"hit your (weekly|usage|session) limit|rate.?limit", re.I)
# Safety-refusal signal.
_REFUSAL_RE = re.compile(r"safeguard|refus", re.I)
#: Claude Code's web search tool; its input carries `query`.
WEB_SEARCH_TOOL = "WebSearch"
#: Claude Code's web page tool; its input carries `url` and `prompt`.
WEB_FETCH_TOOL = "WebFetch"
# How Claude Code hands the agent what a Stop hook said: a user message starting so.
STOP_HOOK_FEEDBACK = "Stop hook feedback:"


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


def _rate_limit_from_event(ev: dict) -> RateLimit:
    """Claude stream `rate_limit_event` (`unifiedWindows`) to RateLimit."""
    info = ev.get("rate_limit_info") or {}
    win = info.get("unifiedWindows") or {}

    def pct(k: str) -> float | None:
        u = (win.get(k) or {}).get("utilization")
        return round(float(u) * 100, 1) if u is not None else None

    def at(k: str) -> str | None:
        ts = (win.get(k) or {}).get("resetsAt")
        return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds") if ts else None

    return RateLimit(
        observed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        status=str(info.get("status", "")),
        five_hour_pct=pct("five_hour"),
        five_hour_resets_at=at("five_hour"),
        seven_day_pct=pct("seven_day"),
        seven_day_resets_at=at("seven_day"),
    )


class StreamReader:
    """One stream-json line at a time: per-call usage, tool use, rate
    limits, denials, retries, and the final result."""

    def __init__(self, limits: Limits):
        self.limits = limits
        self.usage = Usage()
        self.tool_uses: Counter = Counter()
        self.rate_limit: RateLimit | None = None
        self.rate_limits: list[RateLimit] = []
        self.result: dict | None = None
        self.session_id = ""
        self.cli_version = ""
        self.api_key_source = ""
        self.saw_any = False
        self._seen_msg: set[str] = set()
        self.init_model = ""
        self.init_tools = 0
        self.init_errors: list[dict] = []
        self.api_retries = 0
        self.retry_errors: Counter = Counter()
        self.denied: list[dict] = []  # `permission_denied`, ahead of result
        self.hook_errors: list[list[str]] = []  # what a Stop hook sent back, per objection
        self.web_queries: list[str] = []  # WebSearch terms, capped

    def feed(self, line: str) -> Stop | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except ValueError:
            return None
        self.saw_any = True
        typ = ev.get("type")
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
            self.retry_errors[err] += 1
            if err == "authentication_failed" and self.retry_errors[err] >= 2:
                return Stop.AUTH_FAILED
        elif typ == "system" and ev.get("subtype") == "permission_denied":
            self.denied.append({"tool_name": ev.get("tool_name"), "tool_input": ev.get("tool_input") or {}})
            if self.limits.max_denials is not None and len(self.denied) > self.limits.max_denials:
                return Stop.DENIED
        elif typ == "user" and (feedback := stop_hook_feedback(ev)) is not None:
            self.hook_errors.append(feedback_errors(feedback))
        elif typ == "rate_limit_event":
            self.rate_limit = _rate_limit_from_event(ev)
            self.rate_limits.append(self.rate_limit)
        elif typ == "assistant":
            msg = ev.get("message") or {}
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    self.tool_uses[str(b.get("name"))] += 1
                    inp = b.get("input")
                    if not isinstance(inp, dict):
                        inp = {}
                    if b.get("name") == WEB_SEARCH_TOOL:
                        note_web_query(self.web_queries, inp.get("query"))
            mid = str(msg.get("id") or "")
            u = msg.get("usage")
            if u and mid and mid not in self._seen_msg:
                self._seen_msg.add(mid)
                call = CallUsage(
                    model=str(msg.get("model") or ""),
                    input=int(u.get("input_tokens") or 0),
                    cache_read=int(u.get("cache_read_input_tokens") or 0),
                    cache_creation=int(u.get("cache_creation_input_tokens") or 0),
                    output=int(u.get("output_tokens") or 0),
                )
                self.usage.calls.append(call)
                if self.limits.context_budget and call.context > self.limits.context_budget:
                    return Stop.CONTEXT
        elif typ == "result":
            self.result = ev
        return None


def classify_result(res: dict, exit_code: int | None, saw_any: bool) -> Stop:
    """One stop reason from the result JSON. Order matters: usage limit,
    then auth, refusal, abort, turn/budget caps, then generic error."""
    if not res:
        return Stop.NO_OUTPUT if saw_any or exit_code == 0 else Stop.LAUNCH_FAILED
    text = str(res.get("result") or "")
    subtype = str(res.get("subtype") or "")
    status = res.get("api_error_status")
    if status == 429 or RATE_LIMIT_RE.search(text):
        return Stop.RATE_LIMITED
    if status in (401, 403) or text.startswith("Failed to authenticate"):
        return Stop.AUTH_FAILED
    if res.get("stop_reason") == "refusal" or (res.get("is_error") and _REFUSAL_RE.search(text)):
        return Stop.REFUSED
    if str(res.get("terminal_reason") or "").startswith("aborted"):
        return Stop.ABORTED
    if "max_turns" in subtype:
        return Stop.MAX_TURNS
    if "budget" in subtype:
        return Stop.BUDGET
    if res.get("is_error") or (subtype and subtype != "success"):
        return Stop.API_ERROR
    return Stop.COMPLETED


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
    `backends.omp.trace.normalize_event` produces for the analogous omp events, or
    `{"type": "skip"}` for one the monitor has nothing to show for.

    Confirmed against a live `claude -p --output-format stream-json`
    capture (not just `StreamReader.feed`'s own parsing, which only ever
    reads these same top-level shapes): an `assistant` event's `message.
    content` list holds exactly one block per event (text, thinking, or
    tool_use — never fine-grained `content_block_delta` fragments), so
    reading `content[0]` is correct, not a simplification of something
    richer.

    Tool results: claude's wire format echoes a tool's result as a separate
    top-level `{"type": "user", ...}` event carrying `tool_use_id` +
    `content` (never the tool *name*). It is mapped here to the same
    `tool_execution_end` shape omp emits, keyed by `call` = `tool_use_id`.
    The name is deliberately left empty: the monitor matches a result to its
    originating `tool_execution_start` card by `call` id (not by name), so no
    stateful tool_use_id -> name cache is needed and this stays a pure
    one-event-in/one-event-out function. (This closes the former gap where
    claude tool *results* were dropped and only *calls* rendered.)
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
            # First useful one-liner for the card preview: a Bash command, a
            # Grep/Glob pattern, a Read/Edit/Write path, a fetched URL or a search query.
            cmd = str(
                inp.get("command")
                or inp.get("pattern")
                or inp.get("file_path")
                or inp.get("path")
                or inp.get("url")
                or inp.get("query")
                or ""
            )[:800]
            name = block.get("name")
            start = {
                "type": "tool_execution_start",
                "tool": name,
                "cmd": cmd,
                # WebFetch's `prompt` (what to take from the page) is its intent.
                "intent": str(inp.get("prompt") or "")[:200] if name == WEB_FETCH_TOOL else "",
                "call": str(block.get("id") or ""),
            }
            if name == WEB_SEARCH_TOOL:
                return {**start, "web_query": cmd}
            return {**start, "web_fetch": cmd} if name == WEB_FETCH_TOOL else start
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
