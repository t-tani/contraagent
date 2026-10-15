"""Peak context: the whole input of a launch's largest API call, and the warning past
`context_warn_pct`% of `context_budget`, which stops nothing."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Launch, Limits, OmpBackend, OpencodeBackend, PiBackend, Pipeline, PipelineConfig, Stop, agent_task
from contraagent.backends.base import Backend, window_of
from contraagent.backends.launch import CallUsage, LaunchResult, Usage
from contraagent.backends.omp.catalogue import parse_models as omp_models
from contraagent.backends.opencode.catalogue import parse_models as opencode_models
from contraagent.backends.wire import EventFold
from contraagent.backends.pi import agent_dir
from contraagent.contracts import fold_spend
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


def launch_on(model: str, peak: int, window: int | None) -> LaunchResult:
    return LaunchResult(label="t", model=model, usage=Usage(calls=[CallUsage(model, peak, 0, 0, 1)]), context_window=window)


def test_context_pct_is_of_the_window_the_coding_agent_reports():
    """A model whose name does not say its window is measured against the window reported for it."""
    result = launch_on("claude-sonnet-5-5", 500_000, 1_000_000)
    assert result.context_pct == 50.0 and result.as_dict()["context_pct"] == 50.0
    assert launch_on("claude-sonnet-5-5", 500_000, None).context_pct is None  # no window reported
    assert LaunchResult(label="t", context_window=1_000_000).context_pct is None  # no API call read


def test_folded_launches_keep_the_window_of_the_peak_context():
    assert fold_spend(launch_on("big", 900_000, 1_000_000), launch_on("small", 100_000, 200_000)).context_pct == 90.0
    assert fold_spend(launch_on("big", 50_000, 1_000_000), launch_on("small", 100_000, 200_000)).context_pct == 50.0
    assert fold_spend(launch_on("big", 500_000, 1_000_000), launch_on("big", 100_000, None)).context_window == 1_000_000  # a round
    assert fold_spend(launch_on("big", 500_000, None), launch_on("small", 100_000, 200_000)).context_pct is None


def test_the_journal_records_the_reported_window_beside_the_peak_context(tmp_path):
    task = agent_task("summarize", instructions="x", output=Note, max_turns=1, timeout_s=10)
    stub = StubAgent({"summarize": writes({"note": "n"}, peak_context=250_000, context_window=1_000_000)})

    def flow():
        yield task("alpha")

    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, backends=stub.backends()).run(flow)
    [row] = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    assert (row["usage"]["peak_context"], row["usage"]["context_window"]) == (250_000, 1_000_000)
    assert row["hops"][0]["usage"]["context_window"] == 1_000_000
    [launch] = [json.loads(line) for line in (report.run_dir / "launches.jsonl").read_text().splitlines()]
    assert (launch["context_window"], launch["context_pct"]) == (1_000_000, 25.0)


FIXTURES = Path(__file__).parent / "fixtures"


def test_omp_s_catalogue_lists_each_model_s_window():
    """`omp models --json`, as omp 18.9.1 prints it."""
    models = omp_models((FIXTURES / "omp" / "18.9.1" / "models.json").read_text())
    assert models == {"anthropic/claude-haiku-5-5": 100_000, "anthropic-wif/claude-haiku-5-5": 1_000_000, "opencode-go/omen-alpha": None}
    assert omp_models("not json") == {}


def test_opencode_s_catalogue_lists_each_model_s_window():
    """`opencode models --verbose`, as opencode 1.19.0 prints it: `limit.context`, not `limit.input`."""
    models = opencode_models((FIXTURES / "opencode" / "1.19.0" / "models-verbose.txt").read_text())
    assert models == {"opencode/gpt-5.6-luna": 1_050_000, "opencode-go/claude-haiku-5-5": 1_000_000}
    assert opencode_models("opencode/a\nopencode/b\n") == {"opencode/a": None, "opencode/b": None}  # the plain list


def test_pi_s_model_files_list_each_model_s_window(tmp_path):
    """pi 1.2.0's `models-store.json`, and a custom provider's `models.json` over it."""
    (tmp_path / "models-store.json").write_text((FIXTURES / "pi" / "1.2.0" / "models-store.json").read_text())
    custom = {"openai": {"models": [{"id": "gpt-5.6-luna", "contextWindow": 128_000}]}, "local": {"models": [{"id": "small"}]}}
    (tmp_path / "models.json").write_text(json.dumps({"providers": custom}))
    assert agent_dir.windows(tmp_path) == {"anthropic/claude-haiku-5-5": 1_000_000, "openai/gpt-5.6-luna": 128_000}
    assert agent_dir.windows(tmp_path / "none") == {}


def test_a_model_is_found_as_it_was_launched():
    windows = {"anthropic/claude-haiku-5-5": 100_000, "proxy/claude-haiku-5-5": 1_000_000, "openai/gpt-5.6-luna": 272_000, "b/m-v1:0": 8}
    assert window_of(windows, "openai/gpt-5.6-luna") == 272_000
    assert window_of(windows, "openai/gpt-5.6-luna:high") == 272_000  # a reasoning suffix
    assert window_of(windows, "b/m-v1:0") == 8  # a `:` of the id itself
    assert window_of(windows, "gpt-5.6-luna") == 272_000  # a bare id one provider lists
    assert window_of(windows, "claude-haiku-5-5") is None  # two providers, two windows
    assert window_of(windows, "openai/other") is None


class Reported(EventFold):
    """A wire that reported one API call of `context` tokens and, maybe, its window."""

    def __init__(self, context: int, window: int | None):
        super().__init__()
        self.context, self.window = context, window

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        return launch_on(launch.model, self.context, self.window)


class Listed(Backend):
    """A coding agent whose stream reports `stream_window` and whose catalogue is `listed`."""

    name = "listed"

    def __init__(self, listed: dict[str, int | None] | None, stream_window: int | None = None):
        super().__init__(binary=sys.executable)
        self.listed, self.stream_window, self.reads = listed, stream_window, 0

    def argv(self, launch: Launch) -> list[str]:
        return [self.binary, "-c", ""]

    def env(self, launch: Launch) -> dict[str, str]:
        return {}

    def read_models(self) -> dict[str, int | None] | None:
        self.reads += 1
        return self.listed

    def fold(self, launch: Launch) -> EventFold:
        return Reported(50_000, self.stream_window)


def launch_of(backend: Backend, tmp_path, model: str = "p/big") -> LaunchResult:
    return backend.run(Launch(prompt="x", label="t", cwd=tmp_path, model=model, limits=Limits(timeout_s=30)))


def test_a_window_the_stream_does_not_report_comes_from_the_catalogue_read_once(tmp_path):
    agent = Listed({"p/big": 200_000})
    first, second = launch_of(agent, tmp_path), launch_of(agent, tmp_path)
    assert (first.context_window, first.context_pct, second.context_window) == (200_000, 25.0, 200_000)
    assert agent.reads == 1 and agent.catalogue() == {"p/big"}
    assert launch_of(agent, tmp_path, model="p/other").context_window is None  # a model it does not list


def test_the_stream_s_window_wins_over_the_catalogue(tmp_path):
    agent = Listed({"p/big": 200_000}, stream_window=1_000_000)
    assert launch_of(agent, tmp_path).context_window == 1_000_000 and agent.reads == 0


def test_a_catalogue_that_cannot_be_read_leaves_the_window_unknown(tmp_path):
    agent = Listed(None)
    result = launch_of(agent, tmp_path)
    assert (result.context_window, result.context_pct, agent.catalogue(), agent.reads) == (None, None, None, 1)
    for backend in (PiBackend(binary="no-such-pi"), OmpBackend(binary="no-such-omp"), OpencodeBackend(binary="no-such-opencode")):
        assert backend.models() is None and backend.context_window("anthropic/claude-haiku-5-5") is None
