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
`event_msg` `token_count` per API call (`last_token_usage`, the model's
`model_context_window`, `rate_limits`) and a `turn_context` with the model. `read_rollout` takes those.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from contraagent.backends.launch import CallUsage, Launch, LaunchResult, Stop
from contraagent.backends.refusal import FAILED_STOPS, Ending, Signals
from contraagent.backends.wire import EventFold, positive_int, tokens
from contraagent.dispatch.records import QuotaReading
from contraagent.runs.times import iso_of, now_iso

#: How Codex words a refusal: for usage or rate (ChatGPT plan limits, a provider's 429), a
#: refused credential, a safety refusal. A process that printed nothing failed to start
#: when it exited nonzero. A launch that dies before its first event prints only on stderr.
SIGNALS = Signals(
    quota=re.compile(r"\b429\b|usage limit|rate.?limit|quota|too many requests", re.I),
    auth=re.compile(r"\b(401|403)\b|unauthori[sz]ed|forbidden|invalid api key|not logged in", re.I),
    refusal=re.compile(r"cyber_policy|safety|refus", re.I),
    status=re.compile(r"\bstatus (\d{3})\b|\"code\":\s*\"?(\d{3})"),
    silence_is_startup=True,
    stderr_stops=FAILED_STOPS | {Stop.LAUNCH_FAILED},
)
#: `Reconnecting... 2/5 (unexpected status 401 Unauthorized: ...)`
_RECONNECT_RE = re.compile(r"^Reconnecting\.\.\. (\d+)/(\d+) \((.*)\)$", re.S)
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
    status = SIGNALS.status_in(message)
    return f"http_{status}" if status is not None else "error"


def tool_name(item: dict) -> str:
    """The name a tool item is counted under: its type, an MCP tool as `<server>.<tool>`."""
    if item.get("type") == "mcp_tool_call":
        return f"{item.get('server') or ''}.{item.get('tool') or ''}"
    return str(item.get("type") or "")


class EventReader(EventFold):
    """One `--json` event at a time: the thread id, the final message, tool use, retries,
    the end. The rollout file (`rollout`, read after the launch) adds per-call tokens,
    the model, its context window and the plan's usage."""

    agent = "codex"
    known_events = KNOWN_EVENTS
    signals = SIGNALS

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []
        #: The turn's summed `usage` (`turn.completed`).
        self.turn_usage: dict = {}
        self.completed = False
        self.failure = ""
        self.errors: list[str] = []  # item `error`s and `error` events past their retries
        self.api_retries = 0
        self.retry_errors: dict[str, int] = {}
        #: The session's rollout file, read after the launch (`CodexBackend.exchange`).
        self.rollout: Rollout | None = None

    @property
    def thread_id(self) -> str:
        return self.session_id

    @property
    def result_text(self) -> str:
        """The agent's last message: its answer."""
        return self.messages[-1] if self.messages else ""

    def feed(self, ev: dict) -> Stop | None:
        self.saw_any = True
        typ = str(ev.get("type") or "")
        if self.unknown(typ):
            return None
        if typ == "thread.started":
            self.session_id = str(ev.get("thread_id") or "")
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
            self.retry_errors[cause] = self.retry_errors.get(cause, 0) + 1
            # A refused credential never heals by waiting: stop on the second one, as claude does.
            if SIGNALS.auth_in(retry.group(3)) and self.retry_errors[cause] >= 2:
                self.failure = retry.group(3)
                return Stop.AUTH_FAILED
        elif typ == "turn.completed":
            self.completed = True
            self.turn_usage = ev.get("usage") or {}
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
                self.note_web_query(web["web_query"])

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """A completed turn is done whatever else was said; else a failed turn by its
        message, else how the process ended."""
        error = "" if self.completed else self.failure or "\n".join(self.errors)
        return Ending(killed=killed, exit_code=exit_code, saw_any=self.saw_any, error=error, failed=bool(error), completed=self.completed)

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        stop = self.stop(exit_code=exit_code, killed=killed)
        rollout = self.rollout
        calls = rollout.calls if rollout is not None else []
        if not calls and self.turn_usage:
            # No rollout to read: the turn's sum stands in as one call.
            calls = [call_usage(self.turn_usage, launch.model)]
        model = (rollout.model if rollout is not None else "") or launch.model
        # The turn's own sum counts a resumed thread's earlier turns too; the calls do not.
        self.calls = [CallUsage(c.model or model, c.input, c.cache_read, c.cache_creation, c.output) for c in calls]
        text = self.result_text
        structured = None
        if launch.json_schema is not None and stop is Stop.COMPLETED:
            try:
                structured = json.loads(text)
            except ValueError:
                structured = None
        return self.launch_result(
            launch,
            agent,
            stop,
            exit_code=exit_code,
            cli_version=rollout.cli_version if rollout is not None else "",
            result_text=text,
            structured_output=structured,
            quota=list(rollout.quota) if rollout is not None else [],
            init_model=model,
            context_window=rollout.context_window if rollout is not None else None,
            api_retries=self.api_retries,
            retry_errors=dict(self.retry_errors),
            stderr_tail=self.failure,
            raw_result={"usage": self.turn_usage} if self.turn_usage else {},
        )


@dataclass
class Rollout:
    """What a session's rollout file adds to the events: per-call tokens, the model, its
    context window, account usage."""

    calls: list[CallUsage] = field(default_factory=list)
    model: str = ""
    #: The model's context window (`token_count`'s `model_context_window`, the latest); None without one.
    context_window: int | None = None
    cli_version: str = ""
    quota: list[QuotaReading] = field(default_factory=list)


def call_usage(u: dict, model: str) -> CallUsage:
    """One API call's tokens. Codex's `input_tokens` is the whole input, the cached and
    cache-written parts included; `CallUsage.input` is the rest."""
    total, read, written = tokens(u, "input_tokens"), tokens(u, "cached_input_tokens"), tokens(u, "cache_write_input_tokens")
    return CallUsage(
        model=model, input=max(0, total - read - written), cache_read=read, cache_creation=written, output=tokens(u, "output_tokens")
    )


def quota_reading(limits: dict) -> QuotaReading | None:
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
        return iso_of(ts) if isinstance(ts, (int, float)) else None

    def pct(w: dict) -> float | None:
        v = w.get("used_percent")
        return round(float(v), 1) if isinstance(v, (int, float)) else None

    return QuotaReading(
        observed_at=now_iso(),
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
    """Per-call tokens, the model, its context window and the plan's usage from one rollout file, from byte
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
            info = payload.get("info") or {}
            last = info.get("last_token_usage")
            if isinstance(last, dict):
                out.calls.append(call_usage(last, out.model))
            window = positive_int(info.get("model_context_window"))
            if window is not None:
                out.context_window = window
            reading = quota_reading(payload.get("rate_limits") or {})
            if reading is not None:
                out.quota.append(reading)
    return out


def normalize_event(e: dict) -> dict | list[dict]:
    """Map one `codex exec --json` event onto the monitor's renderable shapes (the ones
    `backends.claude.wire.normalize_event` produces), or `{"type": "skip"}`.

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
