"""`WorkQueue`: every accepted task finishes once through `follow_up`, without recursion."""

import sys
import threading
import time
from types import SimpleNamespace

from contraagent import Task, TaskResult
from contraagent.engine import Deferral, WorkQueue


class Runner:
    """Runs a task by sleeping `params["sleep"]` and ending with `params["stop"]`."""

    def __init__(self) -> None:
        self.launched: list[str] = []
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        with self._lock:
            self.launched.append(task.key)
        time.sleep(task.params.get("sleep", 0.0))
        stop = task.params.get("stop", "completed")
        return TaskResult(task=task, ok=stop == "completed", stop=stop)


def test_a_long_chain_of_skipped_follow_ups_drains_without_recursion():
    n = 2000
    seen: list[str] = []

    def follow_up(result: TaskResult) -> list[Task]:
        seen.append(result.stop)
        i = int(result.task.key.removeprefix("k")) + 1
        return [Task("step", key=f"k{i}")] if i < n else []

    runner = Runner()
    q = WorkQueue(runner, follow_up=follow_up, skip=lambda task: True)
    assert q.add(Task("step", key="k0"))
    assert len(seen) == n and set(seen) == {"skipped"}  # finished inside add(), at depth 1
    summary = q.run()
    assert runner.launched == [] and summary["by_stop"] == {"skipped": n}


def test_skip_is_asked_per_task():
    runner = Runner()
    q = WorkQueue(runner, skip=lambda task: task.kind == "old")
    q.add(Task("old", key="a"))
    q.add(Task("new", key="b"))
    q.run()
    assert runner.launched == ["b"] and {r.task.key: r.stop for r in q.results} == {"a": "skipped", "b": "completed"}


def test_a_deferred_task_finishes_through_follow_up_and_its_follow_up_still_runs():
    seen: list[tuple[str, str]] = []

    def follow_up(result: TaskResult) -> list[Task]:
        seen.append((result.task.key, result.stop))
        if result.stop == "deferred":
            return [Task("report", key="report")]
        return []

    events: list[tuple[str, str]] = []
    runner = Runner()
    q = WorkQueue(
        runner,
        follow_up=follow_up,
        deadline_s=0.001,
        finishing_kinds=("report",),
        on_event=lambda event, task, **f: events.append((event, task.key)),
    )
    q.add(Task("scan", key="scan"))
    time.sleep(0.01)
    summary = q.run()
    assert seen == [("scan", "deferred"), ("report", "completed")]
    assert runner.launched == ["report"]
    assert summary["deferred"] == ["scan"] and summary["finished"] == 1  # a deferral is not a finished launch
    assert ("deferred", "scan") in events and ("end", "scan") not in events


def test_follow_ups_of_a_deferral_with_no_way_to_launch_are_deferred_too():
    seen: list[tuple[str, str]] = []

    def follow_up(result: TaskResult) -> list[Task]:
        seen.append((result.task.key, result.stop))
        return [Task("b", key="b", after=("never",))] if result.task.key == "a" else []

    q = WorkQueue(Runner(), follow_up=follow_up)
    q.add(Task("a", key="a", after=("never",)))
    q.run()
    assert seen == [("a", "deferred"), ("b", "deferred")]


def test_a_refused_follow_up_task_finishes_as_duplicate_key():
    seen: list[TaskResult] = []
    retry = Task("slow", key="slow")

    def follow_up(result: TaskResult) -> list[Task]:
        seen.append(result)
        return [retry] if result.task.key == "fast" else []

    runner = Runner()
    q = WorkQueue(runner, follow_up=follow_up)
    q.add(Task("slow", key="slow", params={"sleep": 0.3}))
    q.add(Task("fast", key="fast"))
    q.run()
    by_task = {id(r.task): r.stop for r in seen}
    assert by_task[id(retry)] == "duplicate_key"
    assert sorted(runner.launched) == ["fast", "slow"]
    assert {r.task.key: r.stop for r in q.results} == {"fast": "completed", "slow": "completed"}


def test_tail_s_counts_toward_the_critical_path():
    starts: list[str] = []
    q = WorkQueue(
        Runner(),
        max_concurrent=1,
        on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None,
    )
    q.add(Task("a", key="plain", estimate_s=10))
    q.add(Task("a", key="tail", estimate_s=10, tail_s=100))
    q.run()
    assert starts == ["tail", "plain"]


def test_a_dependency_chain_longer_than_the_recursion_limit_is_ordered():
    # A low limit for the run proves the same as a chain of thousands: nothing recurses per task.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(250)
    try:
        n = sys.getrecursionlimit() + 200
        q = WorkQueue(Runner(), max_concurrent=1)
        for i in range(n):
            q.add(Task("step", key=f"k{i}", after=(f"k{i - 1}",) if i else ()))
        summary = q.run()
    finally:
        sys.setrecursionlimit(limit)
    assert summary["ok"] == n


