"""A validator that takes `before`: the output file as it was before the task, parsed as
`value` is, on every round alike; read only when a validator asks for it."""

import json
from pathlib import Path

from pydantic import BaseModel

from contraagent import CommandValidator, OutputContract, Pipeline, PipelineConfig
from contraagent._internal.contracts.validators import run_validators, wanted_context
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.dispatch.task import STOP_INVALID_OUTPUT
from contraagent.backends import Stop
from contraagent.engine import PythonTaskRunner
from contraagent.testing import StubAgent, fails


class Doc(BaseModel):
    items: list[str]


def grows(path, doc: Doc, *, before: Doc | None):
    if before is not None and len(doc.items) <= len(before.items):
        return [f"items: {len(before.items)} before, {len(doc.items)} now"]


def test_before_is_part_of_the_context_and_is_computed_only_for_a_validator_that_takes_it():
    assert wanted_context(grows) == ("before",)
    assert "before" not in wanted_context(CommandValidator(["true"]))
    calls = []

    def value():
        calls.append(1)
        return Doc(items=["a"])

    def plain(path, doc):
        return None

    assert run_validators([plain], Path("x"), Doc(items=[]), before=value) == []
    assert calls == []
    errors = run_validators([grows, grows], Path("x"), Doc(items=["a"]), before=value)
    assert errors == ["x: [grows] items: 1 before, 1 now"] * 2 and calls == [1]


def test_the_file_is_read_ahead_of_the_task_only_for_a_contract_that_compares(tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps({"items": ["a"]}))
    plain = OutputContract(path, Doc, fresh=False)
    assert not plain.compares and plain.before(tmp_path).text is None
    contract = OutputContract(path, Doc, fresh=False, validators=(grows,))
    before = contract.before(tmp_path)
    assert contract.compares and before.value(Doc) == Doc(items=["a"])
    assert contract.check(tmp_path, before).errors == [f"{path}: [grows] items: 1 before, 1 now"]
    path.write_text(json.dumps({"items": ["a", "b"]}))
    assert contract.check(tmp_path, before).ok


def test_before_is_none_without_a_file_or_with_one_off_its_schema_and_the_text_for_a_text_output(tmp_path):
    path = tmp_path / "doc.json"
    contract = OutputContract(path, Doc, fresh=False, validators=(grows,))
    assert contract.before(tmp_path).value(Doc) is None
    path.write_text('{"items": 3}')
    assert contract.before(tmp_path).value(Doc) is None
    path.write_text("not json")
    assert contract.before(tmp_path).value(Doc) is None
    seen = []

    def records(path, text, *, before):
        seen.append((before, text))

    note = tmp_path / "note.md"
    note.write_text("# one\n")
    text = OutputContract(note, None, fresh=False, validators=(records,))
    was = text.before(tmp_path)
    note.write_text("# one\n# two\n")
    assert text.check(tmp_path, was).ok and seen == [("# one\n", "# one\n# two\n")]


def run_example(tmp_path, reply):
    from contraagent.docs.examples.before import flow as example

    stub = StubAgent({"grow": reply})
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path)
    return pipeline.run(example.backlogs, topics={"alpha": ["Cache the index"]}), stub


def test_a_round_that_adds_nothing_goes_back_and_before_stays_the_file_ahead_of_the_first_round(tmp_path):
    def reply(launch):
        doc = json.loads(Path(launch.call.output.path).read_text())
        if not launch.resumed:
            return {**doc, "ideas": ["Cached index"]}  # one removed, none added
        # The correction: compared with the file start wrote, not with the first round's.
        return {**doc, "ideas": ["Cache the index", "Cached index"]}

    report, stub = run_example(tmp_path, reply)
    assert report.ok, report.failed
    result = report.results["grow-alpha"].launch_result
    assert result is not None and result.rounds == 2
    errors = result.round_errors[0]
    removed = "[adds_an_idea] ideas: 'Cache the index' was removed; keep every idea the file held"
    assert any(e.endswith(removed) for e in errors), errors
    assert any(e.endswith("[adds_an_idea] ideas: add at least one idea to the 1 the file held") for e in errors), errors
    assert "add at least one idea" in next(launch for launch in stub.launches if launch.resumed).prompt


def test_an_attempt_that_does_not_pass_leaves_the_file_as_it_was(tmp_path):
    def reply(launch):
        if launch.n > 1:
            return fails(Stop.TIMEOUT, "killed")
        return {"topic": "alpha", "ideas": []}

    report, _ = run_example(tmp_path, reply)
    assert not report.ok
    out = json.loads((report.run_dir / "out" / "start" / "alpha.json").read_text())
    assert out["ideas"] == ["Cache the index"]


def test_a_python_task_s_validator_compares_with_the_file_before_the_task(tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps({"items": ["a"]}))
    contract = OutputContract(path, Doc, fresh=False, validators=(grows,))

    def same():
        path.write_text(json.dumps({"items": ["b"]}))

    def more():
        path.write_text(json.dumps({"items": ["a", "b"]}))

    result = PythonTaskRunner(cwd=tmp_path).run(make_python_task("same", same, output_contracts=[contract]))
    assert result.stop == STOP_INVALID_OUTPUT and "[grows] items: 1 before, 1 now" in result.reason
    path.write_text(json.dumps({"items": ["a"]}))
    assert PythonTaskRunner(cwd=tmp_path).run(make_python_task("more", more, output_contracts=[contract])).ok
