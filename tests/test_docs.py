"""The documentation installed with the package: its index and its examples.

The examples are the documentation's code: they run here, so they cannot go stale.
"""

import json
import re
import shutil
import subprocess
import sys

import pytest

from contraagent import CheckReport, PipelineConfig
from contraagent._internal import docs
from contraagent._internal.cli import main
from contraagent.backends import ClaudeBackend, OmpBackend
from contraagent.engine import RoutingPlan
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


def _resolve(path: str) -> tuple[str, list[str]]:
    """The longest importable module a dotted path starts with, and the names after it,
    each an attribute of the one before."""
    import importlib

    parts = path.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for name in parts[i:]:
            obj = getattr(obj, name)
        return ".".join(parts[:i]), parts[i:]
    raise ImportError(path)


def test_the_topics_name_public_paths_only():
    """A topic names a public module or object, never a file or module of `_internal`
    (but compatibility.md, which says it is not public); every dotted `contraagent.` path
    in code resolves, through a public module and a name in its `__all__`."""
    import importlib

    for page in docs.DIR.glob("*.md"):
        text = page.read_text()
        if page.name != "compatibility.md":
            assert "_internal" not in text, f"{page.name} names _internal"
        for code in re.findall(r"`([^`\n]+)`", text):
            for path in re.findall(r"\bcontraagent(?:\.[A-Za-z_]\w*)+", code):
                if path == "contraagent._internal" and page.name == "compatibility.md":
                    continue
                try:
                    module, names = _resolve(path)
                except (ImportError, AttributeError):
                    pytest.fail(f"{page.name}: `{path}` names nothing")
                public = getattr(importlib.import_module(module), "__all__", None)
                assert "_internal" not in module, f"{page.name}: `{path}` is not public"
                assert not names or public is None or names[0] in public, f"{page.name}: `{path}` is not in {module}.__all__"


def test_the_examples_import_public_modules_only():
    import ast

    for file in EXAMPLES.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not [n for n in names if "_internal" in n], f"{file.relative_to(EXAMPLES)} imports _internal"


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
    source = (docs.DIR.parent / "_internal" / "pipeline" / "check.py").read_text()
    assert set(re.findall(r'\.add\("(\w+)"', source)) <= names


def test_the_reference_config_builds_a_routing_plan():
    config = PipelineConfig.load(EXAMPLES / "reference" / "pipeline.toml")
    backends = {"claude": ClaudeBackend(base_env={}), "omp": OmpBackend(base_env={})}
    kinds = ["summarize", "analyze", "research", "review-python", "review-go"]
    bases = {"review-python": "review", "review-go": "review"}
    plan = RoutingPlan.build(config, kinds, backends, bases=bases, requirements={"analyze": ["zdr"]})
    assert [(plan.configs[k].model, plan.configs[k].timeout_s) for k in ("review-python", "review-go")] == [
        ("claude-sonnet-5-5", 600),
        ("claude-opus-5-5", 900),
    ]
    assert plan.configs["analyze"].credential == "zdr" and plan.configs["summarize"].max_turns == 20
    assert [str(r) for r in plan.routers["research"].routes] == [
        "claude/claude-sonnet-5-5@subs",
        "omp/litellm/claude-sonnet-5-5@company-gateway",
    ]
    assert plan.credentials["subs"].members == ("token-a", "token-b")
    assert str(plan.routers["summarize"].routes[-1]) == "omp/opencode-go/glm-5.3"  # [[defaults.fallbacks]]
    assert config.table("report")["title"] == "Weekly summary"  # [pipeline.report]


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

    # Its panel reads the run through its records, not through a path of its own.
    from contraagent.monitor import DirectorySource, RunRecords

    monkeypatch.chdir(tmp_path.parent)
    notes = demo.notes(RunRecords("docs", DirectorySource(tmp_path / "demo-runs")))
    assert sorted(notes) == ["alpha", "beta", "delta", "epsilon", "gamma"]
    assert notes["alpha"].startswith("# alpha\n")


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


