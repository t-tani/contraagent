"""`Backend.run`, the one run template, against fake CLIs: what every coding agent's launch
gets alike (its start, the CLI's version, a second look at stderr, the credential check,
the context window from the catalogue), and the one stop ladder (`refusal.classify_stop`)."""

import json
import os
import threading

import pytest

from contraagent import ConfigError, PipelineConfig, agent_task
from contraagent._internal.backends.claude.wire import StreamReader
from contraagent._internal.backends.opencode.wire import EventReader
from contraagent._internal.backends.process import stopped_by
from contraagent._internal.backends.refusal import classify_stop, parse_retry_after
from contraagent.backends import ClaudeBackend, Ending, Launch, LaunchResult, OmpBackend, OmpRpcBackend, OpencodeBackend, Signals, Stop
from contraagent.config import Limits
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
    assert result.quota_refusal is not None and result.quota_refusal.retry_after_s == 120.0
    assert result.started_at and result.cli_version == "2.1.296"


def claude_one_turn(answer: str) -> LaunchResult:
    reader = StreamReader(Limits())
    reader.feed({"type": "system", "subtype": "init", "session_id": "s-1"})
    reader.feed({"type": "result", "subtype": "success", "is_error": False, "result": answer, "num_turns": 1})
    return reader.result(Launch(prompt="x", label="t"), "claude", exit_code=0, killed=None)


@pytest.mark.parametrize(
    "answer",
    [
        "Bash(pytest -q)",
        "I will run the tests.\nBash(pytest -q)\nRead(report.txt)\nWrite(out.json)",
        "- `Read(src/app.py)`\n- `Edit(src/app.py)`",
        "```\nWrite(out.json)\n```",
    ],
)
def test_claude_s_one_turn_answer_of_written_tool_calls_is_hollow(answer):
    result = claude_one_turn(answer)
    assert result.stop is Stop.COMPLETED and result.hollow and not result.ok


@pytest.mark.parametrize(
    "answer",
    [
        "The function opens the file with `Read(path)` and returns its lines.",
        "To check it, I would use Bash(pytest -q) after the change.\nThe change itself is small.",
        "The hook is named so:\n\n```\nBash(rm:*)\n```\n\nIt matches every rm, so the rule denies it.\nNothing else changes.",
    ],
)
def test_claude_s_one_turn_answer_that_quotes_a_tool_call_is_not_hollow(answer):
    result = claude_one_turn(answer)
    assert result.stop is Stop.COMPLETED and not result.hollow and result.ok


def claude_stop(**result) -> Stop:
    reader = StreamReader(Limits())
    reader.feed({"type": "system", "subtype": "init", "session_id": "s-1"})
    reader.feed({"type": "result", **result})
    return reader.result(Launch(prompt="x", label="t"), "claude", exit_code=0, killed=None).stop


@pytest.mark.parametrize(
    "answer",
    [
        "Done: I added rate limiting to the /api endpoint.",
        "The client now backs off on a rate-limit response and on a quota exceeded error.",
        "Requests without a token now get 401; you've hit your usage limit is the message.",
        "Failed to authenticate is what the old handler logged; it now retries.",
        "Callers that are refused get a 403; the safeguard is in middleware.py.",
    ],
)
def test_claude_s_answer_that_mentions_a_limit_is_still_completed(answer):
    """A successful result's text is the answer, not the provider's words: a task about rate
    limits says "rate limit", and its launch completed."""
    assert claude_stop(subtype="success", is_error=False, result=answer, num_turns=5) is Stop.COMPLETED


@pytest.mark.parametrize(
    ("result", "stop"),
    [
        ({"subtype": "success", "is_error": True, "result": "You've hit your usage limit · resets 5pm"}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "You've hit your limit · resets 5pm"}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "You've hit your Opus limit · resets Mon 9am"}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "You've hit your fast limit · resets in 3m"}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "You're out of extra usage · resets 5pm"}, Stop.RATE_LIMITED),
        (
            {
                "subtype": "success",
                "is_error": True,
                "result": "API Error: Request rejected (429) · this may be a temporary capacity issue.",
            },
            Stop.RATE_LIMITED,
        ),
        (
            {
                "subtype": "success",
                "is_error": True,
                "result": "API Error: Server is temporarily limiting requests (not your usage limit) · x",
            },
            Stop.RATE_LIMITED,
        ),
        ({"subtype": "success", "is_error": True, "result": "Opus is experiencing high load. Switch to Sonnet."}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "API Error: the tool in rate_limit.py raised"}, Stop.API_ERROR),
        ({"subtype": "success", "is_error": False, "result": "x", "api_error_status": 429}, Stop.RATE_LIMITED),
        ({"subtype": "success", "is_error": True, "result": "Failed to authenticate. API Error: 401"}, Stop.AUTH_FAILED),
        ({"subtype": "success", "is_error": True, "result": "API Error: overloaded"}, Stop.API_ERROR),
    ],
)
def test_claude_s_error_result_is_read_in_its_words(result, stop):
    assert claude_stop(**result) is stop


