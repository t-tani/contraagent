"""`contraagent monitor export`: the monitor's views of some runs as files, with this
machine's paths and names taken out."""

import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from contraagent import Pipeline, agent_task
from contraagent._internal.cli import main as cli_main
from contraagent._internal.monitor import api
from contraagent._internal.runs import layout
from contraagent.monitor import Monitor, Panel, Period, RunRecords, export
from contraagent.testing import StubAgent


def main(argv: list[str]) -> int:
    return cli_main(["monitor", "export", *argv])


class Note(BaseModel):
    text: str


# One attempt: note-b's failure is what an export redacts, and retrying it would only wait out a backoff.
note = agent_task("note", instructions="Write a note on ${unit}.", output=Note, max_turns=3, timeout_s=60, retries=0)
NOW = lambda: datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def runs(tmp_path: Path, ids=("first", "second")) -> Path:
    """Runs under `tmp_path/runs` whose records hold absolute paths of `tmp_path` (call
    files, output paths, a reason) and, in an output's contents, a system path."""
    stub = StubAgent(
        {
            "note-a": {"text": f"/etc/hosts was read; see {tmp_path}/work/notes.md"},
            "note-b": {"text": 3},  # off its schema twice: a reason with the file's absolute path
        }
    )
    for i, run_id in enumerate(ids):
        Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, backends=stub.backends(), log=lambda line: None).run(
            lambda: [note("a"), note("b")], run_id=run_id
        )
        later(tmp_path / "runs" / run_id / "journal.jsonl", seconds=i)
    return tmp_path / "runs"


def later(journal: Path, seconds: int) -> None:
    """Move a run's journal rows `seconds` on: runs made within one second would tie on their
    last activity (kept to the second), and the export orders runs by it."""
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["ts"] = (datetime.fromisoformat(row["ts"]) + timedelta(seconds=seconds)).isoformat(timespec="seconds")
    journal.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8", newline="\n")


def written(path: Path) -> tuple[str, str]:
    """How a JSON file can hold `path`: as the OS writes it (escaped), and with `/`."""
    return json.dumps(str(path))[1:-1], path.as_posix()


def files(out: Path) -> dict[str, str]:
    return {
        p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.suffix in (".json", ".html")
    }


def panel(run: RunRecords) -> dict:
    return {"run": run.id, "where": str(Path.home() / "secret")}


def test_an_export_holds_each_route_of_the_runs_as_a_file(tmp_path):
    report = export(Monitor(runs(tmp_path), title="notes", panels={"p": panel}), tmp_path / "site", runs=1, now=NOW)
    out = tmp_path / "site"
    assert report.runs == ["second"]  # the newest activity first, one asked for
    names = files(out)
    for name in ("journal", "plan", "outputs", "definitions", "cursor"):
        assert f"data/runs/second/{name}.json" in names
    assert {"data/runs/second/tasks/note-a.json", "data/runs/second/tasks/note-b.json", "data/runs/second/panels/p.json"} <= set(names)
    assert not any("/first/" in n for n in names)
    assert (out / "app.js").is_file() and (out / "ja.js").is_file()
    page = names["index.html"]
    assert '<ca-monitor export="data/"></ca-monitor>' in page and "<title>notes</title>" in page
    info = json.loads(names["data/info.json"])
    assert info["export"] == {
        "exported_at": "2026-10-14T12:00:00+00:00",
        "runs": ["second"],
        "left_out": ["transcripts", "processes"],
        "redacted": ["host", "paths"],
    }
    assert [r["run"] for r in json.loads(names["data/runs.json"])] == ["second"]
    # No transcript, no process: a task's file names none, and its rows and definition are the run's files'.
    task = json.loads(names["data/runs/second/tasks/note-a.json"])
    assert task["stream"] is None and task["launches"] == [] and task["rows"] == [] and task["definition"] is None
    assert task["io"]["outputs"]
    assert not list(out.rglob("*.stream.jsonl"))


def test_this_machine_s_paths_and_name_are_taken_out(tmp_path, monkeypatch):
    monkeypatch.setenv(layout.HOST_ID_ENV, "host-of-the-export-test")  # a name no other text holds
    export(Monitor(runs(tmp_path), panels={"p": panel}), tmp_path / "site", now=NOW)
    text = "\n".join(files(tmp_path / "site" / "data").values())
    assert not any(form in text for path in (tmp_path, Path.home()) for form in written(path))
    assert "host-of-the-export-test" not in text
    if len(socket.gethostname()) >= 8:  # a short host name can be part of another word
        assert socket.gethostname() not in text
    journal = json.loads((tmp_path / "site/data/runs/second/journal.json").read_text(encoding="utf-8"))
    reasons = " ".join(e["reason"] for e in journal["entries"])
    assert "out/note/b.json" in reasons  # made relative to the run directory, not dropped
    assert json.loads((tmp_path / "site/data/runs/second/panels/p.json").read_text(encoding="utf-8"))["where"] == str(Path("~", "secret"))
    outputs = (tmp_path / "site/data/runs/second/outputs.json").read_text(encoding="utf-8")
    # An output's contents keep what is not this machine's: a system path stays, the run's working directory goes.
    assert "/etc/hosts was read; see work/notes.md" in outputs


