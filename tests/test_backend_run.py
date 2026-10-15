"""`Backend.run`, the one run template, against fake CLIs: what every coding agent's launch
gets alike (its start, the CLI's version, a second look at stderr, the credential check,
the context window from the catalogue), and the one stop ladder (`refusal.classify_stop`)."""

import json
import os

import pytest

from contraagent import ClaudeBackend, Launch, Limits, OmpBackend, OmpRpcBackend, OpencodeBackend, Stop
from contraagent.backends.claude.wire import StreamReader
from contraagent.backends.opencode.wire import EventReader
from contraagent.backends.refusal import Ending, Signals, classify_stop, parse_retry_after
from test_backends_offline import fake_cli


def path_of(bindir) -> dict[str, str]:
    return {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"}


def launch(tmp_path, **kw) -> Launch:
    return Launch(prompt="hello", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30), **kw)


# --- every agent's launch gets its start and its CLI's version ----------------------------

OMP_TEXT = r"""
import sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
print("Done.")
"""


def test_every_launch_records_its_start_and_the_cli_version(tmp_path):
    """Only claude and codex recorded them; every backend's run is the template now."""
    result = OmpBackend(base_env=path_of(fake_cli(tmp_path, "omp", OMP_TEXT)), trace=False).run(launch(tmp_path))
    assert result.ok and result.result_text == "Done."
    assert result.started_at and result.cli_version == "18.9.1"


# --- claude: a quota refusal on stderr --------------------------------------------------------

CLAUDE_REFUSED = r"""
import sys
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)"); sys.exit(0)
print("You've hit your usage limit · resets 5pm, retry-after: 120", file=sys.stderr)
sys.exit(1)
"""


def test_claude_reads_a_quota_refusal_on_stderr(tmp_path):
    """A claude that dies at start on a quota prints only on stderr: `rate_limited`, in the
    failover path, not a launch failure (`ClaudeBackend.reclassify` was never called)."""
    result = ClaudeBackend(base_env=path_of(fake_cli(tmp_path, "claude", CLAUDE_REFUSED))).run(launch(tmp_path))
    assert result.stop == Stop.RATE_LIMITED and not result.ok
    assert result.rate_limit is not None and result.rate_limit.status == "quota" and result.rate_limit.retry_after_s == 120.0
    assert result.started_at and result.cli_version == "2.1.296"


def test_claude_counts_the_events_it_does_not_know():
    reader = StreamReader(Limits())
    reader.feed({"type": "system", "subtype": "init", "session_id": "s-1"})
    reader.feed({"type": "brand_new_event"})
    reader.feed({"type": "result", "subtype": "success", "result": "ok"})
    result = reader.result(Launch(prompt="x", label="t"), "claude", exit_code=0, killed=None)
    assert result.stop == Stop.COMPLETED and result.unread_events == {"brand_new_event": 1}


# --- omp-rpc: the template's second look, credential check and catalogue --------------------

OMP_RPC = r"""
import json, sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
if sys.argv[1:3] == ["models", "--json"]:
    print(json.dumps({"models": [{"selector": "p/m", "contextWindow": 300000}]})); sys.exit(0)
def send(o):
    print(json.dumps(o), flush=True)
send({"type": "ready", "supportedProtocolVersions": [1]})
for line in sys.stdin:
    req = json.loads(line)
    if req["type"] == "prompt":
        if "quota" in req["message"]:
            print("429 Go usage limit exceeded, retry-after-ms=60000", file=sys.stderr, flush=True)
            sys.exit(1)
        if "spend" in req["message"]:
            for n in range(5):
                usage = {"input": 10, "output": 5, "cacheRead": 0, "cacheWrite": 0, "cost": {"total": 0.01}}
                send({"type": "message_end", "message": {"role": "assistant", "model": "m", "usage": usage}})
        send({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "done"}})
        send({"type": "agent_end", "isTerminal": True})
    elif req["type"] == "get_state":
        send({"type": "response", "id": req["id"], "command": "get_state", "success": True, "data": {"sessionId": "s-1"}})
"""


@pytest.fixture
def rpc_env(tmp_path):
    return path_of(fake_cli(tmp_path, "omp", OMP_RPC))


def test_omp_rpc_reads_a_quota_refusal_on_stderr(tmp_path, rpc_env):
    result = OmpRpcBackend(base_env=rpc_env).run(Launch(prompt="quota", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30)))
    assert result.stop == Stop.RATE_LIMITED and result.rate_limit is not None and result.rate_limit.retry_after_s == 60.0
    assert "429 Go usage limit exceeded" in result.stderr_tail


