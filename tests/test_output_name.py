"""Where outputs go (`output_name`): a path template under the run's `out/`, its checks at
declaration, and one writer per output file."""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.testing import StubAgent


class Notes(BaseModel):
    text: str


def summary(launch):
    return {"text": launch.key}


summarize = agent_task("summarize", instructions="x", output=Notes, max_turns=1, timeout_s=1)
reports = agent_task("reports", instructions="x", output=Notes, output_name="reports/{unit}.json", max_turns=1, timeout_s=1)
also_reports = agent_task("also_reports", instructions="x", output=Notes, output_name="reports/{unit}.json", max_turns=1, timeout_s=1)


def run(tmp_path, flow, stub: StubAgent | None = None):
    stub = stub or StubAgent({"summarize": summary, "reports": summary, "start": summary, "grow": summary})
    return Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path).run(flow), stub


def test_the_default_puts_each_kind_in_a_directory_of_its_own(tmp_path):
    draft = agent_task("draft", instructions="x", output=str, max_turns=1, timeout_s=1)

    @python_task
    def count(unit: str) -> int:
        return len(unit)

    assert summarize.output_name == count.output_name == "{kind}/{unit}.json"
    assert draft.output_name == "{kind}/{unit}.md"

    def flow():
        summarize("alpha")
        count("alpha")

    report, _ = run(tmp_path, flow)
    assert report.ok, report.failed
    assert json.loads((report.run_dir / "out/summarize/alpha.json").read_text()) == {"text": "summarize-alpha"}
    assert (report.run_dir / "out/count/alpha.json").read_text() == "5"


def test_a_template_places_the_file_anywhere_under_out(tmp_path):
    @python_task(output_name="tables/{kind}-{unit}.json")
    def count(unit: str) -> int:
        return len(unit)

    def flow():
        reports("alpha")
        reports("alpha")  # reports-alpha~2
        reports.options(key="beta-long")("beta")
        count("alpha")

    report, stub = run(tmp_path, flow)
    assert report.ok, report.failed
    out = report.run_dir / "out"
    paths = {launch.key: Path(launch.call.output.path) for launch in stub.launches}
    assert paths == {
        "reports-alpha": out / "reports/alpha.json",
        "reports-alpha~2": out / "reports/alpha~2.json",
        "beta-long": out / "reports/beta-long.json",
    }
    assert all(p.is_file() for p in paths.values())
    assert (out / "tables/count-alpha.json").read_text() == "5"


@pytest.mark.parametrize(
    ("template", "match"),
    [
        ("/tmp/{unit}.json", "is absolute"),
        ("../{unit}.json", "'..' segment"),
        ("reports/../{unit}.json", "'..' segment"),
        ("./{unit}.json", "'.' segment"),
        ("reports//{unit}.json", "empty segment"),
        ("reports/", "empty segment"),
        ("{name}.json", r"names \{name\}"),
        ("{params.topic}.json", r"names \{params.topic\}"),
        ("{}.json", r"names \{\}"),
        ("{unit!r}.json", "no format or conversion"),
        ("{unit:>4}.json", "no format or conversion"),
        ("{unit.json", "output_name"),
    ],
)
def test_an_output_name_outside_out_or_with_an_unknown_field_is_refused_at_declaration(template, match):
    with pytest.raises(ValueError, match=match):
        agent_task("t", instructions="x", output=Notes, output_name=template, max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match=match):
        python_task(output_name=template)(lambda unit: {"n": 1})
    with pytest.raises(TypeError, match="relative to the run's out/"):
        agent_task("t", instructions="x", output=Notes, output_name="", max_turns=1, timeout_s=1)


def test_output_of_writes_the_other_kinds_file_whatever_its_template(tmp_path):
    start = agent_task("start", instructions="x", output=Notes, output_name="notes/{unit}/start.json", max_turns=1, timeout_s=1)
    grow = agent_task("grow", instructions="x", output=Notes, output_of=start, max_turns=1, timeout_s=1)

    def flow():
        start("a")
        grow("a")
        grow("b")  # no start for b: the file start's template names for it

    report, stub = run(tmp_path, flow)
    assert report.ok, report.failed
    out = report.run_dir / "out" / "notes"
    paths = {launch.key: Path(launch.call.output.path) for launch in stub.launches}
    assert paths["start-a"] == paths["grow-a"] == out / "a/start.json"
    assert paths["grow-b"] == out / "b/start.json"
    assert json.loads((out / "a/start.json").read_text()) == {"text": "grow-a"}


def test_two_kinds_whose_templates_name_one_file_raise_at_the_second(tmp_path):
    def flow():
        reports("alpha")
        also_reports("beta")

    with pytest.raises(ValueError, match=r"kinds 'reports' and 'also_reports' both write out/reports/\{unit\}.json"):
        run(tmp_path, flow)


def test_check_reports_two_reachable_kinds_whose_templates_name_one_file():
    async def flow(units):
        notes = await asyncio.gather(*[reports(u) for u in units])
        if notes:
            await also_reports(units[0])

    errors = Pipeline(PipelineConfig({}), backends=StubAgent().backends()).check(flow, ["a"]).errors
    assert any("kinds 'reports' and 'also_reports' both write out/reports/{unit}.json" in e for e in errors), errors


def test_two_tasks_given_one_file_raise_at_the_second(tmp_path):
    table = agent_task("table", instructions="x", output=Notes, output_name="table.json", max_turns=1, timeout_s=1)
    nested = agent_task("nested", instructions="x", output=Notes, output_name="{unit}/n.json", max_turns=1, timeout_s=1)

    def once():
        table("a")
        table("b")

    with pytest.raises(ValueError, match="tasks 'table-a' and 'table-b' would both write out/table.json"):
        run(tmp_path, once)

    def outside():
        nested.options(key="..")("x")

    with pytest.raises(ValueError, match="not a path inside out/"):
        run(tmp_path, outside)
