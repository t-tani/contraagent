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
from contraagent import NoCurrentRun, Pipeline, Run, rundir
from contraagent.docs.examples.panels.records import PANELS, tally
from contraagent.hub.client import DirectClient
from contraagent.hub.core import Hub
from contraagent.hub.relay import Relay
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.monitor import Monitor, Panel, Period, PeriodRuns, api
from contraagent.monitor.source import DirectorySource, StaticLiveness

TEXTS = {"alpha": "one two three", "beta": "four five"}


def run_tally(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    Pipeline(None, runs_dir=runs, cwd=tmp_path, log=lambda line: None).run(tally, TEXTS)
    return runs


def test_a_flow_and_its_python_tasks_write_into_the_run(tmp_path):
    runs = run_tally(tmp_path)
    folder = runs / "tally" / rundir.PIPELINE
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
        seen["run"] = (run.id, run.info()["run_id"], len(run.journal()), run.records(rundir.PLAN) != [], run.dir())
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
    assert hub.store.count(held, rundir.pipeline_log("counts")) == 2
    assert json.loads(hub.store.document(held, rundir.pipeline_document("total")) or "") == {"units": 2, "words": 5}

    # A panel on the hub reads the same records as one on the host.
    local = Monitor(runs, panels=PANELS).panel("words", "tally")
    remote = hub.monitor(panels=PANELS).panel("words", held)
    assert remote == local

    # A row logged later, and a document saved again, reach the hub on the next pass.
    with Run("tally", runs, lock=False):
        contraagent.log("counts", {"unit": "gamma", "words": 1})
        contraagent.save("total", {"units": 3, "words": 6})
    assert relay.pass_once()
    assert hub.store.count(held, rundir.pipeline_log("counts")) == 3
    assert json.loads(hub.store.document(held, rundir.pipeline_document("total")) or "")["words"] == 6

    report = hub.prune(older_than=timedelta(days=30), now=datetime.now(UTC) + timedelta(days=60))
    assert report.runs == [held]
    assert hub.store.count(held, rundir.pipeline_log("counts")) == -1
    assert hub.store.document(held, rundir.pipeline_document("total")) is None
