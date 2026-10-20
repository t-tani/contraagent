"""A claim capacity sized by the host (`PerTask`): free memory and usable cores."""

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from contraagent import ConfigError, PerTask, Pipeline, PipelineConfig, Task, TaskResult, python_task
from contraagent._internal.platform import processes
from contraagent._internal.routing.capacity import STARTUP_S, HostCapacity, sized
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def host(mem: list, cores: int = 64, clock=None) -> HostCapacity:
    """A host whose free memory is `mem[0]` MB (None: not reported)."""
    return HostCapacity(mem_available_mb=lambda: mem[0], cores=cores, clock=clock or Clock())


# --- reading the host ----------------------------------------------------------------


def test_the_host_reports_its_free_memory_and_cores():
    free = processes.mem_available_mb()
    assert free is not None and 0 < free
    assert processes.usable_cores() >= 1


# --- the capacity -----------------------------------------------------------------------


def test_the_holders_plus_as_many_more_as_the_free_memory_holds():
    mem, clock = [5000], Clock()
    index = host(mem, clock=clock).capacity(PerTask(memory_mb=1500))
    assert index.allowed(0) == 3
    assert index.allowed(2) == 5  # what runs is already out of the free memory
    mem[0], clock.now = 1000, clock.now + 1
    assert index.allowed(0) == 1  # nothing holds it: one starts, so the run goes on
    assert index.allowed(1) == 1
    mem[0], clock.now = -50, clock.now + 1
    assert index.allowed(2) == 2


def test_a_task_started_in_its_startup_counts_against_the_free_memory():
    mem, clock = [5000], Clock()
    room = host(mem, clock=clock)
    index, other = room.capacity(PerTask(memory_mb=1500)), room.capacity(PerTask(memory_mb=1000))
    index.started()
    other.started()  # every PerTask name of the queue shares the host
    assert room.free_mb() == 2500
    assert index.allowed(1) == 2
    clock.now += STARTUP_S
    assert room.free_mb() == 5000  # past their startup: MemAvailable shows them
    assert index.allowed(1) == 4


def test_cores_cap_the_name_and_memory_and_cores_both_hold():
    mem = [100_000]
    assert host(mem, cores=8).capacity(PerTask(cores=3)).allowed(0) == 2
    assert host(mem, cores=8).capacity(PerTask(memory_mb=1000, cores=1)).allowed(3) == 8
    assert host([2500], cores=8).capacity(PerTask(memory_mb=1000, cores=1)).allowed(3) == 5
    assert host(mem, cores=2).capacity(PerTask(cores=4)).allowed(0) == 1  # nothing holds it


def test_without_meminfo_memory_does_not_limit():
    assert host([None], cores=4).capacity(PerTask(memory_mb=1500, cores=2)).allowed(1) == 2
    assert host([None]).capacity(PerTask(memory_mb=1500)).allowed(7) > 1000


def test_one_reading_serves_a_pass():
    reads, clock = [], Clock()

    def read():
        reads.append(clock.now)
        return 4000

    room = HostCapacity(mem_available_mb=read, cores=4, clock=clock)
    room.free_mb()
    room.free_mb()
    clock.now += 1.0
    room.free_mb()
    assert len(reads) == 2


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
    """`b` waits while `a` runs and memory is short; memory frees with `a` still running,
    and the queue starts `b` without waiting for `a` to finish."""
    mem = [1000]
    runner = Holders(mem)
    q = WorkQueue(runner, max_concurrent=4, claim_capacity=sized({"index": PerTask(memory_mb=1000)}, host(mem, clock=time.monotonic)))
    q.add(Task("serve", key="a", claims=("index",)))
    q.add(Task("serve", key="b", claims=("index",)))
    q.run()
    assert runner.seen == ["memory frees", "b starts", "a saw b"]


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


_running: list[int] = [0, 0]  # now, most at once
_lock = threading.Lock()


@python_task(claims=["index"])
def serve(unit: str) -> int:
    with _lock:
        _running[0] += 1
        _running[1] = max(_running[1], _running[0])
    time.sleep(0.05)
    with _lock:
        _running[0] -= 1
    return 1


def test_a_run_sizes_a_per_task_capacity_by_the_host(tmp_path):
    async def flow():
        return await asyncio.gather(*[serve(u) for u in "abcd"])

    _running[:] = [0, 0]
    whole = PerTask(cores=processes.usable_cores())  # one task takes every core
    p = Pipeline(None, runs_dir=tmp_path, backends=StubAgent().backends(), log=lambda line: None, claim_capacity={"index": whole})
    assert p.run(flow).ok and _running[1] == 1