#: What a hook or an MCP server may print on a failed launch's stderr: paths, a traceback,
#: a passing mention of a limit. No quota refusal among them.
NOISY_STDERR = """hook: running /work/hooks/rate_limit.py
Traceback (most recent call last):
  File "/work/billing/quota.py", line 429, in main
  File "/work/lib/ratelimit.py", line 12, in check
OSError: [Errno 122] Disk quota exceeded
mcp: server rate-limiter started; rate limiting is on
"""


@pytest.mark.parametrize("backend", [ClaudeBackend(), OmpBackend(trace=False), OmpRpcBackend()], ids=lambda b: type(b).__name__)
def test_a_traceback_or_a_path_on_stderr_does_not_rest_the_route(backend):
    result = LaunchResult(label="t", agent=backend.name, stop=Stop.ERROR, ok=False)
    backend.reclassify(result, NOISY_STDERR)
    assert result.stop is Stop.ERROR and result.quota_refusal is None


@pytest.mark.parametrize(
    ("backend", "words"),
    [
        (ClaudeBackend(), "You've hit your limit · resets 5pm"),
        (ClaudeBackend(), "You've hit your session limit · resets 5pm"),
        (ClaudeBackend(), "API Error: Request rejected (429) · this may be a temporary capacity issue."),
        (OmpBackend(trace=False), "429 Go usage limit exceeded, retry-after-ms=60000"),
        (OmpBackend(trace=False), 'Error: 429 {"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}'),
        (OmpBackend(trace=False), "This request would exceed the rate limit for your organization of 50 requests per minute."),
        (OmpRpcBackend(), "ChatGPT rate limit exceeded."),
    ],
    ids=lambda v: type(v).__name__ if not isinstance(v, str) else v[:30],
)
def test_a_quota_refusal_on_stderr_still_rests_the_route(backend, words):
    result = LaunchResult(label="t", agent=backend.name, stop=Stop.ERROR, ok=False)
    backend.reclassify(result, NOISY_STDERR + words + "\n")
    assert result.stop is Stop.RATE_LIMITED and result.quota_refusal is not None


OMP_TEXT_REFUSED = r"""
import sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
print("Working...", file=sys.stderr)
print("429 Go usage limit exceeded, retry-after-ms=60000", file=sys.stderr)
sys.exit(1)
"""

OMP_TEXT_ANSWER = r"""
import sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
print("Done: the client retries on rate limit exceeded and on 429 Too Many Requests.")
"""


def test_omp_text_mode_reads_a_refusal_by_its_exit_and_its_stderr(tmp_path):
    """omp 18.9 prints a refused message's `errorMessage` on stderr only and exits 1."""
    result = OmpBackend(base_env=path_of(fake_cli(tmp_path, "omp", OMP_TEXT_REFUSED)), trace=False).run(launch(tmp_path))
    assert result.stop == Stop.RATE_LIMITED and result.quota_refusal is not None and result.quota_refusal.retry_after_s == 60.0


def test_omp_text_mode_s_short_answer_that_mentions_a_limit_is_completed(tmp_path):
    result = OmpBackend(base_env=path_of(fake_cli(tmp_path, "omp", OMP_TEXT_ANSWER)), trace=False).run(launch(tmp_path))
    assert result.stop == Stop.COMPLETED and result.ok and "rate limit" in result.result_text


def test_claude_counts_the_events_it_does_not_know():
    reader = StreamReader(Limits())
    reader.feed({"type": "system", "subtype": "init", "session_id": "s-1"})
    reader.feed({"type": "brand_new_event"})
    reader.feed({"type": "result", "subtype": "success", "result": "ok"})
    result = reader.result(Launch(prompt="x", label="t"), "claude", exit_code=0, killed=None)
    # These events carry fewer fields than Claude Code's: those count too (`<event>.<field>`).
    types = {k: n for k, n in result.unread_events.items() if "." not in k}
    assert result.stop == Stop.COMPLETED and types == {"brand_new_event": 1}


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
    assert result.stop == Stop.RATE_LIMITED and result.quota_refusal is not None and result.quota_refusal.retry_after_s == 60.0
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
    assert result.stop == Stop.BUDGET and not result.ok and len(result.usage.calls) == 3


@pytest.mark.parametrize("value", [0, -1, 0.0, float("inf"), float("nan"), True])
def test_a_launch_s_deadline_is_a_number_of_seconds_above_0(value):
    with pytest.raises(ValueError, match="timeout_s"):
        Limits(timeout_s=value)
    errors: list[str] = []
    assert "timeout_s" not in PipelineConfig({"tasks": {"t": {"timeout_s": value}}}).task_tables(errors).get("t", {})
    assert errors and "timeout_s" in errors[0]
    with pytest.raises(ConfigError, match="timeout_s"):
        agent_task("t", instructions="x", max_turns=1, timeout_s=value)


def test_omp_rpc_passes_its_deadline_to_omp_in_whole_seconds_never_0(tmp_path):
    argv = OmpRpcBackend().argv(Launch(prompt="x", cwd=tmp_path, limits=Limits(timeout_s=0.5)))
    assert argv[argv.index("--max-time") + 1] == "1"


