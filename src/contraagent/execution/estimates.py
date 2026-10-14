"""How long each kind of task usually takes, and the work that follows it, from recent runs and from this one.

The queue orders work by estimated path length, and past `deadline - slack` it
defers a task whose work cannot finish before the deadline, so it needs a
duration for every task. A kind's own history is the best guess available: the
median wall time of its completed rows (`estimate`). A kind with no history gets
no estimate, and the queue falls back to its own default.

A generator flow creates the work after a task from the task's result, so when
the task is queued its successors are not. `tail` estimates them: in each past
run, the tail of a task is the longest chain of wall times along its
successors, the tasks whose `after` or `created_from` (`plan.jsonl`) names it,
and theirs, after it (its own wall time excluded). A task's tail estimate is the
median over past tasks with the same tail key (`TailKey`): the flow path's
function names, the kind, and the passes of the loops around it, each capped at
`LOOP_CAP` (so pass 1 of a loop that usually takes three is told from its last
pass). A task's wall time is that of its key's last journal row.

Samples:

* only the `RECENT_RUNS` most recent runs of the runs directory are read (by
  the time their journal was last written): a model, a prompt and a flow
  change, and old runs stop describing the next one;
* a tail is sampled only from a complete chain: the task and every task after it
  completed, and the flow call that created each of them, and every flow call
  around it, returned. A chain cut short by a deferral, a failure, a refused
  input or a flow error would make the tail too short;
* in a run, every finished attempt (`observe_attempt`) adds to its kind's
  durations, and every flow call that returns (`flow_call_ended`) adds the tails
  of the tasks it created itself: the chain inside it and the flow calls it
  yielded, plus the current tail estimate of each last task of that chain (the
  work its parent does after it returns, not known yet). Samples from this run
  replace those of past runs for the same kind or tail key once there is one.
"""

from __future__ import annotations

import json
import statistics
import threading
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from contraagent import rundir
from contraagent.dispatch.task import Task, kind_name

#: What a tail is estimated for: (the flow path's function names, the kind, the passes of
#: the loops around it, outermost first, each capped at `LOOP_CAP`; None when not counted).
TailKey = tuple[tuple[str, ...], str, tuple[int | None, ...]]

#: Passes from this one on share a tail key: 1, 2, 3 and later.
LOOP_CAP = 3

#: How many of the most recent runs the history reads.
RECENT_RUNS = 10


def _capped(p: int | None, cap: int) -> int | None:
    return None if p is None else min(int(p), cap)


def tail_key(task: Task, cap: int = LOOP_CAP) -> TailKey:
    """The tail key of a task: its flow path's function names, its kind, and its loops' passes (capped)."""
    flow = task.origin.flow if task.origin is not None else ()
    passes = tuple(_capped(loop.pass_, cap) for f in flow for loop in f.loops)
    return tuple(f.function for f in flow), kind_name(task.kind), passes


def row_tail_key(row: dict, cap: int = LOOP_CAP) -> TailKey:
    """The tail key of a `plan.jsonl` row."""
    frames = row.get("flow") or ()
    passes = tuple(_capped(loop.get("pass"), cap) for f in frames for loop in f.get("loops") or ())
    return tuple(f.get("function", "") for f in frames), str(row.get("kind") or ""), passes


