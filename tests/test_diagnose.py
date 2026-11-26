"""`contraagent diagnose`: what a run's records say to change in its pipeline, kind by kind,
and with `--against`, what changed since an earlier run of the same tasks."""

import asyncio
import json
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, agent_task
from contraagent._internal.cli import main
from contraagent._internal.monitor.diagnosis import CHANGE_FIELD, CHANGE_FILE, CHANGE_VALIDATOR, DiagnosisError, diagnose
from contraagent.backends import Stop
from contraagent.docs.examples.demo import test_demo as demo
from contraagent.docs.examples.demo.tasks import docs
from contraagent.testing import StubAgent, fails


class Doc(BaseModel):
    unit: str
    text: str


class Given(BaseModel):
    doc: Doc


def three_words(path, doc: Doc):
    """At least three words."""
    if len(doc.text.split()) < 3:
        return [f"text: three words or more, got {len(doc.text.split())}"]


def flow_of(instructions: str = "Write."):
    write = agent_task(
        "write", instructions=instructions, output=Doc, validators=[three_words], max_turns=3, timeout_s=30, max_corrections=1
    )
    check = agent_task("check", instructions="Check.", params=Given, output=Doc, max_turns=3, timeout_s=30)

    async def one(unit: str):
        await check(unit, Given(doc=await write(unit)))

    async def flow(units: list[str]):
        await asyncio.gather(*(one(unit) for unit in units), return_exceptions=True)

    return flow


def pipeline(tmp_path, agent: StubAgent) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)


def signs(found, kind: str) -> dict[str, tuple[str, ...]]:
    """A kind's signs, each by its text up to its count, with its tasks."""
    return {s.what.split(" in ")[0]: s.keys for s in found.kinds[kind].signs}


def test_the_demo_run_names_what_to_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "inputs").mkdir()
    for u in demo.UNITS:
        (tmp_path / "inputs" / f"{u}.md").write_text(f"# {u}\nThe {u} component parses a config file.\n", encoding="utf-8")
    report = Pipeline(demo.HERE / "pipeline.toml", runs_dir=tmp_path / "runs", backends=demo.stub().backends()).run(
        docs, units=demo.UNITS, run_id="docs-1"
    )
    found = diagnose(report.run_dir)
    assert not found.ok
    summarize = found.kinds["summarize"]
    sent_back = next(s for s in summarize.signs if s.change == CHANGE_VALIDATOR)
    assert sent_back.keys == ("summarize-delta",)
    assert sent_back.what == 'an output did not pass [three_points] in 1 of 4 tasks: "points: exactly three expected, got 2"'
    assert sent_back.transcript == "streams/summarize-delta.stream.jsonl"
    assert signs(found, "summarize")["a launch ended rate_limited on hop 1/2 stub/primary-model"] == ("summarize-beta",)
    # review-alpha's first attempt ended in an error, and its retry passed: still a sign.
    assert signs(found, "review")["an attempt ended error"] == ("review-alpha",)
    assert found.kinds["review"].passed == found.kinds["review"].tasks
    assert signs(found, "prepare")["the function raised"] == ("python:prepare-zeta",)
    assert found.kinds["score"].partial == 1 and not found.kinds["score"].signs
    text = str(found)
    assert text.startswith("✗ docs-1, 7 kinds, 25 tasks: 23 passed, 1 partial, 1 failed")
    assert "  nothing to change in score, revise, write_note, report" in text
    assert f"      transcript: {Path(report.run_dir).as_posix()}/streams/summarize-delta.stream.jsonl" in text


def test_an_output_sent_back_is_counted_by_the_check_that_sent_it(tmp_path):
    agent = StubAgent(
        {
            "write-a": lambda launch: {"unit": "a", "text": "three good words"},
            "write-b": [{"unit": "b", "text": "two words"}, {"unit": "b", "text": "now three words"}],
            "write-c": {"unit": "c", "text": "short"},
            "write-d": [{"unit": "d"}, {"unit": "d", "text": "a third try"}],
            "check": lambda launch: launch.params["doc"],
        }
    )
    pipeline(tmp_path, agent).run(flow_of(), units=["a", "b", "c", "d"], run_id="r")
    found = diagnose(tmp_path / "runs" / "r")
    write = {s.what.split(" in ")[0]: s for s in found.kinds["write"].signs}
    # c's only reply is wrong: it is sent back once and still does not pass after its one correction.
    words = write["an output did not pass [three_words]"]
    assert sorted(words.keys) == ["write-b", "write-c"]  # in the order of the journal
    # The message is the first task's, in the order of the journal: b's or c's.
    assert re.fullmatch(
        r'an output did not pass \[three_words\] in 2 of 4 tasks: "text: three words or more, got [12]"; '
        r"1 of them still did not pass it after every correction",
        words.what,
    )
    assert write["an output did not pass the field text"].keys == ("write-d",)
    assert write["an output did not pass the field text"].change == CHANGE_FIELD
    assert found.kinds["write"].failed == 1


