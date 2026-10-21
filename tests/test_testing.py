"""`contraagent._internal.testing.StubAgent`: scripted replies, played through the real runner."""

import json
import os
import sys

import pytest
from pydantic import BaseModel

from contraagent import CommandValidator, Pipeline, PipelineConfig, agent_task
from contraagent.backends import Stop
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent, fails, writes, writes_nothing


class Verdict(BaseModel):
    approved: bool


@pytest.fixture
def plugin_dir(tmp_path):
    new_plugin(tmp_path / "plugins" / "review")
    return tmp_path / "plugins" / "review"


def run(tmp_path, agent, flow, config=None):
    return Pipeline(PipelineConfig(config or {}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(flow)


def test_replies_by_key_kind_list_and_callable(tmp_path, plugin_dir):
    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60, retries=1, retry_backoff_base=0)
    handles = {}

    def flow():
        for u in ("a", "b", "c"):
            handles[u] = review(u)

    agent = StubAgent(
        {
            "review": Verdict(approved=True),
            "review-b": [fails(Stop.ERROR), {"approved": False}],
            "review-c": lambda launch: {"approved": launch.unit == "c"},
        }
    )
    report = run(tmp_path, agent, flow)
    assert report.ok, report.failed
    assert [handles[u].output.approved for u in "abc"] == [True, False, True]
    assert [launch.n for launch in agent.launches_of("review-b")] == [1, 2]


def test_an_output_left_off_contract_is_sent_back_then_refused(tmp_path, plugin_dir):
    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60, retries=0)
    agent = StubAgent({"review": [writes_nothing(), "not json", {"approved": "maybe"}]})
    report = run(tmp_path, agent, lambda: review("a"), config={"defaults": {"agent": "pi"}})  # no stop hook: runner rounds
    assert report.results["review-a"].stop == "invalid_output"
    assert [launch.resumed for launch in agent.launches] == [False, True, True, True]  # the last reply repeats


def test_an_unscripted_task_says_what_is_scripted(tmp_path, plugin_dir):
    review = agent_task("review", plugin=plugin_dir, output=str, max_turns=5, timeout_s=60, retries=0)
    report = run(tmp_path, StubAgent({"summarize": "x"}), lambda: review("a"))
    assert report.results["review-a"].reason == "stub: no reply scripted for review-a (kind review); scripted: summarize"


def test_a_json_list_output_and_the_transcript(tmp_path, plugin_dir):
    from pydantic import RootModel

    Points = RootModel[list[str]]
    review = agent_task("review", plugin=plugin_dir, output=Points, max_turns=5, timeout_s=60)
    report = run(tmp_path, StubAgent({"review": writes(["a", "b"])}), lambda: review("a"))
    assert report.ok
    stream = [json.loads(line) for line in (report.run_dir / "streams" / "review-a.stream.jsonl").read_text().splitlines()]
    assert stream[0]["type"] == "launch" and stream[-1]["message"]["content"][0]["text"] == "stub: wrote the output"


def test_the_transcript_is_readable_in_each_agents_stream_format(tmp_path, plugin_dir):
    from contraagent.monitor import Monitor

    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60)
    for agent in ("claude", "omp"):
        report = run(
            tmp_path / agent, StubAgent({"review": {"approved": True}}), lambda: review("a"), config={"defaults": {"agent": agent}}
        )
        events = Monitor(report.run_dir.parent).stream(report.run_id, "review-a", 0)[0]["events"]
        kinds = [e["type"] for e in events]
        assert kinds.count("tool_execution_start") == 2 and kinds.count("tool_execution_end") == 2, (agent, kinds)
        assert any(e.get("delta") == "stub: wrote the output" or "stub: wrote" in str(e) for e in events)


def test_a_reply_list_starts_over_in_each_run(tmp_path, plugin_dir):
    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60, retries=0)
    agent = StubAgent({"review": [{"approved": "maybe"}, {"approved": True}]})
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path)
    for run_id in ("one", "two"):
        pipeline.run(lambda: review("a"), run_id=run_id)
        assert [launch.n for launch in agent.launches_of("review-a", run=run_id)] == [1, 2]


def test_each_coding_agent_name_answers_as_itself(tmp_path, plugin_dir):
    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60)
    agent = StubAgent({"review": {"approved": True}})
    report = run(tmp_path, agent, lambda: review("a"), config={"defaults": {"agent": "omp"}})
    row = json.loads((report.run_dir / "journal.jsonl").read_text().splitlines()[0])
    assert row["agent"] == "omp" and len(agent.launches) == 1  # one record, shared by every name


@pytest.mark.skipif(sys.platform == "win32", reason="a named pipe (os.mkfifo) is POSIX")
def test_a_stop_hook_past_the_launchs_timeout_ends_it_as_a_timeout(tmp_path, plugin_dir, monkeypatch):
    """The stub's Stop hooks run within the launch's `timeout_s`, as the agent it plays: a hook
    still running at the end of it ends the launch with `Stop.TIMEOUT`, its processes stopped."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    fifo = tmp_path / "never-written"
    os.mkfifo(fifo)  # opening it to read waits for a writer, and the test opens none
    # In the Stop hook (CLAUDE_PLUGIN_ROOT set) the check waits on the pipe; the runner's own check after the launch does not.
    waits = "import os, sys; os.environ.get('CLAUDE_PLUGIN_ROOT') and open(sys.argv[1])"
    blocks = CommandValidator([sys.executable, "-c", waits, str(fifo)], name="blocks")
    review = agent_task("review", plugin=plugin_dir, output=str, validators=[blocks], max_turns=5, timeout_s=1, retries=0)
    agent = StubAgent({"review": "text"})
    report = run(tmp_path, agent, lambda: review("a"))
    assert report.results["review-a"].stop == "timeout"
    assert report.results["review-a"].reason == "stub: past timeout_s (1s) while a Stop hook ran"
    assert len(agent.launches) == 1
