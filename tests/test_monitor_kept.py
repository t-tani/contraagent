"""What the monitor keeps between requests, so that the feeds of many clients do not make
it again each tick: a run's plan and outputs (made again when a record, a running task or an
output file changes), their written text, a run panel's body for one tick, and where a
transcript's last page ended and how many lines it has."""

import asyncio
import json
from pathlib import Path

from pydantic import BaseModel

from contraagent import Pipeline, agent_task
from contraagent._internal.monitor import core, server
from contraagent._internal.monitor.views import VIEWS, serialize, serialize_kept
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


class Given(BaseModel):
    doc: Doc


def make_run(tmp_path, run_id="r"):
    write = agent_task("write", instructions="Write.", output=Doc, max_turns=3, timeout_s=30)
    check = agent_task("check", instructions="Check.", params=Given, output=Doc, max_turns=3, timeout_s=30)
    agent = StubAgent(
        {"write": lambda launch: {"unit": launch.unit, "text": "t"}, "check": lambda launch: {"unit": launch.unit, "text": "c"}}
    )

    async def flow():
        for u in ("a", "b"):
            await check(u, Given(doc=await write(u)))

    runs = tmp_path / "runs"
    Pipeline(None, runs_dir=runs, backends=agent.backends(), cwd=tmp_path, log=lambda line: None).run(flow, run_id=run_id)
    return runs


def append_row(runs, key: str) -> None:
    journal = runs / "r" / "journal.jsonl"
    row = json.loads(journal.read_text().splitlines()[0])
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**row, "key": key}) + "\n")


def test_the_plan_is_kept_until_a_record_of_it_changes(tmp_path):
    runs = make_run(tmp_path)
    monitor = Monitor(runs)
    first = monitor.plan("r")
    assert monitor.plan("r") is first
    append_row(runs, "write-c")
    again = monitor.plan("r")
    assert again is not first and "write-c" in {n["key"] for n in again["nodes"]}


def test_the_outputs_are_kept_until_a_file_they_show_changes(tmp_path, monkeypatch):
    runs = make_run(tmp_path)
    monitor = Monitor(runs)
    first = monitor.outputs("r")
    out = runs / "r" / "out" / "write" / "a.json"
    out.write_text(json.dumps({"unit": "a", "text": "changed by hand"}), encoding="utf-8")
    # Checked less than a tick ago: given as it was, unchecked.
    assert monitor.outputs("r") is first
    monkeypatch.setattr(core, "OUTPUTS_FRESH_S", 0.0)
    again = monitor.outputs("r")
    shown = {Path(spec["path"]): spec["file"]["content"] for rec in again["contracts"] for spec in rec["outputs"]}
    assert again is not first and shown[out.resolve()]["text"] == "changed by hand"
    assert monitor.outputs("r") is again


def test_a_task_s_input_and_output_are_those_of_the_run_s_outputs(tmp_path):
    runs = make_run(tmp_path)
    monitor = Monitor(runs)
    for key in ("write-a", "check-a", "check-b"):
        assert monitor.task_io("r", key) == monitor.task_io("r", key, outputs=monitor.outputs("r"))


def test_a_kept_value_is_written_once(tmp_path):
    runs = make_run(tmp_path)
    monitor = Monitor(runs)
    model = VIEWS["plan"].model
    plan = monitor.plan("r")
    text = serialize_kept(model, plan)
    assert text == serialize(model, plan) and serialize_kept(model, plan) is text
    append_row(runs, "write-c")
    assert serialize_kept(model, monitor.plan("r")) != text


def test_a_run_panel_is_called_once_a_tick_for_every_feed(tmp_path):
    runs = make_run(tmp_path)
    calls: list[str] = []

    def panel(records):
        calls.append("r")
        return {"text": f"{len(calls)} calls"}

    monitor = Monitor(runs, panels={"p": panel})

    async def both():
        return await asyncio.gather(server._panel_body(monitor, "p", "r"), server._panel_body(monitor, "p", "r"))

    first, second = asyncio.run(both())
    assert first == second and calls == ["r"]


def test_a_transcript_is_read_on_from_where_its_last_page_ended(tmp_path):
    runs = make_run(tmp_path)
    log = runs / "r" / "streams" / "write-a.stream.jsonl"
    log.write_text("".join(json.dumps({"type": "x", "n": i}) + "\n" for i in range(10)), encoding="utf-8")
    monitor = Monitor(runs)
    page, end = monitor.stream_from("r", "write-a", None)
    assert (page["total"], end) == (10, 10)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "x", "n": 10}) + "\n" + '{"type": "x", "n": 1')  # the last line not yet whole
    page, end = monitor.stream_from("r", "write-a", end)
    assert (page["total"], end) == (11, 11)
    with log.open("a", encoding="utf-8") as f:
        f.write("1}\n")
    page, end = monitor.stream_from("r", "write-a", end)
    assert (page["total"], end) == (12, 12)
    # Another, shorter log under the same name: fewer lines than the feed read.
    log.write_text(json.dumps({"type": "x"}) + "\n", encoding="utf-8")
    page, _ = monitor.stream_from("r", "write-a", end)
    assert page["total"] == 1 and page["events"] == []
    page, end = monitor.stream_from("r", "write-a", None)
    assert (page["total"], end) == (1, 1)
