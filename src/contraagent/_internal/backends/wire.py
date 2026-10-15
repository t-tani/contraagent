"""What every coding agent's wire reader shares.

A coding agent's wire is what it prints about a launch as it runs: one event per line
(`<agent>/wire.py` reads each one). Its reader is an `EventFold`: fed one line at a time
while the launch runs (`Backend.run`), or every line of a finished output at once
(`EventFold.read`), it folds the events into the facts of a `LaunchResult` (`result`).
The base keeps what every wire reports alike: whether anything was seen, the session id,
each tool call (a bounded sample of its arguments), web searches, the tokens and cost of
each API call, the context window, and the event types it does not know (`unread_events`).

`LimitsWatch` ends a launch on the budgets a coding agent cannot enforce itself
(`max_budget_usd`, `context_budget`, `max_turns`), from what the fold has read so far.
`tool_preview` is the one-line preview of a tool call the monitor shows.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Iterator
from typing import Self

from contraagent._internal.backends.launch import CallUsage, Launch, LaunchResult, Limits, Stop, Usage, note_web_query
from contraagent._internal.backends.refusal import Ending, Signals, classify_stop

_logger = logging.getLogger(__name__)
_warned: set[tuple[str, str]] = set()  # (agent, unread event type) already logged by this process

#: Arguments kept per tool (`LaunchResult.raw_result["tool_args"]`), and characters per sample.
TOOL_ARGS_MAX = 20
TOOL_ARG_CHARS = 500


def parse_line(raw: bytes | str) -> dict | None:
    """One wire line as an event: a JSON object, else None (blank, not JSON, not an object)."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    if not text.strip():
        return None
    try:
        ev = json.loads(text)
    except ValueError:
        return None
    return ev if isinstance(ev, dict) else None


def iter_jsonl(data: bytes) -> Iterator[dict]:
    """Every event of a finished output, in order (`parse_line` of each line)."""
    for raw in data.split(b"\n"):
        ev = parse_line(raw)
        if ev is not None:
            yield ev


def tokens(d: object, *keys: str) -> int:
    """The token counts `d` holds under `keys`, summed; 0 for one missing or empty.
    Raises ValueError or TypeError for one that is not a number."""
    if not isinstance(d, dict):
        return 0
    return sum(int(d.get(k) or 0) for k in keys)


