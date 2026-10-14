"""A pipeline's own views: typed panel bodies (tiles, a table, charts), run and trends panels, and `--panels`."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from contraagent.monitor import Monitor, Panel, Period, api
from contraagent.monitor.core import panel_body

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
    assert body == {"type": "tiles", "collapsed": False, "tiles": [{"id": "n", "label": "Runs", "value": 3.0, "sub": []}]}
    assert panel_body({"any": 1}) == {"any": 1}


def test_run_and_trends_panels(tmp_path):
    from contraagent.docs.examples.panels.views import panels

    write_run(tmp_path, "r1", ROWS[:2])
    write_run(tmp_path, "r2", ROWS[2:])
    mon = Monitor(tmp_path, panels=panels(tmp_path))
    assert [(p["name"], p["scope"]) for p in mon.panel_info()] == [("cost", "trends"), ("spend", "run")]
    assert mon.run_panels() == ["spend"]  # a trends panel is no run's tab, and no run's feed sends it
    spend = BODY.validate_python(mon.panel("spend", "r1"))
    assert isinstance(spend, api.BlocksBody)
    table = spend.blocks[1]
    assert isinstance(table, api.TableBody)
    assert table.rows == [{"kind": "write", "attempts": 2, "done": 0.5, "cost": 0.75, "wall": 630, "_tone": "failed"}]
    with pytest.raises(KeyError):
        mon.panel("cost", "r1")
    period = Period(datetime(2026, 10, 13, tzinfo=UTC), datetime(2026, 10, 15, tzinfo=UTC), tz="Asia/Tokyo")
    cost = BODY.validate_python(mon.trends_panel("cost", ["r1", "r2"], period))
    assert isinstance(cost, api.ColumnsBody) and cost.stacked
    # Days in Tokyo: 23:30 UTC on the 13th is the 14th there, so every attempt is on 10-14.
    assert cost.x == ["10-14"]
    assert {s.name: s.values for s in cost.series} == {"triage": [0.1], "write": [0.75]}
    with pytest.raises(KeyError):
        mon.trends_panel("spend", ["r1"], period)


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
        "PANELS = {'facts': Panel(lambda run: {'run': run}, title='Facts')}\n"
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
