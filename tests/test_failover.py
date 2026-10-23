"""Failover, end to end: every path the original harness had, exercised with stub agents."""

import logging
import threading

import pytest

from contraagent import Overrides, PipelineConfig, RoutingError, Task
from contraagent.backends import Backend, CredentialBinding, LaunchResult, QuotaRefusal, Stop
from contraagent.config import KindConfig, Route
from contraagent.engine import AgentRunner, Router, RoutingPlan, TaskAdapter


class Agent(Backend):
    """A coding agent that answers per (model) from a script, and records every launch."""

    drivable_model_chain = False

    def __init__(self, name, script):
        super().__init__()
        self.name, self.binary, self.script = name, name, script
        self.seen: list[tuple[str, str | None]] = []
        self._lock = threading.Lock()

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.seen.append((launch.model, launch.fallback_model))
        stop = self.script(launch.model)
        rl = QuotaRefusal(retry_after_s=300) if stop == Stop.RATE_LIMITED else None
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=stop,
            ok=stop == Stop.COMPLETED,
            model=launch.model,
            wall_s=0.1,
            quota_refusal=rl,
            result_text="safeguard refusal" if stop == Stop.REFUSED else "",
        )


def build(tmp_path, backends, routers, kind="k", model="m1", agent=None, **rc):
    primary = agent or next(iter(backends))
    cfg = {kind: KindConfig(agent=primary, model=model, max_turns=3, timeout_s=10, **rc)}
    return AgentRunner(backends, cfg, run_dir=tmp_path, adapter=TaskAdapter(), routers=routers, cwd=tmp_path)


def chain(*pairs):
    return Router(Route(*pairs[0]), tuple(Route(*p) for p in pairs[1:]), probe_interval_s=900, clock=lambda: clock[0])


clock = [0.0]


@pytest.fixture(autouse=True)
def _reset_clock():
    clock[0] = 0.0


