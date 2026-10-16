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
        for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
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
        text = page.read_text(encoding="utf-8")
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
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
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
    # what to read first and the loop that checks a pipeline, each a topic that exists
    assert "Read `guide`, then `tutorial`." in out and "--stub" in out and "StubAgent" in out
    assert {"guide", "tutorial", "testing"} <= {t.name for t in docs.topics()}
    # for any coding agent: no agent's name and no instruction file of one
    for name in ("Claude", "CLAUDE.md", "AGENTS.md", "Codex", "opencode", "omp", " pi "):
        assert name not in out


def test_check_errors_name_topics_that_exist():
    report = CheckReport()
    report.add("routing", ["routing: x"])
    assert "read: (contraagent docs routing)" in str(report)
    names = {t.name for t in docs.topics()}
    source = (docs.DIR.parent / "_internal" / "pipeline" / "check.py").read_text(encoding="utf-8")
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


def test_the_security_config_checks_on_its_flow(capsys):
    """`contraagent check --config` on the security example: three hops, three coding agents.
    `--stub`, so the host's own model lists (opencode's, Codex's) do not decide it."""
    flow, config = EXAMPLES / "security" / "flow.py", EXAMPLES / "security" / "pipeline.toml"
    args = ["check", f"{flow}:audit_all", "--config", str(config), "--stub", "--kwargs", '{"modules": ["auth"]}']
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "audit: claude/claude-opus-5-5" in out and "credential=anthropic-key" in out
    assert "codex/gpt-6.1-sol@openai-key then opencode/opencode-go/deepseek-v4.1-flash@opencode-go" in out


