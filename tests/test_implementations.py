"""`agent_task(implementations=)`: one step declared with several implementations, each a kind."""

import json
import re

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent._internal.pipeline.reach import reachable
from contraagent._internal.pipeline.spec import Implementations
from contraagent._internal.routing.plan import check_task_tables
from contraagent.engine import RoutingPlan
from contraagent.monitor import Monitor, Period
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent


class Review(BaseModel):
    unit: str
    findings: list[str]


@pytest.fixture
def plugins(tmp_path):
    for name in ("review-py", "review-go"):
        new_plugin(tmp_path / "plugins" / name)
    return tmp_path / "plugins"


def declare(plugins, **config):
    return agent_task(
        "review",
        implementations={"py": plugins / "review-py", "go": plugins / "review-go"},
        output=Review,
        max_turns=20,
        timeout_s=600,
        **config,
    )


def test_each_implementation_is_a_kind_with_its_plugin_and_every_other_argument(plugins):
    review = declare(plugins, claims=["unit:{unit}"])
    assert isinstance(review, Implementations) and review.kind == "review"
    assert review.kinds == ["review-py", "review-go"] and list(review) == ["py", "go"] and len(review) == 2
    go = review["go"]
    assert go.kind == "review-go" and go.base_kind == "review" and go.plugin is not None and go.plugin.root == plugins / "review-go"
    assert go.output is Review and go.config == {"max_turns": 20, "timeout_s": 600} and go.claims == ("unit:{unit}",)
    assert dict(review.items()) == {"py": review["py"], "go": go}
    assert review["py"].digest() != go.digest()  # each its own definition, so its own fingerprint
    with pytest.raises(KeyError, match="review has no implementation 'rust'; its implementations: py, go"):
        review["rust"]


@pytest.mark.parametrize(
    ("names", "kwargs", "message"),
    [
        (["go"], {"plugin": "x"}, "implementations names each implementation's plugin; drop plugin="),
        (["go"], {"instructions": "x"}, "drop instructions="),
        ([], {}, "implementations takes a dict"),
        (["go-fast"], {}, "implementation name 'go-fast' is not letters, digits and _"),
    ],
)
def test_a_wrong_declaration_names_its_cause(plugins, names, kwargs, message):
    with pytest.raises(TypeError, match=message):
        agent_task("review", implementations={n: plugins / "review-go" for n in names}, output=Review, **kwargs)


def test_the_base_kind_table_is_every_implementation_s_and_its_own_table_replaces_keys(plugins):
    config = PipelineConfig(
        {
            "tasks": {
                "review": {"model": "base-model", "max_turns": 30, "fallbacks": [{"agent": "stub", "model": "base-fallback"}]},
                "review-go": {"model": "go-model", "fallbacks": [{"agent": "stub", "model": "go-fallback"}]},
            }
        }
    )
    review = declare(plugins)
    specs = {t.kind: t for t in review.values()}
    plan = RoutingPlan.build(
        config,
        list(specs),
        StubAgent().backends(),
        declared={k: s.config for k, s in specs.items()},
        bases={k: s.base_kind for k, s in specs.items()},
    )
    py, go = plan.configs["review-py"], plan.configs["review-go"]
    assert (py.model, py.max_turns, py.timeout_s) == ("base-model", 30, 600)  # [tasks.review] over the declaration
    assert (go.model, go.max_turns) == ("go-model", 30)  # its own key, then the base kind's
    assert [r.model for r in plan.routers["review-py"].routes] == ["base-model", "base-fallback"]
    assert [r.model for r in plan.routers["review-go"].routes] == ["go-model", "go-fallback"]  # its chain, not both


def test_a_base_kind_table_is_not_an_unknown_one(caplog):
    tables = {"review": {}, "reveiw": {}}
    assert check_task_tables(tables, ["review-go"], {"review-go": "review"}) == ["reveiw"]


def review_all(review, units: dict[str, str]):
    found = {}
    for unit, lang in units.items():
        result = yield review[lang](unit)
        found[unit] = result.findings
    return found