OMP_RPC_SILENT = r"""
import pathlib, sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
if "--mode" not in sys.argv:
    sys.exit(0)
pathlib.Path("started").write_text("")
sys.stdin.read()  # never sends ready; ends at stdin's EOF
"""


class StopOnceStarted(threading.Event):
    """A stop mark that is set once the fake omp has started: the request comes during the
    handshake, after the launch was let through."""

    def __init__(self, started) -> None:
        super().__init__()
        self.started = started

    def is_set(self) -> bool:
        return self.started.exists()


def test_omp_rpc_leaves_the_handshake_when_its_task_is_cancelled(tmp_path):
    backend = OmpRpcBackend(base_env=path_of(fake_cli(tmp_path, "omp", OMP_RPC_SILENT)))
    with stopped_by(StopOnceStarted(tmp_path / "started")):
        result = backend.run(launch(tmp_path))
    # Not the deadline's `timeout` 30 s later: the launch left on the stop request.
    assert result.stop is not Stop.TIMEOUT and "no ready frame" not in result.stderr_tail and not result.ok


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


#: opencode under load: on a pipe its list comes out cut short (it exits before the pipe
#: drains), to a file in full.
OPENCODE_CUT_ON_A_PIPE = r"""
import os, stat, sys
if sys.argv[1:2] == ["models"]:
    lines = [f"opencode/m{i}" for i in range(50)] + [f"opencode-go/m{i}" for i in range(30)]
    whole = stat.S_ISREG(os.fstat(1).st_mode)
    print("\n".join(lines if whole else lines[:60]))
"""


def test_opencode_s_catalogue_is_read_whole_when_a_pipe_would_cut_it(tmp_path):
    backend = OpencodeBackend(base_env=path_of(fake_cli(tmp_path, "opencode", OPENCODE_CUT_ON_A_PIPE)))
    listed = backend.catalogue()
    assert listed is not None and "opencode-go/m29" in listed and len(listed) == 80


#: opencode whose list holds the provider of the `opencode.json` of the directory it runs in,
#: unless project config is off.
OPENCODE_PROJECT = r"""
import os, sys
if sys.argv[1:2] == ["models"]:
    print("opencode/m")
    if os.path.exists("opencode.json") and not os.environ.get("OPENCODE_DISABLE_PROJECT_CONFIG"):
        print("project/m")
"""


def test_opencode_s_catalogue_leaves_out_the_project_config_its_launches_leave_out(tmp_path, monkeypatch):
    (tmp_path / "here").mkdir()
    (tmp_path / "here" / "opencode.json").write_text("{}")
    monkeypatch.chdir(tmp_path / "here")
    backend = OpencodeBackend(base_env=path_of(fake_cli(tmp_path, "opencode", OPENCODE_PROJECT)))
    assert backend.catalogue() == {"opencode/m"}


def test_opencode_s_quota_refusal_carries_its_cool_off():
    reader = EventReader("opencode-go/m")
    reader.feed({"type": "error", "error": {"name": "APIError", "data": {"message": "Go usage limit exceeded retry-after-ms=313534000"}}})
    result = reader.result(Launch(prompt="x", label="t", model="opencode-go/m"), "opencode", exit_code=0, killed=None)
    assert result.stop == Stop.RATE_LIMITED and result.quota_refusal is not None and result.quota_refusal.retry_after_s == 313534.0


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
        (Ending(error="rate limit exceeded", completed=True, saw_any=True, text="x"), Stop.COMPLETED),
        (Ending(exit_code=1, saw_any=True), Stop.ERROR),
        (Ending(exit_code=0, saw_any=False), Stop.LAUNCH_FAILED),
        (Ending(exit_code=0, saw_any=True), Stop.NO_OUTPUT),
        (Ending(exit_code=0, saw_any=True, text="answer"), Stop.COMPLETED),
    ],
)
def test_one_ladder_weighs_what_a_wire_said_in_one_order(ending, stop):
    assert classify_stop(ending, Signals()) is stop


def test_a_status_decides_alone_where_the_wire_says_so():
    words = Ending(status=500, error="rate limit exceeded", saw_any=True, text="x")
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


# --- what a backend makes once, however many launches ask together --------------------------


def test_threads_that_ask_together_get_one_version_one_catalogue_and_one_scratch_root(tmp_path, monkeypatch):
    from contraagent._internal.backends import base

    made: list[str] = []
    monkeypatch.setattr(base, "cli_version", lambda binary, env: made.append("version") or "1.0")

    class Counting(OmpBackend):
        def read_models(self):
            made.append("models")
            return {"p/m": 1000}

        def scratch_parent(self):
            made.append("scratch")
            return tmp_path / "scratch"

    backend = Counting(base_env={}, trace=False)
    start = threading.Barrier(8)
    got: list[tuple] = []

    def ask() -> None:
        start.wait()
        got.append((backend.version(), backend.models(), backend.scratch("t", "a").parent.parent))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(made) == ["models", "scratch", "version"]
    assert len(got) == 8 and len({str(g) for g in got}) == 1
    assert [p.name for p in (tmp_path / "scratch").iterdir()] == [got[0][2].name]
