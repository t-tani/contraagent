"""Codex CLI's wire: the `codex exec --json` events and the session's rollout file.

`--json` prints one event per line (checked against codex-cli 0.162.1):
`thread.started` (the thread id), `turn.started`, `item.started` /
`item.updated` / `item.completed` (an `item` with its own `type`:
`agent_message`, `reasoning`, `command_execution`, `file_change`,
`mcp_tool_call`, `web_search`, `todo_list`, `error`), `error` (a request
that failed; `Reconnecting... N/M (...)` while codex retries it) and
`turn.completed` (the turn's summed `usage`) or `turn.failed`.

The events carry no per-call token counts, no model name and no account
usage. The rollout file codex writes for a persisted session
(`$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*-<thread id>.jsonl`) does: one
`event_msg` `token_count` per API call (`last_token_usage`, `rate_limits`)
and a `turn_context` with the model. `read_rollout` takes those.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.launch import CallUsage, RateLimit, Stop, note_web_query

#: A refusal for usage or rate (ChatGPT plan limits, a provider's 429).
RATE_LIMIT_RE = re.compile(r"\b429\b|usage limit|rate.?limit|quota|too many requests", re.I)
_AUTH_RE = re.compile(r"\b(401|403)\b|unauthori[sz]ed|forbidden|invalid api key|not logged in", re.I)
_REFUSAL_RE = re.compile(r"cyber_policy|safety|refus", re.I)
#: `Reconnecting... 2/5 (unexpected status 401 Unauthorized: ...)`
_RECONNECT_RE = re.compile(r"^Reconnecting\.\.\. (\d+)/(\d+) \((.*)\)$", re.S)
_STATUS_RE = re.compile(r"\bstatus (\d{3})\b|\"code\":\s*\"?(\d{3})")
#: The rollout's rate-limit windows by length: 5 hours and 7 days.
_FIVE_HOUR_MIN, _SEVEN_DAY_MIN = 300, 10080

#: Item types that are a tool call; the rest are the agent's own text.
TOOL_ITEMS = ("command_execution", "file_change", "mcp_tool_call", "web_search")
#: Every `--json` event type `EventReader` reads; another is counted in `unread`.
KNOWN_EVENTS = frozenset(
    {"thread.started", "turn.started", "turn.completed", "turn.failed", "item.started", "item.updated", "item.completed", "error"}
)


def _status_class(message: str) -> str:
    """A short cause for a failed request: `http_<status>` when the message has one, else `error`."""
    m = _STATUS_RE.search(message)
    return f"http_{m.group(1) or m.group(2)}" if m else "error"


def tool_name(item: dict) -> str:
    """The name a tool item is counted under: its type, an MCP tool as `<server>.<tool>`."""
    if item.get("type") == "mcp_tool_call":
        return f"{item.get('server') or ''}.{item.get('tool') or ''}"
    return str(item.get("type") or "")


class EventReader:
    """One `--json` line at a time: the thread id, the final message, tool use, retries, the end."""

    def __init__(self) -> None:
        self.thread_id = ""
        self.saw_any = False
        self.messages: list[str] = []
        self.tool_uses: Counter = Counter()
        self.web_queries: list[str] = []
        self.usage: dict = {}
        self.completed = False
        self.failure = ""
        self.errors: list[str] = []  # item `error`s and `error` events past their retries
        self.api_retries = 0
        self.retry_errors: Counter = Counter()
        self.unread: Counter = Counter()

    @property
    def result_text(self) -> str:
        """The agent's last message: its answer."""
        return self.messages[-1] if self.messages else ""

    def feed(self, line: str) -> Stop | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except ValueError:
            return None
        if not isinstance(ev, dict):
            return None
        self.saw_any = True
        typ = str(ev.get("type") or "")
        if typ not in KNOWN_EVENTS:
            self.unread[typ] += 1
        elif typ == "thread.started":
            self.thread_id = str(ev.get("thread_id") or "")
        elif typ == "item.completed":
            self._item(ev.get("item") or {})
        elif typ == "error":
            message = str(ev.get("message") or "")
            retry = _RECONNECT_RE.match(message)
            if retry is None:
                self.errors.append(message)
                return None
            cause = _status_class(retry.group(3))
            self.api_retries += 1
            self.retry_errors[cause] += 1
            # A refused credential never heals by waiting: stop on the second one, as claude does.
            if _AUTH_RE.search(retry.group(3)) and self.retry_errors[cause] >= 2:
                self.failure = retry.group(3)
                return Stop.AUTH_FAILED
        elif typ == "turn.completed":
            self.completed = True
            self.usage = ev.get("usage") or {}
        elif typ == "turn.failed":
            self.failure = str((ev.get("error") or {}).get("message") or "")
        return None

    def _item(self, item: dict) -> None:
        kind = item.get("type")
        if kind == "agent_message":
            self.messages.append(str(item.get("text") or ""))
        elif kind == "error":
            self.errors.append(str(item.get("message") or ""))
        elif kind in TOOL_ITEMS:
            self.tool_uses[tool_name(item)] += 1
            web = web_target(item) if kind == "web_search" else {}
            if "web_query" in web:
                note_web_query(self.web_queries, web["web_query"])


