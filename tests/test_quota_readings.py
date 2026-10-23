"""Utilization readings in full, and the account each one is of.

A reading carries every window and field the coding agent reports, and a digest of
the account that reported it (`account_digest`): a credential's rests are judged by
the readings of the account a launch as it bills now, never by another account's.
"""

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from contraagent import PipelineConfig, Task
from contraagent._internal.backends.claude.wire import StreamReader
from contraagent._internal.backends.launch import ACCOUNT_SECRET, ACCOUNT_UUID, account_digest
from contraagent.backends import Backend, ClaudeBackend, Launch, LaunchResult, OmpBackend, Stop
from contraagent.config import AMBIENT, Bedrock, KindConfig, Limits, OAuthToken, QuotaReading, QuotaWindow, Route, Secret, Subscription
from contraagent.engine import AgentRunner, CredentialRests, Router, TaskAdapter
from fake_cli import write_fake_cli

FIXTURES = Path(__file__).parent / "fixtures" / "claude"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


# --- what a reading carries ------------------------------------------------------------


def test_claude_s_rate_limit_events_are_read_in_full():
    """Two real events: an account well under its limits, and one past a warning threshold."""
    reader = StreamReader(Limits())
    for line in (FIXTURES / "rate_limit_events.jsonl").read_text().splitlines():
        reader.feed_line(line)
    calm, warned = reader.quota
    assert (calm.status, calm.status_window, calm.threshold_pct) == ("allowed", "five_hour", None)
    assert (calm.five_hour_pct, calm.seven_day_pct) == (41.0, 24.0)
    assert (calm.overage_status, calm.overage_disabled_reason, calm.using_overage) == ("rejected", "org_level_disabled", False)
    assert calm.windows == {
        "five_hour": QuotaWindow(pct=41.0, resets_at="2026-10-14T14:30:00+00:00"),
        "seven_day": QuotaWindow(pct=24.0, resets_at="2026-10-15T08:00:00+00:00"),
    }
    assert calm.extra == {}
    assert (warned.status, warned.status_window, warned.threshold_pct, warned.seven_day_pct) == ("allowed_warning", "seven_day", 75.0, 98.0)


def test_a_window_or_a_field_the_reader_does_not_name_is_kept():
    event = {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed",
            "rateLimitType": "seven_day_opus",
            "utilization": 0.5,
            "resetsAt": 1792051200,
            "newField": {"x": 1},
            "unifiedWindows": {"five_hour": {"utilization": 0.1, "resetsAt": 1791988200}},
        },
    }
    reader = StreamReader(Limits())
    reader.feed(event)
    [r] = reader.quota
    assert r.windows["seven_day_opus"] == QuotaWindow(pct=50.0, resets_at="2026-10-15T08:00:00+00:00")  # the status's own window
    assert r.extra == {"newField": {"x": 1}}
    assert r.seven_day_pct is None  # not reported: not guessed


OMP_USAGE = r"""
import json, sys
if "usage" in sys.argv:
    limit = lambda w, used, resets: {"scope": {"provider": "anthropic", "windowId": w, "shared": True}, "status": "ok",
                                     "window": {"id": w, "resetsAt": resets}, "amount": {"usedFraction": used, "unit": "percent"}}
    report = {"provider": "anthropic", "fetchedAt": 1791776226254, "metadata": {"accountId": "6f1c2b9e-account"},
              "limits": [limit("5h", 0.05, 1791784800000), limit("7d", 0.79, 1791979200000),
                         {**limit("7d", 0.3, 1791979200000), "scope": {"windowId": "7d", "tier": "fable"}}]}
    print(json.dumps({"reports": [report]})); sys.exit(0)
print(json.dumps({"type": "session", "id": "s-1"}))
print(json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "ok"}}))
"""


def fake_cli(tmp_path: Path, name: str, body: str) -> Path:
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, name, body)
    return bindir