def test_the_root_readme_code_is_the_example_it_quotes():
    """GitHub does not expand `::code`, so the root README writes the code out: each
    fenced block that follows `<!-- ::code{...} -->` lines is those quotes, two blank lines
    between them (as `ruff format` writes it), and stays identical to the example files."""
    root = docs.DIR.parents[2]
    readme = root / "README.md"
    lines = readme.read_text().splitlines()
    checked = 0
    for i, line in enumerate(lines):
        if not line.startswith("<!-- ::code{") or lines[i - 1].startswith("<!-- ::code{"):
            continue
        quotes, j = [], i
        while lines[j].startswith("<!-- ::code{"):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', lines[j]))
            quotes.append(docs.quote(readme, attrs, root)[1:-1])
            j += 1
        assert lines[j].startswith("```"), f"README.md:{j + 1}: a fenced block follows the quotes"
        end = next(k for k in range(j + 1, len(lines)) if lines[k].startswith("```"))
        want = [line for n, q in enumerate(quotes) for line in (["", ""] if n else []) + q]
        assert lines[j + 1 : end] == want, f"README.md:{j + 1}: the block differs from what it quotes"
        checked += 1
    assert checked, "the root README quotes an example"


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
    groups = Monitor(tmp_path / "runs").plan(report.run_dir.name)["groups"]
    assert [(g["id"], g["total"], g["done"]) for g in groups] == [("review", 3, 3)]


def test_the_reference_config_writes_every_key_of_the_schema():
    """Every key the config's JSON Schema names is written in the reference, as a setting or
    as a commented-out `# key = ...` line, in a table of its kind: a kind of credential's
    own keys in a table of that type, the keys every type shares in some credential table
    (in each type's when its default differs between types, as `isolate`'s does);
    `_comment`, which every table takes, at least once."""
    import tomllib

    schema = json.loads((docs.DIR / "schemas" / "pipeline.schema.json").read_text())
    defs = schema["$defs"]
    types = {
        t: ref.rsplit("/", 1)[-1]
        for t, ref in schema["properties"]["credentials"]["additionalProperties"]["discriminator"]["mapping"].items()
    }
    text = (EXAMPLES / "reference" / "pipeline.toml").read_text()
    config = tomllib.loads(text)

    def table_of(parts: list[str]) -> str | None:
        if parts[0] == "credentials":
            return types[config["credentials"][parts[1]]["type"]]
        return {"defaults": "DefaultsTable", "tasks": "TaskTable"}.get(parts[0])

    written: dict[str, set[str]] = {name: set() for name in defs}
    table = None
    for line in text.splitlines():
        if header := re.match(r"^\[\[?([^\]]+)\]\]?", line):
            parts = header[1].replace('"', "").split(".")
            parent = table_of(parts)
            sub = parts[-1] if len(parts) == (2 if parts[0] == "defaults" else 3) else None
            if parent and sub:  # a sub-table: [defaults.claim_capacity], [[tasks.x.fallbacks]]
                written[parent].add(sub)
            table = "FallbackTable" if sub == "fallbacks" else None if sub else parent
        elif (key := re.match(r"^#?\s*(\w+)\s*=", line)) and table is not None:
            written[table].add(key[1])
    for entry in config["defaults"]["claim_capacity"].values():
        if isinstance(entry, dict):
            written["PerTaskTable"] |= set(entry)

    credentials = [defs[name] for name in types.values()]
    shared = set.intersection(*(set(d["properties"]) for d in credentials))
    same = {k for k in shared if len({json.dumps(d["properties"][k].get("default")) for d in credentials}) == 1}
    in_some = set().union(*(written[name] for name in types.values()))
    missing = {}
    for name, d in defs.items():
        keys = set(d["properties"]) - written[name] - {"_comment"}
        if name in types.values():
            keys -= same & in_some
        missing[name] = sorted(keys)
    assert {name: keys for name, keys in missing.items() if keys} == {}
    assert set(types) == {config["credentials"][c]["type"] for c in config["credentials"]}
    assert re.search(r"^_comment =", text, re.M)