def classify(reader: EventReader, exit_code: int | None) -> Stop:
    """One stop reason from what the events said: a failed turn by its message, else how the process ended."""
    if reader.completed:
        return Stop.COMPLETED
    text = reader.failure or "\n".join(reader.errors)
    if text:
        if RATE_LIMIT_RE.search(text):
            return Stop.RATE_LIMITED
        if _AUTH_RE.search(text):
            return Stop.AUTH_FAILED
        if _REFUSAL_RE.search(text):
            return Stop.REFUSED
        return Stop.API_ERROR
    if not reader.saw_any:
        return Stop.NO_OUTPUT if exit_code == 0 else Stop.LAUNCH_FAILED
    return Stop.ERROR if exit_code not in (0, None) else Stop.NO_OUTPUT


@dataclass
class Rollout:
    """What a session's rollout file adds to the events: per-call tokens, the model, account usage."""

    calls: list[CallUsage] = field(default_factory=list)
    model: str = ""
    cli_version: str = ""
    rate_limits: list[RateLimit] = field(default_factory=list)


def call_usage(u: dict, model: str) -> CallUsage:
    """One API call's tokens. Codex's `input_tokens` is the whole input, the cached and
    cache-written parts included; `CallUsage.input` is the rest."""
    total = int(u.get("input_tokens") or 0)
    read = int(u.get("cached_input_tokens") or 0)
    written = int(u.get("cache_write_input_tokens") or 0)
    return CallUsage(
        model=model,
        input=max(0, total - read - written),
        cache_read=read,
        cache_creation=written,
        output=int(u.get("output_tokens") or 0),
    )


def rate_limit(limits: dict) -> RateLimit | None:
    """A `token_count`'s `rate_limits` (a ChatGPT plan's windows) as a reading, or None when it has no window."""
    five: dict = {}
    week: dict = {}
    for key in ("primary", "secondary"):
        w = limits.get(key)
        if not isinstance(w, dict):
            continue
        minutes = w.get("window_minutes")
        if minutes == _FIVE_HOUR_MIN:
            five = w
        elif minutes == _SEVEN_DAY_MIN:
            week = w
    if not five and not week:
        return None

    def at(w: dict) -> str | None:
        ts = w.get("resets_at")
        return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds") if isinstance(ts, (int, float)) else None

    def pct(w: dict) -> float | None:
        v = w.get("used_percent")
        return round(float(v), 1) if isinstance(v, (int, float)) else None

    return RateLimit(
        observed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        status=str(limits.get("rate_limit_reached_type") or "allowed"),
        five_hour_pct=pct(five),
        five_hour_resets_at=at(five),
        seven_day_pct=pct(week),
        seven_day_resets_at=at(week),
    )


def find_rollout(codex_home: Path, thread_id: str) -> Path | None:
    """The rollout file of thread `thread_id` under `codex_home`, or None."""
    if not re.fullmatch(r"[0-9A-Za-z-]{1,64}", thread_id or ""):
        return None
    return next(iter(sorted((codex_home / "sessions").glob(f"*/*/*/rollout-*-{thread_id}.jsonl"))), None)


def read_rollout(path: Path, start: int = 0) -> Rollout:
    """Per-call tokens, the model and the plan's usage from one rollout file, from byte
    `start` on: a resumed session appends to the file its earlier turns are in."""
    out = Rollout()
    try:
        with open(path, "rb") as f:
            f.seek(start)
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        payload = ev.get("payload") if isinstance(ev, dict) else None
        if not isinstance(payload, dict):
            continue
        typ = ev.get("type")
        if typ == "session_meta":
            out.cli_version = str(payload.get("cli_version") or "")
        elif typ == "turn_context":
            out.model = str(payload.get("model") or out.model)
        elif typ == "event_msg" and payload.get("type") == "token_count":
            last = (payload.get("info") or {}).get("last_token_usage")
            if isinstance(last, dict):
                out.calls.append(call_usage(last, out.model))
            reading = rate_limit(payload.get("rate_limits") or {})
            if reading is not None:
                out.rate_limits.append(reading)
    return out


