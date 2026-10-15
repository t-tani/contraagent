"""Credential pools (several subscriptions or tokens as one) and gateways (your own endpoint)."""

import threading

import pytest

from contraagent import (
    AgentRunner,
    Backend,
    ClaudeBackend,
    ConfigError,
    Gateway,
    KindConfig,
    LaunchResult,
    OmpBackend,
    PipelineConfig,
    QuotaRefusal,
    Route,
    Router,
    RoutingError,
    RoutingPlan,
    Stop,
    Task,
    TaskAdapter,
)
from contraagent.routing.pool import pools_of

POOLS = """
[credentials.sub-a]
type = "subscription"
config_dir = "/logins/a"
traits = ["company", "zdr"]

[credentials.sub-b]
type = "subscription"
config_dir = "/logins/b"
traits = ["company"]

[credentials.subs]
type = "pool"
members = ["sub-a", "sub-b"]
strategy = "{strategy}"
"""


def creds(tmp_path, strategy="in_order", extra=""):
    f = tmp_path / "p.toml"
    f.write_text(POOLS.replace("{strategy}", strategy) + extra)
    return PipelineConfig.load(f)


def test_a_pools_traits_are_what_every_member_carries(tmp_path):
    pool = creds(tmp_path).credentials()["subs"]
    assert pool.traits == {"company"}  # zdr only on sub-a: the pool is not zdr
    for bad, match in (
        ('\n[credentials.p2]\ntype = "pool"\nmembers = ["nope"]\n', "no member"),
        ('\n[credentials.p2]\ntype = "pool"\nmembers = ["subs"]\n', "itself a pool"),
        ('\n[credentials.p2]\ntype = "pool"\nmembers = ["sub-a"]\ntraits = ["zdr"]\n', "members' in common"),
    ):
        with pytest.raises(ConfigError, match=match):
            creds(tmp_path, extra=bad).credentials()


def test_in_order_and_round_robin(tmp_path):
    clock = [0.0]
    for strategy, expected in (("in_order", ["sub-a", "sub-a", "sub-a"]), ("round_robin", ["sub-a", "sub-b", "sub-a"])):
        pool = pools_of(creds(tmp_path, strategy).credentials(), clock=lambda: clock[0])["subs"]
        assert [pool.pick("m").label for _ in range(3)] == expected
    pool = pools_of(creds(tmp_path).credentials(), clock=lambda: clock[0])["subs"]
    pool.rate_limited(pool.pick("m"), "m", retry_after_s=600)
    assert pool.pick("m").label == "sub-b"  # in order: the next one only after a 429
    assert pool.pick("other").label == "sub-a"  # a cool-down is per model
    clock[0] = 601
    assert pool.pick("m").label == "sub-a"  # back to the first once it has rested


class Agent(Backend):
    name = binary = "claude"

    def __init__(self, limited):
        super().__init__()
        self.limited, self.seen, self._lock = limited, [], threading.Lock()

    def argv(self, launch):
        return ["x"]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.seen.append((launch.model, launch.credential.label))
        hit = (launch.model, launch.credential.label) in self.limited
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            credential=launch.credential.label,
            stop=Stop.RATE_LIMITED if hit else Stop.COMPLETED,
            ok=not hit,
            model=launch.model,
            quota_refusal=QuotaRefusal(retry_after_s=600) if hit else None,
        )


def runner(tmp_path, agent, credentials, routers=None):
    cfg = {"k": KindConfig(agent="claude", model="m1", credential="subs", max_turns=1, timeout_s=10)}
    return AgentRunner(agent, cfg, run_dir=tmp_path, adapter=TaskAdapter(), credentials=credentials, routers=routers, cwd=tmp_path)


def test_a_rate_limited_member_hands_the_task_to_the_next_one(tmp_path):
    agent = Agent(limited={("m1", "sub-a")})
    r = runner(tmp_path, agent, creds(tmp_path).credentials())
    res = r.run(Task("k", key="t1"))
    assert res.ok and agent.seen == [("m1", "sub-a"), ("m1", "sub-b")]
    assert "pool subs: sub-a rate limited, ran on sub-b" in res.reason
    agent.seen.clear()
    assert r.run(Task("k", key="t2")).ok and agent.seen == [("m1", "sub-b")]  # sub-a is resting


def test_with_every_member_cooling_the_routes_failover_takes_over(tmp_path):
    agent = Agent(limited={("m1", "sub-a"), ("m1", "sub-b")})
    router = Router(Route("claude", "m1", "subs"), (Route("claude", "m2", "subs"),))
    res = runner(tmp_path, agent, creds(tmp_path).credentials(), {"k": router}).run(Task("k", key="t"))
    assert res.ok and res.route.startswith("hop 2/2 claude/m2@subs")
    assert agent.seen == [("m1", "sub-a"), ("m1", "sub-b"), ("m2", "sub-a")]


def test_a_requirement_is_checked_on_every_member(tmp_path):
    text = '[defaults]\nagent = "claude"\ncredential = "subs"\n[tasks.k]\nmax_turns = 1\ntimeout_s = 9\n'
    with pytest.raises(RoutingError, match="requires zdr; credential subs carries company"):
        RoutingPlan.build(creds(tmp_path, extra="\n" + text), ["k"], {"claude": ClaudeBackend(base_env={})}, requirements={"k": ["zdr"]})


def test_gateways_bind_to_each_agents_own_variables():
    gw = Gateway(name="litellm", base_url="https://llm.internal", token="env:LITELLM_API_TOKEN", headers={"X-Team": "research"})
    env = {"LITELLM_API_TOKEN": "tok"}
    claude = ClaudeBackend(base_env={}).bind_credential(gw, "claude-sonnet-5-5", env=env, label="t").env
    assert claude["ANTHROPIC_BASE_URL"] == "https://llm.internal" and claude["ANTHROPIC_AUTH_TOKEN"] == "tok"
    assert claude["ANTHROPIC_CUSTOM_HEADERS"] == "X-Team: research"
    as_key = ClaudeBackend(base_env={}).bind_credential(gw.model_copy(update={"auth": "api_key"}), "m", env=env, label="t")
    assert as_key.env["ANTHROPIC_API_KEY"] == "tok" and "ANTHROPIC_AUTH_TOKEN" not in as_key.env
    plain = gw.model_copy(update={"headers": {}})
    omp = OmpBackend(base_env={}).bind_credential(plain, "litellm/claude-sonnet", env=env, label="t")
    assert omp.env == {"LITELLM_BASE_URL": "https://llm.internal", "LITELLM_API_KEY": "tok"} and omp.isolated
    with pytest.raises(Exception, match="custom headers only to an anthropic endpoint"):
        OmpBackend(base_env={}).bind_credential(gw, "litellm/x", label="t")
    with pytest.raises(Exception, match="openai model; credential litellm is for litellm"):
        OmpBackend(base_env={}).bind_credential(plain, "openai/gpt", label="t")
