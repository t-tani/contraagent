"""A claim capacity sized by the host (`PerTask`): free memory, what each task takes, and
usable cores."""

import asyncio
import os
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from contraagent import ConfigError, PerTask, Pipeline, PipelineConfig, Task, TaskResult, python_task
from contraagent._internal.execution import run as run_module
from contraagent._internal.platform import processes
from contraagent._internal.routing.capacity import HostCapacity, sized, task_usage_mb
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


def host(mem: list, cores: int = 64, usage: dict | None = None) -> HostCapacity:
    """A host whose free memory is `mem[0]` MB (None: not reported), where the processes of
    each running task take `usage[key]` MB (none: nothing found)."""
    taken = usage if usage is not None else {}
    return HostCapacity(
        mem_available_mb=lambda: mem[0],
        usage_mb=lambda keys: {k: taken[k] for k in keys if k in taken},
        cores=cores,
    )


# --- reading the host ----------------------------------------------------------------


def test_the_host_reports_its_free_memory_and_cores():
    free = processes.mem_available_mb()
    assert free is not None and 0 < free
    assert processes.usable_cores() >= 1


def test_the_host_reports_what_a_child_holds_and_its_variables():
    env = {**os.environ, "CONTRAAGENT_TASK": "t1", "CONTRAAGENT_RUN": "r1"}
    code = "import sys; print('ready', flush=True); sys.stdin.read()"
    with subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env) as child:
        assert child.stdin is not None and child.stdout is not None
        try:
            assert child.stdout.readline() == "ready\n"  # it runs its own program
            seen = {p.pid: p for p in processes.descendants("CONTRAAGENT_")}
            assert child.pid in seen and seen[child.pid].ppid == os.getpid()
            assert seen[child.pid].own_mb >= 0
            if sys.platform != "darwin":  # macOS shows no other process's environment
                assert seen[child.pid].env == {"CONTRAAGENT_TASK": "t1", "CONTRAAGENT_RUN": "r1"}
                assert set(task_usage_mb(["t1"], run="r1")) == {"t1"}
        finally:
            child.stdin.close()


def test_a_process_counts_for_the_task_it_or_its_parent_names(monkeypatch):
    me = os.getpid()
    tele = "claude -p TELEMETRY run=r1 kind=k unit=- key=t2 role=-"
    procs = [
        processes.Descendant(10, me, "claude -p", {"CONTRAAGENT_RUN": "r1", "CONTRAAGENT_TASK": "t1"}, 300),
        processes.Descendant(11, 10, "index-server", {}, 1200),  # its variables not shown: its parent's task
        processes.Descendant(12, 11, "worker", {}, 100),
        processes.Descendant(20, me, tele, {}, 250),  # no variables shown: its telemetry line
        processes.Descendant(30, me, "claude -p", {"CONTRAAGENT_RUN": "r0", "CONTRAAGENT_TASK": "t1"}, 999),  # another run's
        processes.Descendant(40, me, "python helper.py", {}, 500),  # no task named: other work
    ]
    monkeypatch.setattr(processes, "descendants", lambda prefix: procs)
    assert task_usage_mb(["t1", "t2", "t3"], run="r1") == {"t1": 1600, "t2": 250}
    assert task_usage_mb([], run="r1") == {}


# --- the capacity -----------------------------------------------------------------------


def test_as_many_start_as_the_baseline_holds_while_none_runs():
    mem = [5000]
    room = host(mem)
    index = room.capacity(PerTask(memory_mb=1500))
    assert index.allowed(0) == 3
    mem[0] = 1000
    room.refresh()
    assert index.allowed(0) == 1  # nothing holds it: one starts, so the run goes on


def test_one_reading_serves_each_time_the_queue_starts_tasks():
    reads: list[int] = []

    def free() -> int:
        reads.append(1)
        return 4000

    room = HostCapacity(mem_available_mb=free, usage_mb=lambda keys: {}, cores=4)
    index = room.capacity(PerTask(memory_mb=1000))
    index.allowed(0)
    index.allowed(0)
    assert len(reads) == 1
    room.refresh()
    index.allowed(0)
    assert len(reads) == 2


def test_a_task_that_takes_its_memory_late_holds_it_until_it_ends():
    mem, usage = [5000], {}
    room = host(mem, usage=usage)
    index = room.capacity(PerTask(memory_mb=1500))
    index.allowed(0)
    index.started("a")
    index.started("b")
    room.refresh()  # neither has taken its memory yet, however long it has run
    assert index.allowed(2) == 3  # 3000 of the 5000 held
    usage["a"], mem[0] = 1500, 3500  # `a` takes it at last
    room.refresh()
    assert index.allowed(2) == 3
    index.ended("a")
    mem[0] = 5000
    room.refresh()
    assert index.allowed(1) == 3  # its hold ended with it


