"""The parts of an output file an agent task keeps (`agent_task(preserve=)`): the pointers
(`contraagent._internal.contracts.pointers`), their checks at declaration, and a run whose agent breaks a part."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.contracts.pointers import kept, pointer_of, same, schema_error, segments, select, syntax_error
from contraagent.backends import CallFile, Stop
from contraagent.engine import OutputContract
from contraagent.testing import StubAgent, fails


class Entry(BaseModel):
    id: str
    title: str
    tags: dict[str, str] = {}
    extra: Any = None


class Doc(BaseModel):
    source: str
    items: list[Entry]
    pair: tuple[int, str] = (0, "")


DOC = {"source": "a.md", "items": [{"id": "x1", "title": "One"}, {"id": "x2", "title": "Two"}], "a/b": {"~": 1}}


def test_a_pointer_selects_each_value_by_the_pointer_that_names_it_alone():
    assert select(DOC, "/items/*/id") == {"/items/0/id": "x1", "/items/1/id": "x2"}
    assert select(DOC, "/source") == {"/source": "a.md"}
    assert select(DOC, "/items/1") == {"/items/1": {"id": "x2", "title": "Two"}}
    assert select(DOC, "/a~1b/~0") == {"/a~1b/~0": 1}
    assert select(DOC, "/*") == {"/source": "a.md", "/items": DOC["items"], "/a~1b": {"~": 1}}
    # What the document does not hold selects nothing.
    assert select(DOC, "/missing") == {}
    assert select(DOC, "/items/5/id") == {}
    assert select(DOC, "/items/01/id") == {}
    assert select(DOC, "/source/*") == {}
    assert segments("/a~1b/~0/*") == ["a/b", "~", "*"]
    assert pointer_of(["a/b", "~", 3]) == "/a~1b/~0/3"


def test_kept_names_each_part_that_changed_or_was_removed():
    before = select(DOC, "/items/*/id") | select(DOC, "/source")
    after = {"source": "a.md", "items": [{"id": "x1"}, {"id": "y2"}]}
    assert kept(after, before) == ['/items/1/id changed: it must stay "x2" (now "y2")']
    assert kept({"items": [{"id": "x1"}]}, before) == [
        '/items/1/id removed: it must stay "x2"',
        '/source removed: it must stay "a.md"',
    ]
    assert kept(DOC, before) == []


def test_json_values_are_equal_by_value():
    assert same(1, 1.0) and same({"a": [1, 2]}, {"a": [1.0, 2]})
    assert not same(True, 1) and not same(0, False) and not same("1", 1) and not same(None, 0)
    assert same({"a": 1, "b": 2}, {"b": 2, "a": 1}) and not same([1, 2], [2, 1])


def test_a_pointer_is_judged_by_its_syntax_and_by_the_schema():
    assert syntax_error("/items/*/id") is None
    assert "does not start with /" in (syntax_error("items") or "")
    assert "whole document" in (syntax_error("") or "")
    assert "~0 or ~1" in (syntax_error("/a~2") or "")
    assert "not a string" in (syntax_error(3) or "")
    schema = Doc.model_json_schema()
    good = ("/source", "/items/*/id", "/items/0/title", "/items/*/tags/any", "/items/*/tags/*", "/items/*/extra/deep/0", "/pair/1", "/*")
    for pointer in good:
        assert schema_error(pointer, schema) is None, pointer
    assert schema_error("/sorce", schema) == "'/sorce': the document has no field 'sorce' in the output schema"
    assert schema_error("/items/*/name", schema) == "'/items/*/name': /items/* has no field 'name' in the output schema"
    assert schema_error("/items/id", schema) == "'/items/id': /items is a list; name an index or *"
    assert schema_error("/source/x", schema) is not None


def test_a_declaration_that_cannot_preserve_is_refused():
    def declare(**options):
        return agent_task("fill", instructions="x", max_turns=1, timeout_s=1, **{"output": Doc, **options})

    assert declare(preserve=["/source", "/items/*/id"]).preserve == ("/source", "/items/*/id")
    with pytest.raises(TypeError, match="has no field 'sorce'"):
        declare(preserve=["/sorce"])
    with pytest.raises(TypeError, match="does not start with /"):
        declare(preserve=["source"])
    with pytest.raises(TypeError, match="not one string"):
        declare(preserve="/source")
    with pytest.raises(TypeError, match="a pydantic model"):
        declare(output=str, preserve=["/source"])
    with pytest.raises(TypeError, match='output_from="message"'):
        declare(output_from="message", preserve=["/source"])


def test_preserve_is_part_of_the_definition():
    plain = agent_task("fill", instructions="x", output=Doc, max_turns=1, timeout_s=1)
    keeping = agent_task("fill", instructions="x", output=Doc, preserve=["/source"], max_turns=1, timeout_s=1)
    assert plain.digest() != keeping.digest()
    assert plain.differences(keeping) == ["preserve"]


def test_a_contract_checks_the_parts_against_the_file_as_it_was(tmp_path):
    path = tmp_path / "doc.json"
    contract = OutputContract(path, Doc, fresh=False, preserve=("/items/*/id",))
    assert contract.before(tmp_path).preserved == {}  # no file: nothing to keep
    path.write_text(json.dumps({"source": "a.md", "items": [{"id": "x1", "title": "One"}]}))
    before = contract.before(tmp_path)
    assert before.preserved == {"/items/0/id": "x1"}
    path.write_text(json.dumps({"source": "a.md", "items": [{"id": "y1", "title": "One"}], "pair": "bad"}))
    errors = contract.check(tmp_path, before).errors
    assert any("pair" in e for e in errors), errors  # the schema's errors and the parts', in one round
    assert f'{path}: /items/0/id changed: it must stay "x1" (now "y1")' in errors
    path.write_text(json.dumps({"source": "b.md", "items": [{"id": "x1", "title": "Uno"}]}))
    assert contract.check(tmp_path, before).ok
    path.write_text("not json")
    assert contract.before(tmp_path).preserved == {}  # a file that does not parse keeps nothing


def run_example(tmp_path, reply):
    from contraagent.docs.examples.preserve import flow as example

    stub = StubAgent({"fill": reply})
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path)
    report = pipeline.run(example.reports, units={"alpha": ["Setup", "Usage"]})
    return report, stub


def filled(launch, **changes):
    """The report in the output file as it is, every summary filled in, then `changes`."""
    doc = json.loads(Path(launch.call.output.path).read_text())
    for item in doc["items"]:
        item["summary"] = f"About {item['title']}."
    return {**doc, **changes}


def test_a_round_that_breaks_a_kept_part_goes_back_and_the_next_round_keeps_it(tmp_path):
    def reply(launch):
        doc = filled(launch)
        if not launch.resumed:
            doc["items"][1]["id"] = "alpha-9"
            doc["source"] = "elsewhere.md"
        else:  # the correction: the parts the errors name, back as they were
            doc["items"][1]["id"] = "alpha-2"
            doc["source"] = "inputs/alpha.md"
        return doc

    report, stub = run_example(tmp_path, reply)
    assert report.ok, report.failed
    result = report.results["fill-alpha"].launch_result
    assert result is not None and result.rounds == 2
    errors = result.round_errors[0]
    assert any(e.endswith('/items/1/id changed: it must stay "alpha-2" (now "alpha-9")') for e in errors), errors
    assert any(e.endswith('/source changed: it must stay "inputs/alpha.md" (now "elsewhere.md")') for e in errors), errors
    resumed = [launch for launch in stub.launches if launch.resumed]
    assert len(resumed) == 1 and "/items/1/id changed" in resumed[0].prompt
    first = stub.launches[0]
    assert "`/items/*/id`" in first.prompt and "Read the file first" in first.prompt
    call = CallFile.read(report.run_dir / "calls" / "fill-alpha.json")
    assert call.output is not None and call.output.preserve == ["/source", "/items/*/id", "/items/*/title"]
    out = json.loads((report.run_dir / "out" / "outline" / "alpha.json").read_text())
    assert [i["id"] for i in out["items"]] == ["alpha-1", "alpha-2"] and out["items"][0]["summary"] == "About Setup."
    definition = json.loads((report.run_dir / "definitions" / "fill.json").read_text())
    assert definition["preserve"] == ["/source", "/items/*/id", "/items/*/title"]
    contracts = json.loads((report.run_dir / "contracts" / "fill-alpha.json").read_text())
    assert contracts["outputs"][0]["preserve"] == ["/source", "/items/*/id", "/items/*/title"]


def test_an_attempt_that_does_not_pass_leaves_the_file_as_it_was(tmp_path):
    def reply(launch):
        if launch.n > 1:
            return fails(Stop.TIMEOUT, "killed")
        return filled(launch, items=[])  # every item removed

    report, _ = run_example(tmp_path, reply)
    assert not report.ok
    out = json.loads((report.run_dir / "out" / "outline" / "alpha.json").read_text())
    assert [(i["id"], i["summary"]) for i in out["items"]] == [("alpha-1", ""), ("alpha-2", "")]


class Notes(BaseModel):
    text: str = ""
    seen: int = 0


def test_output_of_is_refused_where_it_cannot_name_a_file_of_the_same_format():
    from contraagent import python_task

    @python_task
    def start(unit: str) -> Notes:
        return Notes()

    @python_task
    def nothing(unit: str) -> None:
        return None

    def declare(**options):
        return agent_task("grow", instructions="x", max_turns=1, timeout_s=1, **{"output": Notes, "output_of": start, **options})

    assert declare().output_of is start
    assert declare().digest() != agent_task("grow", instructions="x", output=Notes, max_turns=1, timeout_s=1).digest()
    text = agent_task("draft", instructions="x", output=str, max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="drop output_name"):
        declare(output_name="{unit}.json")
    with pytest.raises(TypeError, match="needs output="):
        declare(output=None)
    with pytest.raises(TypeError, match="writes no output file"):
        declare(output_of=nothing)
    with pytest.raises(TypeError, match="writes a text file, and this output is json"):
        declare(output_of=text)
    with pytest.raises(TypeError, match="takes a task declaration"):
        declare(output_of="start")


def test_output_of_writes_the_file_of_the_latest_task_of_that_kind_for_the_unit_and_waits_for_it(tmp_path):
    start = agent_task("start", instructions="x", output=Notes, max_turns=1, timeout_s=1)
    grow = agent_task("grow", instructions="x", output=Notes, output_of=start, preserve=["/text"], max_turns=1, timeout_s=1)

    def flow():
        start("a")
        grow("a")  # out/start/a.json, after start-a
        start("a")  # start-a~2: out/start/a~2.json
        grow("a")  # grow-a~2: out/start/a~2.json, after start-a~2
        grow("a")  # grow-a~3: the same file, after grow-a~2, its last writer
        grow("b")  # no start for b: out/start/b.json, waiting for nothing

    def reply(launch):
        path = Path(launch.call.output.path)
        doc = json.loads(path.read_text()) if path.exists() else {"text": launch.key}
        return {**doc, "seen": doc.get("seen", 0) + 1}

    stub = StubAgent({"start": reply, "grow": reply})
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path).run(flow)
    assert report.ok, report.failed
    out = report.run_dir / "out" / "start"
    paths = {launch.key: Path(launch.call.output.path) for launch in stub.launches}
    assert paths["grow-a"] == out / "a.json" and paths["grow-b"] == out / "b.json"
    assert paths["grow-a~2"] == paths["grow-a~3"] == paths["start-a~2"] == out / "a~2.json"
    rows = [json.loads(line) for line in (report.run_dir / "plan.jsonl").read_text().splitlines()]
    after = {row["key"]: row.get("after", []) for row in rows if "key" in row}
    assert "start-a" in after["grow-a"] and "start-a~2" in after["grow-a~2"] and "grow-a~2" in after["grow-a~3"]
    assert after["grow-b"] == []
    assert json.loads((out / "a~2.json").read_text()) == {"text": "start-a~2", "seen": 3}
