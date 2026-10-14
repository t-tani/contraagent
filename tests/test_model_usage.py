"""What each model was used for: every hop records its own tokens, cost and time, and the
monitor sums them per model (`Plan.models`)."""

import threading

from contraagent import AgentRunner, Backend, KindConfig, LaunchResult, Route, Router, Stop, Task, TaskAdapter
from contraagent.backends.launch import CallUsage
from contraagent.execution.journal import Journal
from contraagent.monitor.core import model_usage


class Agent(Backend):
    """Answers per model: `m1` is rate limited after spending, `m2` completes."""

    drivable_model_chain = False

    def __init__(self, name):
        super().__init__()
        self.name = self.binary = name
        self._lock = threading.Lock()

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        limited = launch.model == "m1"
        result = LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=Stop.RATE_LIMITED if limited else Stop.COMPLETED,
            ok=not limited,
            model=launch.model,
            wall_s=2.0 if limited else 5.0,
            cost_usd=0.01 if limited else 0.04,
        )
        size = 100 if limited else 1000
        result.usage.calls = [CallUsage(launch.model, size, 10 * size, size // 2, size // 10)]
        result.usage.output_total = size // 10
        return result


def test_each_hop_of_a_failover_keeps_its_own_spend(tmp_path):
    router = Router(Route("claude", "m1"), (Route("omp", "m2"),), probe_interval_s=900)
    runner = AgentRunner(
        {"claude": Agent("claude"), "omp": Agent("omp")},
        {"k": KindConfig(agent="claude", model="m1", max_turns=3, timeout_s=10)},
        run_dir=tmp_path,
        adapter=TaskAdapter(),
        routers={"k": router},
        cwd=tmp_path,
    )
    result = runner.run(Task("k", key="t"))
    assert result.ok
    first, second = result.hops
    assert (first["agent"], first["model"], second["agent"], second["model"]) == ("claude", "m1", "omp", "m2")
    assert first["usage"] == {"input": 100, "output": 10, "cache_read": 1000, "cache_creation": 50, "calls": 1}
    assert second["usage"] == {"input": 1000, "output": 100, "cache_read": 10000, "cache_creation": 500, "calls": 1}
    assert (first["cost_usd"], second["cost_usd"]) == (0.01, 0.04)

    journal = Journal(tmp_path / "journal.jsonl", tmp_path / "launches.jsonl", run_id="r", run_group="r", unit_of=lambda t: t.unit)
    row = journal.append(result).model_dump()
    assert row["usage"]["input"] == 1100  # the attempt holds both hops' tokens
    models = model_usage([row])
    assert [(m["agent"], m["model"]) for m in models] == [("claude", "m1"), ("omp", "m2")]
    assert [(m["sessions"], m["input"], m["cache_read"], m["output"], m["calls"]) for m in models] == [
        (1, 100, 1000, 10, 1),
        (1, 1000, 10000, 100, 1),
    ]
    assert [m["cost_usd"] for m in models] == [0.01, 0.04]
    assert [m["wall_s"] for m in models] == [2.0, 5.0]


def test_the_summary_is_in_first_use_order_and_leaves_python_rows_and_unlaunched_hops_out():
    def hop(agent, model, *, cost=None, wall=1.0, usage=None):
        return {"agent": agent, "model": model, "cost_usd": cost, "wall_s": wall, "usage": usage}

    rows = [
        {"executor": "agent", "agent": "omp", "hops": [hop("omp", "glm", wall=3.0, usage={"input": 5, "calls": 1})]},
        {"executor": "python", "agent": "", "hops": []},
        {"executor": "agent", "agent": "claude", "hops": [hop("claude", "haiku", cost=0.5, wall=2.0, usage={"output": 7, "calls": 2})]},
        {"executor": "agent", "agent": "omp", "hops": [hop("omp", "glm", cost=0.25, wall=1.0, usage={"input": 1, "calls": 1})]},
        # a row of one hop with no tokens of its own: the row's are the hop's
        {"executor": "agent", "agent": "claude", "hops": [{"model": "haiku", "wall_s": 1.0}], "usage": {"input": 9, "calls": 1}},
        # refused before a launch: no hop, nothing counted
        {"executor": "agent", "agent": "claude", "model": "haiku", "hops": []},
    ]
    models = model_usage(rows)
    assert [(m["agent"], m["model"]) for m in models] == [("omp", "glm"), ("claude", "haiku")]
    glm, haiku = models
    assert (glm["sessions"], glm["input"], glm["calls"], glm["cost_usd"], glm["wall_s"]) == (2, 6, 2, 0.25, 4.0)
    assert [haiku[k] for k in ("sessions", "input", "output", "calls", "cost_usd", "wall_s")] == [2, 9, 7, 3, 0.5, 3.0]
    assert model_usage([{"executor": "agent", "hops": [hop("claude", "x")]}])[0]["cost_usd"] is None  # no cost reported: none


def test_the_monitor_s_plan_carries_the_models(tmp_path):
    from pydantic import BaseModel

    from contraagent import Pipeline, PipelineConfig, agent_task
    from contraagent.monitor import Monitor
    from contraagent.monitor.api import Plan
    from contraagent.testing import StubAgent, writes

    class Note(BaseModel):
        note: str

    note = agent_task("note", instructions="x", output=Note, max_turns=3, timeout_s=60, agent="claude", model="haiku")
    stub = StubAgent({"note": writes({"note": "n"}, cost_usd=0.02)})
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path, backends=stub.backends(), cwd=tmp_path)
    report = pipeline.run(lambda: [note(u) for u in "ab"], run_id="r")
    assert report.ok, report.failed
    plan = Plan.model_validate(Monitor(tmp_path).plan("r"))
    [m] = plan.models
    assert (m.agent, m.model, m.sessions, m.cost_usd) == ("claude", "haiku", 2, 0.04)
