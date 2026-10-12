"""Testing a pipeline without spending tokens: check the flow, then run it on the stub agent.

    pytest "$(contraagent docs --path)/examples/demo/test_demo.py"

`Pipeline.check` finds what is wrong before anything launches. `StubAgent`
replaces only the coding agent: the output checks, fix-up rounds, failover,
retries and the journal are the real ones, so these tests pin down the
flow's wiring. Whether the plugin's roles make a real LLM write good outputs
is for a live run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contraagent import Pipeline
from contraagent.docs.examples.demo.tasks import docs, docs_one_review
from contraagent.testing import StubAgent, fails, rate_limited

HERE = Path(__file__).resolve().parent

UNITS = ["alpha", "beta", "delta", "zeta"]


def summary(launch):
    """A reply decided per launch: delta's first summary has two points, its fix-up three."""
    points = ["parses a config file", "validates it", "reports errors"]
    return {"unit": launch.unit, "points": points[:2] if launch.unit == "delta" and not launch.resumed else points}


def stub() -> StubAgent:
    return StubAgent(
        {
            "summarize": summary,
            # A task key outranks its kind; the callable sees the model, so only the primary hop is rate limited.
            "summarize-beta": lambda launch: rate_limited() if launch.model == "primary-model" else summary(launch),
            "review": {"approved": True, "note": "Accurate."},
            "review-alpha": [fails(), {"approved": False, "note": "Too short."}],  # one reply per launch
            "revise": lambda launch: launch.params["summary"],
            "write_note": lambda launch: f"# {launch.unit}\n\n" + "\n".join(launch.params["summary"]["points"]) + "\n",
        }
    )


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "inputs").mkdir()
    for u in UNITS:
        (tmp_path / "inputs" / f"{u}.md").write_text(f"# {u}\nThe {u} component parses a config file.\n")
    return tmp_path


def test_the_flow_checks_clean():
    report = Pipeline(HERE / "pipeline.toml", backends=StubAgent().backends()).check(docs, units=UNITS)
    assert report.ok, report
    assert report.kinds == {"prepare": 4, "summarize": 4}  # what the flow creates before its first wait
    assert {"score", "review", "revise", "write_note", "report"} <= set(report.later_kinds)  # what its code reaches


def test_the_flow_runs_on_the_stub(inputs):
    agent = stub()
    report = Pipeline(HERE / "pipeline.toml", runs_dir=inputs / "runs", backends=agent.backends()).run(docs, units=UNITS)

    stops = {k: r.stop for k, r in report.results.items()}
    assert stops["python:prepare-zeta"] == "error"  # its input is malformed
    assert stops["summarize-zeta"] == "invalid_input"  # refused before launch: zeta's review loop ends there
    assert not any(launch.unit == "zeta" for launch in agent.launches)
    assert [launch.model for launch in agent.launches_of("summarize-beta")] == ["primary-model", "fallback-model"]
    assert [launch.resumed for launch in agent.launches_of("summarize-delta")] == [False, True]  # sent back by `three_points`
    assert "exactly three expected" in agent.launches_of("summarize-delta")[1].prompt
    assert len(agent.launches_of("review-alpha")) == 2  # retried after the scripted error; the review does not approve
    assert [stops[k] for k in ("revise-alpha", "review-alpha~2", "write_note-alpha")] == ["completed"] * 3  # pass 2 approves


def test_the_report_covers_the_approved_summaries(inputs):
    report = Pipeline(HERE / "pipeline.toml", runs_dir=inputs / "runs", backends=stub().backends()).run(docs, units=["alpha", "zeta"])
    assert report.value == "alpha: 3 points"  # the flow's return value: what the report task returned


def test_the_flow_without_waiting_refuses_what_a_failure_feeds(inputs):
    report = Pipeline(HERE / "pipeline.toml", runs_dir=inputs / "runs", backends=stub().backends()).run(docs_one_review, units=UNITS)
    stops = {k: r.stop for k, r in report.results.items()}
    assert {stops[k] for k in ("summarize-zeta", "review-zeta", "write_note-zeta", "python:report")} == {"invalid_input"}