def test_a_task_that_took_its_memory_is_counted_once():
    mem, usage = [5000], {}
    room = host(mem, usage=usage)
    index = room.capacity(PerTask(memory_mb=1500))
    index.allowed(0)
    index.started("a")
    usage["a"], mem[0] = 1500, 3500
    room.refresh()
    assert index.allowed(1) == 3  # 1500 held of the 5000; the 3500 free holds two more


def test_a_task_that_takes_more_than_it_declared_holds_what_it_takes():
    mem, usage = [5000], {}
    room = host(mem, usage=usage)
    index = room.capacity(PerTask(memory_mb=1500))
    index.allowed(0)
    index.started("a")
    usage["a"], mem[0] = 3000, 2000
    room.refresh()
    assert index.allowed(1) == 2  # 3000 held: room for one more


def test_memory_other_work_takes_and_gives_back_counts():
    mem, usage = [5000], {"a": 500}
    room = host(mem, usage=usage)
    index = room.capacity(PerTask(memory_mb=1500))
    index.allowed(0)
    index.started("a")
    mem[0] = 1000  # other work took 3500 since the baseline; `a` has 1000 still to take
    room.refresh()
    assert index.allowed(1) == 1
    mem[0] = 3500  # it gave back 2500
    room.refresh()
    assert index.allowed(1) == 2


def test_a_burst_of_starts_on_one_reading_counts_each_new_one():
    """Other work took 2000 after the baseline: the declarations alone would let two more
    start beside `a`; the free memory, less what `a` and each one started on this reading
    will take, lets one."""
    mem = [5000]
    room = host(mem)
    index = room.capacity(PerTask(memory_mb=1500))
    index.allowed(0)
    index.started("a")
    mem[0] = 3000  # `a` has taken nothing yet
    room.refresh()
    assert index.allowed(1) == 2
    index.started("b")  # the same reading: `b` counts as held and not yet taken
    assert index.allowed(2) == 2
    index.ended("a")
    index.ended("b")
    room.refresh()
    assert room.tasks == {} and index.allowed(0) == 2  # none runs: the baseline is read again


def test_a_task_with_two_per_task_names_holds_both_and_counts_its_usage_once():
    mem, usage = [6000], {}
    room = host(mem, usage=usage)
    index, db = room.capacity(PerTask(memory_mb=1500)), room.capacity(PerTask(memory_mb=1000))
    index.allowed(0)
    index.started("t")
    db.started("t")  # one task that needs both
    usage["t"], mem[0] = 2500, 3500
    room.refresh()
    assert room.tasks == {"t": [2500, 2]}
    assert db.allowed(0) == 3  # 2500 held of the 6000, its 2500 taken counted once
    index.ended("t")
    assert room.tasks == {"t": [1000, 1]}
    db.ended("t")
    assert room.tasks == {}


def test_the_baseline_is_read_while_none_runs_and_only_then():
    mem = [5000]
    room = host(mem)
    index = room.capacity(PerTask(memory_mb=1000))
    index.allowed(0)
    index.started("a")
    mem[0] = 9000
    room.refresh()
    assert index.allowed(1) == 5 and room.baseline_mb == 5000
    index.ended("a")
    room.refresh()
    assert index.allowed(0) == 9 and room.baseline_mb == 9000


def test_a_cores_only_task_reads_the_baseline_before_it_starts():
    mem = [5000]
    room = host(mem)
    room.capacity(PerTask(cores=1)).started("a")
    mem[0] = 100
    room.refresh()
    assert room.baseline_mb == 5000
    assert room.capacity(PerTask(memory_mb=1000)).allowed(0) == 1


def test_cores_cap_the_name_and_memory_and_cores_both_hold():
    mem = [100_000]
    assert host(mem, cores=8).capacity(PerTask(cores=3)).allowed(0) == 2
    assert host(mem, cores=8).capacity(PerTask(memory_mb=1000, cores=1)).allowed(3) == 8
    assert host([2500], cores=8).capacity(PerTask(memory_mb=1000, cores=1)).allowed(3) == 5
    assert host(mem, cores=2).capacity(PerTask(cores=4)).allowed(0) == 1  # nothing holds it


def test_without_meminfo_memory_does_not_limit():
    assert host([None], cores=4).capacity(PerTask(memory_mb=1500, cores=2)).allowed(1) == 2
    assert host([None]).capacity(PerTask(memory_mb=1500)).allowed(7) > 1000


def test_numbers_stay_numbers():
    assert sized({"a": 2, "b:*": 0}) == {"a": 2, "b:*": 0}


# --- in the queue ------------------------------------------------------------------------