def test_a_person_s_windows_path_is_taken_out_on_any_os():
    from contraagent._internal.monitor.export import Redactor

    redact = Redactor([])
    assert redact.path("read C:\\Users\\alice\\notes.md and D:\\data\\x.csv") == "read <path> and D:\\data\\x.csv"
    assert redact.path("C:\\Users\\alice\\a.md", content=True) == "C:\\Users\\alice\\a.md"  # a document's contents stay


def test_keep_puts_the_paths_back_and_exclude_takes_a_key_out(tmp_path):
    rd = runs(tmp_path, ids=("only",))
    export(Monitor(rd), tmp_path / "kept", keep=["paths"], now=NOW)
    assert written(tmp_path)[0] in "\n".join(files(tmp_path / "kept").values())
    export(Monitor(rd), tmp_path / "lean", exclude=["params"], now=NOW)
    text = "\n".join(files(tmp_path / "lean").values())
    assert '"params":' not in text
    assert json.loads((tmp_path / "lean/data/info.json").read_text(encoding="utf-8"))["export"]["redacted"] == ["host", "params", "paths"]


def test_an_export_written_again_holds_only_the_runs_chosen_now(tmp_path):
    rd = runs(tmp_path)
    out = tmp_path / "site"
    period = Period.parse()  # one period for every export: the default one ends on today's date
    export(Monitor(rd), out, runs=None, now=NOW, period=period)
    first = files(out)
    export(Monitor(rd), out, runs=None, now=NOW, period=period)
    assert files(out) == first  # the same runs: the same files
    export(Monitor(rd), out, runs=1, now=NOW, period=period)
    assert not (out / "data/runs/first").exists()


def test_the_cli_writes_the_export_and_says_how_large_it_is(tmp_path, capsys):
    rd = runs(tmp_path, ids=("only",))
    assert main(["--runs-dir", str(rd), "--out", str(tmp_path / "site"), "--title", "notes", "--exclude", "params"]) == 0
    said = capsys.readouterr().out
    assert "only:" in said and "wrote 1 runs" in said
    assert '"params":' not in (tmp_path / "site/data/runs/only/tasks/note-a.json").read_text(encoding="utf-8")


def test_an_export_holds_the_trends_of_its_period_and_the_trend_panels(tmp_path):
    seen: dict = {}

    def days(run_ids, period):
        seen["args"] = (sorted(run_ids), period.tz)
        return {"panel": "days", "where": str(tmp_path)}

    rd = runs(tmp_path, ids=("only",))
    started = json.loads((rd / "only" / "run.json").read_text(encoding="utf-8"))["started_at"]
    # The day the run started in Tokyo, not UTC's; read from the run, so midnight between the run and this line does not matter.
    today = datetime.fromisoformat(started).astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()
    monitor = Monitor(rd, panels={"days": Panel(days, scope="trends"), "p": Panel(panel)})
    export(monitor, tmp_path / "site", now=NOW, period=Period.parse(today, today, "Asia/Tokyo"))
    data = tmp_path / "site/data"
    trends = api.Trends.model_validate_json((data / "trends.json").read_text(encoding="utf-8"))
    assert trends.period.tz == "Asia/Tokyo" and trends.totals.runs == 1 and [r.run for r in trends.runs] == ["only"]
    assert seen["args"] == (["only"], "Asia/Tokyo")
    # Redacted as any view: a temporary directory outside the runs is no root of the export;
    # under the home directory (Windows' temporary directory is), it starts with `~` instead.
    home = str(Path.home())
    where = "~" + str(tmp_path)[len(home) :] if tmp_path.is_relative_to(home) else "<path>"
    assert json.loads((data / "trends/panels/days.json").read_text(encoding="utf-8")) == {"panel": "days", "where": where}
    assert not (data / "runs/only/panels/days.json").exists()
    assert (data / "runs/only/panels/p.json").exists()


