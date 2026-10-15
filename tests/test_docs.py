"""The documentation installed with the package: its index and its examples.

The examples are the documentation's code: they run here, so they cannot go stale.
"""

import json
import re
import shutil
import subprocess
import sys

import pytest

from contraagent import ClaudeBackend, OmpBackend, PipelineConfig, RoutingPlan, docs
from contraagent.cli import main
from contraagent.pipeline.check import CheckReport
from contraagent.plugins import Plugin

EXAMPLES = docs.DIR / "examples"


def test_the_index_lists_every_topic_and_nothing_else():
    listed = {t.name for t in docs.topics()}
    assert listed == {p.stem for p in docs.DIR.glob("*.md")} - {"README"}
    assert all(t.path.is_file() and t.summary for t in docs.topics())


def test_every_relative_link_resolves():
    for page in docs.DIR.glob("*.md"):
        for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", page.read_text()):
            assert (page.parent / target).exists(), f"{page.name}: {target}"


def test_a_topic_is_printed_and_an_unknown_one_named(capsys):
    assert main(["docs", "testing"]) == 0
    assert capsys.readouterr().out.startswith("# Checking and testing")
    assert main(["docs", "nope"]) == 1
    assert "the topics: tutorial, guide, concepts" in capsys.readouterr().err


def test_the_pointer_names_the_commands_it_points_to(capsys):
    assert main(["docs", "--pointer"]) == 0
    out = capsys.readouterr().out
    assert out == docs.POINTER and "`contraagent docs`" in out and "`contraagent check`" in out


def test_check_errors_name_topics_that_exist():
    report = CheckReport()
    report.add("routing", ["routing: x"])
    assert "read: `contraagent docs routing`" in str(report)
    names = {t.name for t in docs.topics()}
    source = (docs.DIR.parent / "pipeline" / "check.py").read_text()
    assert set(re.findall(r'\.add\("(\w+)"', source)) <= names


def test_the_reference_config_builds_a_routing_plan():
    config = PipelineConfig.load(EXAMPLES / "reference" / "pipeline.toml")
    backends = {"claude": ClaudeBackend(base_env={}), "omp": OmpBackend(base_env={})}
    plan = RoutingPlan.build(config, ["summarize", "analyze", "research"], backends, requirements={"analyze": ["zdr"]})
    assert plan.configs["analyze"].credential == "zdr" and plan.configs["summarize"].max_turns == 20
    assert [str(r) for r in plan.routers["research"].routes] == [
        "claude/claude-sonnet-5-5@subs",
        "omp/litellm/claude-sonnet-5-5@company-gateway",
    ]
    assert plan.credentials["subs"].members == ("token-a", "token-b")
    assert str(plan.routers["summarize"].routes[-1]) == "omp/opencode-go/glm-5.3"  # [[defaults.fallbacks]]


def test_the_demo_plugin_is_clean():
    assert Plugin.load(EXAMPLES / "demo" / "plugins" / "docs").lint() == []


def test_the_demo_runs_end_to_end_as_its_docstring_says(tmp_path, monkeypatch):
    from contraagent.docs.examples.demo import run as demo

    monkeypatch.chdir(tmp_path)
    report = demo.main(["--no-serve", "--fast"])
    stops = {k: r.stop for k, r in report.results.items()}
    assert stops["python:prepare-zeta"] == "error"
    assert stops["summarize-zeta"] == "invalid_input"  # zeta's review loop ends there
    assert all(r.ok for k, r in report.results.items() if "zeta" not in k) and report.flow_errors == []
    assert report.value == "\n".join(f"{u}: 3 points" for u in ("alpha", "beta", "gamma", "delta", "epsilon"))
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    by = {(r["key"], r["attempt"]): r for r in rows}
    assert by[("summarize-beta", 0)]["route"].startswith("hop 2/2")  # failed over on a 429
    assert by[("summarize-delta", 0)]["rounds"] == 2  # sent back by a Python validator
    assert by[("write_note-alpha", 0)]["rounds"] == 2  # sent back by the linter
    assert [r["stop"] for r in rows if r["key"] == "review-gamma"] == ["error", "error", "completed"]
    assert [r["stop"] for r in rows if r["key"] in ("revise-gamma", "python:score-gamma~2", "review-gamma~2")] == [
        "completed"
    ] * 3  # pass 2