def test_a_finishing_task_after_a_deferred_one_launches():
    runner = Runner()
    q = WorkQueue(runner, deadline_s=0.001, finishing_kinds=("report",))
    q.add(Task("scan", key="scan"))
    q.add(Task("report", key="report", after=("scan",)))
    time.sleep(0.01)
    summary = q.run()
    assert runner.launched == ["report"] and summary["deferred"] == ["scan"]


# --- the order, the starvation guard and the deadline -------------------------------------


def starts_of(**options):
    """A queue over `Runner` and the keys in the order they start."""
    starts: list[str] = []
    q = WorkQueue(Runner(), on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None, **options)
    return q, starts


def two_claims(overdue_s: float) -> list[str]:
    """`head` claims two names; `heavy` is held when it arrives, `net` is free, and three
    lower `fillers` claim `net` (the P1 probe of the scheduling report)."""
    q, starts = starts_of(max_concurrent=4, overdue_s=overdue_s)
    q.add(Task("hold", key="hold", claims=("heavy",), params={"sleep": 0.2}))
    q.add(Task("kick", key="kick"))

    def follow_up(res: TaskResult) -> list[Task]:
        if res.task.key != "kick":
            return []
        head = Task("head", key="head", claims=("heavy", "net"), estimate_s=5000)
        return [head] + [Task("filler", key=f"net{i}", claims=("net",), estimate_s=10, params={"sleep": 0.1}) for i in range(3)]

    q.follow_up = follow_up
    q.run()
    return starts


def test_an_overdue_task_that_claims_two_names_keeps_the_free_one():
    assert two_claims(overdue_s=0.0) == ["hold", "kick", "head", "net0", "net1", "net2"]
    starts = two_claims(overdue_s=60.0)  # not overdue yet: greedy, the fillers take `net`
    assert starts.index("net0") < starts.index("head")


def test_an_overdue_task_of_a_capped_kind_keeps_its_place_under_the_cap():
    class Capped(Runner):
        def config(self, task: Task) -> SimpleNamespace:
            return SimpleNamespace(max_concurrent=1 if task.kind == "k" else None)

    starts: list[str] = []
    q = WorkQueue(
        Capped(),
        overdue_s=0.0,
        on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None,
    )
    q.add(Task("hold", key="hold", claims=("heavy",), estimate_s=5000, params={"sleep": 0.2}))
    q.add(Task("k", key="head", claims=("heavy",), estimate_s=1000))
    q.add(Task("k", key="low", estimate_s=1))
    q.run()
    assert starts == ["hold", "head", "low"]  # `low` would have taken kind k's one place


def test_a_task_waiting_longer_than_overdue_s_goes_before_a_higher_level_one():
    def order(overdue_s: float) -> list[str]:
        q, starts = starts_of(max_concurrent=1, overdue_s=overdue_s)
        q.add(Task("a", key="first", estimate_s=100, params={"sleep": 0.1}))
        q.add(Task("a", key="low", estimate_s=1))
        q.follow_up = lambda res: [Task("a", key="high", estimate_s=1000)] if res.task.key == "first" else []
        q.run()
        return starts

    assert order(overdue_s=0.05) == ["first", "low", "high"]
    assert order(overdue_s=60.0) == ["first", "high", "low"]


def test_before_the_deadline_less_slack_the_longest_work_goes_first_and_after_it_the_shortest():
    def order(slack_s: float) -> list[str]:
        q, starts = starts_of(max_concurrent=1, deadline_s=60, slack_s=slack_s, finishing_kinds=("report",))
        q.add(Task("a", key="big", estimate_s=3, tail_s=2))
        q.add(Task("a", key="small", estimate_s=1))
        q.add(Task("report", key="report", estimate_s=2))
        q.run()
        return starts

    assert order(slack_s=0.0) == ["big", "report", "small"]
    assert order(slack_s=60.0) == ["report", "small", "big"]  # finishing kinds first only from there


def test_a_task_that_cannot_finish_before_the_deadline_is_deferred_at_once():
    seen: list[tuple[str, str, str]] = []
    q, starts = starts_of(max_concurrent=2, deadline_s=30, slack_s=30, finishing_kinds=("report",))
    q.follow_up = lambda res: seen.append((res.task.key, res.stop, res.reason)) or []
    q.add(Task("a", key="huge", estimate_s=20, tail_s=100))
    q.add(Task("a", key="fits", estimate_s=1))
    q.add(Task("a", key="unknown"))  # no estimate: never deferred for the deadline
    q.add(Task("report", key="report", estimate_s=100))  # a finishing task has the grace window
    summary = q.run()
    assert sorted(starts) == ["fits", "report", "unknown"]
    assert summary["deferred"] == ["huge"]
    [(_, stop, reason)] = [s for s in seen if s[0] == "huge"]
    assert stop == "deferred" and reason.startswith("cannot finish before the deadline: needs 120s")


def test_priority_breaks_a_tie_of_bottom_levels_highest_first():
    q, starts = starts_of(max_concurrent=1)
    q.add(Task("a", key="plain", estimate_s=10))
    q.add(Task("a", key="low", estimate_s=10, priority=-1))
    q.add(Task("a", key="high", estimate_s=10, priority=2.5))
    q.add(Task("a", key="mid", estimate_s=10, priority=1))
    q.add(Task("a", key="plain2", estimate_s=10))
    q.run()
    assert starts == ["high", "mid", "plain", "plain2", "low"]  # equal priorities: arrival


