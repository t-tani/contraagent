"""The format of a run directory (`run.json` `format`): what a run writes, what a resume
refuses, and the run directories of every format the monitor reads."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from contraagent import RunFormatError
from contraagent._internal.monitor import api
from contraagent._internal.monitor.views import VIEWS, serialize
from contraagent._internal.runs import layout
from contraagent.engine import Run
from contraagent.monitor import Monitor, Period

FIXTURES = Path(__file__).parent / "fixtures" / "runs"

#: A run directory of each format this release reads, by format.
FORMAT_FIXTURES = {1: FIXTURES / "v1" / "review"}


def test_every_format_read_has_a_fixture():
    assert set(FORMAT_FIXTURES) == set(layout.FORMATS)
    assert layout.FORMAT == max(layout.FORMATS)
    for fmt, run_dir in FORMAT_FIXTURES.items():
        assert json.loads((run_dir / layout.RUN_INFO).read_text())["format"] == fmt


def _runs(tmp_path: Path, fmt: int) -> Path:
    runs = tmp_path / "runs"
    shutil.copytree(FORMAT_FIXTURES[fmt], runs / "review")
    return runs


@pytest.mark.parametrize("fmt", sorted(FORMAT_FIXTURES))
def test_the_monitor_reads_a_run_of_each_format(tmp_path, fmt):
    mon = Monitor(_runs(tmp_path, fmt))
    (summary,) = TypeAdapter(list[api.RunSummary]).validate_python(mon.runs())
    assert summary.run == "review" and summary.host_id == "host-1" and not summary.running and summary.stub
    for view in VIEWS.values():
        serialize(view.model, view.read(mon, "review"))
    plan = mon.plan("review")
    states = {n["key"]: n["state"] for n in plan["nodes"]}
    assert states["review-alpha"] == "done" and states["review-gamma"] == "failed"
    assert len(mon.journal("review")[0]) == 7
    for key in states:
        TypeAdapter(api.TaskDetail).validate_python(mon.task_detail("review", key))
    for stream in sorted((FORMAT_FIXTURES[fmt] / layout.STREAMS).glob(f"*{layout.STREAM_SUFFIX}")):
        page, _ = mon.stream("review", stream.name.removesuffix(layout.STREAM_SUFFIX), 0)
        assert TypeAdapter(api.StreamPage).validate_python(page).events
    day = date.fromisoformat(json.loads((FORMAT_FIXTURES[fmt] / layout.RUN_INFO).read_text())["started_at"][:10])
    trends = TypeAdapter(api.Trends).validate_python(mon.trends(Period(day, day), stub=True))
    assert trends.model_dump()


def test_a_run_records_its_format(tmp_path):
    run = Run("r", tmp_path / "runs", log=lambda line: None)
    run.close()
    assert json.loads((run.dir / layout.RUN_INFO).read_text())["format"] == layout.FORMAT


def test_a_run_of_a_newer_format_is_not_resumed_nor_overwritten(tmp_path):
    runs = _runs(tmp_path, layout.FORMAT)
    info_path = runs / "review" / layout.RUN_INFO
    info = json.loads(info_path.read_text())
    info_path.write_text(json.dumps({**info, "format": layout.FORMAT + 1}))
    before = info_path.read_text()
    with pytest.raises(RunFormatError, match=rf"format {layout.FORMAT + 1}; this contraagent reads format 1"):
        Run("review", runs)
    assert info_path.read_text() == before
    # The lock was let go: a later Run of the same id is refused for its format, not its lock.
    with pytest.raises(RunFormatError):
        Run("review", runs)


@pytest.mark.parametrize("value", ["1", 0, True, None])
def test_a_format_that_is_not_a_positive_whole_number_is_refused(tmp_path, value):
    runs = _runs(tmp_path, layout.FORMAT)
    info_path = runs / "review" / layout.RUN_INFO
    info_path.write_text(json.dumps({**json.loads(info_path.read_text()), "format": value}))
    with pytest.raises(RunFormatError):
        Run("review", runs)


def test_a_run_json_without_format_is_format_1(tmp_path):
    runs = _runs(tmp_path, 1)
    info_path = runs / "review" / layout.RUN_INFO
    info = json.loads(info_path.read_text())
    del info["format"]
    info_path.write_text(json.dumps(info))
    run = Run("review", runs, log=lambda line: None)
    run.close()
    resumed = json.loads(info_path.read_text())
    assert resumed["format"] == 1 and resumed["run_uid"] == info["run_uid"]