def test_the_demo_tests_pass_on_the_stub_agent():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(EXAMPLES / "demo" / "test_demo.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]


def test_the_tutorial_plugin_is_clean():
    assert Plugin.load(EXAMPLES / "tutorial" / "plugins" / "triage").lint() == []


def test_the_tutorial_tests_pass_on_the_stub_agent():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(EXAMPLES / "tutorial" / "test_tutorial.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]


def test_the_tutorial_commands_print_what_the_page_shows(tmp_path):
    """The tutorial's check and stub run, from a project laid out as it says."""
    for part in ("tasks.py", "pipeline.toml", "plugins", "issues"):
        (shutil.copytree if (EXAMPLES / "tutorial" / part).is_dir() else shutil.copy)(EXAMPLES / "tutorial" / part, tmp_path / part)
    page = docs.text("tutorial")
    reports = '{"reports": ["login-timeout", "csv-export", "dark-mode"]}'
    for args in (["check", "tasks.py:triage_all"], ["run", "tasks.py:triage_all", "--stub"]):
        assert f"contraagent {' '.join(args)} --kwargs '{reports}'" in page
        proc = subprocess.run(
            [sys.executable, "-m", "contraagent", *args, "--kwargs", reports], cwd=tmp_path, capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        shown = [line for line in proc.stdout.splitlines() if line.startswith(("✓ 4 tasks", "  triage", "  write_table"))]
        assert shown and all(line in page for line in shown), shown


def test_every_page_of_every_package_expands(tmp_path):
    """Each quote resolves: what `contraagent docs` prints and the site renders."""
    root = docs.DIR.parents[2]
    packages = [root / "web/packages" / p for p in ("ui", "elements")]
    for index, home in ((docs.INDEX, docs.DIR), *((p / "README.md", p) for p in packages)):
        for page in [index, *(e.path for e in docs.entries(index))]:
            docs.expand(page, home)
    assert 'title="examples/demo/tasks.py"' in docs.text("tasks") and "def docs_one_review(" in docs.text("tasks")


def test_a_quote_that_does_not_resolve_says_where(tmp_path):
    page = tmp_path / "p.md"
    page.write_text('# P\n\n::code{file="x.py" from="nowhere"}\n')
    (tmp_path / "x.py").write_text("a = 1\n")
    with pytest.raises(docs.DocsError, match="p.md: ::code{file='x.py'}: no line contains 'nowhere'"):
        docs.expand(page, tmp_path)


def test_the_implementations_example_launches_each_unit_s_kind_with_its_plugin(tmp_path):
    from contraagent import Pipeline
    from contraagent.docs.examples.implementations import flow
    from contraagent.monitor import Monitor
    from contraagent.testing import StubAgent

    plugins = EXAMPLES / "implementations" / "plugins"
    assert [Plugin.load(plugins / name).lint() for name in ("review-python", "review-go")] == [[], []]
    units = {"parser": "python", "server": "go", "lexer": "python"}
    check = Pipeline(runs_dir=tmp_path / "runs", backends=StubAgent().backends(), cwd=tmp_path).check(flow.review_all, units=units)
    assert check.ok and check.later_kinds == ["review-go"]
    agent = StubAgent(default=lambda launch: {"unit": launch.unit, "findings": [launch.kind]})
    report = Pipeline(runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(flow.review_all, units=units)
    assert report.ok and report.value == {"parser": 1, "server": 1, "lexer": 1}
    assert {(launch.unit, launch.kind, launch.launch.plugin_dirs[0]) for launch in agent.launches} == {
        ("parser", "review-python", str(plugins / "review-python")),
        ("server", "review-go", str(plugins / "review-go")),
        ("lexer", "review-python", str(plugins / "review-python")),
    }
    groups = Monitor(tmp_path / "runs", groups=flow.GROUPS).plan(report.run_dir.name)["groups"]
    assert [(g["id"], g["total"], g["done"]) for g in groups] == [("review", 3, 3)]


def test_the_reference_config_has_every_task_table_key():
    from contraagent.routing.kind_config import TASK_TABLE_KEYS

    text = (EXAMPLES / "reference" / "pipeline.toml").read_text()
    assert [k for k in TASK_TABLE_KEYS if not re.search(rf"^{k} =", text, re.M)] == []
