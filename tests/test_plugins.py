"""Plugins: the implementation of an agent task, with hooks declared once for every coding agent."""

import json
import subprocess
import sys

import pytest

from contraagent import Plugin, PluginError, agent_task
from contraagent.backends.omp.backend import plugin_extension_args
from contraagent.pipeline.adapter import SpecAdapter
from contraagent.pipeline.graph import Graph
from contraagent.plugins import hooks, new_plugin


@pytest.fixture
def plugin(tmp_path):
    new_plugin(tmp_path / "plugins" / "summarize")
    return tmp_path / "plugins" / "summarize"


def add_hooks(plugin, text):
    (plugin / "hooks.toml").write_text((plugin / "hooks.toml").read_text() + text)


def test_the_template_is_a_clean_plugin(plugin):
    p = Plugin.load(plugin)
    assert p.lint() == [] and p.roles == ("worker",) and p.resolve_role(None) == "worker"
    assert [h["on"] for h in p.hooks] == ["stop"]
    assert "call validate" in (plugin / "hooks" / "hooks.json").read_text()  # rendered for Claude Code


def test_lint_catches_disagreement(plugin):
    (plugin / "agents" / "worker.md").write_text("---\nname: other\n---\nx\n")
    (plugin / "settings.json").write_text("{not json")
    (plugin / "hooks.toml").write_text('[[hooks]]\non = "post_tool"\ntool = "bash"\n\n[[hooks]]\non = "sideways"\n')
    errs = "\n".join(Plugin.load(plugin).lint())
    for needle in (
        "frontmatter name is 'other'",
        "no description",
        "settings.json: not valid JSON",
        "post_tool hook needs a script",
        "'on' must be one of",
        "no stop hook",
    ):
        assert needle in errs, needle


def test_roles_are_checked_where_the_task_is_declared(plugin):
    with pytest.raises(PluginError, match="no role 'nobody'"):
        agent_task("x", plugin=plugin, role="nobody")
    (plugin / "agents" / "second.md").write_text("---\nname: second\ndescription: d\n---\n")
    with pytest.raises(PluginError, match="name one"):
        agent_task("x", plugin=plugin)
    assert agent_task("x", plugin=plugin, role="second").role == "second"


def test_hooks_are_declared_once_and_rendered_into_each_agent(plugin):
    (plugin / "hooks" / "pre.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (plugin / "hooks" / "post.sh").write_text("#!/usr/bin/env bash\ncat >/dev/null\n")
    add_hooks(
        plugin,
        '\n[[hooks]]\non = "pre_tool"\ntool = "bash"\nscript = "hooks/pre.sh"\n'
        '\n[[hooks]]\non = "post_tool"\ntool = "bash"\nmatch = "update-finding"\nscript = "hooks/post.sh"\n',
    )
    p = Plugin.load(plugin)
    assert any("out of date" in e for e in p.lint())  # declaration changed, renders did not
    written, notes = hooks.write(p)
    assert p.lint() == [] and hooks.stale(p) == []
    claude = json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"]
    assert claude["PreToolUse"][0]["matcher"] == "Bash"
    assert claude["PreToolUse"][0]["hooks"][0]["command"] == "${CLAUDE_PLUGIN_ROOT}/hooks/pre.sh"
    assert "Stop" in claude
    omp = (plugin / "omp" / "index.ts").read_text()
    assert 'pi.on("tool_call"' in omp and 'pi.on("tool_result"' in omp and '"match": "update-finding"' in omp
    assert json.loads((plugin / "package.json").read_text())["omp"] == {"extensions": ["./omp/index.ts"]}
    assert any("stop hook cannot continue" in n for n in notes)  # the difference is stated, not hidden
    assert plugin_extension_args([str(plugin)]) == ["-e", str(plugin.resolve() / "omp" / "index.ts")]


def test_a_new_agent_registers_its_own_renderer(plugin):
    hooks.register_renderer("fake", lambda p: ({"fake.txt": ",".join(h["on"] for h in p.hooks)}, []))
    try:
        files, _ = hooks.render(Plugin.load(plugin), ["fake"])
        assert files == {"fake.txt": "stop"}
    finally:
        hooks.RENDERERS.pop("fake")


def test_a_coding_agent_without_a_named_agent_flag_gets_the_role_attached(plugin, tmp_path):
    class Inline:  # omp: no --agent, so the role's definition travels as a file
        needs_inline_role_file = True

    class Native:  # Claude Code: --agent resolves the role itself
        needs_inline_role_file = False

    task_spec = agent_task("summarize", plugin=plugin)
    graph = Graph(tmp_path / "out")
    with graph.building():
        task_spec("a")
    [task] = graph.tasks()
    adapter = SpecAdapter("r", tmp_path)
    assert adapter.context_files(task, Inline()) == (str(plugin.resolve() / "agents" / "worker.md"),)
    assert adapter.context_files(task, Native()) == ()


def test_cli(plugin, tmp_path):
    def run(*a):
        return subprocess.run([sys.executable, "-m", "contraagent", *a], capture_output=True, text=True, cwd=tmp_path)

    ok = run("plugin", "lint", str(plugin.parent))
    assert ok.returncode == 0 and "✓" in ok.stdout
    (plugin / "agents" / "worker.md").unlink()
    bad = run("plugin", "lint", str(plugin))
    assert bad.returncode == 1 and "no role" in bad.stdout
    assert "refusing" in run("plugin", "new", str(plugin)).stderr
    assert run("call", "validate").returncode == 0  # no call file: nothing to check