def _run_dir(tmp_path: Path, journal: list[dict], launches: list[dict] = (), **info) -> Path:
    """A run directory written by hand: `run.json`, the journal and the launches."""
    d = tmp_path / "runs" / "hand"
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"format": 1, "run_id": "hand", "finished_at": "2026-11-26T10:00:00Z", **info}))
    rows = [{"ts": "2026-11-26T09:00:00Z", "ok": True, "stop": "completed", "rounds": 1, **row} for row in journal]
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "launches.jsonl").write_text("".join(json.dumps(r) + "\n" for r in launches))
    return d


def _hop(stop: str = "completed", **more) -> dict:
    return {"route": "hop 1/1 claude/m", "agent": "claude", "model": "m", "stop": stop, **more}


def test_launches_stopped_refused_or_passed_over(tmp_path):
    journal = [
        {"key": "r-a", "kind": "r", "hops": [_hop("max_turns", max_turns=20, num_turns=20), _hop(num_turns=5)], "cost_usd": 0.1},
        {"key": "r-b", "kind": "r", "hops": [_hop("refused")], "ok": False, "stop": "refused", "cost_usd": 0.1},
        {"key": "r-c", "kind": "r", "hops": [_hop()], "safety_stops": [{"part": "response"}], "context_warned": True, "cost_usd": 0.1},
        {
            "key": "r-d",
            "kind": "r",
            "hops": [_hop()],
            "skipped_hops": [{"credential": "team", "route": "hop 1/2 claude/m"}],
            "cost_usd": 0.1,
        },
        {"key": "r-e", "kind": "r", "hops": [_hop()], "cost_usd": 0.9},
        {"key": "r-f", "kind": "r", "hops": [_hop()], "cost_usd": 0.1},
        {"key": "w-a", "kind": "w", "hops": [_hop("context_budget")], "ok": False, "stop": "context_budget", "context_warned": True},
        {
            "key": "w-a",
            "kind": "w",
            "attempt": 1,
            "hops": [_hop("rate_limited"), _hop("no_output", route="hop 2/2 omp/m")],
            "ok": False,
            "stop": "no_output",
            "reason": "nothing written",
        },
    ]
    launches = [
        {
            "label": "r-a",
            "permission_denials": 2,
            "denied": [{"tool": "Bash", "input": '{"command": "rm -rf build"}'}, {"tool": "WebFetch", "input": "{}"}],
        }
    ]
    found = diagnose(_run_dir(tmp_path, journal, launches))
    r = signs(found, "r")
    assert r["a launch reached its max_turns (20)"] == ("r-a",)
    assert r["a launch refused by a safety classifier"] == ("r-b",)
    assert r["part of a launch stopped by a safety classifier"] == ("r-c",)
    assert r["the peak context came near context_budget"] == ("r-c",)
    assert r["hop 1/2 claude/m passed over while team rested"] == ("r-d",)
    assert r["calls of Bash refused"] == ("r-a",)
    assert r["cost over 3 times the kind's median ($0.10)"] == ("r-e",)
    assert found.kinds["r"].failed == 1 and found.kinds["r"].cost_usd == pytest.approx(1.4)
    w = signs(found, "w")
    # A launch stopped at a limit is not also an attempt that ended in another stop.
    assert w == {
        "a launch reached its context_budget": ("w-a",),
        "a launch ended rate_limited on hop 1/1 claude/m": ("w-a",),
        "an attempt ended no_output": ("w-a",),
    }


def test_a_run_with_nothing_to_change(tmp_path, capsys):
    d = _run_dir(tmp_path, [{"key": "r-a", "kind": "r", "hops": [_hop()]}], finished_at="")
    found = diagnose(d)
    assert found.ok and not found.finished
    assert str(found) == "✓ hand, 1 kind, 1 task: 1 passed; the run has not finished\n  nothing to change in r"
    assert main(["diagnose", str(d)]) == 0
    assert capsys.readouterr().out.startswith("✓ hand")


