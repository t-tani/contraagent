"""How long each kind of task usually takes, and the work that follows it, from recent runs and from this one.

The queue orders work by estimated path length, and past `deadline - slack` it
defers a task unlikely to finish before the deadline, so it needs a duration for
every task and, near a deadline, how likely its work fits in the time left. A
kind's own history is the best guess available. The samples are kept, not only
their median: the order takes the median (`estimate`, `tail`), and a deadline
takes the share of samples that fit (`finish_chance`). A kind with no history
gets no estimate, and the queue falls back to its own default.

The order keeps the median, a point: a bottom level adds estimates along a path,
and only their relative size matters to the order. The median is not pulled by
the heavy tail of agent durations (one launch in twenty may take five times the
usual time), where a mean or a high quantile would rank a kind by its rare long
launches. A deadline needs more than a point (3Sigma, EuroSys 2018: planning with
the whole distribution misses fewer deadlines than a point estimate does): with
the median, about half of the tasks deferred would have fit.

An async flow creates the work after a task from the task's result, so when
the task is queued its successors are not. `tail` estimates them: in each past
run, the tail of a task is the longest chain of wall times along its
successors, the tasks whose `after` or `created_from` (`plan.jsonl`) names it,
and theirs, after it (its own wall time excluded). A task's tail estimate is the
median over past tasks with the same tail key (`TailKey`): the flow path's
function names, the kind, and the passes of the loops around it, each capped at
`LOOP_CAP` (so pass 1 of a loop that usually takes three is told from its last
pass). A task's wall time is that of its key's last journal row.

`finish_chance(task, within_s, after_s)` is the share of samples that end within
`within_s`: each sample of the task's tail key is a past task's own wall time plus
the longer of its tail and `after_s` (the known work after the task, which the
queue measures along the tasks already queued after it). A tail key with no
sample takes its kind's wall times, plus `after_s` or the task's `tail_s`. With
neither, there is no chance to give (None).

Samples:

* only the `RECENT_RUNS` most recent runs of the runs directory are read (by
  the time their journal was last written): a model, a prompt and a flow
  change, and old runs stop describing the next one;
* each kind and each tail key keeps its `SAMPLES` most recent samples, from the
  recent runs and, apart, from this run: enough to tell a chance of 0.2 from
  one of 0.5 (a share of 100 samples is within 0.1 of the true chance, two
  standard errors), and few enough that a pass of the queue reads them all;
* a tail is sampled only from a complete chain: the task and every task after it
  completed, and the flow call that created each of them, and every flow call
  around it, returned. A chain cut short by a deferral, a failure, a refused
  input or a flow error would make the tail too short;
* in a run, every finished attempt (`observe_attempt`) adds to its kind's
  durations, and every flow call that returns (`flow_call_ended`) adds the tails
  of the tasks it created itself: the chain inside it and the flow calls it
  created, plus the current tail estimate of each last task of that chain (the
  work its parent does after it returns, not known yet). Samples from this run
  replace those of past runs for the same kind or tail key once there is one.
"""

from __future__ import annotations

import statistics
import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contraagent._internal.dispatch.task import Task, kind_name
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import iter_rows, last_line, parse_rows
from contraagent._internal.runs.source import DirectorySource
from contraagent._internal.runs.times import parse_iso

#: What a tail is estimated for: (the flow path's function names, the kind, the passes of
#: the loops around it, outermost first, each capped at `LOOP_CAP`; None when not counted).
TailKey = tuple[tuple[str, ...], str, tuple[int | None, ...]]

#: Passes from this one on share a tail key: 1, 2, 3 and later.
LOOP_CAP = 3

#: How many of the most recent runs the history reads.
RECENT_RUNS = 10

#: How many samples each kind and each tail key keeps, the most recent: from the recent
#: runs, and apart from them, from this run.
SAMPLES = 100


def _capped(p: int | None, cap: int) -> int | None:
    return None if p is None else min(int(p), cap)


def tail_key(task: Task, cap: int = LOOP_CAP) -> TailKey:
    """The tail key of a task: its flow path's function names, its kind, and its loops' passes (capped)."""
    flow = task.origin.flow if task.origin is not None else ()
    passes = tuple(_capped(loop.pass_, cap) for f in flow for loop in f.loops)
    return tuple(f.function for f in flow), kind_name(task.kind), passes


def row_tail_key(row: dict[str, Any], cap: int = LOOP_CAP) -> TailKey:
    """The tail key of a `plan.jsonl` row."""
    frames = row.get("flow") or ()
    passes = tuple(_capped(loop.get("pass"), cap) for f in frames for loop in f.get("loops") or ())
    return tuple(f.get("function", "") for f in frames), str(row.get("kind") or ""), passes


