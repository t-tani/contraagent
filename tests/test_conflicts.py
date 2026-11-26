"""Tasks that conflict never run at once (`WorkQueue`, a runner's `conflicts`): a pipeline's
tasks conflict when they work in one directory and their `changes` patterns may cover the
same files, also when the flow creates them after an `await`, where `contraagent check`
does not see them. `lean/Contraagent/Dispatch/Queue/Conflicts.lean` proves it of the
queue's description."""

import asyncio
import threading
import time
from types import SimpleNamespace

from pydantic import BaseModel

from contraagent import Pipeline, Task, TaskResult, agent_task, python_task
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


class Note(BaseModel):
    unit: str


class Peak:
    """How many launches run at once, and the most that ever did."""

    def __init__(self) -> None:
        self.now = self.most = 0
        self._lock = threading.Lock()

    def reply(self, launch):
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
        time.sleep(0.2)  # long enough for the queue to start a second task beside it, if it would
        with self._lock:
            self.now -= 1
        return {"unit": launch.unit}


def run(tmp_path, changes, units=("a", "b", "c"), cwd_of=None) -> int:
    """Run one `work` task per unit, each created after an awaited Python task, and give the
    most that ran at once."""
    peak = Peak()
    work = agent_task("work", instructions="Work.", output=Note, changes=changes, max_turns=3, timeout_s=30)

    @python_task
    def prepare(unit: str) -> Note:
        return Note(unit=unit)

    async def one(unit: str):
        await prepare(unit)
        call = work.options(cwd=cwd_of(unit)) if cwd_of is not None else work
        await call(unit)

    async def flow():
        await asyncio.gather(*(one(u) for u in units))

    stub = StubAgent({"work": peak.reply})
    report = Pipeline(None, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, log=lambda line: None).run(flow)
    assert report.ok, [r.reason for r in report.failed]
    return peak.most


def test_tasks_whose_changes_may_cover_the_same_files_run_one_at_a_time(tmp_path):
    assert run(tmp_path, ["corpus"]) == 1


def test_a_directory_above_another_s_files_is_a_conflict(tmp_path):
    seen: list[set[str]] = []
    running: set[str] = set()
    lock = threading.Lock()

    def reply(launch):
        with lock:
            running.add(launch.key)
            seen.append(set(running))
        time.sleep(0.2)
        with lock:
            running.discard(launch.key)
        return {"unit": launch.unit}

    whole = agent_task("whole", instructions="Work.", output=Note, changes=["corpus"], max_turns=3, timeout_s=30)
    part = agent_task("part", instructions="Work.", output=Note, changes=["corpus/{unit}/*.txt"], max_turns=3, timeout_s=30)

    async def flow():
        await asyncio.gather(whole("all"), part("a"), part("b"))

    stub = StubAgent({"whole": reply, "part": reply})
    report = Pipeline(None, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, log=lambda line: None).run(flow)
    assert report.ok
    assert not any("whole-all" in now and len(now) > 1 for now in seen)  # `whole` ran alone
    assert {"part-a", "part-b"} in seen  # the two parts ran together


def test_a_unit_s_own_directory_lets_the_tasks_run_together(tmp_path):
    assert run(tmp_path, ["corpus/{unit}"]) == 3


def test_tasks_in_directories_of_their_own_run_together(tmp_path):
    for unit in "abc":
        (tmp_path / unit).mkdir()
    assert run(tmp_path, ["corpus"], cwd_of=lambda unit: tmp_path / unit) == 3


def test_tasks_that_declare_no_changes_run_together(tmp_path):
    assert run(tmp_path, ()) == 3


class Runner:
    """A runner whose tasks of keys `x*` conflict with each other; each run takes as long as
    the test lets it."""

    def __init__(self) -> None:
        self.running: set[str] = set()
        self.together: list[set[str]] = []
        self.gates: dict[str, threading.Event] = {}

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def conflicts(self, task: Task, other: Task) -> bool:
        return task.key.startswith("x") and other.key.startswith("x")

    def run(self, task: Task) -> TaskResult:
        self.running.add(task.key)
        self.together.append(set(self.running))
        self.gates.setdefault(task.key, threading.Event()).wait(timeout=0.05)
        self.running.discard(task.key)
        return TaskResult(task=task, ok=True, stop="completed")


def test_the_queue_starts_no_task_beside_one_it_conflicts_with():
    runner = Runner()
    q = WorkQueue(runner, max_concurrent=4)
    q.extend([Task("k", key=key) for key in ("x1", "x2", "y1", "x3", "y2")])
    q.run()
    assert all(len({k for k in seen if k.startswith("x")}) <= 1 for seen in runner.together)
    assert any(len(seen) > 1 for seen in runner.together)  # the others ran beside them
    assert {r.task.key for r in q.results} == {"x1", "x2", "y1", "x3", "y2"}


def test_the_starvation_guard_holds_back_a_task_the_overdue_one_conflicts_with():
    """When the first task of the order that cannot start is overdue, a later task may not
    start that it conflicts with: once what holds it back ends, it starts, not the later task."""
    q = WorkQueue(Runner(), max_concurrent=4)
    assert q._takes(Task("k", key="x2"), Task("k", key="x1"))
    assert not q._takes(Task("k", key="y1"), Task("k", key="x1"))


def test_patterns_the_test_finds_apart_cover_no_file_of_both(tmp_path):
    """What two patterns cover is what `scan` finds under the working directory, the files a
    failed attempt's rollback may remove. Whenever two patterns cover a file of both,
    `may_overlap` finds them: the Lean description proves it of its reading of the patterns
    (`mayOverlap_sound`), and this holds it to `Path.glob`'s."""
    import random

    from contraagent._internal.execution.changes import may_overlap, scan

    names = ["f", "ba", "a.md", "b.md", "x[", ".hidden"]  # no name of a directory: a file and a directory of one name cannot both be
    rng = random.Random(20261126)
    for top in ("a", "b", "ab", "docs"):
        for sub in ("", "a", "b", "ab"):
            for name in rng.sample(names, 3):
                path = tmp_path / top / sub / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
    segments = ["a", "b", "ab", "a*", "*b", "*", "?", "a?", "[ab]", "[!a]*", "x[", "**", "*.md", "docs", ".*"]

    def pattern() -> str:
        return "/".join(rng.choice(segments) for _ in range(rng.randint(1, 3)))

    covered: dict[str, set[str]] = {}
    checked = found = 0
    for _ in range(400):
        pa, pb = pattern(), pattern()
        for p in (pa, pb):
            if p not in covered:
                covered[p] = set(scan(tmp_path, [p])[0])
        if covered[pa] & covered[pb]:
            found += 1
            assert may_overlap([pa], [pb]) is not None, (pa, pb, sorted(covered[pa] & covered[pb])[:3])
        checked += 1
    assert found > 50 and checked - found > 50  # both answers came up