def test_a_directory_that_is_no_run(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    assert main(["diagnose", str(tmp_path / "empty")]) == 1
    assert "holds no run.json, so it is no run directory" in capsys.readouterr().out
    with pytest.raises(DiagnosisError, match="no such directory"):
        diagnose(tmp_path / "absent")
    d = _run_dir(tmp_path, [], format=9)
    with pytest.raises(DiagnosisError, match="run format 9"):
        diagnose(d)


def test_a_change_compared_with_the_run_it_was_made_from(tmp_path, capsys):
    """The role of `write` changes, and `b`'s output with it: the new run launches every
    `write` again and the `check` given b's new output, and takes over a's `check`."""
    texts = {"a": "three good words", "b": "two words"}
    agent = StubAgent(
        {
            "write": lambda launch: {"unit": launch.unit, "text": texts[launch.unit]},
            "check": lambda launch: launch.params["doc"],
        }
    )
    old = pipeline(tmp_path, agent).run(flow_of(), units=["a", "b"], run_id="old")
    assert not old.ok  # b's write fails its validator twice
    texts["b"] = "now three words"
    new = pipeline(tmp_path, agent).run(flow_of("Write three words or more."), units=["a", "b"], run_id="new", resume_from="old")
    assert new.ok
    found = diagnose(new.run_dir, against=old.run_dir)
    assert found.ok and found.taken_over == 1 and found.resumed_from == "old"  # a's check
    c = found.against
    assert c is not None and c.earlier == "old" and c.taken_over == 1  # a's check: same input, same definition
    write = c.kinds["write"]
    assert write.tasks == 2 and write.parts == {"definition": 2}
    assert write.passing == ["write-b"] and write.failing == []
    assert write.passed == (1, 2) and write.sent_back == (1, 0)
    assert write.outputs_compared == 1 and write.outputs_differ == []  # a wrote the same output
    assert "check" not in c.kinds  # b's check did not run in the old run
    assert main(["diagnose", str(new.run_dir), "--against", str(old.run_dir)]) == 0
    out = capsys.readouterr().out
    assert "against old: 2 tasks ran in both runs, and new took over 1 from it" in out
    assert "  write, 2 tasks, changed: definition in 2\n    passed 1 → 2, sent back 1 → 0\n    passing now: write-b" in out
    assert out.rstrip().endswith("each task ran once in each run: a difference in a few tasks can be chance")
    with pytest.raises(DiagnosisError, match="the run itself"):
        diagnose(new.run_dir, against=new.run_dir)


def test_an_error_line_gives_the_check_that_sent_it():
    from contraagent._internal.monitor.diagnosis import _check_of

    assert _check_of("/runs/r/out/w/a.json: [three_words] text: three words or more, got 2") == (
        "[three_words]",
        CHANGE_VALIDATOR,
        "text: three words or more, got 2",
    )
    assert _check_of("/runs/r/out/w/a.json: items.3.address: Field required")[:2] == ("the field items.*.address", CHANGE_FIELD)
    assert _check_of("/runs/r/out/w/a.jsonl: line 7: severity: Input should be 'low' (got: \"x\")") == (
        "the field severity",
        CHANGE_FIELD,
        "line 7: severity: Input should be 'low'",
    )
    assert _check_of("/runs/r/out/w/a.json: <root>: Input should be an object")[0] == "the output as a whole"
    assert _check_of("/runs/r/out/w/a.json: file was not written") == ("file was not written", CHANGE_FILE, "file was not written")
    assert _check_of("C:/runs/r/out/w/a.json: not valid JSON: Expecting value: line 1 column 1 (char 0)")[0] == "not valid JSON"
    assert _check_of("the final message is empty")[0] == "the final message is empty"


def test_a_stub_failure_is_no_launch_limit(tmp_path):
    """A launch the stub ends on max_turns: the attempt's stop is the hop's, one sign."""
    agent = StubAgent({"write": fails(Stop.MAX_TURNS, "out of turns"), "check": lambda launch: launch.params["doc"]})
    pipeline(tmp_path, agent).run(flow_of(), units=["a"], run_id="r")
    assert signs(diagnose(tmp_path / "runs" / "r"), "write") == {"a launch reached its max_turns (3)": ("write-a",)}
