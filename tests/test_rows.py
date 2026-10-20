"""Rows (`output=Rows[Row]`, a JSON Lines file checked line by line) and partial results of
agent tasks (`partial_on`: a launch stopped for its time keeps what it wrote), apart and
together."""

import json
from pathlib import Path

import pytest

from contraagent import ConfigError, Pipeline, PipelineConfig, Rows, agent_task, python_task
from contraagent._internal.contracts.calls import CallFile, validate_call
from contraagent._internal.contracts.contract import InputContract, check_file, check_input
from contraagent._internal.contracts.rows import rows_file
from contraagent.backends import Stop
from contraagent.docs.examples.rows import flow as example
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent, fails, writes, writes_example

Finding = example.Finding


def finding(n: int, doc: str = "docs/a.md") -> dict:
    return {"document": doc, "line": n, "note": f"problem {n}"}


def pipeline(tmp_path: Path, agent: StubAgent, config: Path | None = None) -> Pipeline:
    return Pipeline(config, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def output(report, unit: str = "a") -> Path:
    return report.run_dir / "out" / "review" / f"{unit}.jsonl"


# --- the check ---------------------------------------------------------------------


def test_a_rows_file_is_checked_line_by_line_and_its_value_is_a_list_of_rows(tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text("\n".join(json.dumps(finding(n)) for n in (1, 2)) + "\n\n")  # a blank line is no row
    chk = check_file(path, rows_file(Finding))
    assert chk.ok and isinstance(chk.value, Rows) and isinstance(chk.value, list)
    assert [f.line for f in chk.value] == [1, 2] and all(isinstance(f, Finding) for f in chk.value)


def test_each_error_of_a_rows_file_names_its_line(tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text(json.dumps(finding(1)) + "\n" + '{"document": "x", "line": 0, "note": "n"}\n' + "{not json\n")
    chk = check_file(path, rows_file(Finding))
    assert not chk.ok
    assert any(e.endswith("line 2: line: Input should be greater than or equal to 1 (got: 0)") for e in chk.errors), chk.errors
    assert any("line 3: not valid JSON" in e for e in chk.errors), chk.errors
    path.write_text(json.dumps([finding(1), finding(2)]))
    assert "the file is one JSON array; write one JSON object per line" in check_file(path, rows_file(Finding)).errors[0]


def test_a_rows_input_is_checked_line_by_line_too(tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text(json.dumps(finding(1)) + "\n{}\n")
    errors = check_input(InputContract(path, rows_file(Finding)), tmp_path)
    assert errors and all("line 2" in e for e in errors)


# --- a run ---------------------------------------------------------------------


def test_the_flow_receives_the_rows_as_a_list_and_passes_them_on(tmp_path):
    agent = StubAgent({"review": writes([finding(1), finding(2, "docs/b.md")])})
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    assert report.ok, report.results
    assert output(report).read_text().count("\n") == 2  # one row per line
    tally = json.loads((report.run_dir / "out" / "tally" / "a.json").read_text())
    assert tally == {"findings": 2, "documents": 2}
    [launch] = agent.launches
    assert launch.call.output is not None and launch.call.output.format == "jsonl"
    assert launch.call.output.json_schema == Finding.model_json_schema()
    assert launch.call.output.schema_ref is not None and launch.call.output.schema_ref.qualname == "Finding"
    assert "JSON Lines: one JSON object per line" in launch.prompt and "one line at a time" in launch.prompt


def test_a_bad_line_goes_back_in_a_correction_round_that_names_it(tmp_path):
    bad = '{"document": "docs/a.md", "line": 0, "note": "n"}'
    agent = StubAgent({"review": [writes(json.dumps(finding(1)) + "\n" + bad + "\n"), writes([finding(1), finding(2)])]})
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    assert report.ok
    resumed = [launch for launch in agent.launches if launch.resumed]
    assert len(resumed) == 1 and "line 2: line: Input should be greater than or equal to 1" in resumed[0].prompt
    assert "Required JSON Schema of each line" in resumed[0].prompt
    [row] = [r for r in journal(report) if r["kind"] == "review"]
    assert row["rounds"] == 2


def test_validators_see_the_rows_as_a_list(tmp_path):
    agent = StubAgent({"review": [writes([finding(1), finding(1)]), writes([finding(1), finding(2)])]})
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    assert report.ok
    [resumed] = [launch for launch in agent.launches if launch.resumed]
    assert "row 2: docs/a.md:1 has a finding already" in resumed.prompt


def test_the_example_of_rows_is_one_row(tmp_path):
    agent = StubAgent(default=writes_example())
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    assert report.ok
    assert [json.loads(line) for line in output(report).read_text().splitlines()] == [
        {"document": "docs/a.md", "line": 1, "note": "a broken link"}
    ]


def test_the_in_session_hook_checks_rows_line_by_line(tmp_path):
    agent = StubAgent({"review": writes([finding(1)])})
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    call_path = report.run_dir / "calls" / "review-a.json"
    assert validate_call(call_path) == (0, "")
    output(report).write_text("{}\n")
    code, message = validate_call(call_path)
    assert code == 2 and "line 1: document: Field required" in message


def test_a_python_task_returns_rows(tmp_path):
    @python_task
    def collect(unit: str) -> Rows[Finding]:
        return Rows([Finding(document="docs/a.md", line=n, note="n") for n in (1, 2)])

    async def flow():
        found = await collect("a")
        return [f.line for f in found]

    report = pipeline(tmp_path, StubAgent()).run(flow)
    assert report.ok and report.value == [1, 2]
    assert collect.output_format == "jsonl" and collect.output_name == "{kind}/{unit}.jsonl"
    assert len((report.run_dir / "out" / "collect" / "a.jsonl").read_text().splitlines()) == 2


def test_the_monitor_shows_rows_by_their_row_model_and_their_lines(tmp_path):
    report = pipeline(tmp_path, StubAgent({"review": writes([finding(1), finding(2)])})).run(example.reviews, units=["a"])
    outs = Monitor(tmp_path / "runs").outputs(report.run_dir.name)
    [spec] = next(c for c in outs["contracts"] if c["key"] == "review-a")["outputs"]
    assert spec["format"] == "jsonl" and spec["schema_name"] == "Rows[Finding]"
    assert [f["name"] for f in spec["fields"]] == ["document", "line", "note"]
    assert [r["line"] for r in spec["file"]["content"]] == [1, 2]


def test_a_rows_declaration_is_checked():
    with pytest.raises(TypeError, match="Rows takes a pydantic model"):
        agent_task("r", instructions="x", output=Rows[int], max_turns=1, timeout_s=1)  # pyright: ignore[reportInvalidTypeArguments]
    with pytest.raises(TypeError, match="Rows takes the model of one line"):
        agent_task("r", instructions="x", output=Rows, max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="preserve keeps parts of a JSON document"):
        agent_task("r", instructions="x", output=Rows[Finding], preserve=["/x"], max_turns=1, timeout_s=1)


# --- partial results of agent tasks -----------------------------------------------------------


def test_a_stopped_launch_with_three_valid_rows_is_a_partial_result_with_those_rows(tmp_path):
    rows = [finding(n) for n in (1, 2, 3)]
    agent = StubAgent({"review": writes(rows, stop=Stop.TIMEOUT)})

    async def flow():
        found = await example.review("a")
        return found

    report = pipeline(tmp_path, agent).run(flow)
    result = report.results["review-a"]
    assert result.ok and result.stop == "partial" and result.reason == "timeout"
    assert report.ok and report.partial == [result]
    assert isinstance(report.value, Rows) and [f.line for f in report.value] == [1, 2, 3]
    assert [h.stop for h in result.hops] == ["timeout"]  # the launch's own stop
    [row] = journal(report)
    assert row["stop"] == "partial" and row["ok"] and row["reason"] == "timeout"
    assert len(agent.launches) == 1  # no correction round, no retry
    nodes = {n["key"]: n for n in Monitor(tmp_path / "runs").plan(report.run_dir.name)["nodes"]}
    assert nodes["review-a"]["state"] == "partial"


def test_the_unfinished_last_line_of_a_stopped_launch_is_cut_off(tmp_path):
    def write_and_stop(launch):
        assert launch.call.output is not None
        lines = [json.dumps(finding(n)) for n in (1, 2)]
        Path(launch.call.output.path).write_text("\n".join(lines) + '\n{"document": "docs/a.md", "li')
        return fails(Stop.STALLED, "stub: no transcript line for 600 s")

    report = pipeline(tmp_path, StubAgent({"review": write_and_stop})).run(example.reviews, units=["a"])
    result = report.results["review-a"]
    assert result.stop == "partial" and result.reason == "stalled"
    assert len(output(report).read_text().splitlines()) == 2
    assert json.loads((report.run_dir / "out" / "tally" / "a.json").read_text())["findings"] == 2


def test_a_stopped_launch_whose_output_fails_its_checks_fails(tmp_path):
    agent = StubAgent({"review": writes([finding(1), finding(1)], stop=Stop.TIMEOUT)})  # `distinct` rejects it
    report = pipeline(tmp_path, agent).run(example.reviews, units=["a"])
    assert report.results["review-a"].stop == "timeout" and not report.results["review-a"].ok
    assert not any(launch.resumed for launch in agent.launches)


def test_a_stopped_launch_that_wrote_nothing_fails(tmp_path):
    report = pipeline(tmp_path, StubAgent({"review": fails(Stop.TIMEOUT)})).run(example.reviews, units=["a"])
    assert report.results["review-a"].stop == "timeout"


def test_other_stops_and_kinds_without_partial_on_keep_nothing(tmp_path):
    plain = agent_task("plain", instructions="x", output=Rows[Finding], max_turns=5, timeout_s=60, retries=0)
    capped = agent_task("capped", instructions="x", output=Rows[Finding], partial_on=["timeout"], max_turns=5, timeout_s=60, retries=0)
    agent = StubAgent({"plain": writes([finding(1)], stop=Stop.TIMEOUT), "capped": writes([finding(1)], stop=Stop.BUDGET)})
    report = pipeline(tmp_path, agent).run(lambda: [plain("a"), capped("a")])
    assert report.results["plain-a"].stop == "timeout"
    assert report.results["capped-a"].stop == "budget"
    assert not report.partial


def test_a_json_output_is_kept_after_a_timeout_too(tmp_path):
    long_task = agent_task("long", instructions="x", output=Finding, partial_on=["timeout"], max_turns=5, timeout_s=60)
    report = pipeline(tmp_path, StubAgent({"long": writes(finding(4), stop=Stop.TIMEOUT)})).run(lambda: long_task("a"))
    assert report.results["long-a"].stop == "partial"


def test_the_config_sets_partial_on_and_refuses_another_stop(tmp_path):
    long_task = agent_task("long", instructions="x", output=Finding, max_turns=5, timeout_s=60)
    config = tmp_path / "pipeline.toml"
    config.write_text('[tasks.long]\npartial_on = ["stalled"]\n')
    agent = StubAgent({"long": writes(finding(4), stop=Stop.STALLED)})
    report = pipeline(tmp_path, agent, config).run(lambda: long_task("a"))
    assert report.results["long-a"].stop == "partial" and report.results["long-a"].reason == "stalled"
    with pytest.raises(ConfigError, match=r"partial_on must be a list of 'timeout' and 'stalled', not 'budget'"):
        PipelineConfig({"tasks": {"long": {"partial_on": ["budget"]}}}).task_tables()
    with pytest.raises(ConfigError, match="partial_on"):
        agent_task("x", instructions="x", output=Finding, partial_on=["max_turns"], max_turns=1, timeout_s=1)  # pyright: ignore[reportArgumentType]


def test_partial_on_takes_an_output_the_agent_writes(tmp_path):
    with pytest.raises(TypeError, match="partial_on keeps the output file"):
        agent_task("m", instructions="x", output=Finding, output_from="message", partial_on=["timeout"], max_turns=1, timeout_s=1)
    verdict = agent_task("verdict", instructions="x", output=Finding, output_from="message", max_turns=1, timeout_s=1)
    config = tmp_path / "pipeline.toml"
    config.write_text('[tasks.verdict]\npartial_on = ["timeout"]\n')
    check = pipeline(tmp_path, StubAgent(), config).check(lambda: verdict("a"))
    assert any("partial_on = ['timeout'] keeps the output file" in e for e in check.errors), check.errors
    assert "contracts" in check.topics


def test_a_resume_runs_a_partial_review_again(tmp_path):
    agent = StubAgent({"review": [writes([finding(1)], stop=Stop.TIMEOUT), writes([finding(1), finding(2)])]})
    p = pipeline(tmp_path, agent)
    first = p.run(example.reviews, units=["a"], run_id="r")
    assert first.results["review-a"].stop == "partial"
    second = p.run(example.reviews, units=["a"], run_id="r", resume=True)
    assert second.results["review-a"].stop == "completed"
    assert second.results["python:tally-a"].stop == "completed"  # it waits for the review that ran again
    assert json.loads((second.run_dir / "out" / "tally" / "a.json").read_text())["findings"] == 2


def test_the_call_file_says_the_format(tmp_path):
    report = pipeline(tmp_path, StubAgent({"review": writes([finding(1)])})).run(example.reviews, units=["a"])
    call = CallFile.read(report.run_dir / "calls" / "review-a.json")
    assert call.output is not None and call.output.format == "jsonl" and call.output.path.endswith("review/a.jsonl")


def test_a_replay_plays_a_partial_review_as_partial_again(tmp_path):
    def run(name: str, **kw):
        (tmp_path / name).mkdir()
        return Pipeline(None, runs_dir=tmp_path / f"{name}-runs", cwd=tmp_path / name, log=lambda line: None, **kw).run(
            example.reviews, units=["a"]
        )

    live = run("live", stub=StubAgent({"review": writes([finding(1), finding(2)], stop=Stop.TIMEOUT)}), record=tmp_path / "rec")
    assert live.results["review-a"].stop == "partial"
    played = run("replay", replay=tmp_path / "rec")
    result = played.results["review-a"]
    assert result.stop == "partial" and result.reason == "timeout"
    assert output(played).read_text() == output(live).read_text()
