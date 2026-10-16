"""A pipeline's own logs and documents: `contraagent.log` and `contraagent.save` in flow code
and in Python tasks, read back by panels (`RunRecords`, `PeriodRuns`), shipped by a relay to
a hub, read there the same way, and pruned with their run."""

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

import contraagent
from contraagent import NoCurrentRun, Pipeline
from contraagent._internal.hub.client import DirectClient
from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.relay import Relay
from contraagent._internal.hub.server import hub_monitor
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore
from contraagent._internal.monitor import api
from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import StaticLiveness
from contraagent.docs.examples.panels.records import PANELS, tally
from contraagent.engine import Run
from contraagent.monitor import DirectorySource, Monitor, Panel, Period, PeriodRuns

TEXTS = {"alpha": "one two three", "beta": "four five"}


def run_tally(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    Pipeline(None, runs_dir=runs, cwd=tmp_path, log=lambda line: None).run(tally, TEXTS)
    return runs


def test_a_flow_and_its_python_tasks_write_into_the_run(tmp_path):
    runs = run_tally(tmp_path)
    folder = runs / "tally" / layout.PIPELINE
    rows = [json.loads(line) for line in (folder / "counts.jsonl").read_text().splitlines()]
    assert sorted(rows, key=lambda r: r["unit"]) == [{"unit": "alpha", "words": 3}, {"unit": "beta", "words": 2}]
    assert json.loads((folder / "total.json").read_text()) == {"units": 2, "words": 5}


def test_a_run_panel_reads_them_through_its_run_records(tmp_path):
    runs = run_tally(tmp_path)
    body = api.BlocksBody.model_validate(Monitor(runs, panels=PANELS).panel("words", "tally"))
    tiles, table = body.blocks
    assert isinstance(tiles, api.TilesBody) and tiles.tiles[0].value == 5
    assert isinstance(table, api.TableBody) and sorted(r["unit"] for r in table.rows) == ["alpha", "beta"]


def test_records_of_a_run_and_of_a_period(tmp_path):
    runs = run_tally(tmp_path)
    seen: dict = {}

    def view(run) -> dict:
        seen["run"] = (run.id, run.info()["run_id"], len(run.journal()), run.records(layout.PLAN) != [], run.dir())
        seen["missing"] = (run.log("nothing"), run.document("nothing"))
        return {}

    def period(runs: PeriodRuns, period: Period) -> dict:
        seen["period"] = [(len(runs.log(r, "counts")), runs.document(r, "total")["words"], runs.run(r).id) for r in runs]
        return {}

    mon = Monitor(runs, panels={"v": Panel(view), "p": Panel(period, scope="trends")})
    mon.panel("v", "tally")
    mon.trends_panel("p", Period.parse())
    assert seen["run"] == ("tally", "tally", 2, True, (runs / "tally").resolve())
    assert seen["missing"] == ([], None)
    assert seen["period"] == [(2, 5, "tally")]


def test_a_python_task_on_a_thread_of_its_own_writes_into_its_run(tmp_path):
    """The queue runs a Python task on a worker thread; the run it writes into is the one its
    runner runs it for, whatever thread calls it."""
    got: list[BaseException] = []

    def elsewhere() -> None:
        try:
            contraagent.log("x", {})
        except NoCurrentRun as exc:
            got.append(exc)

    with Run("r", tmp_path / "runs"):
        contraagent.save("here", [1, 2])
        t = threading.Thread(target=elsewhere)  # a thread of the pipeline's own: no run
        t.start()
        t.join()
    assert json.loads((tmp_path / "runs/r/pipeline/here.json").read_text()) == [1, 2]
    assert len(got) == 1 and "outside a run" in str(got[0])


def test_outside_a_run_and_for_a_bad_name_or_value_the_error_names_the_cause(tmp_path):
    with pytest.raises(NoCurrentRun, match=r"contraagent.save is called outside a run"):
        contraagent.save("total", {})

    class Row(BaseModel):
        n: int

    with Run("r", tmp_path / "runs"):
        contraagent.log("rows", Row(n=1))  # a model is a row too
        bad = [("a/b", "not a plain name"), ("..", "not a plain name"), ("", "needs a name"), ("rows.jsonl", "without its suffix")]
        for name, says in bad:
            with pytest.raises(ValueError, match=says):
                contraagent.log(name, {})
        with pytest.raises(TypeError, match="a row is a JSON object"):
            contraagent.log("rows", [1])  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="not a JSON value"):
            contraagent.save("x", {"when": datetime.now(UTC)})
    assert (tmp_path / "runs/r/pipeline/rows.jsonl").read_text() == '{"n":1}\n'