def test_omp_s_reading_names_its_account_and_every_window(tmp_path):
    bindir = fake_cli(tmp_path, "omp", OMP_USAGE)
    backend = OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"})
    launch = Launch(prompt="hi", label="t", model="anthropic/claude-haiku-5-5", cwd=tmp_path, limits=Limits(timeout_s=30))
    [reading] = backend.run(launch).quota
    assert reading.account == account_digest(ACCOUNT_UUID, "6f1c2b9e-account")
    assert (reading.five_hour_pct, reading.seven_day_pct) == (5.0, 79.0)  # the account's own windows, not a model's
    assert reading.windows["seven_day_fable"].pct == 30.0  # a model's own window, named
    assert backend.account(AMBIENT, "anthropic/claude-haiku-5-5") == reading.account
    assert backend.account(AMBIENT, "no-provider") == ""


# --- the account digest ------------------------------------------------------------------


def test_an_account_digest_tells_accounts_apart_and_reveals_none():
    token = "sk-ant-oat01-" + "x" * 40
    d = account_digest(ACCOUNT_SECRET, token)
    assert len(d) == 12 and all(c in "0123456789abcdef" for c in d)
    assert d == account_digest(ACCOUNT_SECRET, token)
    assert d != account_digest(ACCOUNT_SECRET, token + "y")
    assert d != account_digest(ACCOUNT_UUID, token)  # one value, two sources: compared only within one
    assert token[:12] not in d and account_digest(ACCOUNT_SECRET, "") == ""


def login(config_dir: Path, uuid: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / ".claude.json").write_text(json.dumps({"oauthAccount": {"accountUuid": uuid, "emailAddress": "a@example.com"}}))
    return config_dir


def test_claude_code_s_account_is_its_login_s_or_its_credential_s_secret(tmp_path):
    work = login(tmp_path / "work", "uuid-work")
    home = login(tmp_path / "home", "uuid-home")
    b = ClaudeBackend(base_env={"CLAUDE_CONFIG_DIR": str(home), "TOKEN_A": "tok-a"})
    assert b.account(AMBIENT) == account_digest(ACCOUNT_UUID, "uuid-home")
    assert b.account(Subscription(name="work", config_dir=work)) == account_digest(ACCOUNT_UUID, "uuid-work")
    assert b.account(OAuthToken(name="a", token=Secret("env:TOKEN_A"))) == account_digest(ACCOUNT_SECRET, "tok-a")
    assert b.account(OAuthToken(name="b", token=Secret("env:TOKEN_B"))) == ""  # unset: not known
    assert b.account(Bedrock(name="br", region="us-east-1")) == ""
    # An ambient launch bills a token in its environment before the login.
    assert ClaudeBackend(base_env={"CLAUDE_CONFIG_DIR": str(home), "CLAUDE_CODE_OAUTH_TOKEN": "tok-c"}).account(AMBIENT) == account_digest(
        ACCOUNT_SECRET, "tok-c"
    )
    assert ClaudeBackend(base_env={"CLAUDE_CONFIG_DIR": str(tmp_path / "none")}).account(AMBIENT) == ""  # no login


# --- rests are judged by the account a launch bills ---------------------------------------


def creds(tmp_path):
    f = tmp_path / "p.toml"
    f.write_text('[credentials.personal]\ntype = "subscription"\nmax_seven_day_pct = 90\n')
    return PipelineConfig.load(f).credentials()


def reading(credential="personal", week=99.0, account="", minutes=0) -> QuotaReading:
    return QuotaReading(
        credential=credential,
        account=account,
        seven_day_pct=week,
        seven_day_resets_at=(NOW + timedelta(days=2)).isoformat(),
        observed_at=(NOW + timedelta(minutes=minutes)).isoformat(),
    )


def test_a_reading_of_another_account_does_not_rest_a_credential(tmp_path):
    """The token behind `personal` was replaced: the old account's 99% does not rest the new one."""
    r = CredentialRests(creds(tmp_path), now=lambda: NOW)
    r.observe(reading(account="old"))
    assert r.reason("personal", account=lambda name: "new") == ""
    assert r.reason("personal", account=lambda name: "old") == "personal rests: weekly usage 99%, max 90%"
    assert r.reason("personal") != ""  # the account a launch bills not known: the newest reading counts
    r.observe(reading(week=10.0, account="new", minutes=1))
    assert r.reason("personal", account=lambda name: "new") == ""
    assert r.reason("personal", account=lambda name: "old") != ""  # each account keeps its own