def test_rate_limit_walks_the_chain_and_the_breaker_stays_open(tmp_path):
    a = Agent("claude", lambda m: Stop.RATE_LIMITED if m in ("m1", "m2") else Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"), ("claude", "m3"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    res = runner.run(Task("k", key="t1"))
    assert res.ok and [h.stop for h in res.hops] == ["rate_limited", "rate_limited", "completed"]
    assert res.route.startswith("hop 3/3") and "failing over" in res.reason
    a.seen.clear()
    assert runner.run(Task("k", key="t2")).ok
    assert [m for m, _ in a.seen] == ["m3"]  # the breaker is open: no task re-tries the dead routes
    assert [b for _, b in router.history()][-1].startswith("hop 3/3")


def test_an_attempt_counts_the_time_of_every_hop(tmp_path):
    """A model switch after a rate limit still spent the time before it."""
    a = Agent("claude", lambda m: Stop.RATE_LIMITED if m == "m1" else Stop.COMPLETED)
    res = build(tmp_path, {"claude": a}, {"k": chain(("claude", "m1"), ("claude", "m2"))}).run(Task("k", key="t1"))
    assert [h.wall_s for h in res.hops] == [0.1, 0.1]
    assert res.wall_s == 0.2


def test_half_open_probe_returns_to_the_primary_when_it_recovers(tmp_path):
    state = {"primary_down": True}
    a = Agent("claude", lambda m: Stop.RATE_LIMITED if m == "m1" and state["primary_down"] else Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    assert runner.run(Task("k", key="t1")).route.startswith("hop 2/2")
    a.seen.clear()
    runner.run(Task("k", key="t2"))
    assert [m for m, _ in a.seen] == ["m2"]  # still on the fallback before the cool-off
    clock[0] = 10_000  # the provider's stated cool-off has passed
    state["primary_down"] = False
    a.seen.clear()
    res = runner.run(Task("k", key="t3"))
    assert [m for m, _ in a.seen] == ["m1"] and res.route.startswith("hop 1/2")  # one task probes, lands
    assert router.active().model == "m1"  # breaker closed for good
    assert any("primary recovered" in b for _, b in router.history())


def test_a_success_begun_before_the_breaker_opened_does_not_close_it():
    """A launch on the primary that began before another task's 429 says nothing of the
    limit since: its success leaves the breaker open. A launch begun after it is a probe."""
    router = chain(("claude", "m1"), ("claude", "m2"))
    primary = router.routes[0]
    clock[0] = 1.0
    earlier = router.now()  # task A starts on the primary
    clock[0] = 2.0
    router.rate_limited(primary)  # task B: 429, the breaker opens
    clock[0] = 3.0
    router.succeeded(primary, started=earlier)  # A lands now
    assert router.active().model == "m2" and router.pick().model == "m2"
    clock[0] = 10_000  # the cool-off has passed: the next task probes the primary
    probe = router.now()
    assert router.pick().model == "m1"
    router.succeeded(primary, started=probe)
    assert router.active().model == "m1"


def test_a_failed_probe_keeps_the_fallback(tmp_path):
    a = Agent("claude", lambda m: Stop.RATE_LIMITED if m == "m1" else Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    runner.run(Task("k", key="t1"))
    clock[0] = 10_000
    a.seen.clear()
    res = runner.run(Task("k", key="t2"))  # the probe hits m1 again, is refused, and the task still completes
    assert [m for m, _ in a.seen] == ["m1", "m2"] and res.ok and router.active().model == "m2"


def test_every_hop_refusing_is_an_error_not_a_stall(tmp_path):
    a = Agent("claude", lambda m: Stop.RATE_LIMITED)
    router = chain(("claude", "m1"), ("claude", "m2"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    res = runner.run(Task("k", key="t1"))
    assert not res.ok and res.stop == "rate_limited" and "no hop left" in res.reason
    again = runner.run(Task("k", key="t2"))  # exhausted: no launch at all
    assert again.stop == "rate_limited" and "all 2 hops rate limited" in again.reason


def test_failover_crosses_coding_agents(tmp_path):
    claude = Agent("claude", lambda m: Stop.RATE_LIMITED)
    omp = Agent("omp", lambda m: Stop.COMPLETED)
    router = chain(("claude", "opus"), ("omp", "other/model"))
    runner = build(tmp_path, {"claude": claude, "omp": omp}, {"k": router}, model="opus", agent="claude")
    res = runner.run(Task("k", key="t1"))
    assert res.ok and omp.seen == [("other/model", None)] and "omp/other/model" in res.route


def test_a_refusal_moves_only_that_task(tmp_path):
    a = Agent("claude", lambda m: Stop.REFUSED if m == "m1" else Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    first = runner.run(Task("k", key="flagged"))
    assert first.ok and "safeguard refusal" in first.reason and first.route.startswith("hop 2/2")
    assert router.active().model == "m1"  # a refusal is about the content, not the provider
    a.seen.clear()
    runner.run(Task("k", key="other"))
    assert a.seen[0][0] == "m1"  # the next task still starts on hop 1


def test_model_failover_hands_the_same_agent_remainder_to_agents_that_have_a_flag(tmp_path):
    class ClaudeLike(Agent):
        drivable_model_chain = True

    a = ClaudeLike("claude", lambda m: Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"), ("omp", "x"))
    off = build(tmp_path, {"claude": a}, {"k": router})
    off.run(Task("k", key="t1"))
    assert a.seen[-1][1] is None  # opt-in: nothing is handed over by default
    on = build(tmp_path, {"claude": a}, {"k": router}, model_failover=True)
    on.run(Task("k", key="t2"))
    assert a.seen[-1] == ("m1", "m2")  # same-agent hops only; the omp hop stays the Router's


def test_config_builds_per_kind_chains_and_drops_hops_with_no_backend(tmp_path, caplog):
    cfg = tmp_path / "p.toml"
    cfg.write_text("""
[defaults]
agent = "claude"
model = "m1"

[tasks.a]
max_turns = 3
timeout_s = 10

[tasks.b]
max_turns = 3
timeout_s = 10
[[tasks.b.fallbacks]]
agent = "omp"
model = "b-backup"

[[defaults.fallbacks]]
agent = "omp"
model = "global-backup"
[[defaults.fallbacks]]
agent = "omp-rpc"
model = "no-backend-here"
""")
    backends = {"claude": Agent("claude", lambda m: Stop.COMPLETED), "omp": Agent("omp", lambda m: Stop.COMPLETED)}
    with caplog.at_level(logging.INFO, logger="contraagent._internal.routing"):
        routers = RoutingPlan.build(PipelineConfig.load(cfg), ["a", "b"], backends).routers
    assert routers["a"].chain().endswith("omp/global-backup") and len(routers["a"].routes) == 2  # omp-rpc hop dropped
    assert routers["b"].chain().endswith("omp/b-backup")  # its own chain wins
    assert any("dropping hop" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_preflight_drops_a_dead_route_and_rebuilds_the_chain(tmp_path):
    claude = Agent("claude", lambda m: Stop.RATE_LIMITED if m == "dead" else Stop.COMPLETED)
    omp = Agent("omp", lambda m: Stop.COMPLETED)
    backends = {"claude": claude, "omp": omp}
    configs = {"k": KindConfig(agent="claude", model="dead", max_turns=3, timeout_s=10)}
    routers = {"k": chain(("claude", "dead"), ("omp", "alive"))}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs, routers=routers)
    plan.preflight("substitute")
    assert [str(r) for r in plan.routers["k"].routes] == ["omp/alive"]  # the chain is rebuilt around what answered
    assert plan.routers["k"].routes[0].agent == "omp"


def test_an_unknown_agent_name_is_still_a_config_error(tmp_path):
    cfg = tmp_path / "p.toml"
    cfg.write_text(
        '[defaults]\nagent = "claude"\n[tasks.a]\nmax_turns = 3\ntimeout_s = 10\n[[defaults.fallbacks]]\nagent = "codexx"\nmodel = "typo"\n'
    )
    backends = {"claude": Agent("claude", lambda m: Stop.COMPLETED)}
    with pytest.raises(RoutingError, match="unknown agent 'codexx'"):
        RoutingPlan.build(PipelineConfig.load(cfg), ["a"], backends)


def test_an_effort_the_agent_does_not_accept_is_a_config_error(tmp_path):
    cfg = tmp_path / "p.toml"
    cfg.write_text('[defaults]\nagent = "claude"\neffort = "auto"\n[tasks.a]\nmax_turns = 3\ntimeout_s = 10\n')
    backends = {"claude": Agent("claude", lambda m: Stop.COMPLETED)}
    with pytest.raises(RoutingError, match="claude takes: low"):
        RoutingPlan.build(PipelineConfig.load(cfg), ["a"], backends)


def test_an_attempt_counts_the_tokens_and_cost_of_every_hop(tmp_path):
    """A rate-limited hop still spent tokens; the attempt and its journal row carry the sum."""
    from contraagent._internal.execution.journal import Journal
    from contraagent.backends import CallUsage, Usage

    class Spending(Agent):
        def run(self, launch):
            r = super().run(launch)
            r.usage = Usage(calls=[CallUsage(model=launch.model, input=100, cache_read=50, cache_creation=10, output=20)], output_total=20)
            r.cost_usd = 0.01
            return r

    a = Spending("claude", lambda m: Stop.RATE_LIMITED if m == "m1" else Stop.COMPLETED)
    res = build(tmp_path, {"claude": a}, {"k": chain(("claude", "m1"), ("claude", "m2"))}).run(Task("k", key="t1"))
    assert [h.cost_usd for h in res.hops] == [0.01, 0.01]
    row = Journal(tmp_path / "j", tmp_path / "l", run_id="r", run_group="r", unit_of=lambda t: t.unit).row(res)
    assert row.cost_usd == 0.02
    assert row.usage is not None and (row.usage.input, row.usage.cache_read, row.usage.output, row.usage.calls) == (200, 100, 40, 2)


def test_an_agent_or_model_override_runs_every_kind_without_hops(tmp_path, caplog):
    cfg = PipelineConfig({"tasks": {"a": {"max_turns": 3, "timeout_s": 10}}, "defaults": {"fallbacks": [{"agent": "omp", "model": "x"}]}})
    backends = {"claude": Agent("claude", lambda m: Stop.COMPLETED), "omp": Agent("omp", lambda m: Stop.COMPLETED)}
    assert RoutingPlan.build(cfg, ["a"], backends).routers
    with caplog.at_level(logging.WARNING, logger="contraagent._internal.routing"):
        assert RoutingPlan.build(cfg, ["a"], backends, Overrides(agent="omp")).routers == {}
    assert "a: no failover hops; the override agent=omp" in caplog.text


def test_a_kind_without_a_chain_records_its_one_route(tmp_path):
    res = build(tmp_path, {"claude": Agent("claude", lambda m: Stop.COMPLETED)}, {}).run(Task("k", key="t1"))
    assert res.route == "hop 1/1 claude/m1" and [h.route for h in res.hops] == ["hop 1/1 claude/m1"]


@pytest.mark.parametrize("stop", [Stop.ERROR, Stop.AUTH_FAILED, Stop.TIMEOUT, Stop.INVALID_OUTPUT, Stop.LAUNCH_FAILED])
def test_any_failure_moves_only_that_task_to_the_next_hop(tmp_path, stop):
    a = Agent("claude", lambda m: stop if m == "m1" else Stop.COMPLETED)
    router = chain(("claude", "m1"), ("claude", "m2"))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    res = runner.run(Task("k", key="t1"))
    assert res.ok and res.route.startswith("hop 2/2") and f"{stop.value} on hop 1/2" in res.reason
    assert [h.stop for h in res.hops] == [stop.value, "completed"]
    assert router.active().model == "m1"  # the breaker moves on a 429 only


def test_a_failure_on_the_last_hop_ends_the_task(tmp_path):
    a = Agent("claude", lambda m: Stop.ERROR)
    res = build(tmp_path, {"claude": a}, {"k": chain(("claude", "m1"), ("claude", "m2"))}).run(Task("k", key="t1"))
    assert not res.ok and res.stop == "error" and [h.stop for h in res.hops] == ["error", "error"]


def test_a_credential_mismatch_or_a_signal_does_not_fail_over(tmp_path):
    class Killed(Agent):
        def run(self, launch):
            result = super().run(launch)
            result.exit_code = -15  # SIGTERM: the run is stopping
            return result

    for agent in (Agent("claude", lambda m: Stop.CREDENTIAL_MISMATCH), Killed("claude", lambda m: Stop.ERROR)):
        res = build(tmp_path, {"claude": agent}, {"k": chain(("claude", "m1"), ("claude", "m2"))}).run(Task("k", key="t1"))
        assert not res.ok and [m for m, _ in agent.seen] == ["m1"]


def test_a_credential_override_is_every_hops_credential(tmp_path):
    cfg = PipelineConfig(
        {
            "tasks": {"a": {"max_turns": 3, "timeout_s": 10}},
            "defaults": {"fallbacks": [{"agent": "claude", "model": "m2", "credential": "other"}]},
            "credentials": {"mine": {"type": "api_key", "key": "env:MINE"}, "other": {"type": "api_key", "key": "env:OTHER"}},
        }
    )

    class AnyCredential(Agent):
        def bind_credential(self, credential, model="", *, env=None, label="", cwd=None):
            return CredentialBinding()

    backends = {"claude": AnyCredential("claude", lambda m: Stop.COMPLETED)}
    assert [r.credential for r in RoutingPlan.build(cfg, ["a"], backends).routers["a"].routes] == ["ambient", "other"]
    routes = RoutingPlan.build(cfg, ["a"], backends, Overrides(credential="mine")).routers["a"].routes
    assert [r.credential for r in routes] == ["mine", "mine"]


# --- a hop's stops ---------------------------------------------------------------


def stops_chain(*hops):
    """`chain`, each hop after the first `(agent, model, stops)`."""
    first, *rest = hops
    return Router(Route(*first), tuple(Route(a, m, stops=s) for a, m, s in rest), probe_interval_s=900, clock=lambda: clock[0])


def test_a_task_fails_over_to_the_next_hop_for_its_stop(tmp_path):
    """A refusal passes over a hop for rate limits; a rate limit passes over a hop for refusals."""
    script = {"m1": Stop.REFUSED}
    a = Agent("claude", lambda m: script.get(m, Stop.COMPLETED))
    router = stops_chain(("claude", "m1"), ("claude", "m2", ("rate_limited",)), ("claude", "m3", ("refused",)))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    res = runner.run(Task("k", key="t1"))
    assert res.ok and [m for m, _ in a.seen] == ["m1", "m3"] and res.route.startswith("hop 3/3")
    assert "failing over to hop 3/3" in res.reason
    script["m1"] = Stop.RATE_LIMITED
    a.seen.clear()
    res = runner.run(Task("k", key="t2"))
    assert res.ok and [m for m, _ in a.seen] == ["m1", "m2"] and router.active().model == "m2"


def test_the_breaker_opens_on_a_hop_for_rate_limits_only(tmp_path):
    a = Agent("claude", lambda m: Stop.RATE_LIMITED if m == "m1" else Stop.COMPLETED)
    router = stops_chain(("claude", "m1"), ("claude", "m2", ("refused",)), ("claude", "m3", ()))
    runner = build(tmp_path, {"claude": a}, {"k": router})
    assert runner.run(Task("k", key="t1")).ok and [m for m, _ in a.seen] == ["m1", "m3"]
    assert router.active().model == "m3" and router.history() == [("hop 1/3 claude/m1", "hop 3/3 claude/m3")]


def test_with_no_hop_for_its_stop_the_launch_s_own_stop_stands(tmp_path):
    a = Agent("claude", lambda m: Stop.TIMEOUT if m == "m1" else Stop.COMPLETED)
    router = stops_chain(("claude", "m1"), ("claude", "m2", ("rate_limited", "api_error")))
    res = build(tmp_path, {"claude": a}, {"k": router}).run(Task("k", key="t1"))
    assert not res.ok and res.stop == "timeout" and [m for m, _ in a.seen] == ["m1"] and len(res.hops) == 1


def test_a_hop_s_stops_are_read_checked_and_shown(tmp_path):
    cfg = PipelineConfig(
        {
            "tasks": {"a": {"max_turns": 3, "timeout_s": 10}},
            "defaults": {"model": "m1", "fallbacks": [{"agent": "claude", "model": "m2", "stops": ["rate_limited", "api_error"]}]},
        }
    )
    backends = {"claude": Agent("claude", lambda m: Stop.COMPLETED)}
    router = RoutingPlan.build(cfg, ["a"], backends).routers["a"]
    assert [r.stops for r in router.routes] == [(), ("rate_limited", "api_error")]
    assert router.chain() == "hop 1/2 claude/m1 -> hop 2/2 claude/m2 on rate_limited, api_error"
    assert router.on_credential("other").routes[1].stops == ("rate_limited", "api_error")
    assert router.same_agent_after(router.routes[0]) == []  # the agent's own flag would take it on any stop
    for stops, said in (
        (["rate_limit"], "stops names 'rate_limit' (did you mean rate_limited?)"),
        (["completed"], "not a stop a task fails over on"),
        ([], "stops must be a non-empty list"),
        ("refused", "stops must be a non-empty list"),
    ):
        bad = PipelineConfig(
            {
                "tasks": {"a": {"max_turns": 3, "timeout_s": 10}},
                "defaults": {"fallbacks": [{"agent": "claude", "model": "m2", "stops": stops}]},
            }
        )
        with pytest.raises(RoutingError, match="block 1 \\(hop 2\\)") as err:
            RoutingPlan.build(bad, ["a"], backends)
        assert said in str(err.value)