def test_the_runner_adds_a_journal_column_and_resumes(tmp_path, monkeypatch):
    from contraagent.docs.examples.runner import run as runner
    from contraagent.testing import StubAgent

    monkeypatch.chdir(tmp_path)
    agent = StubAgent({"review": lambda launch: {"severity": "high" if launch.unit == "alpha" else "low", "summary": "s"}})
    assert runner.main(["alpha", "beta"], backends=agent.backends()).ok
    rows = [json.loads(line) for line in (tmp_path / "runs" / "reviews" / "journal.jsonl").read_text().splitlines()]
    assert {r["unit"]: r["severity"] for r in rows} == {"alpha": "high", "beta": "low"}
    assert runner.main(["alpha", "beta", "gamma", "--resume"], backends=agent.backends()).ok
    assert sorted(launch.unit for launch in agent.launches) == ["alpha", "beta", "gamma"]  # the resume reviews gamma only


def test_the_runner_s_quota_rule_rests_past_80_percent():
    from contraagent.config import QuotaReading
    from contraagent.docs.examples.runner.run import rest_past_80

    assert rest_past_80("personal", QuotaReading(five_hour_pct=80)) is None
    rest = rest_past_80("personal", QuotaReading(five_hour_pct=91, five_hour_resets_at="2026-10-15T12:00:00+00:00"))
    assert isinstance(rest, tuple) and rest[0] == "5-hour usage 91% is past 80%" and rest[1].hour == 12


def test_routing_names_every_key_defaults_takes():
    from contraagent._internal.routing.config import DEFAULTS_KEYS

    precedence = docs.text("routing").split("## Precedence", 1)[1].split("\n## ", 1)[0]
    assert [k for k in DEFAULTS_KEYS if f"`{k}`" not in precedence] == []


def test_the_testing_module_lists_every_kind_of_reply():
    import contraagent.testing

    doc = contraagent.testing.__doc__ or ""
    replies = [n for n in contraagent.testing.__all__ if n[0].islower()]
    assert [n for n in replies if f"`{n}(" not in doc] == []


AGENTS = ("claude", "omp", "opencode", "pi", "codex")


def _agent_table() -> dict[str, dict[str, str]]:
    """agents.md's table of what each coding agent does: {row label: {agent: cell}}."""
    text = (docs.DIR / "agents.md").read_text()
    block = text[text.index("| | claude |") :].split("\n\n", 1)[0].splitlines()
    agents = [c.strip() for c in block[0].strip("|").split("|")][1:]
    table = {}
    for row in block[2:]:
        label, *cells = [c.strip() for c in row.strip("|").split("|")]
        table[label] = dict(zip(agents, cells, strict=True))
    return table


def test_the_agents_table_says_what_each_backend_class_does():
    """Every yes/no cell of agents.md's table, against the agent's `Backend` class."""
    from contraagent._internal.backends import backend_class
    from contraagent.backends import Backend

    table = _agent_table()
    assert all(tuple(cells) == AGENTS for cells in table.values())

    def says(row: str, agent: str) -> bool:
        cell = table[row][agent]
        assert cell.startswith(("yes", "no")), f"{row} / {agent}: {cell}"
        return cell.startswith("yes")

    for agent in AGENTS:
        cls = backend_class(agent)
        assert cls is not None
        assert says("Stop hook continues the session (`stop_hooks_file`)", agent) == (cls.stop_hooks_file is not None)
        assert says("Light launch (`light_launch`)", agent) == cls.light_launch
        assert says("Role file attached to the prompt (`needs_inline_role_file`)", agent) == cls.needs_inline_role_file
        assert says("`disallowed_tools` taken", agent) == (cls.tool_deny_problem(("WebFetch",)) is None)
        reads = cls.usage_reading is not Backend.usage_reading
        assert says("Quota readings read by contraagent before each launch (`usage_reading`)", agent) == reads
        for limit in ("max_turns", "max_budget_usd", "context_budget"):
            row = f"`{limit}` enforced"
            assert ("by contraagent" in table[row][agent]) == (limit in cls.watched_limits), f"{row} / {agent}"
            assert says(row, agent) or limit not in cls.watched_limits, f"{row} / {agent}"
        session = "session's so far" in table["Cost of a resumed session (`cost_is_session_total`)"][agent]
        assert session == cls.cost_is_session_total, agent