def test_a_reading_that_names_no_account_counts_for_every_account(tmp_path):
    """Journals of an older contraagent name no account: their readings still count."""
    r = CredentialRests(creds(tmp_path), now=lambda: NOW)
    r.observe(reading(account=""))
    assert r.reason("personal", account=lambda name: "any") != ""


def test_ambient_on_two_coding_agents_is_two_accounts(tmp_path):
    """Claude Code's login and omp's login, both `ambient`: a rule rests only the busy one."""
    rule = lambda cred, rd: f"pace {rd.seven_day_pct:.0f}%" if (rd.seven_day_pct or 0) > 50 else None
    r = CredentialRests(creds(tmp_path), rule, now=lambda: NOW)
    r.observe(reading("ambient", week=98.0, account="omp-login"))
    r.observe(reading("ambient", week=11.0, account="claude-login", minutes=1))
    assert r.reason("ambient", account=lambda name: "claude-login") == ""
    assert r.reason("ambient", account=lambda name: "omp-login") == "ambient rests: pace 98%"


class Agent(Backend):
    """A coding agent on one account: its readings name none, `account` names it."""

    name = binary = "claude"

    def __init__(self, account, week):
        super().__init__()
        self.acct, self.week, self.asked, self.seen, self._lock = account, week, 0, [], threading.Lock()

    def argv(self, launch):
        return ["x"]

    def env(self, launch):
        return {}

    def account(self, credential, model="", *, cwd=None):
        with self._lock:
            self.asked += 1
        return self.acct

    def run(self, launch):
        with self._lock:
            self.seen.append(launch.credential.label)
        r = QuotaReading(seven_day_pct=self.week, seven_day_resets_at=(NOW + timedelta(days=2)).isoformat(), observed_at=NOW.isoformat())
        label = launch.credential.label
        return LaunchResult(label=launch.label, agent=self.name, credential=label, stop=Stop.COMPLETED, ok=True, quota=[r])


def make_runner(tmp_path, agent, rests):
    cfg = {"k": KindConfig(agent="claude", model="m1", credential="personal", max_turns=1, timeout_s=10)}
    return AgentRunner(
        agent,
        cfg,
        run_dir=tmp_path,
        adapter=TaskAdapter(),
        credentials=rests.credentials,
        routers={"k": Router(Route("claude", "m1", "personal"), ())},
        cwd=tmp_path,
        rests=rests,
    )


def test_the_runner_names_each_reading_s_account_and_asks_once(tmp_path):
    rests = CredentialRests(creds(tmp_path), now=lambda: NOW)
    rests.observe(reading(account=account_digest(ACCOUNT_SECRET, "old token")))  # a recent run's, on the old token
    agent = Agent(account_digest(ACCOUNT_SECRET, "new token"), week=20.0)
    r = make_runner(tmp_path, agent, rests)
    assert r.deferral(Task("k", key="t0")) is None  # the old account's 99% does not rest the new one
    result = r.run(Task("k", key="t1"))
    assert result.ok and agent.seen == ["personal"]
    [read] = result.launch_result.quota
    assert (read.credential, read.account) == ("personal", agent.acct)
    r.run(Task("k", key="t2"))
    assert agent.asked == 1  # asked once a run


def test_the_reading_names_every_coding_agent_that_reports_one():
    import re

    from contraagent._internal.backends import backend_class, known_agents

    def reports(name: str) -> bool:  # read before a launch, or found in the agent's stream
        cls = backend_class(name)
        assert cls is not None
        return cls.usage_reading is not Backend.usage_reading or hasattr(cls.wire, "QuotaReading")

    doc = QuotaReading.__doc__ or ""
    sources = [name for name in known_agents() if reports(name)]
    assert {"claude", "codex", "omp", "omp-rpc", "opencode", "pi"} <= set(sources)
    for name in sources:
        assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", doc, re.IGNORECASE), name