class Holders:
    """Runs `a`, which frees memory and then waits for `b` to start; records what happened
    in order."""

    def __init__(self, mem: list) -> None:
        self.mem = mem
        self.seen: list[str] = []
        self.b_started = threading.Event()
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def note(self, what: str) -> None:
        with self._lock:
            self.seen.append(what)

    def run(self, task: Task) -> TaskResult:
        if task.key == "a":
            with self._lock:
                self.mem[0] = 3000
                self.seen.append("memory frees")
            if self.b_started.wait(timeout=30):
                self.note("a saw b")
        else:
            self.note("b starts")
            self.b_started.set()
        return TaskResult(task=task, ok=True, stop="completed")


def test_the_queue_starts_a_holder_once_memory_frees_while_the_others_still_run():
    """`b` waits while `a` runs and other work holds the memory; that memory frees with `a`
    still running, and the queue starts `b` without waiting for `a` to finish."""
    idle, busy = 3000, [500]  # free while nothing runs; while `a` runs
    runner = Holders(busy)
    room = HostCapacity(mem_available_mb=lambda: busy[0] if room.tasks else idle, usage_mb=lambda keys: {}, cores=64)
    q = WorkQueue(runner, max_concurrent=4, claim_capacity=sized({"index": PerTask(memory_mb=1000)}, room))
    q.add(Task("serve", key="a", claims=("index",)))
    q.add(Task("serve", key="b", claims=("index",)))
    q.run()
    assert runner.seen == ["memory frees", "b starts", "a saw b"]
    assert room.tasks == {}  # the queue told it of each end


def test_a_pattern_sizes_each_name_on_its_own_and_the_guard_sees_room():
    q = WorkQueue(Holders([0]), claim_capacity=sized({"index:*": PerTask(memory_mb=1000)}, host([0])))
    q._held = {"index:a": 1}
    assert q.capacity("index:a") == 1
    assert q.capacity("index:b") == 1  # its own capacity: nothing holds it
    assert not q._free(Task("serve", key="c", claims=("index:a",)))
    assert q._possible(Task("serve", key="c", claims=("index:a",)))  # alone, it could start


# --- declared ---------------------------------------------------------------------------


def test_per_task_takes_one_or_both_positive_numbers():
    assert PerTask(cores=1) == PerTask(memory_mb=None, cores=1)
    with pytest.raises(ConfigError, match="give memory_mb, cores, or both"):
        PerTask()
    with pytest.raises(ConfigError, match="memory_mb = 0 is not a positive integer"):
        PerTask(memory_mb=0)
    with pytest.raises(ConfigError, match="cores = 1.5"):
        PerTask(cores=1.5)  # type: ignore[arg-type]


def test_the_config_holds_a_per_task_capacity_as_a_table(tmp_path):
    config = PipelineConfig({"defaults": {"claim_capacity": {"index": {"memory_mb": 1500, "cores": 1}, "topic:*": 2}}})
    assert config.claim_capacity() == {"index": PerTask(memory_mb=1500, cores=1), "topic:*": 2}
    errors: list[str] = []
    PipelineConfig({"defaults": {"claim_capacity": {"a": {"memory": 1}, "b": {}, "c": {"cores": 0}}}}).claim_capacity(errors)
    assert "'a' has unknown keys 'memory' (did you mean memory_mb?)" in errors[0]
    assert errors[1].endswith("'b': give memory_mb, cores, or both")
    assert errors[2].endswith("'c': cores = 0 is not a positive integer")
    p = Pipeline(config, runs_dir=tmp_path, backends=StubAgent().backends(), claim_capacity={"index": PerTask(cores=2)})
    assert p.queue_options["claim_capacity"]["index"] == PerTask(cores=2)
    with pytest.raises(ConfigError, match=r"Pipeline\(claim_capacity=\) 'index' = 1.5"):
        Pipeline(config, runs_dir=tmp_path, backends=StubAgent().backends(), claim_capacity={"index": 1.5})


@python_task(claims=["index"])
def serve(unit: str) -> int:
    return 1


def test_a_run_sizes_a_per_task_capacity_by_the_host(tmp_path, monkeypatch):
    """The run's queue holds the `PerTask` entry as this host's capacity, and tells it of
    every start and end."""
    made: list[dict] = []

    def keep(claim_capacity, host=None):
        made.append(sized(claim_capacity, host))
        return made[-1]

    monkeypatch.setattr(run_module, "sized", keep)

    async def flow():
        return await asyncio.gather(*[serve(u) for u in "abcd"])

    whole = PerTask(cores=processes.usable_cores())  # one task takes every core
    p = Pipeline(None, runs_dir=tmp_path, backends=StubAgent().backends(), log=lambda line: None, claim_capacity={"index": whole})
    assert p.run(flow).ok
    index = made[0]["index"]
    assert index.allowed(1) == 1  # one at a time
    assert index.host.tasks == {} and index.host.baseline_mb is not None  # each start had its end