def test_the_cli_takes_the_trends_period(tmp_path):
    rd = runs(tmp_path, ids=("only",))
    assert main(["--runs-dir", str(rd), "--out", str(tmp_path / "a"), "--from", "2026-09-01", "--to", "2026-09-30", "--tz", "UTC"]) == 0
    assert json.loads((tmp_path / "a/data/trends.json").read_text(encoding="utf-8"))["period"]["from"] == "2026-09-01"
    assert main(["--runs-dir", str(rd), "--out", str(tmp_path / "b"), "--days", "7", "--to", "2026-10-14"]) == 0
    assert json.loads((tmp_path / "b/data/trends.json").read_text(encoding="utf-8"))["period"]["from"] == "2026-10-08"
    assert main(["--runs-dir", str(rd), "--out", str(tmp_path / "c"), "--tz", "Mars/Olympus"]) == 2


def test_the_cli_takes_panels_groups_and_task_detail_as_the_monitor_does(tmp_path):
    rd = runs(tmp_path, ids=("only",))
    views = tmp_path / "views.py"
    views.write_text(
        "from contraagent.monitor import Panel\n"
        "def kinds(runs, period):\n"
        "    return {'type': 'tiles', 'tiles': [{'id': 'n', 'label': 'Rows', 'value': sum(len(runs.journal(r)) for r in runs)}]}\n"
        "PANELS = {'kinds': Panel(kinds, scope='trends')}\n"
        "GROUPS = [{'id': 'writing', 'label': 'Writing', 'kinds': ['note']}]\n"
        "def detail(run, key, rows):\n    return {'attempts_seen': len(rows)}\n",
        encoding="utf-8",
        newline="\n",
    )
    out = tmp_path / "site"
    argv = ["--runs-dir", str(rd), "--out", str(out), "--panels", f"{views}:PANELS", "--groups", f"{views}:GROUPS"]
    assert main([*argv, "--task-detail", f"{views}:detail", "--days", "366"]) == 0
    trends = json.loads((out / "data/trends.json").read_text(encoding="utf-8"))
    assert {k["kind"]: k["group"] for k in trends["kinds"]} == {"note": "Writing"}  # grouped as the live monitor groups it
    value = json.loads((out / "data/trends/panels/kinds.json").read_text(encoding="utf-8"))["tiles"][0]["value"]
    assert isinstance(value, int) and value >= 2  # an int stays one
    assert json.loads((out / "data/runs/only/tasks/note-a.json").read_text(encoding="utf-8"))["attempts_seen"] >= 1
    assert main(["--runs-dir", str(rd), "--out", str(out), "--groups", "nowhere.py:GROUPS"]) == 2


def test_an_export_writes_the_monitor_s_own_page(tmp_path):
    static = tmp_path / "ui"
    static.mkdir()
    (static / "index.html").write_text("<title>x</title><ca-monitor></ca-monitor>", encoding="utf-8", newline="\n")
    for name in ("app.js", "ja.js"):
        (static / name).write_text(f"// own {name}", encoding="utf-8", newline="\n")
    export(Monitor(runs(tmp_path, ids=("only",)), static_dir=static), tmp_path / "site", now=NOW)
    assert (tmp_path / "site/app.js").read_text(encoding="utf-8") == "// own app.js"
    assert '<ca-monitor export="data/">' in (tmp_path / "site/index.html").read_text(encoding="utf-8")
    assert not (tmp_path / "site/favicon.svg").exists()  # a UI without icons: none copied


def test_an_export_carries_the_bundled_page_s_icons(tmp_path):
    export(Monitor(runs(tmp_path, ids=("only",))), tmp_path / "site", now=NOW)
    for name in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        assert (tmp_path / "site" / name).is_file()


def test_a_run_still_running_is_left_out_unless_asked_for(tmp_path):
    rd = runs(tmp_path)
    monitor = Monitor(rd)
    listed = monitor.runs()
    monitor.runs = lambda: [{**s, "running": s["run"] == "second"} for s in listed]  # the run writing the export
    assert export(monitor, tmp_path / "a", now=NOW).runs == ["first"]
    assert [r["run"] for r in json.loads((tmp_path / "a/data/runs.json").read_text(encoding="utf-8"))] == ["first"]
    assert export(monitor, tmp_path / "b", now=NOW, live=True).runs == ["second", "first"]


def test_a_trends_panel_is_checked_before_it_is_written(tmp_path):
    rd = runs(tmp_path, ids=("only",))
    bad = Panel(lambda runs, period: {"type": "hbars", "bars": [{"label": "x"}]}, scope="trends")
    export(Monitor(rd, panels={"bad": bad}), tmp_path / "site", now=NOW, period=Period.parse("2026-01-01", "2026-12-31"))
    written = json.loads((tmp_path / "site/data/trends/panels/bad.json").read_text(encoding="utf-8"))
    assert written.keys() == {"error"} and "ValidationError" in written["error"]