def test_check_routes_every_implementation_before_the_flow_creates_one(tmp_path, plugins):
    review = declare(plugins)
    assert [t.kind for t in reachable(review_all, review)] == ["review-py", "review-go"]
    config = PipelineConfig({"tasks": {"review": {"model": "base-model"}, "review-go": {"model": "go-model"}}})
    report = Pipeline(config, backends=StubAgent().backends(), cwd=tmp_path).check(review_all, review, {"a": "py"})
    assert report.ok and report.later_kinds == ["review-go"]
    assert "/base-model " in report.routes["review-py"] and "/go-model " in report.routes["review-go"]
    assert not any("[tasks.review]" in w for w in report.warnings)


def test_a_stub_run_launches_each_unit_s_kind_and_the_monitor_draws_one_group(tmp_path, plugins):
    review = declare(plugins)
    agent = StubAgent(default=lambda launch: {"unit": launch.unit, "findings": [launch.kind]})
    units = {"a": "py", "b": "go", "c": "py"}
    report = Pipeline(runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(review_all, review, units)
    assert report.ok and report.value == {"a": ["review-py"], "b": ["review-go"], "c": ["review-py"]}
    assert sorted((launch.unit, launch.launch.plugin_dirs[0]) for launch in agent.launches) == [
        ("a", str(plugins / "review-py")),
        ("b", str(plugins / "review-go")),
        ("c", str(plugins / "review-py")),
    ]
    rows = [json.loads(line) for line in (report.run_dir / "plan.jsonl").read_text().splitlines()]
    assert {r["kind"]: r["base_kind"] for r in rows} == {"review-py": "review", "review-go": "review"}
    definition = json.loads((report.run_dir / "definitions" / "review-go.json").read_text())
    assert definition["base_kind"] == "review"

    run = report.run_dir.name
    plan = Monitor(tmp_path / "runs").plan(run)
    assert [(g["id"], g["total"], g["done"]) for g in plan["groups"]] == [("review", 3, 3)]
    assert {n["group"] for n in plan["nodes"]} == {"review"}
    # A group of the monitor's own wins for the kinds it lists; the others keep the base kind's.
    mine = [{"id": "go", "label": "Go", "kinds": ["review-go"]}]
    plan = Monitor(tmp_path / "runs", groups=mine).plan(run)
    assert [(g["id"], g["total"]) for g in plan["groups"]] == [("go", 1), ("review", 2)]
    # The trends count each kind in its base kind's group too.
    kinds = {k["kind"]: k["group"] for k in Monitor(tmp_path / "runs", keep_digests=False).trends(Period.parse(tz="UTC"))["kinds"]}
    assert kinds == {"review-py": "review", "review-go": "review"}


def created_then_implementation(review, other, lang: str):
    yield other("a")
    yield review[lang]("a")


def reached_only(review, other):  # `other` is reachable, never created
    if False:
        yield other("a")
    yield review["py"]("a")


def test_a_kind_that_is_a_base_kind_or_an_implementation_kind_of_another_declaration_is_refused(tmp_path, plugins):
    review = declare(plugins)
    plain = agent_task("review", plugin=plugins / "review-py", output=Review, max_turns=5, timeout_s=60)
    twin = agent_task("review-go", plugin=plugins / "review-go", output=Review, max_turns=5, timeout_s=60)

    @python_task(name="review-py")
    def same_name(unit: str) -> None:
        return None

    impl = "agent_task('review', implementations=...)"
    cases = [
        (plain, f"kind 'review' of agent_task('review') is also the base kind of {impl}"),
        (twin, f"kind 'review-go' is declared by {impl} (implementation 'go') and by agent_task('review-go')"),
        (same_name, f"kind 'review-py' is declared by {impl} (implementation 'py') and by @python_task review-py"),
    ]
    stub = StubAgent(default=lambda launch: {"unit": launch.unit, "findings": []})
    for other, message in cases:
        lang = "py" if other is same_name else "go"
        reached = Pipeline(backends=stub.backends(), cwd=tmp_path).check(reached_only, review, other).errors
        assert len(reached) == 1 and reached[0].startswith(f"flow: {message}") and "give one of them another name" in reached[0]
        created = Pipeline(backends=stub.backends(), cwd=tmp_path).check(created_then_implementation, review, other, lang).errors
        assert any(message in e for e in created), created
        with pytest.raises(ValueError, match=re.escape(message)):  # before the first launch
            Pipeline(runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path).run(reached_only, review, other)
    assert stub.launches == []