def test_omp_rpc_takes_the_context_window_from_the_catalogue(tmp_path, rpc_env):
    """get_state names no window here: the one `omp models --json` lists for the model."""
    result = OmpRpcBackend(base_env=rpc_env).run(launch(tmp_path))
    assert result.ok and result.session_id == "s-1" and result.context_window == 300_000
    assert result.started_at and result.cli_version == "18.9.1" and result.credential == "ambient"


def test_omp_rpc_checks_the_credential_the_agent_reports(tmp_path, rpc_env):
    class Mismatched(OmpRpcBackend):
        def attest(self, launch_result, credential):
            return "the agent used another login"

    result = Mismatched(base_env=rpc_env).run(launch(tmp_path))
    assert result.stop == Stop.CREDENTIAL_MISMATCH and not result.ok and "another login" in result.stderr_tail


def test_omp_rpc_ends_a_launch_past_its_cost_cap(tmp_path, rpc_env):
    limits = Limits(timeout_s=30, max_budget_usd=0.025)
    result = OmpRpcBackend(base_env=rpc_env).run(Launch(prompt="spend", label="t", model="p/m", cwd=tmp_path, limits=limits))
    assert result.stop == Stop.BUDGET and not result.ok and result.usage.n_calls == 3


# --- opencode: its catalogue's time limit, its refusal's cool-off ------------------------------

OPENCODE_SLOW = r"""
import sys, time
if sys.argv[1:2] == ["models"]:
    time.sleep(5)
    print("p/m")
"""


def test_opencode_s_catalogue_waits_its_own_time_limit(tmp_path):
    backend = OpencodeBackend(base_env=path_of(fake_cli(tmp_path, "opencode", OPENCODE_SLOW)))
    assert OpencodeBackend.catalogue_timeout_s == 60.0
    backend.catalogue_timeout_s = 0.5
    assert backend.read_models() is None


def test_opencode_s_quota_refusal_carries_its_cool_off():
    reader = EventReader("opencode-go/m")
    reader.feed({"type": "error", "error": {"name": "APIError", "data": {"message": "Go usage limit exceeded retry-after-ms=313534000"}}})
    result = reader.result(Launch(prompt="x", label="t", model="opencode-go/m"), "opencode", exit_code=0, killed=None)
    assert result.stop == Stop.RATE_LIMITED and result.rate_limit is not None and result.rate_limit.retry_after_s == 313534.0


# --- the one ladder ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ending", "stop"),
    [
        (Ending(killed=Stop.TIMEOUT, status=429), Stop.TIMEOUT),
        (Ending(status=429, failed=True, saw_any=True), Stop.RATE_LIMITED),
        (Ending(error="rate limit exceeded", saw_any=True, text="x"), Stop.RATE_LIMITED),
        (Ending(status=401, failed=True, saw_any=True), Stop.AUTH_FAILED),
        (Ending(refused=True, failed=True, saw_any=True), Stop.REFUSED),
        (Ending(aborted=True, failed=True, saw_any=True), Stop.ABORTED),
        (Ending(capped=Stop.MAX_TURNS, failed=True, saw_any=True), Stop.MAX_TURNS),
        (Ending(failed=True, saw_any=True), Stop.API_ERROR),
        (Ending(completed=True, saw_any=True), Stop.COMPLETED),
        (Ending(exit_code=1, saw_any=True), Stop.ERROR),
        (Ending(exit_code=0, saw_any=False), Stop.LAUNCH_FAILED),
        (Ending(exit_code=0, saw_any=True), Stop.NO_OUTPUT),
        (Ending(exit_code=0, saw_any=True, text="answer"), Stop.COMPLETED),
    ],
)
def test_one_ladder_weighs_what_a_wire_said_in_one_order(ending, stop):
    assert classify_stop(ending, Signals()) is stop


def test_a_status_decides_alone_where_the_wire_says_so():
    words = Ending(status=500, error="rate limit", saw_any=True, text="x")
    assert classify_stop(words, Signals(status_decides=True)) is Stop.COMPLETED
    assert classify_stop(words, Signals()) is Stop.RATE_LIMITED


def test_silence_reads_as_a_failed_start_for_an_agent_that_says_so():
    quiet = Signals(silence_is_startup=True, nonzero_exit_is_error=False)
    assert classify_stop(Ending(exit_code=1), quiet) is Stop.LAUNCH_FAILED
    assert classify_stop(Ending(exit_code=0), quiet) is Stop.NO_OUTPUT
    assert classify_stop(Ending(exit_code=1, saw_any=True), quiet) is Stop.NO_OUTPUT


def test_a_cool_off_is_read_in_either_form():
    assert parse_retry_after("retry-after-ms=1500") == 1.5
    assert parse_retry_after('{"retry_after": 30}') == 30.0
    assert parse_retry_after("no cool-off") is None
    assert json.dumps(parse_retry_after("")) == "null"
