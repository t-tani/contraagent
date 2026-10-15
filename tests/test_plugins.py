"""Plugins: the implementation of an agent task, with hooks declared once for every coding agent."""

import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from contraagent import PluginError, agent_task
from contraagent._internal.backends.omp.backend import plugin_extension_args
from contraagent._internal.backends.pi.backend import plugin_args as pi_plugin_args
from contraagent._internal.pipeline.adapter import SpecAdapter
from contraagent._internal.pipeline.graph import Graph
from contraagent._internal.plugins import hooks
from contraagent.backends import Launch, OpencodeBackend
from contraagent.plugins import Plugin, new_plugin


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
    pi = (plugin / "pi" / "index.ts").read_text()
    assert 'pi.on("tool_call"' in pi and "ExtensionAPI" in pi and "@oh-my-pi" not in pi and '"find": "Glob"' in pi
    # one package.json declares both extensions
    pkg = json.loads((plugin / "package.json").read_text())
    assert pkg["omp"] == {"extensions": ["./omp/index.ts"]} and pkg["pi"] == {"extensions": ["./pi/index.ts"]}
    assert any("stop hook cannot continue" in n for n in notes)  # the difference is stated, not hidden
    assert plugin_extension_args([str(plugin)]) == ["-e", str(plugin.resolve() / "omp" / "index.ts")]
    opencode = (plugin / "opencode" / "index.js").read_text()
    assert '"tool.execute.before"' in opencode and '"tool.execute.after"' in opencode and '"match": "update-finding"' in opencode
    assert any(n.startswith("opencode: a stop hook") for n in notes)
    launch = Launch(prompt="x", plugin_dirs=(str(plugin),))
    assert OpencodeBackend(base_env={}).config(launch)["plugin"] == [f"file://{plugin.resolve()}/opencode/index.js"]
    assert pi_plugin_args([str(plugin)])[-2:] == ["-e", str(plugin / "pi" / "index.ts")]


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


