"""An OpenCode key across the agents that run its models: opencode, pi and omp find it each their
own way, and agree on the account it bills and on the Go subscription's usage."""

import json
from pathlib import Path

import pytest

from contraagent import AMBIENT, ApiKey, Gateway, Launch, OmpBackend, OpencodeBackend, PiBackend, Subscription
from contraagent.backends import opencode_key as login
from contraagent.backends.launch import ACCOUNT_SECRET, RateLimit, account_digest
from contraagent.backends.omp.backend import dotenv_credentials, omp_dotenv_files
from contraagent.routing.quota import QuotaRests

FIXTURES = Path(__file__).parent / "fixtures" / "opencode"
KEY = "sk-test-opencode-go-0000"
OTHER = "sk-test-opencode-go-1111"
GO_MODEL = "opencode-go/glm-5.3"


def store(tmp_path: Path, logins: dict) -> dict[str, str]:
    """An opencode data directory holding `logins`, as an environment that points at it."""
    data = tmp_path / "data"
    (data / "opencode").mkdir(parents=True)
    (data / "opencode" / "auth.json").write_text(json.dumps(logins))
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"XDG_DATA_HOME": str(data), "HOME": str(home), "PATH": "/usr/bin:/bin"}


def go_body() -> dict:
    return json.loads((FIXTURES / "go-usage.json").read_text())


# --- the shared reader ------------------------------------------------------------


def test_the_go_usage_route_reads_as_the_windows_omp_reports():
    r = login.go_reading(go_body(), KEY)
    assert r is not None
    assert (r.five_hour_pct, r.seven_day_pct) == (0.0, 99.0)
    assert r.five_hour_resets_at == "2026-10-14T22:38:16+00:00" and r.seven_day_resets_at == "2026-10-19T00:00:00+00:00"
    assert r.windows["monthly"] == {"pct": 100.0, "resets_at": "2026-11-04T00:48:31+00:00"}
    assert r.status == "exhausted,warning"  # monthly refused, weekly past 80%
    assert r.account == account_digest(ACCOUNT_SECRET, KEY)
    assert KEY not in json.dumps(r.__dict__)


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"usage": {}},
        {"usage": {**go_body()["usage"], "weekly": {"status": "ok"}}},
        {"usage": {**go_body()["usage"], "rolling": None}},
    ],
)
def test_an_answer_missing_a_window_is_no_reading(body):
    assert login.go_reading(body, KEY) is None


def test_the_route_is_asked_with_the_key_under_the_base_and_any_failure_is_none():
    asked = []

    def fetch(url, key, timeout):
        asked.append((url, key))
        return go_body()

    assert login.go_usage(KEY, fetch=fetch) is not None
    assert login.go_usage(KEY, "https://gw.example/zen/go/v1/", fetch=fetch) is not None
    assert asked == [("https://opencode.ai/zen/go/v1/usage", KEY), ("https://gw.example/zen/go/v1/usage", KEY)]

    def broken(url, key, timeout):
        raise OSError("refused")

    assert login.go_usage(KEY, fetch=broken) is None
    assert login.go_usage("", fetch=fetch) is None and len(asked) == 2  # no key, no request


def test_a_stored_login_is_read_by_the_name_opencode_keeps_it_under(tmp_path):
    env = store(tmp_path, {"opencode-go": {"type": "api", "key": KEY}, "opencode": {"type": "api", "key": OTHER}, "x": {"type": "oauth"}})
    assert login.stored_key("opencode-go", env) == KEY
    assert login.stored_key("opencode-zen", env) == login.stored_key("opencode", env) == OTHER  # Zen is `opencode` there
    assert login.stored_key("x", env) == ""  # an OAuth login has no key
    assert login.stored_key("opencode-go", {"XDG_DATA_HOME": str(tmp_path / "none")}) == ""


def test_a_dotenv_file_reads_as_the_agents_read_it(tmp_path):
    f = tmp_path / ".env"
    f.write_text("# keys\nexport OPENCODE_API_KEY='a b'\nLITELLM_BASE_URL=\"https://x\"\nBROKEN\n")
    assert login.dotenv(f) == {"OPENCODE_API_KEY": "a b", "LITELLM_BASE_URL": "https://x"}
    assert login.dotenv(tmp_path / "missing") == {}


# --- each agent ---------------------------------------------------------------------


def test_opencode_bills_the_key_it_sends_and_reads_its_usage(tmp_path, monkeypatch):
    env = store(tmp_path, {"opencode-go": {"type": "api", "key": KEY}})
    be = OpencodeBackend(base_env={**env, "OPENCODE_API_KEY": OTHER})
    sub = Subscription(name="oc", provider="opencode-go")
    assert be.account(sub, GO_MODEL) == login.account_of_key(KEY)  # the stored login
    assert be.account(AMBIENT, GO_MODEL) == login.account_of_key(KEY)  # the stored login outranks the variable
    assert be.account(ApiKey(name="k", provider="opencode-go", key="env:MINE"), GO_MODEL) == ""  # unset secret
    be2 = OpencodeBackend(base_env={**env, "MINE": OTHER})
    assert be2.account(ApiKey(name="k", provider="opencode-go", key="env:MINE"), GO_MODEL) == login.account_of_key(OTHER)
    assert be.account(sub, "anthropic/claude-haiku-5-5") == ""
    seen = []
    monkeypatch.setattr(login, "go_usage", lambda key, base="", **_: seen.append(key) or login.go_reading(go_body(), key))
    r = be.usage_reading(Launch(prompt="", label="t", model=GO_MODEL, credential=sub))
    assert r is not None and r.account == login.account_of_key(KEY) and seen == [KEY]
    assert be.usage_reading(Launch(prompt="", label="t", model="opencode/kimi", credential=sub)) is None  # Zen has no windows


