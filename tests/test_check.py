"""`Pipeline.check` and `contraagent check`: what is found wrong before anything launches."""

import functools
import json
import re
import sys

import pytest
from pydantic import BaseModel, Field, field_validator

from contraagent import CommandValidator, Pipeline, PipelineConfig, agent_task, python_task
from contraagent.cli import main
from contraagent.dispatch.task import kind_name
from contraagent.docs.examples.review import flow as example
from contraagent.pipeline.reach import reachable
from contraagent.plugins import new_plugin
from contraagent.routing.plan import RoutingPlan
from contraagent.testing import StubAgent


class Doc(BaseModel):
    path: str
    words: int


class Named(BaseModel):
    n: int = Field(ge=1)
    name: str

    @field_validator("name")
    @classmethod
    def lowercase(cls, v: str) -> str:
        if v != v.lower():
            raise ValueError("must be lowercase")
        return v


class Summary(BaseModel):
    points: list[str]


@pytest.fixture
def plugin_dir(tmp_path):
    new_plugin(tmp_path / "plugins" / "summarize")
    return tmp_path / "plugins" / "summarize"


def pipeline(config: dict | None = None) -> Pipeline:
    return Pipeline(PipelineConfig(config or {}), backends=StubAgent().backends())


def test_a_sound_flow_passes_and_counts_its_tasks(tmp_path, plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, params=Doc, output=Summary, max_turns=5, timeout_s=60)

    @python_task
    def total(summaries: list[Summary]) -> int:
        return sum(len(s.points) for s in summaries)

    def flow(units):
        total(summaries=[summarize(u, path=f"{u}.md", words=3) for u in units])

    report = pipeline().check(flow, ["a", "b"])
    assert report.ok, report
    assert report.kinds == {"summarize": 2, "total": 1}
    assert not (tmp_path / "runs").exists()


def test_what_a_run_would_find_one_launch_at_a_time_is_reported_at_once(plugin_dir):
    def local_model():
        class Local(BaseModel):
            x: int

        return Local

    summarize = agent_task(
        "summarize",
        plugin=plugin_dir,
        params=Doc,
        output=local_model(),
        validators=[CommandValidator(["no-such-linter-xyz"])],
        max_turns=5,
        timeout_s=60,
    )
    review = agent_task("review", plugin=plugin_dir, output=str)  # no budget

    def flow():
        s = summarize("a", path="a.md", words="many")
        review("a", s=s, after=["python:nowhere"])

    report = pipeline({"tasks": {"sumarize": {"max_turns": 3}}}).check(flow)
    assert not report.ok
    text = "\n".join(report.errors)
    assert "review-a: after='python:nowhere' names no task of this run" in text
    assert "summarize-a: param words: Input should be a valid integer" in text
    assert "where the in-session hook cannot import it" in text
    assert "no-such-linter-xyz is not on PATH" in text
    assert "kind review has no budget (max_turns, timeout_s): set it in agent_task('review', max_turns=..., timeout_s=...)" in text
    assert any("[tasks.sumarize] is not a kind of this run" in w for w in report.warnings)  # a typo, said out loud


def test_parameters_are_validated_as_the_run_will(plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, params=Named, output=Summary, max_turns=5, timeout_s=60)
    names = agent_task("names", plugin=plugin_dir, params=Named, output=Summary, max_turns=5, timeout_s=60)

    def flow():
        summarize("a", n=0, name="ABC")  # constraints and validators: the whole model
        names("b", n=0, name=summarize("c", n=1, name="c"))  # a Pending among them: field by field

    errors = pipeline().check(flow).errors
    assert "summarize-a: param n: Input should be greater than or equal to 1" in errors
    assert "summarize-a: param name: Value error, must be lowercase" in errors
    assert "names-b: param n: Input should be greater than or equal to 1" in errors
    assert not any(e.startswith("summarize-c") for e in errors)


def test_a_flow_that_raises_is_reported_at_the_callers_line(plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, params=Doc, output=Summary, max_turns=5, timeout_s=60)

    def flow():
        summarize("a", path="a.md")  # words missing

    report = pipeline().check(flow)
    assert len(report.errors) == 1
    assert f"{__file__}:" in report.errors[0] and "missing words" in report.errors[0]