def skill_plugin(root, name="common", skill="house-style"):
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
    (root / "skills" / skill).mkdir(parents=True)
    (root / "skills" / skill / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: d\n---\nShort sentences.\n")
    return root


def test_a_skill_plugin_is_loaded_after_the_tasks_own(plugin, tmp_path):
    common = skill_plugin(tmp_path / "plugins" / "common")
    spec = agent_task("summarize", plugin=plugin, skills_from=[common])
    graph = Graph(tmp_path / "out")
    with graph.building():
        spec("a")
    [task] = graph.tasks()
    adapter = SpecAdapter("r", tmp_path)
    assert adapter.plugin_dirs(task) == (str(plugin.resolve()), str(common.resolve()))
    assert adapter.settings_path(task) == str(plugin.resolve() / "settings.json")  # the task's own plugin's only
    assert adapter.mcp_config_path(task) is None
    definition = adapter.definition(task)
    assert definition["plugin_dirs"] == [str(plugin.resolve()), str(common.resolve())]
    assert {"path": "common/skills/house-style/SKILL.md", "part": "skill"}.items() <= next(
        f for f in definition["files"] if f["path"].startswith("common/")
    ).items()


def test_a_skill_plugin_holds_skills_only(plugin, tmp_path):
    common = skill_plugin(tmp_path / "common")
    assert Plugin.load(common).skills_only and Plugin.load(common).lint() == []  # no role, no stop hook: not asked for
    (common / "settings.json").write_text("{}")
    (common / "agents").mkdir()
    with pytest.raises(PluginError, match=r"holds agents, settings.json; a plugin it names holds skills only"):
        agent_task("summarize", plugin=plugin, skills_from=[common])
    with pytest.raises(PluginError, match="hooks.toml, hooks, package.json;"):  # a task's own plugin is not a skill plugin
        agent_task("summarize", plugin=plugin, skills_from=[plugin])


def test_skills_from_is_relative_to_the_declaring_file_and_part_of_the_fingerprint(plugin, tmp_path):
    common = skill_plugin(tmp_path / "plugins" / "common")
    declaring = tmp_path / "tasks.py"
    declaring.write_text(
        "from contraagent import agent_task\nspec = agent_task('summarize', plugin='plugins/summarize', skills_from=['plugins/common'])\n"
    )
    declared = runpy.run_path(str(declaring))["spec"]
    assert [p.root for p in declared.plugins] == [plugin.resolve(), common.resolve()]
    a = agent_task("summarize", plugin=plugin, skills_from=[common])
    assert a.differences(agent_task("summarize", plugin=plugin)) == ["skills", "skills_from"]
    digest = a.digest()
    (common / "skills" / "house-style" / "SKILL.md").write_text("---\nname: house-style\ndescription: d\n---\nLong sentences.\n")
    assert a.digest() != digest  # an edited skill runs the task again on resume


def test_check_lints_every_plugin_a_task_loads(plugin, tmp_path):
    from contraagent import Pipeline
    from contraagent.testing import StubAgent

    common = skill_plugin(tmp_path / "common")
    spec = agent_task("summarize", plugin=plugin, skills_from=[common], max_turns=1, timeout_s=10)
    (common / "skills" / "house-style" / "SKILL.md").write_text("no frontmatter\n")
    report = Pipeline(backends=StubAgent().backends()).check(lambda: spec("a"))
    assert any(str(common.resolve()) in e and "frontmatter has no name" in e for e in report.errors)


def test_the_example_shares_one_skill_plugin(tmp_path):
    from contraagent import Pipeline
    from contraagent.docs.examples.skills import tasks
    from contraagent.testing import StubAgent

    agent = StubAgent({"summarize": lambda launch: {"unit": launch.unit, "points": ["a"]}, "write_note": "# Note\n"})
    report = Pipeline(runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(tasks.notes, units=["alpha"])
    assert report.ok
    style = str(Path(tasks.__file__).parent / "plugins" / "house-style")
    assert {launch.kind: launch.launch.plugin_dirs[-1] for launch in agent.launches} == {"summarize": style, "write_note": style}
    assert {launch.role for launch in agent.launches} == {"summarizer", "writer"}


def test_a_skill_linked_in_from_elsewhere_is_the_plugin_s(plugin, tmp_path):
    """A skill directory that is a symbolic link is read like any other: its files are in
    the digest and the definition, and a link back up the tree is read once."""
    elsewhere = tmp_path / "shared" / "s1"
    (elsewhere / "refs").mkdir(parents=True)
    (elsewhere / "SKILL.md").write_text("---\nname: s1\ndescription: d\n---\nShort sentences.\n")
    (elsewhere / "refs" / "terms.md").write_text("terms\n")
    (plugin / "skills" / "s1").symlink_to(elsewhere, target_is_directory=True)
    (elsewhere / "loop").symlink_to(plugin / "skills", target_is_directory=True)  # a cycle
    p = Plugin.load(plugin)
    paths = [path for path, _ in p.skill_files()]
    assert "skills/s1/SKILL.md" in paths and "skills/s1/refs/terms.md" in paths
    assert len(paths) == len(set(paths))
    assert "skills/s1/SKILL.md" in [f["path"] for f in p.definition("worker")["files"]]
    a = agent_task("summarize", plugin=plugin)
    digest = a.digest()
    (elsewhere / "SKILL.md").write_text("---\nname: s1\ndescription: d\n---\nLong sentences.\n")
    assert a.digest() != digest  # editing the linked skill runs the task again on resume


def test_render_leaves_a_skill_plugin_alone_and_lint_names_what_it_left(tmp_path, capsys):
    from contraagent._internal.cli import main

    common = skill_plugin(tmp_path / "common")
    assert main(["plugin", "render", str(common)]) == 0
    assert "is a skill plugin: it declares no hooks, so nothing is rendered" in capsys.readouterr().out
    assert sorted(p.name for p in common.iterdir()) == [".claude-plugin", "skills"]
    assert Plugin.load(common).lint() == []
    # what an older render left behind
    (common / "package.json").write_text('{"name": "common", "version": "0.1.0"}\n')
    (common / "hooks").mkdir()
    (common / "hooks" / "hooks.json").write_text('{"hooks": {}}\n')
    errs = Plugin.load(common).lint()
    assert errs == ["hooks, package.json: written by `contraagent plugin render`, which a skill plugin does not need; remove them"]
    with pytest.raises(PluginError, match="written by `contraagent plugin render`; remove them"):
        agent_task("t", instructions="x", skills_from=[common])


DRIVE = """
const [, , root] = process.argv;
const out = {};
const write = { path: `${root}/n.md`, content: "x" };
const oc = await (await import(`${root}/opencode/index.js`)).ContraagentHooks({ directory: root });
const result = { title: "edit", output: "Edited.", metadata: {} };
await oc["tool.execute.after"]({ tool: "edit", args: { filePath: write.path, oldString: "a", newString: "b" } }, result);
out.opencode = result.output;
for (const agent of ["omp", "pi"]) {
  const handlers = {};
  (await import(`${root}/${agent}/index.ts`)).default({ on: (name, fn) => (handlers[name] = fn) });
  const input = agent === "pi"
    ? { path: write.path, edits: [{ oldText: "a", newText: "b" }] }
    : { path: write.path, old_string: "a", new_string: "b" };
  const r = await handlers.tool_result({ toolName: "edit", input, content: [{ type: "text", text: "Edited." }] }, { cwd: root });
  out[agent] = r.content.map((c) => c.text).join(" | ");
  out[`${agent}_unnamed`] = await handlers.tool_result({ toolName: "read", input: { path: "x" }, content: [] }, { cwd: root }) ?? null;
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("bun") is None, reason="bun runs the rendered omp and pi extensions")
def test_each_agent_s_hooks_read_claude_code_s_input_and_return_a_post_tool_objection(plugin, tmp_path):
    """The rendered omp and pi extensions and the opencode plugin, driven as each agent calls
    them: the script reads `file_path`, `old_string` and `new_string` whatever the agent named
    them, and its exit 2 reaches the result the agent sees."""
    (plugin / "hooks" / "object.sh").write_text(
        '#!/usr/bin/env bash\ncat >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"\necho >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"\n'
        'echo "add a title line" >&2\nexit 2\n'
    )
    (plugin / "hooks" / "object.sh").chmod(0o755)
    add_hooks(plugin, '\n[[hooks]]\non = "post_tool"\ntool = "edit"\nscript = "hooks/object.sh"\n')
    hooks.write(Plugin.load(plugin))
    (tmp_path / "drive.mjs").write_text(DRIVE)
    proc = subprocess.run(["bun", str(tmp_path / "drive.mjs"), str(plugin.resolve())], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    said = hooks.FEEDBACK.replace("\\n", "\n") + "add a title line"  # the JS template literal reads `\\n` as a line break
    assert out["opencode"] == f"Edited.\n\n{said}"
    assert out["omp"] == out["pi"] == f"Edited. | {said}"
    assert out["omp_unnamed"] is None and out["pi_unnamed"] is None  # a tool the hook does not name: unchanged
    seen = [json.loads(line) for line in (plugin / "seen.jsonl").read_text().splitlines() if line.strip()]
    assert [s["tool_name"] for s in seen] == ["Edit"] * 3
    for s in seen:
        assert s["tool_input"]["file_path"].endswith("/n.md")
        assert (s["tool_input"]["old_string"], s["tool_input"]["new_string"]) == ("a", "b")