class JournalEstimates:
    """Median wall time per kind (a Python task's kind is its own name) and median tail per
    tail key, over the `recent` most recent runs of `runs_dir` and over this run as it goes.

    `observe_plan(row)`, `observe_attempt(row)` and `flow_call_ended(call_id, state)` take
    this run's `plan.jsonl` rows, journal rows and flow call ends as they are written (`Run`
    passes them). Safe from worker threads."""

    def __init__(self, runs_dir: str | Path = "runs", *, recent: int = RECENT_RUNS, loop_cap: int = LOOP_CAP) -> None:
        self.loop_cap = loop_cap
        samples: dict[str, list[float]] = {}
        tails: dict[TailKey, list[float]] = {}
        journals = recent_journals(runs_dir, recent)
        for run_dir in (p.parent for p in journals):
            journal = list(_rows(run_dir / rundir.JOURNAL))
            for e in journal:
                wall = float(e.get("wall_s") or 0)
                key = e.get("kind") or ""
                if key and wall > 0 and e.get("stop") == "completed":
                    samples.setdefault(key, []).append(wall)
            plan = list(_rows(run_dir / rundir.PLAN))
            calls = list(_rows(run_dir / rundir.FLOW_CALLS))
            for key, tail in run_tails(plan, journal, calls, loop_cap=loop_cap):
                tails.setdefault(key, []).append(tail)
        self._median = {k: statistics.median(v) for k, v in samples.items()}
        self._tail = {k: statistics.median(v) for k, v in tails.items()}
        # This run, as it goes.
        self._lock = threading.Lock()
        self._run_samples: dict[str, list[float]] = {}
        self._run_tails: dict[TailKey, list[float]] = {}
        self._plan: dict[str, dict] = {}  # by key: the first row
        self._last: dict[str, dict] = {}  # by key: the last journal row
        self._by_call: dict[str, list[str]] = {}  # flow call id -> the keys it created
        self._returned: set[str] = set()

    # --- what the queue and the graph ask ------------------------------------------

    def estimate(self, task: Task) -> float | None:
        """A task's expected wall time: the median of its kind's completed attempts in this
        run, else in the recent runs; None with no history."""
        kind = kind_name(task.kind)
        with self._lock:
            run = self._run_samples.get(kind)
            if run:
                return statistics.median(run)
        return self._median.get(kind)

    def tail(self, task: Task) -> float | None:
        """The expected wall time of the longest chain of work after `task`; None with no history."""
        return self._tail_of(tail_key(task, self.loop_cap))

    def _tail_of(self, key: TailKey) -> float | None:
        with self._lock:
            run = self._run_tails.get(key)
            if run:
                return statistics.median(run)
        return self._tail.get(key)

    # --- this run ------------------------------------------------------------------

    def observe_plan(self, row: dict) -> None:
        """A `plan.jsonl` row of this run: a task the queue accepted."""
        key = row.get("key")
        if not key:
            return
        with self._lock:
            if key not in self._plan:
                self._plan[key] = row
                self._by_call.setdefault(str(row.get("flow_call") or "0"), []).append(key)

    def observe_attempt(self, row: dict) -> None:
        """A journal row of this run: one finished attempt."""
        key = row.get("key")
        if not key:
            return
        wall = float(row.get("wall_s") or 0)
        kind = str(row.get("kind") or "")
        with self._lock:
            self._last[key] = row
            if kind and wall > 0 and row.get("stop") == "completed":
                self._run_samples.setdefault(kind, []).append(wall)

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
            for key, tail in samples:
                self._run_tails.setdefault(key, []).append(tail)


def run_tails(
    plan: list[dict],
    journal: list[dict],
    flow_calls: Iterable[dict] = (),
    *,
    loop_cap: int = LOOP_CAP,
    after_last: Callable[[dict], float] | None = None,
    only: set[str] | None = None,
) -> list[tuple[TailKey, float]]:
    """One run's tails: `(tail key, tail)` for each task of `plan` whose chain is complete.

    `plan`, `journal` and `flow_calls` are the rows of its `plan.jsonl`, `journal.jsonl`
    and `flow_calls.jsonl`. A chain is complete when the task and every task after it
    completed (their key's last journal row) and, when `flow_calls` is given, the flow
    call that created each, and every flow call around it, returned.

    `after_last(row)`: the tail counted after a task with no successor in `plan` (default
    0), and such a task is then not sampled itself. `only`: the keys to sample (default
    every key)."""
    nodes: dict[str, dict] = {}
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
    out: list[tuple[TailKey, float]] = []
    for k, r in nodes.items():
        if not complete.get(k) or (only is not None and k not in only):
            continue
        if after_last is not None and not successors[k]:
            continue
        out.append((row_tail_key(r, loop_cap), tail[k]))
    return out


def recent_journals(runs_dir: str | Path, recent: int = RECENT_RUNS) -> list[Path]:
    """The `journal.jsonl` of the `recent` runs of `runs_dir` written to last, oldest first."""
    return sorted(Path(runs_dir).glob(f"*/{rundir.JOURNAL}"), key=_mtime)[-recent:] if recent > 0 else []


def journal_rows(path: Path) -> Iterator[dict]:
    """The rows of a journal (any JSON lines file), skipping a line that does not parse."""
    return _rows(path)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _rows(path: Path) -> Iterator[dict]:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            yield row