def normalize_event(e: dict) -> dict | list[dict]:
    """Map one `codex exec --json` event onto the monitor's renderable shapes (the ones
    `backends.claude.stream.normalize_event` produces), or `{"type": "skip"}`.

    An item's start opens its tool card and its completion closes it, matched by the
    item id; the agent's messages and reasoning arrive whole, on completion. A web
    search starts with no query: its completion names it, then ends the card.
    """
    typ = e.get("type")
    if typ == "item.started" or typ == "item.completed":
        item = e.get("item") or {}
        kind = item.get("type")
        call = str(item.get("id") or "")
        if typ == "item.completed" and kind == "agent_message":
            return {"type": "message_update", "ev": "text_delta", "delta": str(item.get("text") or "")}
        if typ == "item.completed" and kind == "reasoning":
            return {"type": "message_update", "ev": "thinking_delta", "delta": str(item.get("text") or "")}
        if typ == "item.completed" and kind == "error":
            return {"type": "notice", "text": str(item.get("message") or "")[:800]}
        if kind not in TOOL_ITEMS:
            return {"type": "skip"}
        if typ == "item.started":
            return _tool_start(item, call)
        end = {"type": "tool_execution_end", "tool": "", "out": _tool_output(item)[:4000], "err": _tool_failed(item), "call": call}
        return [_tool_start(item, call), end] if kind == "web_search" else end
    if typ == "error":
        message = str(e.get("message") or "")
        retry = _RECONNECT_RE.match(message)
        if retry is not None:
            return {"type": "auto_retry_start", "attempt": int(retry.group(1)), "err": retry.group(3)[:200]}
        return {"type": "notice", "text": message[:800]}
    if typ == "turn.failed":
        return {"type": "notice", "text": f"turn failed: {(e.get('error') or {}).get('message') or ''}"[:800]}
    if typ == "thread.started":
        return {"type": "notice", "text": f"session started: {e.get('thread_id') or ''}"[:800]}
    return {"type": "skip"}


def _tool_start(item: dict, call: str) -> dict:
    kind = item.get("type")
    start = {"type": "tool_execution_start", "tool": tool_name(item), "intent": "", "call": call}
    if kind == "command_execution":
        return {**start, "cmd": str(item.get("command") or "")[:800]}
    if kind == "file_change":
        paths = [f"{c.get('kind') or ''} {c.get('path') or ''}".strip() for c in item.get("changes") or [] if isinstance(c, dict)]
        return {**start, "cmd": "\n".join(paths)[:800]}
    if kind == "web_search":
        web = web_target(item)
        return {**start, "cmd": next(iter(web.values()), ""), **web}
    return {**start, "cmd": json.dumps(item.get("arguments") or {}, ensure_ascii=False)[:800]}


def web_target(item: dict) -> dict:
    """A web search item's query (`web_query`) or the page it opened (`web_fetch`), or {} while
    it has neither: codex fills them in when the search ends (`action`: search, open_page,
    find_in_page)."""
    action = item.get("action")
    if not isinstance(action, dict):
        action = {}
    if action.get("type") in ("open_page", "find_in_page") and action.get("url"):
        return {"web_fetch": str(action["url"])[:800]}
    query = str(action.get("query") or item.get("query") or "")[:800]
    return {"web_query": query} if query else {}


def _tool_output(item: dict) -> str:
    kind = item.get("type")
    if kind == "web_search":
        # One `{"title", "url"}` per page: the form the monitor reads a search's pages from.
        found = [r for r in item.get("results") or [] if isinstance(r, dict) and r.get("url")]
        return "\n".join(json.dumps({"title": str(r.get("title") or ""), "url": str(r["url"])}, ensure_ascii=False) for r in found)
    if kind == "command_execution":
        return str(item.get("aggregated_output") or "")
    if kind == "file_change":
        return str(item.get("status") or "")
    if kind == "mcp_tool_call":
        err = item.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        result = item.get("result")
        blocks = result.get("content") if isinstance(result, dict) else None
        if isinstance(blocks, list):
            return "\n".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _tool_failed(item: dict) -> bool:
    if item.get("status") == "failed" or item.get("error"):
        return True
    code = item.get("exit_code")
    return isinstance(code, int) and code != 0