def positive_int(v: object) -> int | None:
    """`v` when it is a whole number above 0 (a context window, as a wire or a catalogue lists
    it), else None."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def first_text(args: object, *keys: str) -> str:
    """The first of `keys` with a value in `args` (a tool call's input), as text; '' with none."""
    if not isinstance(args, dict):
        return ""
    return str(next((args[k] for k in keys if args.get(k)), "") or "")


def tool_preview(cmd: object, *, web_query: bool = False, web_fetch: bool = False) -> dict:
    """A tool call's one-line preview for the monitor (`cmd`, cut at 800 characters): also its
    query when it is a web search (`web_query`), its URL when it reads a web page (`web_fetch`)."""
    text = str(cmd or "")[:800]
    if web_query:
        return {"cmd": text, "web_query": text}
    if web_fetch:
        return {"cmd": text, "web_fetch": text}
    return {"cmd": text}


class EventFold:
    """Folds one coding agent's wire into a `LaunchResult`: the base of every wire's reader.

    A subclass reads its own events in `feed` (returning a `Stop` ends the launch there:
    a refused credential that will not heal by waiting), says how the launch ended in
    `ending`, and adds its own facts to the result in `result`.
    """

    #: The coding agent whose wire this is, in the warning about an unread event.
    agent: str = ""
    #: The event types this reader knows; another is counted in `unread_events`. None: every type.
    known_events: frozenset[str] | None = None
    #: How this wire words a refusal (`refusal.Signals`).
    signals: Signals = Signals()

    def __init__(self) -> None:
        self.saw_any = False
        self.session_id = ""
        self.tool_uses: Counter = Counter()
        self.tool_args: dict[str, list[str]] = {}
        self.web_queries: list[str] = []
        self.calls: list[CallUsage] = []
        self.cost: float | None = None
        self.unread: Counter = Counter()
        #: The model's context window, when the wire reports one.
        self.context_window: int | None = None

    # --- reading ------------------------------------------------------------

    def feed_line(self, raw: bytes | str) -> Stop | None:
        """One line of the wire as it arrives (`Backend.run`'s sink)."""
        ev = parse_line(raw)
        return self.feed(ev) if ev is not None else None

    def feed(self, ev: dict) -> Stop | None:
        """One event. A `Stop` ends the launch there."""
        raise NotImplementedError

    def read(self, data: bytes) -> Self:
        """Every line of a finished output, folded."""
        for ev in iter_jsonl(data):
            self.feed(ev)
        return self

    def unknown(self, typ: str) -> bool:
        """Whether event type `typ` is one this reader does not know; it is counted if so."""
        if self.known_events is None or typ in self.known_events:
            return False
        self.unread[typ or "<untyped>"] += 1
        return True

    def note_tool(self, name: str, args: object = None) -> None:
        """One tool call: counted, with a bounded sample of its arguments (what did 138 bash calls run?)."""
        if not name:
            return
        self.tool_uses[name] += 1
        buf = self.tool_args.setdefault(name, [])
        if not isinstance(args, dict) or len(buf) >= TOOL_ARGS_MAX:
            return
        try:
            buf.append(json.dumps(args, ensure_ascii=False)[:TOOL_ARG_CHARS])
        except (TypeError, ValueError):
            pass

    def note_web_query(self, query: object) -> None:
        note_web_query(self.web_queries, query)

    def add_call(self, call: CallUsage, cost: float | None = None) -> None:
        """One API call's tokens, and its cost (USD) when the wire reports one."""
        self.calls.append(call)
        if cost is not None:
            self.cost = (self.cost or 0.0) + cost

    # --- the end ------------------------------------------------------------

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """What this reader observed, for `classify_stop`."""
        return Ending(killed=killed, exit_code=exit_code, saw_any=self.saw_any)

    def stop(self, *, exit_code: int | None, killed: Stop | None) -> Stop:
        """How the launch ended (`refusal.classify_stop` over `ending`)."""
        return classify_stop(self.ending(exit_code=exit_code, killed=killed), self.signals)

    def usage(self) -> Usage:
        """The tokens of every API call; the output total their sum."""
        return Usage(calls=list(self.calls), output_total=sum(c.output for c in self.calls))

    def warn_unread(self) -> None:
        """Log each unread event type once per process."""
        for typ in sorted(t for t in self.unread if (self.agent, t) not in _warned):
            _warned.add((self.agent, typ))
            _logger.warning(
                f"[{self.agent}] event {typ!r} is not one this contraagent reads; a newer {self.agent}? (LaunchResult.unread_events)"
            )

    def launch_result(self, launch: Launch, agent: str, stop: Stop, *, exit_code: int | None, **fields) -> LaunchResult:
        """The `LaunchResult` with what every wire reports alike, and `fields` over it."""
        self.warn_unread()
        base = dict(
            label=launch.label,
            agent=agent,
            stop=stop,
            ok=stop is Stop.COMPLETED,
            exit_code=exit_code,
            model=launch.model,
            session_id=self.session_id,
            tool_uses=dict(self.tool_uses),
            web_queries=list(self.web_queries),
            usage=self.usage(),
            cost_usd=round(self.cost, 6) if self.cost is not None else None,
            raw_result={"tool_args": dict(self.tool_args)},
            unread_events=dict(self.unread),
            context_window=self.context_window,
        )
        return LaunchResult(**{**base, **fields})

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """How the launch ended, and everything read on the way."""
        stop = self.stop(exit_code=exit_code, killed=killed)
        return self.launch_result(launch, agent, stop, exit_code=exit_code)


class LimitsWatch:
    """Ends a launch on the budgets its coding agent cannot enforce itself, from what its
    reader (`fold`) has read so far: `context_budget` (one call's whole input past it),
    `max_budget_usd` (the cost so far past it), `max_turns` (more tool calls than it).
    `watched` names the `Limits` fields this agent leaves to the wrapper."""

    def __init__(self, limits: Limits, watched: frozenset[str], fold: EventFold):
        self.fold = fold
        self.context = limits.context_budget if "context_budget" in watched else None
        self.budget = limits.max_budget_usd if "max_budget_usd" in watched else None
        self.turns = limits.max_turns if "max_turns" in watched else None
        self._seen = 0  # calls already checked against the context budget

    def __call__(self) -> Stop | None:
        f = self.fold
        if self.context is not None:
            new, self._seen = f.calls[self._seen :], len(f.calls)
            if any(c.context > self.context for c in new):
                return Stop.CONTEXT
        if self.budget is not None and (f.cost or 0.0) > self.budget:
            return Stop.BUDGET
        if self.turns is not None and sum(f.tool_uses.values()) > self.turns:
            return Stop.MAX_TURNS
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
