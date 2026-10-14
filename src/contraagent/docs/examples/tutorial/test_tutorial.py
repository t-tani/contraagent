"""The tutorial's tests: its flows checked, and run on the stub agent.

pytest "$(contraagent docs --path)/examples/tutorial/test_tutorial.py"
"""

from __future__ import annotations

from pathlib import Path

from contraagent import Pipeline
from contraagent.docs.examples.tutorial.tasks import triage_all, triage_and_plan
from contraagent.testing import StubAgent

HERE = Path(__file__).resolve().parent

REPORTS = ["login-timeout", "csv-export", "dark-mode"]


def triage(launch):
    """A reply decided per launch: login-timeout is high severity, and its first summary is too long."""
    if launch.unit != "login-timeout":
        return {"severity": "low", "area": "settings", "summary": "Icons are hard to see in dark mode."}
    summary = "Login fails on slow networks." if launch.resumed else "Login fails " + "and fails " * 15 + "again."
    return {"severity": "high", "area": "login", "summary": summary}


def stub() -> StubAgent:
    return StubAgent(
        {
            "triage": triage,
            "plan_fix": {"cause": "The login request times out after 30 seconds.", "steps": ["Raise the timeout."]},
        }
    )


def test_the_flows_check_clean():
    pipeline = Pipeline(HERE / "pipeline.toml", backends=StubAgent().backends())
    assert pipeline.check(triage_all, reports=REPORTS).ok
    report = pipeline.check(triage_and_plan, reports=REPORTS)
    assert report.ok, report
    assert {"plan_fix", "write_table"} <= set(report.later_kinds)  # created after the first wait


def test_only_a_high_severity_report_gets_a_plan(tmp_path):
    agent = stub()
    report = Pipeline(HERE / "pipeline.toml", runs_dir=tmp_path, backends=agent.backends()).run(triage_and_plan, reports=REPORTS)
    assert report.ok
    assert [launch.key for launch in agent.launches if launch.kind == "plan_fix"] == ["plan_fix-login-timeout"]
    assert agent.launches_of("plan_fix-login-timeout")[0].model == "claude-opus-5-5"  # [tasks.plan_fix] in pipeline.toml


def test_a_long_summary_goes_back_to_the_same_session(tmp_path):
    agent = stub()
    Pipeline(HERE / "pipeline.toml", runs_dir=tmp_path, backends=agent.backends()).run(triage_all, reports=REPORTS)
    first, fix = agent.launches_of("triage-login-timeout")
    assert (first.resumed, fix.resumed) == (False, True)
    assert "summary: at most 25 words" in fix.prompt  # what `short_summary` returned


def test_the_table_lists_the_most_severe_first(tmp_path):
    report = Pipeline(HERE / "pipeline.toml", runs_dir=tmp_path, backends=stub().backends()).run(triage_and_plan, reports=REPORTS)
    rows = report.value.splitlines()[2:]  # the flow's return value: the table write_table returned
    assert [row.split(" | ")[0] for row in rows] == ["| login-timeout", "| csv-export", "| dark-mode"]
