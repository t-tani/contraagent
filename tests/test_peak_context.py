"""Peak context: the whole input of a launch's largest API call, and the warning past
`context_warn_pct`% of `context_budget`, which stops nothing."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Limits, Pipeline, PipelineConfig, agent_task
from contraagent.routing.config import ConfigError
from contraagent.testing import StubAgent, writes


class Note(BaseModel):
    note: str


def test_limits_warn_past_the_percent_of_the_budget():
    limits = Limits(context_budget=100_000, context_warn_pct=80)
    assert not limits.context_warned(80_000) and limits.context_warned(80_001)
    assert not limits.context_warned(None)  # the agent's stream told no peak context
    assert not Limits(context_budget=100_000).context_warned(99_000)  # no warning asked for


@pytest.mark.parametrize(("pct", "budget"), [(0, 1000), (100, 1000), (True, 1000), (80, None)])
def test_limits_refuse_a_warning_that_is_not_a_percent_of_a_budget(pct, budget):
    with pytest.raises(ValueError, match="context_warn_pct"):
        Limits(context_budget=budget, context_warn_pct=pct)


def run(tmp_path, config: dict, *, peak: int, **declared):
    task = agent_task("summarize", instructions="x", output=Note, max_turns=1, timeout_s=10, **declared)
    stub = StubAgent({"summarize": writes({"note": "n"}, peak_context=peak)})
    lines: list[str] = []

    def flow():
        yield task("alpha")

    report = Pipeline(PipelineConfig(config), runs_dir=tmp_path / "runs", cwd=tmp_path, backends=stub.backends(), log=lines.append).run(
        flow
    )
    [row] = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    return report, row, lines


def test_an_attempt_past_its_warning_is_recorded_and_logged_and_not_stopped(tmp_path):
    report, row, lines = run(tmp_path, {}, peak=130_000, context_budget=150_000, context_warn_pct=80)
    assert report.ok and row["ok"] and row["stop"] == "completed"
    assert (row["usage"]["peak_context"], row["context_budget"], row["context_warned"]) == (130_000, 150_000, True)
    assert row["hops"][0]["usage"]["peak_context"] == 130_000
    [line] = [x for x in lines if x.startswith("[context]")]
    assert line == "[context] summarize-alpha: peak context 130000 tokens (86% of context_budget 150000), past context_warn_pct 80%"


def test_an_attempt_under_its_warning_is_not_warned(tmp_path):
    _, row, lines = run(tmp_path, {"tasks": {"summarize": {"context_budget": 150_000, "context_warn_pct": 90}}}, peak=130_000)
    assert (row["usage"]["peak_context"], row["context_budget"], row["context_warned"]) == (130_000, 150_000, False)
    assert not [x for x in lines if x.startswith("[context]")]


def test_the_defaults_warning_holds_for_each_kind_with_a_budget(tmp_path):
    config = {"defaults": {"context_warn_pct": 50}, "tasks": {"summarize": {"context_budget": 200_000}}}
    _, row, _ = run(tmp_path, config, peak=120_000)
    assert row["context_warned"]


def test_without_a_budget_the_row_has_none_and_no_warning(tmp_path):
    _, row, _ = run(tmp_path, {"defaults": {"context_warn_pct": 50}}, peak=120_000)
    assert (row["usage"]["peak_context"], row["context_budget"], row["context_warned"]) == (120_000, None, False)


def test_a_warning_without_a_budget_is_refused_before_anything_launches(tmp_path):
    task = agent_task("summarize", instructions="x", output=Note, max_turns=1, timeout_s=10, context_warn_pct=80)

    def flow():
        yield task("alpha")

    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, backends=StubAgent().backends()).check(flow)
    assert not report.ok
    assert any("kind summarize has context_warn_pct = 80 but no context_budget" in e for e in report.errors), report.errors


@pytest.mark.parametrize("value", [0, 100, 85.5, True])
def test_a_warning_that_is_not_a_whole_percent_is_a_config_error(value):
    errors: list[str] = []
    assert "context_warn_pct" not in PipelineConfig({"tasks": {"summarize": {"context_warn_pct": value}}}).task_tables(errors).get(
        "summarize", {}
    )
    assert errors and "context_warn_pct" in errors[0]
    errors = []
    PipelineConfig({"defaults": {"context_warn_pct": value}}).defaults(errors)
    assert errors and "[defaults].context_warn_pct" in errors[0]
    with pytest.raises(ConfigError, match="context_warn_pct"):
        agent_task("summarize", instructions="x", output=Note, max_turns=1, timeout_s=10, context_budget=1000, context_warn_pct=value)