def test_a_broken_plugin_is_linted(plugin_dir):
    (plugin_dir / "hooks.toml").write_text("")
    summarize = agent_task("summarize", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    report = pipeline().check(lambda: summarize("a"))
    assert any(e.startswith(f"plugin {plugin_dir.resolve()}: hooks.toml: no stop hook") for e in report.errors)


def test_the_command_line_imports_a_flow_file_as_the_hook_would(tmp_path, plugin_dir, capsys, monkeypatch):
    (tmp_path / "tasks.py").write_text(
        "from pydantic import BaseModel\n"
        "from contraagent import agent_task\n"
        "class Summary(BaseModel):\n    points: list[str]\n"
        "summarize = agent_task('summarize', plugin='plugins/summarize', output=Summary, max_turns=5, timeout_s=60)\n"
        "def flow(units):\n    for u in units:\n        summarize(u)\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert main(["check", "tasks.py:flow", "--stub", "--kwargs", json.dumps({"units": ["a", "b"]})]) == 0
    assert capsys.readouterr().out.startswith("✓ 2 tasks, 1 kinds: summarize 2")
    sys.modules.pop("tasks", None)

    (tmp_path / "tasks.py").write_text(
        "from contraagent import agent_task\nsummarize = agent_task('summarize', plugin='plugins/summarize', role='nobody', output=str)\n"
    )
    assert main(["check", "tasks.py:flow"]) == 1
    assert "no role 'nobody'" in capsys.readouterr().out
    sys.modules.pop("tasks", None)


def test_every_routing_problem_is_reported_in_one_check(plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    review = agent_task("review", plugin=plugin_dir, output=Summary)  # no budget
    config = {
        "defaults": {"max_turnz": 3, "effort": "ultra"},
        "tasks": {
            "summarize": {"max_turn": 3},
            "review": {"fallbacks": [{"agent": "clade", "model": "m"}]},
        },
    }

    def flow():
        review("a", s=summarize("a"))

    errors = Pipeline(PipelineConfig(config)).check(flow).errors
    assert [e.split("; expected")[0].split("; claude takes")[0].split("; known:")[0] for e in errors] == [
        "routing: <config>: [defaults] has unknown keys 'max_turnz' (max_turns is a [tasks.<kind>] key, or an agent_task argument)",
        "routing: <config>: [tasks.summarize] has unknown keys 'max_turn' (did you mean max_turns?)",
        "routing: kind review has no budget (max_turns, timeout_s): "
        "set it in agent_task('review', max_turns=..., timeout_s=...) or in [tasks.review]",
        "routing: effort 'ultra' for kinds review, summarize on agent claude is not accepted",
        "routing: <config> [[tasks.review.fallbacks]]: block 1 (hop 2) names unknown agent 'clade' (did you mean claude?)",
    ]


def test_a_call_file_validator_on_a_python_task_is_reported():
    @python_task(validators=[CommandValidator(["true", "{call}"])])
    def total() -> int:
        return 1

    assert any("uses {call}; a Python task has no call file" in e for e in pipeline().check(lambda: total()).errors)


def test_an_unknown_primary_agent_is_refused_with_the_closest_name(plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    errors = pipeline({"tasks": {"summarize": {"agent": "opm"}}}).check(lambda: summarize("a")).errors
    known = "claude, omp, omp-rpc, opencode, pi, stub"
    assert errors == [f"routing: kind summarize names unknown agent 'opm' (did you mean omp?); known: {known}"]


def test_the_report_shows_each_kinds_route_and_a_flow_error_at_the_flows_line(plugin_dir, tmp_path):
    summarize = agent_task("summarize", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    report = pipeline({"tasks": {"summarize": {"model": "m1", "fallbacks": [{"agent": "omp", "model": "m2"}]}}}).check(
        lambda: summarize("a")
    )
    assert report.routes == {"summarize": "claude/m1 effort=medium max_turns=5 timeout_s=60; on a 429: omp/m2"}

    def flow():
        (tmp_path / "missing.txt").read_text()  # raises inside pathlib

    errors = pipeline().check(flow).errors
    assert f"{__file__}:" in errors[0] and "FileNotFoundError" in errors[0]


def test_run_takes_what_check_takes_and_exits_by_the_outcome(tmp_path, capsys, monkeypatch):
    (tmp_path / "steps.py").write_text(
        "from contraagent import python_task\n"
        "@python_task\ndef double(n: int) -> int:\n    return 2 * n\n"
        "@python_task\ndef fail() -> int:\n    raise ValueError('no')\n"
        "def flow(n):\n    return double(n=n)\n"
        "def failing():\n    fail()\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    args = ["steps.py:flow", "--kwargs", '{"n": 2}']
    assert main(["check", *args]) == 0
    assert main(["run", *args]) == 0
    assert re.search(r"✓ 1/1 tasks done in \d+\.\ds; run in runs/flow", capsys.readouterr().out)
    assert main(["run", *args]) == 1  # the run id holds a run
    assert "`contraagent run --resume`" in capsys.readouterr().out
    assert main(["run", *args, "--resume"]) == 0
    assert main(["run", "steps.py:failing"]) == 1
    assert "python:fail: error" in capsys.readouterr().out
    sys.modules.pop("steps", None)


def test_a_model_the_coding_agent_does_not_list_is_reported(plugin_dir):
    summarize = agent_task("summarize", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    review = agent_task("review", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    lint = agent_task("lint", plugin=plugin_dir, output=Summary, max_turns=5, timeout_s=60)
    tasks = {
        "summarize": {"agent": "omp", "model": "anthropic/claude-haiku-5"},
        "review": {"agent": "omp", "model": "claude-haiku-5-5:low"},
        "lint": {"agent": "omp", "model": "haiku-ish"},
    }
    p = pipeline({"tasks": tasks})
    p.backends["omp"].catalogue = lambda: {"anthropic/claude-haiku-5-5", "openai/gpt-5"}  # type: ignore[method-assign]
    report = p.check(lambda: [summarize("a"), review("a"), lint("a")])
    assert report.errors == [
        "routing: summarize: model 'anthropic/claude-haiku-5' is not in the omp model list (did you mean anthropic/claude-haiku-5-5?)"
    ]
    assert report.warnings == ["routing: lint: model 'haiku-ish' is not in the omp model list; omp may still resolve it"]


# --- generator flows: the first step, and the kinds the code reaches ---------------


def test_a_generator_flow_is_checked_to_its_first_wait_with_its_reachable_kinds():
    report = pipeline().check(example.docs, units=["a", "b"])
    assert report.ok, report
    assert report.kinds == {"summarize": 2}  # the first step of each unit's flow call
    assert sorted(report.later_kinds) == ["report", "review", "revise"]  # created as it runs
    assert sorted(report.routes) == ["review", "revise", "summarize"]
    assert str(report).startswith("✓ 2 tasks, 1 kinds: summarize 2; later kinds: ")


def summarize_via_module(unit):
    """Reaches the example's tasks as attributes of its module."""
    summary = yield example.summarize(unit, path="x")
    return (yield example.review(unit, summary=summary))


def test_reachable_follows_globals_module_attributes_closures_and_containers():
    later = agent_task("later", instructions="l", output=Summary, max_turns=5, timeout_s=60)
    table = {"later": later}

    def helper(u):  # a closure holding a dict that holds a declaration
        return table["later"](u)

    def flow():
        yield from summarize_via_module("a")
        yield helper("a")

    kinds = [spec.kind for spec in reachable(flow)]
    assert sorted(kinds) == ["later", "review", "summarize"]
    assert "revise" not in kinds  # declared in the module, never referred to
    assert [spec.kind for spec in reachable(functools.partial(helper, "a"))] == ["later"]


def test_a_reachable_kinds_routing_is_checked_before_any_task_of_it_exists():
    late = agent_task("late", instructions="l", output=Summary)  # no budget

    def flow():
        summary = yield example.summarize("a", path="x")
        yield late("a", summary=summary)

    report = pipeline().check(flow)
    assert report.kinds == {"summarize": 1} and report.later_kinds == ["late"]
    assert any("kind late has no budget" in e for e in report.errors)


def review_twice(unit, revise=example.revise):
    """Revises with `revise`: the example's, unless the caller gives another."""
    summary = yield example.summarize(unit, path="x")
    yield example.review(unit, summary=summary)
    return (yield revise(unit, summary=summary))


def test_two_reachable_declarations_of_one_kind_that_differ_are_a_warning():
    terse = agent_task("revise", instructions="be terse", output=example.Summary, max_turns=5, timeout_s=60)

    def flow():
        return (yield from review_twice("a", revise=terse))

    report = pipeline().check(flow)
    assert report.ok, report
    assert sorted(report.later_kinds) == ["review", "revise"]
    assert report.warnings == [
        "flow: kind 'revise' has agent_task declarations with different instructions, config; "
        "a run raises if it creates tasks of two of them; checked as the first one found"
    ]


def test_the_first_steps_params_and_flow_call_errors_are_reported(plugin_dir):
    named = agent_task("named", plugin=plugin_dir, params=Named, output=Summary, max_turns=5, timeout_s=60)

    def part(u):
        yield named(u, n=0, name=u)

    def bad(u):
        raise ValueError(f"no {u}")
        yield

    def flow():
        yield [part("a"), bad("b")]

    report = pipeline().check(flow)
    assert "named-a: param n: Input should be greater than or equal to 1" in report.errors
    [raised] = [e for e in report.errors if e.startswith("flow call 0.2 ")]
    assert "bad): " in raised and f"{__file__}:" in raised and raised.endswith("ValueError: no b")


def test_a_generator_flow_that_adds_no_task_is_reported():
    def flow():
        yield []

    report = pipeline().check(flow)
    assert report.ok and not report.kinds and not report.later_kinds
    assert str(report).startswith("✗ the flow added no task")


def test_the_preflight_probes_every_reachable_kind(tmp_path, monkeypatch):
    probed: list[list[str]] = []
    monkeypatch.setattr(RoutingPlan, "preflight", lambda self: probed.append(sorted(map(kind_name, self.configs))))
    agent = StubAgent({"summarize": {"unit": "a", "points": ["p"]}, "review": {"approved": True, "note": ""}})
    p = Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, preflight=True, log=lambda line: None)
    assert p.run(example.docs, units=["a"]).ok
    assert probed == [["review", "revise", "summarize"]]  # revise never ran, and was probed