def test_a_refusal_moves_only_that_task_along_the_security_chain(tmp_path):
    """What the README's diagram draws: a refused task takes hop 2, then hop 3, and is
    never launched on the same route again; the other tasks stay on hop 1."""
    from contraagent import Pipeline
    from contraagent.backends import Stop
    from contraagent.docs.examples.security import flow
    from contraagent.testing import StubAgent, fails

    refused = fails(Stop.REFUSED, "the provider declined the request")
    findings = {"findings": []}
    agent = StubAgent(
        {
            "audit-upload": lambda launch: refused if launch.model == "claude-opus-5-5" else findings,
            "audit-exploit": refused,
            "audit": findings,
        }
    )
    pipeline = Pipeline(EXAMPLES / "security" / "pipeline.toml", runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path)
    report = pipeline.run(flow.audit_all, modules=["auth", "upload", "exploit"])
    rows = {r["key"]: r for r in map(json.loads, (report.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines())}
    assert len(rows) == 3  # one attempt each: a refusal is not retried
    hops = {key: [(h["agent"], h["model"], h["stop"]) for h in row["hops"]] for key, row in rows.items()}
    assert hops["audit-auth"] == [("claude", "claude-opus-5-5", "completed")]
    assert hops["audit-upload"] == [("claude", "claude-opus-5-5", "refused"), ("codex", "gpt-6.1-sol", "completed")]
    assert rows["audit-upload"]["stop"] == "completed" and rows["audit-upload"]["credential"] == "openai-key"
    refusal = "safeguard refusal on hop 1/3 claude/claude-opus-5-5@anthropic-key (the provider declined the request)"
    assert rows["audit-upload"]["reason"].startswith(refusal)
    assert hops["audit-exploit"] == [
        ("claude", "claude-opus-5-5", "refused"),
        ("codex", "gpt-6.1-sol", "refused"),
        ("opencode", "opencode-go/deepseek-v4.1-flash", "refused"),
    ]
    assert rows["audit-exploit"]["stop"] == "refused" and not report.results["audit-exploit"].ok
    assert [launch.model for launch in agent.launches_of("audit-auth")] == ["claude-opus-5-5"]


def test_the_credentials_example_runs_the_restricted_document_as_its_call_s_credential(tmp_path, capsys):
    """The routing topic's example: the document in `RESTRICTED` runs as `company` on the
    primary and, after a 429, on the failover hop; the other runs as the kind's `team`."""
    from contraagent import Pipeline
    from contraagent.docs.examples.credentials import flow
    from contraagent.testing import StubAgent, rate_limited

    path, config = EXAMPLES / "credentials" / "flow.py", EXAMPLES / "credentials" / "pipeline.toml"
    assert (
        main(["check", f"{path}:summarize_all", "--config", str(config), "--stub", "--kwargs", '{"documents": ["plan", "contract"]}']) == 0
    )
    assert "summarize: claude/claude-opus-5-5" in capsys.readouterr().out
    summary = {"text": "a summary"}
    agent = StubAgent(
        {"summarize-contract": lambda launch: rate_limited() if launch.model == "claude-opus-5-5" else summary, "summarize": summary}
    )
    pipeline = Pipeline(config, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path)
    report = pipeline.run(flow.summarize_all, documents=["plan", "contract"])
    assert report.ok, report.failed
    rows = {r["key"]: r for r in map(json.loads, (report.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines())}
    assert [(h["model"], h["credential"]) for h in rows["summarize-contract"]["hops"]] == [
        ("claude-opus-5-5", "company"),
        ("claude-sonnet-5-5", "company"),
    ]
    assert [(h["model"], h["credential"]) for h in rows["summarize-plan"]["hops"]] == [("claude-opus-5-5", "team")]


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
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
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
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout[-2000:]


def test_the_tutorial_plugin_is_clean():
    assert Plugin.load(EXAMPLES / "tutorial" / "plugins" / "triage").lint() == []


def test_the_tutorial_tests_pass_on_the_stub_agent():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(EXAMPLES / "tutorial" / "test_tutorial.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
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
            [sys.executable, "-m", "contraagent", *args, "--kwargs", reports],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
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


def _collector():
    """The documentation site's collector (web/apps/docs/scripts/collect.py), as a module."""
    import importlib.util

    path = docs.DIR.parents[2] / "web/apps/docs/scripts/collect.py"
    spec = importlib.util.spec_from_file_location("collect", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_page_of_any_package_holds_an_html_tag_in_its_prose():
    """The site renders a page's Markdown: a `<title>` outside a code span is HTML there,
    and swallows the rest of the page. A paragraph marked `<!-- not on the site -->` is
    left out of the site, its mark too."""
    collect = _collector()
    for index, home, _, _ in collect.SECTIONS:
        for page in [index, *(e.path for e in docs.entries(index))]:
            collect.check_html(page, collect.site_only(docs.expand(page, home).splitlines()))
    bad = collect.ROOT / "web/apps/docs/scripts/collect.py"  # any file under the repository, for its name
    with pytest.raises(SystemExit, match=r"<title> \(line 2 .*code span"):
        collect.check_html(bad, ["`<code>` is fine", 'the title, "<title> monitor"', "```", "<title>", "```"])
    marked = ["a", "", collect.NOT_ON_SITE, "![x](images/x.webp)", "Live on the site.", "", "b"]
    assert collect.site_only(marked) == ["a", "", "b"]
    with pytest.raises(SystemExit, match="<!--"):
        collect.check_html(bad, ["<!-- a comment of another kind -->"])


def test_the_site_shows_each_element_live_in_place_of_its_screenshot(tmp_path, monkeypatch):
    """Every screenshot of an element in the web packages becomes the live element on the
    site; a topic of @contraagent/elements, or a screenshot, without one stops the collector."""
    collect = _collector()
    monkeypatch.setattr(collect, "CONTENT", tmp_path / "content")
    monkeypatch.setattr(collect, "SCHEMAS", tmp_path / "schemas")
    collect.main()
    shots = 0
    for index in (collect.ROOT / "web/packages/ui/README.md", collect.ROOT / "web/packages/elements/README.md"):
        for page in [index, *(e.path for e in docs.entries(index))]:
            shots += len(re.findall(r"!\[[^\]]*\]\((?:docs/)?images/", page.read_text(encoding="utf-8")))
    pages = [p.read_text(encoding="utf-8") for p in (tmp_path / "content" / "node").rglob("*.md*")]
    assert shots and sum(p.count("<LiveFigure ") for p in pages) >= shots
    assert not any(re.search(r"!\[[^\]]*\]\((?:docs/)?images/", p) for p in pages)

    live = dict(collect.LIVE)
    monkeypatch.setattr(collect, "LIVE", {k: v for k, v in live.items() if k != "node/elements/graph"})
    with pytest.raises(SystemExit, match="node/elements/graph shows no element live"):
        collect.main()
    monkeypatch.setattr(collect, "NO_ELEMENT", {*collect.NO_ELEMENT, "node/elements/graph"})
    with pytest.raises(SystemExit, match="the screenshot images/graph.webp has no live element"):
        collect.main()


def test_the_site_links_its_pages_relative_to_each_other(tmp_path, monkeypatch):
    """The site is served under a base path (web/apps/docs/site.ts), so a link from one
    collected page to another is relative to the linking page, and a link from the
    server's root stops the collector."""
    collect = _collector()
    monkeypatch.setattr(collect, "CONTENT", tmp_path / "content")
    monkeypatch.setattr(collect, "SCHEMAS", tmp_path / "schemas")
    collect.main()
    links = [m for p in (tmp_path / "content").rglob("*.md*") for m in collect.LINK.findall(p.read_text(encoding="utf-8"))]
    assert any(link.startswith("../") for link in links)
    assert [link for link in links if link.startswith("/")] == []

    source = docs.DIR / "tutorial.md"
    pages = {(docs.DIR / "guide.md").resolve(): {"url": "/python/guide/"}}
    assert collect.link(source, {"url": "/python/tutorial/"}, "guide.md#steps", pages) == "../guide/#steps"
    assert collect.link(docs.DIR / "README.md", {"url": "/python/"}, "guide.md", pages) == "guide/"
    with pytest.raises(SystemExit, match="is not relative to the page"):
        collect.link(source, {"url": "/python/tutorial/"}, "/python/guide/", pages)


def test_the_root_readme_code_is_the_example_it_quotes():
    """GitHub does not expand `::code`, so the root README writes the code out: each
    fenced block that follows `<!-- ::code{...} -->` lines is those quotes, two blank lines
    between them (as `ruff format` writes it), and stays identical to the example files."""
    root = docs.DIR.parents[2]
    readme = root / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines()
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
    page.write_text('# P\n\n::code{file="x.py" from="nowhere"}\n', encoding="utf-8", newline="\n")
    (tmp_path / "x.py").write_text("a = 1\n", encoding="utf-8", newline="\n")
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

    schema = json.loads((docs.DIR / "schemas" / "pipeline.schema.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    types = {
        t: ref.rsplit("/", 1)[-1]
        for t, ref in schema["properties"]["credentials"]["additionalProperties"]["discriminator"]["mapping"].items()
    }
    text = (EXAMPLES / "reference" / "pipeline.toml").read_text(encoding="utf-8")
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
    rows = [json.loads(line) for line in (tmp_path / "runs" / "reviews" / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
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
    text = (docs.DIR / "agents.md").read_text(encoding="utf-8")
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


def test_the_demo_takes_every_registered_coding_agent(capsys):
    from contraagent.backends import known_agents
    from contraagent.docs.examples.demo.run import main as demo

    with pytest.raises(SystemExit):
        demo(["--help"])
    help = " ".join(capsys.readouterr().out.split())
    assert f"({', '.join(known_agents())})" in help


def test_the_landing_scenes_stage_css_is_current():
    """how-stages.css is what scripts/how_css.py writes, and its stages' shares are the
    ones HowItWorks.astro gives the track (and how-scene.ts reads from it)."""
    import importlib.util
    import re

    root = docs.DIR.parents[2] / "web/apps/docs"
    spec = importlib.util.spec_from_file_location("how_css", root / "scripts/how_css.py")
    assert spec and spec.loader
    how = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(how)
    assert (root / "src/components/home/how-stages.css").read_text(encoding="utf-8") == how.css(), "run web/apps/docs/scripts/how_css.py"
    astro = (root / "src/components/home/HowItWorks.astro").read_text(encoding="utf-8")
    weights = re.search(r"const WEIGHTS = \[([\d, ]+)\]", astro)
    assert weights and [int(w) for w in weights.group(1).split(",")] == how.WEIGHTS


def _landing():
    """The landing page's capture of the CLI's output (web/apps/docs/scripts/landing.py), as a module."""
    import importlib.util

    path = docs.DIR.parents[2] / "web/apps/docs/scripts/landing.py"
    spec = importlib.util.spec_from_file_location("landing", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_landing_pages_cli_outputs_are_current():
    """landing-outputs.json is what scripts/landing.py writes now: the commands run again here,
    and the file holds no timing, so only a change to what they print makes a difference."""
    landing = _landing()
    assert landing.OUT.read_text(encoding="utf-8") == landing.text(landing.outputs()), "run uv run python web/apps/docs/scripts/landing.py"
    how = (landing.HERE / "src/components/home/how.ts").read_text(encoding="utf-8")
    assert f"export const KWARGS = '{landing.KWARGS}';" in how


def test_the_docs_site_runs_no_command_when_it_renders():
    """What a command prints is captured by a script of web/apps/docs/scripts into src/fixtures;
    a page that ran it would take seconds to answer on the dev server."""
    src = _landing().HERE / "src"
    running = [
        str(f.relative_to(src))
        for f in src.rglob("*")
        if f.suffix in {".ts", ".js", ".mjs", ".astro", ".tsx", ".jsx"}
        and re.search(r"child_process|\bexeca\b", f.read_text(encoding="utf-8"))
    ]
    assert running == []