def test_priority_does_not_beat_a_larger_bottom_level():
    q, starts = starts_of(max_concurrent=1)
    q.add(Task("a", key="urgent", estimate_s=1, priority=100))
    q.add(Task("a", key="long", estimate_s=10))
    q.add(Task("a", key="tail", estimate_s=1, tail_s=5))
    q.run()
    assert starts == ["long", "tail", "urgent"]


def test_priority_does_not_beat_an_overdue_task():
    def order(overdue_s: float) -> list[str]:
        q, starts = starts_of(max_concurrent=1, overdue_s=overdue_s)
        q.add(Task("a", key="first", estimate_s=100, params={"sleep": 0.1}))
        q.add(Task("a", key="waiting", estimate_s=1))
        q.follow_up = lambda res: [Task("a", key="late", estimate_s=1, priority=10)] if res.task.key == "first" else []
        q.run()
        return starts

    assert order(overdue_s=0.05) == ["first", "waiting", "late"]
    assert order(overdue_s=60.0) == ["first", "late", "waiting"]


def test_in_a_time_box_endgame_priority_breaks_ties_only():
    q, starts = starts_of(max_concurrent=1, deadline_s=60, slack_s=60, finishing_kinds=("report",))
    q.add(Task("a", key="plain", estimate_s=1))
    q.add(Task("a", key="high", estimate_s=1, priority=5))
    q.add(Task("a", key="short", estimate_s=0.5, priority=-3))
    q.add(Task("report", key="report", estimate_s=2))
    q.run()
    assert starts == ["report", "short", "high", "plain"]


class Spans(Runner):
    """Records each task's (start, end) to tell which ran at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.spans: dict[str, tuple[float, float]] = {}

    def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        res = super().run(task)
        self.spans[task.key] = (t0, time.monotonic())
        return res

    def overlap(self, a: str, b: str) -> bool:
        (a0, a1), (b0, b1) = self.spans[a], self.spans[b]
        return a0 < b1 and b0 < a1


# --- what a deferral queues during a pass ---------------------------------------------


class Resting(Runner):
    """A runner whose credential rests for `resting` kinds: it defers them (`deferral`)."""

    def __init__(self, resting: set[str]) -> None:
        super().__init__()
        self.resting = resting

    def deferral(self, task: Task) -> Deferral | None:
        return Deferral("personal rests", {"cause": "rest"}) if task.kind in self.resting else None


def finishes_after(deferred_key: str, *follow: Task):
    """A follow-up that answers `deferred_key`'s deferral with `follow`; `seen`: how each task ended."""
    seen: dict[str, str] = {}

    def follow_up(res: TaskResult) -> list[Task]:
        seen[res.task.key] = res.stop
        return list(follow) if res.task.key == deferred_key and res.stop == "deferred" else []

    return follow_up, seen


def test_a_task_a_rest_s_follow_up_queues_launches():
    """The H1 shape: a rest defers the only task, nothing runs, and its follow-up queues a
    finishing Python task in the same pass. It launches (it was deferred as never queued)."""
    runner = Resting({"write"})
    follow_up, seen = finishes_after("write", Task("lint_check", key="lint_check"))
    q = WorkQueue(runner, follow_up=follow_up, finishing_kinds=("lint_check",))
    q.add(Task("write", key="write"))
    summary = q.run()
    assert runner.launched == ["lint_check"]
    assert seen == {"write": "deferred", "lint_check": "completed"}
    assert summary["deferred"] == ["write"]


def test_a_task_queued_after_a_late_deferral_or_a_closed_box_launches():
    # Late: its bottom level does not fit in the time left.
    runner = Runner()
    follow_up, seen = finishes_after("huge", Task("report", key="report"))
    q = WorkQueue(runner, follow_up=follow_up, deadline_s=30, slack_s=30, finishing_kinds=("report",))
    q.add(Task("a", key="huge", estimate_s=100))
    q.run()
    assert runner.launched == ["report"] and seen["huge"] == "deferred"
    # Closed: past the deadline, only the finishing kinds launch.
    runner = Runner()
    follow_up, seen = finishes_after("scan", Task("report", key="report"))
    q = WorkQueue(runner, follow_up=follow_up, deadline_s=0.001, finishing_kinds=("report",))
    q.add(Task("scan", key="scan"))
    time.sleep(0.01)
    q.run()
    assert runner.launched == ["report"] and seen["scan"] == "deferred"


def test_a_dependency_that_never_comes_still_ends_deferred():
    seen: dict[str, str] = {}
    q = WorkQueue(Runner(), follow_up=lambda res: seen.update({res.task.key: res.stop}) or [])
    q.add(Task("b", key="b", after=("never",)))
    summary = q.run()
    assert seen == {"b": "deferred"} and summary["deferred"] == ["b"]
