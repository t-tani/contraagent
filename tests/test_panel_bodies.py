"""A pipeline's own views: typed panel bodies (tiles, a table, charts), run and trends panels, and `--panels`."""

import json
import os
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from contraagent.monitor import Monitor, Panel, Period, PeriodRuns, api
from contraagent.monitor.core import panel_body
from contraagent.monitor.source import DirectorySource

BODY = TypeAdapter(api.PanelBody)


def write_run(runs: Path, run: str, rows: list[dict]) -> None:
    (runs / run).mkdir(parents=True)
    (runs / run / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


ROWS = [
    {"ts": "2026-10-13T23:30:00Z", "key": "write-a", "kind": "write", "stop": "completed", "ok": True, "cost_usd": 0.5, "wall_s": 30},
    {"ts": "2026-10-14T01:00:00Z", "key": "write-b", "kind": "write", "stop": "timeout", "ok": False, "cost_usd": 0.25, "wall_s": 600},
    {"ts": "2026-10-14T02:00:00Z", "key": "triage-a", "kind": "triage", "stop": "completed", "ok": True, "cost_usd": 0.1, "wall_s": 9},
]


def test_a_typed_body_validates_by_its_type_and_any_other_object_is_untyped():
    body = BODY.validate_python(
        {"type": "blocks", "blocks": [{"type": "tiles", "tiles": [{"id": "c", "label": "Cost", "value": 2}]}, {"x": 1}]}
    )
    assert isinstance(body, api.BlocksBody) and isinstance(body.blocks[0], api.TilesBody) and body.blocks[1] == {"x": 1}
    assert BODY.validate_python({"rows": []}) == {"rows": []}  # no type: shown as a JSON tree
    assert BODY.validate_python({"type": "sideways"}) == {"type": "sideways"}  # not a body type: also untyped
    with pytest.raises(ValidationError):  # a typed body that does not validate is an error, never a JSON tree
        BODY.validate_python({"type": "table", "columns": [{"id": "a"}], "rows": []})
    with pytest.raises(ValidationError):
        BODY.validate_python({"type": "columns", "x": ["a"], "series": [{"name": "s", "values": ["one"]}]})


def test_a_panel_may_return_a_model_and_is_sent_as_its_json():
    body = panel_body(api.TilesBody(tiles=[api.PanelTile(id="n", label="Runs", value=3)]))
    assert body == {"type": "tiles", "collapsed": False, "tiles": [{"id": "n", "label": "Runs", "value": 3, "sub": []}]}
    assert json.dumps(body["tiles"][0]["value"]) == "3"  # an integer stays one, not 3.0
    assert panel_body({"any": 1}) == {"any": 1}


def test_a_note_a_status_grid_and_a_link_column():
    note = BODY.validate_python({"type": "note", "text": "Counts **run starts**.", "tone": "attention"})
    assert isinstance(note, api.NoteBody) and note.tone == "attention"
    grid = BODY.validate_python(
        {
            "type": "status_grid",
            "x": ["00", "01"],
            "y": ["Mon", "Tue"],
            "cells": [[{"label": "done", "tone": "done"}, None], [{"label": "failed", "tone": "failed", "tip": "run 0312"}, None]],
        }
    )
    assert isinstance(grid, api.StatusGridBody) and grid.cells[1][0] is not None and grid.cells[1][0].tip == "run 0312"
    table = BODY.validate_python(
        {"type": "table", "columns": [{"id": "topic", "label": "Topic", "link": "url"}], "rows": [{"topic": "a", "url": "https://x"}]}
    )
    assert isinstance(table, api.TableBody) and table.columns[0].link == "url"


def test_the_hourly_runs_example_draws_a_status_grid_a_note_and_linked_runs(tmp_path):
    from contraagent.docs.examples.panels.cycles import cycles

    def run(name: str, started: str, ok: bool, finished: bool = True) -> None:
        write_run(tmp_path, name, [{**ROWS[0], "ok": ok}])
        info = {"run_id": name, "started_at": started} | ({"finished_at": started} if finished else {})
        (tmp_path / name / "run.json").write_text(json.dumps(info))

    run("c1", "2026-10-13T23:05:00Z", ok=True)  # 08:05 on 10-14 in Tokyo
    run("c2", "2026-10-14T00:05:00Z", ok=False)  # 09:05
    run("c3", "2026-10-14T01:05:00Z", ok=True, finished=False)  # 10:05, still running
    period = Period.parse("2026-10-13", "2026-10-14", "Asia/Tokyo")
    body = BODY.validate_python(panel_body(cycles()(PeriodRuns(["c1", "c2", "c3"], DirectorySource(tmp_path)), period)))
    assert isinstance(body, api.BlocksBody)
    note, grid, table = body.blocks
    assert isinstance(note, api.NoteBody) and isinstance(grid, api.StatusGridBody) and isinstance(table, api.TableBody)
    assert grid.y == ["10-13", "10-14"] and len(grid.x) == 24
    states = {(grid.y[r], grid.x[c]): cell.label for r, row in enumerate(grid.cells) for c, cell in enumerate(row) if cell}
    assert states == {("10-14", "08"): "done", ("10-14", "09"): "failed", ("10-14", "10"): "running"}
    assert [(r["run"], r["url"], r["_tone"]) for r in table.rows] == [
        ("c3", "http://127.0.0.1:8787/?run=c3", "running"),
        ("c2", "http://127.0.0.1:8787/?run=c2", "failed"),
        ("c1", "http://127.0.0.1:8787/?run=c1", "done"),
    ]


@pytest.mark.parametrize(
    "body, says",
    [
        ({"type": "status_grid", "x": ["00"], "y": ["Mon", "Tue"], "cells": [[None]]}, "cells has 1 rows; y has 2"),
        ({"type": "status_grid", "x": ["00", "01"], "y": ["Mon"], "cells": [[None]]}, "cells[0] has 1 cells; x has 2"),
        ({"type": "status_grid", "x": ["00"], "y": ["Mon"], "cells": [[{"label": "ok", "tone": "ok"}]]}, "'failed', 'attention'"),
        ({"type": "note", "text": "x", "tone": "ok"}, "'failed', 'attention'"),
        ({"type": "tiles", "tiles": [{"id": "a", "label": "A", "value": 1, "tone": "ok"}]}, "'failed', 'attention'"),
        (
            {"type": "table", "columns": [{"id": "a", "label": "A"}], "rows": [{"a": 1}, {"a": 2, "_tone": "ok"}]},
            "rows[1]._tone is 'ok'; a tone is one of failed, attention, done, running, muted, neutral",
        ),
        ({"type": "table", "columns": [{"id": "a", "label": "A", "link": ""}], "rows": []}, "at least 1 character"),
    ],
)
def test_a_body_names_what_is_wrong_with_it(body, says):
    with pytest.raises(ValidationError, match=re.escape(says)):
        BODY.validate_python(body)


def test_run_and_trends_panels(tmp_path):
    from contraagent.docs.examples.panels.views import PANELS

    write_run(tmp_path, "r1", ROWS[:2])
    write_run(tmp_path, "r2", ROWS[2:])
    mon = Monitor(tmp_path, panels=PANELS)
    assert [(p["name"], p["scope"]) for p in mon.panel_info()] == [("spend", "run"), ("cost", "trends")]  # the dict's order
    assert mon.run_panels() == ["spend"]  # a trends panel is no run's tab, and no run's feed sends it
    spend = BODY.validate_python(mon.panel("spend", "r1"))
    assert isinstance(spend, api.BlocksBody)
    table = spend.blocks[1]
    assert isinstance(table, api.TableBody)
    assert table.rows == [{"kind": "write", "attempts": 2, "done": 0.5, "cost": 0.75, "wall": 630, "_tone": "failed"}]
    with pytest.raises(KeyError):
        mon.panel("cost", "r1")
    period = Period.parse("2026-10-13", "2026-10-15", "Asia/Tokyo")
    cost = BODY.validate_python(mon.trends_panel("cost", period))
    assert isinstance(cost, api.ColumnsBody) and cost.stacked
    # Days in Tokyo: 23:30 UTC on the 13th is the 14th there, so every attempt is on 10-14.
    assert cost.x == ["10-13", "10-14", "10-15"]
    assert {s.name: s.values for s in cost.series} == {"triage": [None, 0.1, None], "write": [None, 0.75, None]}
    with pytest.raises(KeyError):
        mon.trends_panel("spend", period)


def test_a_trends_panel_names_its_tab_of_the_trends_page(tmp_path):
    body = lambda runs, period: {"type": "tiles", "tiles": []}
    mon = Monitor(tmp_path, panels={"latency": Panel(body, scope="trends", tab="Reliability"), "quality": Panel(body, scope="trends")})
    assert [(p["name"], p["tab"]) for p in mon.panel_info()] == [("latency", "Reliability"), ("quality", "")]
    trends = api.Trends.model_validate(mon.trends(Period.parse("2026-10-13", "2026-10-15")))
    assert [(p.name, p.scope, p.tab) for p in trends.panels] == [("latency", "trends", "Reliability"), ("quality", "trends", "")]
    with pytest.raises(ValueError, match="a run panel is a tab of its own"):
        Panel(lambda run: {}, title="spend", tab="Reliability")


def test_the_server_sends_a_run_panel_and_lists_each_panel_s_scope(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from contraagent.monitor import server

    write_run(tmp_path, "r1", ROWS)
    bad = Panel(lambda run: {"type": "hbars", "bars": [{"label": "x"}]}, title="bad")
    mon = Monitor(tmp_path, panels={"ok": Panel(lambda run: {"type": "tiles", "tiles": []}), "bad": bad})
    c = TestClient(server.create_app(mon), base_url="http://127.0.0.1")
    assert [p["scope"] for p in c.get("/api/info").json()["panels"]] == ["run", "run"]
    assert c.get("/api/runs/r1/panels/ok").json() == {"type": "tiles", "tiles": []}
    # The response is checked against its model: a malformed typed body fails, never sent as a JSON tree.
    from fastapi.exceptions import ResponseValidationError

    with pytest.raises(ResponseValidationError):
        c.get("/api/runs/r1/panels/bad")


def test_the_monitor_command_loads_panels_groups_and_task_detail(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from contraagent.monitor import server

    views = tmp_path / "views.py"
    views.write_text(
        "from contraagent.monitor import Panel\n"
        "PANELS = {'facts': Panel(lambda run: {'run': run.id}, title='Facts')}\n"
        "GROUPS = [{'id': 'all', 'label': 'All', 'kinds': ['write']}]\n"
        "def detail(run, key, rows):\n    return {'n': len(rows)}\n"
    )
    seen = {}
    monkeypatch.setattr(server, "serve", lambda monitor, *a, **k: seen.setdefault("monitor", monitor))
    monkeypatch.chdir(tmp_path)
    argv = ["--runs-dir", str(tmp_path), "--panels", f"{views}:PANELS", "--groups", "views.py:GROUPS"]
    assert server.main([*argv, "--task-detail", "views:detail"]) == 0
    mon = seen["monitor"]
    assert list(mon.panels) == ["facts"] and mon.group_defs[0]["id"] == "all"
    assert mon.task_detail_fn("r", "k", [1, 2]) == {"n": 2}
    assert server.main(["--panels", "views.py"]) == 2
    assert server.main(["--panels", "nowhere.py:PANELS"]) == 2


def test_the_example_s_panels_load_as_the_command_would(tmp_path, monkeypatch):
    from contraagent.docs.examples.panels import views
    from contraagent.monitor.server import load_attr

    monkeypatch.chdir(tmp_path)
    assert load_attr(f"{os.path.abspath(views.__file__)}:PANELS").keys() == {"spend", "cost"}
