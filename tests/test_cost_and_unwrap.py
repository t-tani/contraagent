"""What a task's fix-up rounds cost, and a JSON output taken out of a final message that wraps it."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.contracts.contract import unwrap_json
from contraagent.backends import Stop
from contraagent.testing import Reply, StubAgent, writes


class Verdict(BaseModel):
    approved: bool
    note: str


def once_short():
    """A validator that refuses the first output it sees: the task takes a fix-up round."""
    seen: list[int] = []

    def short_note(path, value: Verdict):
        seen.append(1)
        return ["note: too long"] if len(seen) == 1 else []

    return short_note


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def launches(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "launches.jsonl").read_text().splitlines()]


def run(tmp_path, agent, flow, config=None, log=None):
    return Pipeline(
        PipelineConfig(config or {}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=log or (lambda line: None)
    ).run(flow)


# --- the cost of fix-up rounds ---------------------------------------------------------


@pytest.mark.parametrize("name", ["claude", "omp"])
def test_a_fix_up_round_is_counted_once_however_the_coding_agent_reports_its_cost(tmp_path, name):
    """Claude Code reports a resumed session's cost so far, omp each launch's own: either way
    the attempt costs what its two rounds cost, $0.01 each."""
    review = agent_task("review", instructions="Review.", output=Verdict, validators=[once_short()], agent=name, max_turns=3, timeout_s=60)
    stub = StubAgent({"review": writes({"approved": True, "note": "ok"}, cost_usd=0.01)})
    report = run(tmp_path, stub, lambda: review("a"))
    assert report.ok, report.failed
    [row] = journal(report)
    assert row["rounds"] == 2 and row["agent"] == name
    assert row["cost_usd"] == pytest.approx(0.02)
    assert row["hops"][0]["cost_usd"] == pytest.approx(0.02)  # the model-share view sums these
    [launch] = launches(report)
    assert launch["round_costs"] == pytest.approx([0.01, 0.01])


def test_failover_hops_are_separate_sessions_and_add_up(tmp_path):
    """Each hop is a session of its own: a failed hop's cost adds to the next hop's."""
    review = agent_task("review", instructions="Review.", output=Verdict, agent="claude", max_turns=3, timeout_s=60)
    config = {"tasks": {"review": {"fallbacks": [{"agent": "omp", "model": "m2"}]}}}

    def reply(launch):
        if launch.model == "m2":
            return writes({"approved": True, "note": "ok"}, cost_usd=0.02)
        return Reply(stop=Stop.ERROR, reason="broke", cost_usd=0.01)

    report = run(tmp_path, StubAgent({"review": reply}), lambda: review("a"), config)
    assert report.ok, report.failed
    [row] = journal(report)
    assert [h["cost_usd"] for h in row["hops"]] == pytest.approx([0.01, 0.02])
    assert row["cost_usd"] == pytest.approx(0.03)


# --- a JSON output taken out of a final message ----------------------------------------

WRAPPED = 'Here is the final output.\n\n```json\n{"approved": true, "note": "fine"}\n```\n\nLet me know if anything else is needed.'


def classify(**options):
    return agent_task("classify", instructions="Classify.", output=Verdict, output_from="message", max_turns=2, timeout_s=60, **options)


def test_unwrap_takes_the_document_out_of_the_message_in_one_round(tmp_path):
    task = classify(unwrap=True)
    handle = {}
    lines: list[str] = []
    report = run(tmp_path, StubAgent({"classify": WRAPPED}), lambda: handle.setdefault("a", task("a")), log=lines.append)
    assert report.ok, report.failed
    assert handle["a"].output == Verdict(approved=True, note="fine")
    path = handle["a"].path
    assert json.loads(path.read_text()) == {"approved": True, "note": "fine"}
    assert path.with_name(path.name + ".message.txt").read_text() == WRAPPED  # the whole message, kept
    [row] = journal(report)
    assert row["rounds"] == 1
    assert launches(report)[0]["unwrapped"] is True
    assert any("output unwrapped from the final message" in line for line in lines)


def test_without_unwrap_the_wrapped_message_goes_back_and_the_end_line_says_why(tmp_path):
    task = classify()
    lines: list[str] = []
    stub = StubAgent({"classify": [WRAPPED, '{"approved": true, "note": "fine"}']})
    report = run(tmp_path, stub, lambda: task("a"), log=lines.append)
    assert report.ok, report.failed
    [row] = journal(report)
    assert row["rounds"] == 2
    [end] = [line for line in lines if line.startswith("[end]")]
    assert "2 rounds (round 1: " in end and "not valid JSON" in end


def test_unwrap_needs_a_json_output_from_the_message_and_enters_the_definition():
    with pytest.raises(TypeError, match="unwrap takes a JSON output"):
        agent_task("x", instructions="x", output=Verdict, unwrap=True, max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="unwrap takes a JSON output"):
        agent_task("x", instructions="x", output=str, output_from="message", unwrap=True, max_turns=1, timeout_s=1)
    assert classify(unwrap=True).digest() != classify().digest()
    assert "unwrap" not in classify()._defined()  # an existing task keeps its fingerprint


@pytest.mark.parametrize(
    "message, document",
    [
        ('{"a": 1}', '{"a": 1}'),
        ('Here it is:\n{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": [1, 2]}\n```\nThanks.', '{"a": [1, 2]}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('```python\nprint(1)\n```\n{"b": 2}', '{"b": 2}'),
        ('The answer {"a": 1}, as in [1].', '{"a": 1}'),  # the longest, not a [1] after it
        ('[{"a": 1}, {"a": 2}] done', '[{"a": 1}, {"a": 2}]'),
        ("no document here", None),
        ('cut off {"a": ', None),
    ],
)
def test_unwrap_json(message, document):
    assert unwrap_json(message) == document


def test_the_end_line_names_the_cause_whatever_the_run_directory_s_path(tmp_path):
    deep = tmp_path / ("very-long-directory-name-" * 8)
    task = classify()
    lines: list[str] = []
    stub = StubAgent({"classify": [WRAPPED, '{"approved": true, "note": "fine"}']})
    run(deep, stub, lambda: task("a"), log=lines.append)
    [end] = [line for line in lines if line.startswith("[end]")]
    assert "round 1: out/classify/" in end and "not valid JSON" in end and str(deep) not in end
