"""The pipeline's own pages: ASGI apps the monitor serves under apps/<name>/, shown by a
panel in a frame (`EmbedBody`)."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from contraagent._internal import cli
from contraagent._internal.monitor import api, server
from contraagent.monitor import EmbedBody, Monitor, create_app

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

BODY = TypeAdapter(api.PanelBody)


def client(monitor: Monitor) -> TestClient:
    return TestClient(create_app(monitor), base_url="http://127.0.0.1")


def write_run(runs, run: str) -> None:
    (runs / run).mkdir(parents=True)
    rows = [{"ts": "2026-10-14T01:00:00Z", "key": "write-a", "kind": "write", "stop": "completed", "ok": True}]
    (runs / run / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_the_example_s_page_is_served_under_apps_and_its_panel_frames_it(tmp_path, monkeypatch):
    from contraagent.docs.examples.panels import page

    write_run(tmp_path, "r1")
    monkeypatch.setattr(page, "RUNS", page.DirectorySource(tmp_path))
    c = client(Monitor(tmp_path, apps=page.APPS, panels=page.PANELS))
    html = c.get("/apps/attempts/?run=r1")
    assert html.status_code == 200 and "<title>Attempts</title>" in html.text
    assert c.get("/apps/attempts/data?run=r1").json() == [{"key": "write-a", "stop": "completed"}]
    body = c.get("/api/runs/r1/panels/attempts").json()
    assert (body["type"], body["url"]) == ("embed", "apps/attempts/?run=r1")
    # The monitor's own routes are as they were, and a host it does not answer is refused for the page too.
    assert c.get("/api/info").json()["panels"][0]["name"] == "attempts"
    assert TestClient(create_app(Monitor(tmp_path, apps=page.APPS)), base_url="http://elsewhere").get("/apps/attempts/").status_code == 400


def test_an_app_has_a_plain_name_and_is_callable(tmp_path):
    with pytest.raises(ValueError, match="app name"):
        Monitor(tmp_path, apps={"a/b": lambda scope, receive, send: None})  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="is not an ASGI app"):
        Monitor(tmp_path, apps={"page": "app.py"})  # pyright: ignore[reportArgumentType]


def test_an_embed_names_a_path_under_the_monitor_or_an_http_url():
    assert BODY.validate_python({"type": "embed", "url": "apps/page/?run=r1", "height": 600}) == EmbedBody(
        url="apps/page/?run=r1", height=600
    )
    assert BODY.validate_python({"type": "embed", "url": "https://example.com/page"}).url == "https://example.com/page"  # pyright: ignore[reportAttributeAccessIssue]
    for url in ("/apps/page/", "javascript:alert(1)", "data:text/html,x", "//example.com/page", ""):
        with pytest.raises(ValidationError):
            EmbedBody(url=url)
    with pytest.raises(ValidationError):
        EmbedBody(url="apps/page/", height=10)


def test_the_command_loads_the_apps(tmp_path, monkeypatch):
    (tmp_path / "views.py").write_text("async def app(scope, receive, send):\n    pass\nAPPS = {'page': app}\n")
    seen = {}
    monkeypatch.setattr(server, "bind_option", lambda host, port: None)
    monkeypatch.setattr(server, "_serve", lambda monitor, *a, **k: seen.setdefault("monitor", monitor))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["monitor", "--runs-dir", str(tmp_path), "--apps", "views.py:APPS"]) == 0
    assert list(seen["monitor"].apps) == ["page"]