def test_a_relay_ships_them_a_hub_serves_them_to_panels_and_a_prune_removes_them(tmp_path):
    runs = run_tally(tmp_path)
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    relay = Relay(DirectClient(hub), runs, tmp_path / "progress.json", host_id="h1", liveness=StaticLiveness(DirectorySource(runs)))
    assert relay.pass_once()
    held = "tally@h1"
    assert hub.store.count(held, layout.pipeline_log("counts")) == 2
    assert json.loads(hub.store.document(held, layout.pipeline_document("total")) or "") == {"units": 2, "words": 5}

    # A panel on the hub reads the same records as one on the host.
    local = Monitor(runs, panels=PANELS).panel("words", "tally")
    remote = hub_monitor(hub, panels=PANELS).panel("words", held)
    assert remote == local

    # A row logged later, and a document saved again, reach the hub on the next pass.
    with Run("tally", runs, lock=False):
        contraagent.log("counts", {"unit": "gamma", "words": 1})
        contraagent.save("total", {"units": 3, "words": 6})
    assert relay.pass_once()
    assert hub.store.count(held, layout.pipeline_log("counts")) == 3
    assert json.loads(hub.store.document(held, layout.pipeline_document("total")) or "")["words"] == 6

    report = hub.prune(older_than=timedelta(days=30), now=datetime.now(UTC) + timedelta(days=60))
    assert report.runs == [held]
    assert hub.store.count(held, layout.pipeline_log("counts")) == -1
    assert hub.store.document(held, layout.pipeline_document("total")) is None


def test_a_flow_and_its_python_tasks_read_their_pipeline_table(tmp_path):
    config = tmp_path / "pipeline.toml"
    config.write_text('[pipeline.report]\ntitle = "Weekly"\n')

    @contraagent.python_task
    def heading(unit: str) -> str:
        return f"{contraagent.pipeline_table('report')['title']}: {unit}"

    def flow():
        assert contraagent.pipeline_table("absent") == {}
        text = yield heading(unit=contraagent.pipeline_table("report")["title"].lower())
        contraagent.save("heading", text)

    Pipeline(config, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None).run(flow)
    assert json.loads((tmp_path / "runs/flow/pipeline/heading.json").read_text()) == "Weekly: weekly"

    seen: list[dict] = []
    Pipeline(None, runs_dir=tmp_path / "runs2", cwd=tmp_path, log=lambda line: None).run(
        lambda: seen.append(contraagent.pipeline_table("report"))
    )
    assert seen == [{}]  # a run with no config file

    with pytest.raises(NoCurrentRun, match=r"contraagent.pipeline_table is called outside a run"):
        contraagent.pipeline_table("report")


def test_a_cli_run_reads_the_pipeline_table_of_its_config(tmp_path, monkeypatch):
    import sys

    from contraagent._internal.cli import main

    (tmp_path / "pipeline.toml").write_text("[pipeline.index]\nport = 8080\n")
    (tmp_path / "steps.py").write_text(
        "import contraagent\n"
        "@contraagent.python_task\ndef port() -> int:\n    return contraagent.pipeline_table('index')['port']\n"
        "def flow():\n    contraagent.save('port', (yield port()))\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert main(["run", "steps.py:flow", "--config", "pipeline.toml"]) == 0
    assert json.loads((tmp_path / "runs/flow/pipeline/port.json").read_text()) == 8080
    sys.modules.pop("steps", None)
