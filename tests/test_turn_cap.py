"""A launch that reaches its turn cap (`max_turns`): its session goes on in a continuation
round (`max_continuations`), the task moves to the next hop, and a fresh attempt gets more
turns (`max_turns_growth`) or none."""

import threading

import pytest

from contraagent import ConfigError, Pipeline, PipelineConfig, Task, agent_task
from contraagent.backends import Backend, LaunchResult, Stop
from contraagent.config import KindConfig, Route
from contraagent.engine import AgentRunner, RetryingRunner, Router, TaskAdapter
from contraagent.testing import StubAgent


class Capped(Backend):
    """A coding agent whose session needs `turns` turns in all: a round with fewer under its
    cap stops on `max_turns`, and a resumed round goes on from the turns made before it."""

    drivable_model_chain = False

    def __init__(self, name="claude", turns=5):
        super().__init__()
        self.name, self.binary, self.turns = name, name, turns
        self.seen: list[tuple[str, int, str]] = []  # (model, max_turns, prompt) per round
        self.launches = []
        self._made: dict[str, int] = {}  # turns made so far, by session
        self._lock = threading.Lock()

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        cap = launch.limits.max_turns or 0
        with self._lock:
            self.seen.append((launch.model, cap, launch.prompt))
            self.launches.append(launch)
            session = launch.resume or f"s{len(self.seen)}"
            made = self._made.get(session, 0)
            turns = min(cap, self.turns - made)
            self._made[session] = made + turns
        done = made + turns >= self.turns
        stop = Stop.COMPLETED if done else Stop.MAX_TURNS
        return LaunchResult(
            label=launch.label, agent=self.name, stop=stop, ok=done, model=launch.model, session_id=session, num_turns=turns, wall_s=0.1
        )


def runner(tmp_path, agent, router=None, **rc):
    cfg = {"k": KindConfig(agent=agent.name, model="m1", max_turns=2, timeout_s=10, retry_backoff_base=0.0, **rc)}
    routers = {"k": router} if router is not None else {}
    return AgentRunner({agent.name: agent}, cfg, run_dir=tmp_path, adapter=TaskAdapter(), routers=routers, cwd=tmp_path)


def chain(*models):
    return Router(Route("claude", models[0]), tuple(Route("claude", m) for m in models[1:]))


def test_a_continuation_round_goes_on_in_the_same_session_with_the_whole_budget_again(tmp_path):
    agent = Capped(turns=5)
    res = runner(tmp_path, agent, max_continuations=2).run(Task("k", key="t"))
    assert res.ok and res.rounds == 3 and res.launch_result.continuations == 2 and res.launch_result.num_turns == 5
    assert [cap for _, cap, _ in agent.seen] == [2, 2, 2]
    assert "turn limit" in agent.seen[1][2] and "turn limit" in agent.seen[2][2]
    assert len(res.hops) == 1 and res.hops[0].num_turns == 5


def test_a_launch_out_of_continuations_moves_to_the_next_hop(tmp_path):
    agent = Capped(turns=5)
    res = runner(tmp_path, agent, chain("m1", "m2"), max_continuations=1).run(Task("k", key="t"))
    # Each hop is a session of its own, with its continuation; neither makes the five turns.
    assert res.stop == "max_turns" and [m for m, _, _ in agent.seen] == ["m1", "m1", "m2", "m2"]
    assert [h.num_turns for h in res.hops] == [4, 4]
    first = res.hops[0]
    assert (first.stop, first.num_turns, first.max_turns) == ("max_turns", 4, 2)
    assert "max_turns on hop 1/2 claude/m1 (4 turns in 2 rounds, max_turns 2)" in res.reason


def test_without_continuations_the_turn_cap_ends_the_launch(tmp_path):
    agent = Capped(turns=5)
    res = runner(tmp_path, agent).run(Task("k", key="t"))
    assert res.stop == "max_turns" and len(agent.seen) == 1 and res.reason == "2 turns, max_turns 2"


def test_each_fresh_attempt_multiplies_the_turns_by_the_growth(tmp_path):
    agent = Capped(turns=5)
    res = RetryingRunner(runner(tmp_path, agent, retries=2, max_turns_growth=1.5)).run(Task("k", key="t"))
    assert res.ok and [cap for _, cap, _ in agent.seen] == [2, 3, 5]  # 2, then 2 x 1.5, then 2 x 2.25, rounded up
    assert res.hops[0].max_turns == 5


def test_without_growth_the_turn_cap_gets_no_fresh_attempt(tmp_path):
    agent = Capped(turns=7)
    res = RetryingRunner(runner(tmp_path, agent, retries=2)).run(Task("k", key="t"))
    assert res.stop == "max_turns" and len(agent.seen) == 1


def test_a_continuation_is_no_correction(tmp_path):
    """Each round's stop hook is told the kind's whole `max_corrections` after a continuation."""
    agent = Capped(turns=3)
    assert runner(tmp_path, agent, max_continuations=1, max_corrections=2).run(Task("k", key="t")).ok
    assert [launch.env["CONTRAAGENT_CORRECTIONS_LEFT"] for launch in agent.launches] == ["2", "2"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_continuations", -1),
        ("max_continuations", 11),
        ("max_continuations", 1.5),
        ("max_turns_growth", 0.5),
        ("max_turns_growth", 11),
        ("max_turns_growth", True),
    ],
)
def test_a_value_out_of_range_is_refused(key, value):
    with pytest.raises(ConfigError, match=key):
        agent_task("k", instructions="Count.", output=str, max_turns=2, timeout_s=10, **{key: value})
    errors: list[str] = []
    PipelineConfig({"tasks": {"k": {key: value}}}).task_tables(errors)
    assert len(errors) == 1 and key in errors[0]


def test_check_shows_the_kind_s_continuations_and_growth(tmp_path):
    task = agent_task("k", instructions="Count.", output=str, max_turns=2, timeout_s=10, max_continuations=1, max_turns_growth=2)
    report = Pipeline(PipelineConfig({}), backends=StubAgent().backends(), cwd=tmp_path).check(lambda: task("a"))
    assert report.ok and " max_turns=2 timeout_s=10 max_continuations=1 max_turns_growth=2" in report.routes["k"]