def test_pi_takes_opencodes_stored_login_when_its_own_directory_has_none(tmp_path):
    env = store(tmp_path, {"opencode-go": {"type": "api", "key": KEY}})
    pi_home = tmp_path / "pi"
    pi_home.mkdir()
    (pi_home / "auth.json").write_text(json.dumps({"anthropic": {"type": "oauth"}}))
    be = PiBackend(base_env={**env, "PI_CODING_AGENT_DIR": str(pi_home)}, agent_dirs=tmp_path / "dirs")
    sub = Subscription(name="oc", provider="opencode-go")
    child = be.env(Launch(prompt="", label="t", model=GO_MODEL, credential=sub))
    assert child["OPENCODE_API_KEY"] == KEY
    assert "opencode's stored opencode-go login" in be.bind_credential(sub, GO_MODEL, env=be._base_env).isolation
    assert be.account(sub, GO_MODEL) == login.account_of_key(KEY)
    assert be.account(AMBIENT, GO_MODEL) == ""  # ambient is the host's own: no key there

    # pi's own login wins: nothing is added over it.
    (pi_home / "auth.json").write_text(json.dumps({"opencode-go": {"type": "api_key", "key": OTHER}}))
    child = be.env(Launch(prompt="", label="t2", model=GO_MODEL, credential=sub))
    assert "OPENCODE_API_KEY" not in child
    assert be.account(sub, GO_MODEL) == login.account_of_key(OTHER)


def test_omp_bills_the_key_of_its_env_files_and_says_they_break_isolation(tmp_path):
    env = store(tmp_path, {})
    home = Path(env["HOME"])
    (home / ".env").write_text(f"OPENCODE_API_KEY={KEY}\nLITELLM_BASE_URL=https://gw\n")
    assert omp_dotenv_files(env, ("--profile", "p"), cwd=tmp_path) == [
        tmp_path / ".env",
        home / ".omp" / "profiles" / "p" / "agent" / ".env",
        home / ".omp" / "profiles" / "p" / ".env",
        home / ".env",
    ]
    be = OmpBackend(base_env=env)
    assert be.account(AMBIENT, GO_MODEL) == login.account_of_key(KEY)
    assert be.account(Subscription(name="oc", provider="opencode-go"), GO_MODEL) == login.account_of_key(KEY)
    mine = OmpBackend(base_env={**env, "MINE": OTHER})
    assert mine.account(ApiKey(name="k", provider="opencode-go", key="env:MINE"), GO_MODEL) == login.account_of_key(OTHER)
    assert set(dotenv_credentials(env)) == {"OPENCODE_API_KEY", "LITELLM_BASE_URL"}  # a gateway's endpoint picks the bill too
    # An isolated launch whose provider's variable comes back from a .env file is not isolated.
    gw = be.bind_credential(Gateway(name="g", provider="litellm", base_url="https://other"), "litellm/m", env=env)
    assert gw.isolated is True  # the binding sets LITELLM_BASE_URL itself
    bound = be.bind_credential(ApiKey(name="a", provider="openai", key="env:MINE"), "openai/gpt", env={**env, "MINE": OTHER})
    assert bound.isolated is False and "omp profile" in bound.isolation
    (home / ".env").write_text(f"OPENCODE_API_KEY={KEY}\nANTHROPIC_API_KEY=sk-ant-x\n")
    ant = be.bind_credential(Subscription(name="s", provider="anthropic"), "anthropic/claude", env=env)
    assert ant.isolated is False and f"ANTHROPIC_API_KEY from {home / '.env'}" in ant.isolation


def test_one_login_is_one_account_so_a_rest_on_one_agent_holds_on_the_others(tmp_path):
    env = store(tmp_path, {"opencode-go": {"type": "api", "key": KEY}})
    (Path(env["HOME"]) / ".env").write_text(f"OPENCODE_API_KEY={KEY}\n")
    pi_home = tmp_path / "pi"
    pi_home.mkdir()
    sub = Subscription(name="oc", provider="opencode-go", max_seven_day_pct=95)
    agents = [OpencodeBackend(base_env=env), PiBackend(base_env={**env, "PI_CODING_AGENT_DIR": str(pi_home)}), OmpBackend(base_env=env)]
    accounts = {be.name: be.account(sub, GO_MODEL) for be in agents}
    assert set(accounts.values()) == {login.account_of_key(KEY)}
    rests = QuotaRests({"oc": sub})
    reading = login.go_reading(go_body(), KEY)
    assert isinstance(reading, RateLimit)
    reading.credential = "oc"  # as the runner labels a reading of the opencode launch
    rests.observe(reading)
    for be in agents:
        assert rests.rests("oc", "k", lambda name, be=be: be.account(sub, GO_MODEL)), be.name
    # Another key on the same credential name is another account: the reading does not hold it.
    other = OpencodeBackend(base_env=store(tmp_path / "b", {"opencode-go": {"type": "api", "key": OTHER}}))
    assert not rests.rests("oc", "k", lambda name: other.account(sub, GO_MODEL))