class JournalEstimates:
    """Wall times per kind (a Python task's kind is its own name) and tails per tail key,
    over the `recent` most recent runs of `runs_dir` and over this run as it goes: their
    medians (`estimate`, `tail`), and the chance that a task's work fits in a time
    (`finish_chance`).

    `observe_plan(row)`, `observe_attempt(row)` and `flow_call_ended(call_id, state)` take
    this run's `plan.jsonl` rows, journal rows and flow call ends as they are written (`Run`
    passes them). Safe from worker threads."""

    def __init__(self, runs_dir: str | Path = "runs", *, recent: int = RECENT_RUNS, loop_cap: int = LOOP_CAP) -> None:
        self.loop_cap = loop_cap
        # Past runs, oldest first, so each bounded deque keeps the most recent samples.
        self._walls: dict[str, deque[float]] = {}
        self._pairs: dict[TailKey, deque[tuple[float, float]]] = {}  # (own wall time, tail)
        source = DirectorySource(runs_dir)
        for run in recent_runs(source, recent):
            journal = parse_rows(source.lines(run, layout.JOURNAL)[0])
            for e in journal:
                wall = float(e.get("wall_s") or 0)
                key = e.get("kind") or ""
                if key and wall > 0 and e.get("stop") == "completed":
                    self._walls.setdefault(key, deque(maxlen=SAMPLES)).append(wall)
            plan = parse_rows(source.lines(run, layout.PLAN)[0])
            calls = parse_rows(source.lines(run, layout.FLOW_CALLS)[0])
            for key, own, tail in run_tails(plan, journal, calls, loop_cap=loop_cap):
                self._pairs.setdefault(key, deque(maxlen=SAMPLES)).append((own, tail))
        self._median = {k: statistics.median(v) for k, v in self._walls.items()}
        self._tail = {k: statistics.median(t for _, t in v) for k, v in self._pairs.items()}
        # This run, as it goes: its samples replace the past runs' for a kind or a tail key
        # once there is one.
        self._lock = threading.Lock()
        self._run_walls: dict[str, deque[float]] = {}
        self._run_pairs: dict[TailKey, deque[tuple[float, float]]] = {}
        self._plan: dict[str, dict[str, Any]] = {}  # by key: the first row
        self._last: dict[str, dict[str, Any]] = {}  # by key: the last journal row
        self._by_call: dict[str, list[str]] = {}  # flow call id -> the keys it created
        self._returned: set[str] = set()

    # --- what the queue and the graph ask ------------------------------------------

    def estimate(self, task: Task) -> float | None:
        """A task's expected wall time: the median of its kind's completed attempts in this
        run, else in the recent runs; None with no history."""
        kind = kind_name(task.kind)
        with self._lock:
            run = self._run_walls.get(kind)
            if run:
                return statistics.median(run)
        return self._median.get(kind)

    def tail(self, task: Task) -> float | None:
        """The expected wall time of the longest chain of work after `task`; None with no history."""
        return self._tail_of(tail_key(task, self.loop_cap))

    def _tail_of(self, key: TailKey) -> float | None:
        with self._lock:
            run = self._run_pairs.get(key)
            if run:
                return statistics.median(t for _, t in run)
        return self._tail.get(key)

    def finish_chance(self, task: Task, within_s: float, after_s: float = 0.0) -> float | None:
        """The chance that `task` and the work after it end within `within_s` seconds of its
        start: the share of its samples that do, each a past task's own wall time plus the
        longer of its tail and `after_s`, the known work after `task` (the module
        docstring). None with no sample of its tail key or its kind."""
        key, kind = tail_key(task, self.loop_cap), kind_name(task.kind)
        with self._lock:
            pairs = list(self._run_pairs.get(key) or self._pairs.get(key) or ())
            walls = list(self._run_walls.get(kind) or self._walls.get(kind) or ())
        if pairs:
            needs = [own + max(tail, after_s) for own, tail in pairs]
        elif walls:
            after = max(after_s, task.tail_s or 0.0)
            needs = [wall + after for wall in walls]
        else:
            return None
        return sum(1 for need in needs if need <= within_s) / len(needs)

    # --- this run ------------------------------------------------------------------

    def observe_plan(self, row: dict[str, Any]) -> None:
        """A `plan.jsonl` row of this run: a task the queue accepted."""
        key = row.get("key")
        if not key:
            return
        with self._lock:
            if key not in self._plan:
                self._plan[key] = row
                self._by_call.setdefault(str(row.get("flow_call") or "0"), []).append(key)

    def observe_attempt(self, row: dict[str, Any]) -> None:
        """A journal row of this run: one finished attempt."""
        key = row.get("key")
        if not key:
            return
        wall = float(row.get("wall_s") or 0)
        kind = str(row.get("kind") or "")
        with self._lock:
            self._last[key] = row
            if kind and wall > 0 and row.get("stop") == "completed":
                self._run_walls.setdefault(kind, deque(maxlen=SAMPLES)).append(wall)

    def flow_call_ended(self, call_id: str, state: str) -> None:
        """A flow call of this run ended. One that returned adds a tail sample for each
        task it created itself that has work after it inside it."""
        if state != "returned":
            return
        with self._lock:
            self._returned.add(call_id)
            inside = [k for c, keys in self._by_call.items() if c == call_id or c.startswith(call_id + ".") for k in keys]
            plan = [self._plan[k] for k in inside]
            journal = [self._last[k] for k in inside if k in self._last]
            own = {k for k in inside if str(self._plan[k].get("flow_call") or "0") == call_id}
            returned = [c for c in self._returned if c == call_id or c.startswith(call_id + ".")]
        parts = call_id.split(".")
        around = [".".join(parts[:i]) for i in range(1, len(parts))]  # still running: what they do next is `after_last`
        calls = [{"id": c, "event": "end", "state": "returned"} for c in [*around, *returned]]
        samples = run_tails(
            plan,
            journal,
            calls,
            loop_cap=self.loop_cap,
            after_last=lambda row: self._tail_of(row_tail_key(row, self.loop_cap)) or 0.0,
            only=own,
        )
        with self._lock:
            for key, own, tail in samples:
                self._run_pairs.setdefault(key, deque(maxlen=SAMPLES)).append((own, tail))


def run_tails(
    plan: list[dict[str, Any]],
    journal: list[dict[str, Any]],
    flow_calls: Iterable[dict[str, Any]] = (),
    *,
    loop_cap: int = LOOP_CAP,
    after_last: Callable[[dict[str, Any]], float] | None = None,
    only: set[str] | None = None,
) -> list[tuple[TailKey, float, float]]:
    """One run's tails: `(tail key, wall time, tail)` for each task of `plan` whose chain is
    complete, the wall time its own.

    `plan`, `journal` and `flow_calls` are the rows of its `plan.jsonl`, `journal.jsonl`
    and `flow_calls.jsonl`. A chain is complete when the task and every task after it
    completed (their key's last journal row) and, when `flow_calls` is given, the flow
    call that created each, and every flow call around it, returned.

    `after_last(row)`: the tail counted after a task with no successor in `plan` (default
    0), and such a task is then not sampled itself. `only`: the keys to sample (default
    every key)."""
    nodes: dict[str, dict[str, Any]] = {}
    for r in plan:
        if r.get("key"):
            nodes.setdefault(r["key"], r)  # the first row per key, as the monitor reads it
    last = {r["key"]: r for r in journal if r.get("key")}
    wall = {k: float(last[k].get("wall_s") or 0) if k in last else 0.0 for k in nodes}
    ended = {str(r.get("id")): r.get("state") for r in flow_calls if r.get("event") == "end"}

    def call_returned(call: str) -> bool:
        parts = call.split(".")
        return all(ended.get(".".join(parts[: i + 1])) == "returned" for i in range(len(parts)))

    whole = {
        k: last.get(k, {}).get("stop") == "completed" and (not ended or call_returned(str(r.get("flow_call") or "0")))
        for k, r in nodes.items()
    }
    successors: dict[str, set[str]] = {k: set() for k in nodes}
    for k, r in nodes.items():
        for before in {*(r.get("after") or ()), *(r.get("created_from") or ())}:
            if before in successors and before != k:
                successors[before].add(k)
    tail: dict[str, float] = {}
    complete: dict[str, bool] = {}
    for k in nodes:  # depth first from an explicit stack: a chain of any length costs no stack
        path: list[tuple[str, Iterator[str]]] = [(k, iter(successors[k]))] if k not in tail else []
        on_path = {k}
        while path:
            node, todo = path[-1]
            nxt = next((s for s in todo if s not in tail and s not in on_path), None)  # on the path: a cycle, cut
            if nxt is not None:
                path.append((nxt, iter(successors[nxt])))
                on_path.add(nxt)
                continue
            after = successors[node]
            if after:
                tail[node] = max(wall[s] + tail.get(s, 0.0) for s in after)
            else:
                tail[node] = after_last(nodes[node]) if after_last is not None else 0.0
            complete[node] = whole[node] and all(complete.get(s, False) for s in after)
            on_path.discard(node)
            path.pop()
    out: list[tuple[TailKey, float, float]] = []
    for k, r in nodes.items():
        if not complete.get(k) or (only is not None and k not in only):
            continue
        if after_last is not None and not successors[k]:
            continue
        out.append((row_tail_key(r, loop_cap), wall[k], tail[k]))
    return out


def recent_runs(source: DirectorySource, recent: int = RECENT_RUNS) -> list[str]:
    """The `recent` runs of `source` whose journal was written to last, oldest first: by
    the time (`ts`) of its last row, which a copy of the runs directory keeps, and by the
    journal's modification time when that row has none."""
    if recent <= 0:
        return []
    written: list[tuple[datetime, str]] = []
    for run in source.runs():
        st = source.stat(run, layout.JOURNAL)
        if st is None:
            continue
        try:
            line = last_line(source.path(run, layout.JOURNAL))
        except OSError:
            line = None
        row = next(iter_rows([line]), {}) if line is not None else {}
        at = parse_iso(row.get("ts")) or datetime.fromtimestamp(st.mtime_ns / 1e9, tz=UTC)
        written.append((at, run))
    return [run for _, run in sorted(written)[-recent:]]
