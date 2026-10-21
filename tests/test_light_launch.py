"""A light launch (`agent_task(tools=())`): no tools, the role as the system prompt, the call in the prompt."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, RoutingError, agent_task
from contraagent._internal.cli import main
from contraagent.backends import Backend, CallUsage, ClaudeBackend, Launch, LaunchResult, OmpBackend, Stop, Usage
from contraagent.engine import RoutingPlan
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent


class Verdict(BaseModel):
    same: bool


class Titles(BaseModel):
    first: str
    second: str


class Title(BaseModel):
    first: str


ROLE = (
    "---\nname: judge\ndescription: Judges whether two titles name one subject.\ntools: Read\n---\n\n"
    "- Answer whether the two titles name one subject.\n"
)


@pytest.fixture
def plugin(tmp_path):
    root = tmp_path / "plugins" / "judge"
    new_plugin(root)
    (root / "agents" / "worker.md").unlink()
    (root / "agents" / "judge.md").write_text(ROLE)
    return root


def judge_task(plugin, **kw):
    return agent_task(
        "judge",
        plugin=plugin,
        output=Verdict,
        params=Titles,
        output_from="message",
        tools=(),
        max_turns=2,
        timeout_s=60,
        **{"model": "m", **kw},
    )


def run(tmp_path, flow, stub):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, log=lambda line: None).run(flow)


def test_the_call_is_in_the_prompt_and_the_role_is_the_system_prompt(plugin, tmp_path):
    judge = judge_task(plugin)
    stub = StubAgent({"judge": {"same": True}})
    report = run(tmp_path, lambda: judge("a", Titles(first="Acme patches VPN", second="VPN flaw fixed by Acme")), stub)
    assert report.ok, report.failed
    [launch] = stub.launches
    prompt = launch.launch.prompt
    assert '"first": "Acme patches VPN"' in prompt  # the params, as JSON
    assert '"same"' in prompt and '"type": "boolean"' in prompt  # the output's JSON Schema
    assert "call file" not in prompt  # the agent cannot read one
    assert (report.run_dir / "calls" / "judge-a.json").is_file()  # still written, for the record
    assert launch.launch.system_prompt == "- Answer whether the two titles name one subject."  # no frontmatter
    assert launch.launch.tools == () and launch.launch.plugin_dirs == () and launch.launch.role is None
    assert launch.launch.settings is None and launch.launch.mcp_config is None


def test_claude_code_gets_no_tools_and_the_role_as_its_system_prompt(plugin, tmp_path):
    judge = judge_task(plugin)
    stub = StubAgent({"judge": {"same": False}})
    run(tmp_path, lambda: judge("a", Titles(first="x", second="y")), stub)
    argv = ClaudeBackend().argv(stub.launches[0].launch)
    role = Path(argv[argv.index("--system-prompt-file") + 1])  # a file: the text is never on the command line
    assert role.read_text(encoding="utf-8") == "- Answer whether the two titles name one subject."
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in argv
    assert "--plugin-dir" not in argv and "--agent" not in argv and "--settings" not in argv


def test_omp_gets_no_tools_and_the_role_as_its_system_prompt():
    launch = Launch(prompt="p", model="anthropic/claude-haiku-5-5", system_prompt="- judge", tools=())
    argv = OmpBackend().argv(launch)
    [flag] = [a for a in argv if a.startswith("--system-prompt=")]
    assert Path(flag.removeprefix("--system-prompt=")).read_text(encoding="utf-8") == "- judge"
    assert "--no-tools" in argv and "--no-lsp" in argv
    assert "--plugin-dir" not in argv
    assert "--tools=read,grep" in OmpBackend().argv(Launch(prompt="p", tools=("read", "grep")))
    assert not any(a.startswith(("--system-prompt", "--no-tools", "--tools")) for a in OmpBackend().argv(Launch(prompt="p")))


def test_a_message_that_fails_its_checks_goes_back_to_the_same_session(plugin, tmp_path):
    def agrees(path, value: Verdict):
        return [] if value.same else ["same: the two titles name one subject"]

    judge = judge_task(plugin, validators=[agrees])
    stub = StubAgent({"judge": [{"same": False}, {"same": True}]})
    report = run(tmp_path, lambda: judge("a", Titles(first="x", second="y")), stub)
    assert report.ok, report.failed
    first, fix = stub.launches_of("judge-a")
    assert (first.resumed, fix.resumed) == (False, True)
    assert "the two titles name one subject" in fix.prompt
    assert fix.launch.tools == () and fix.launch.system_prompt == first.launch.system_prompt


def test_a_task_with_no_plugin_has_its_instructions_as_its_system_prompt(tmp_path):
    judge = agent_task(
        "judge",
        instructions="You judge two titles.",
        output=Verdict,
        params=Title,
        output_from="message",
        tools=(),
        max_turns=2,
        timeout_s=60,
    )
    stub = StubAgent({"judge": {"same": True}})
    run(tmp_path, lambda: judge("a", Title(first="x")), stub)
    launch = stub.launches[0].launch
    assert launch.system_prompt == "You judge two titles."
    assert "You judge two titles." not in launch.prompt and '"first": "x"' in launch.prompt
    assert launch.settings is None  # not the template's permissions: there is no tool to permit


def test_tools_are_checked_where_they_are_declared(plugin, tmp_path):
    with pytest.raises(TypeError, match='writes no file: give output_from="message"'):
        agent_task("judge", instructions="x", output=Verdict, tools=(), max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="each coding agent's own names"):
        agent_task("judge", instructions="x", output=Verdict, output_from="message", tools=["Read"], max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="must be \\(\\) \\(no tools\\) or None"):
        agent_task("judge", instructions="x", output=Verdict, output_from="message", tools="", max_turns=1, timeout_s=1)
    common = tmp_path / "plugins" / "common"
    (common / ".claude-plugin").mkdir(parents=True)
    (common / ".claude-plugin" / "plugin.json").write_text('{"name": "common"}')
    (common / "skills" / "s").mkdir(parents=True)
    (common / "skills" / "s" / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nx\n")
    with pytest.raises(TypeError, match="loads no skill"):
        judge_task(plugin, skills_from=[common])
    light, full = (
        judge_task(plugin),
        agent_task("judge", plugin=plugin, output=Verdict, params=Titles, output_from="message", max_turns=2, timeout_s=60),
    )
    assert "tools" in light.differences(full) and light.digest() != full.digest()


def test_contraagent_check_names_a_light_launch_with_a_file_output(tmp_path, monkeypatch, capsys):
    (tmp_path / "flow.py").write_text(
        "from pydantic import BaseModel\nfrom contraagent import agent_task\n\n\nclass V(BaseModel):\n    same: bool\n\n\n"
        "judge = agent_task('judge', instructions='x', output=V, tools=(), max_turns=1, timeout_s=1)\n\n\n"
        "def flow():\n    judge('a')\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert main(["check", "flow.py:flow", "--stub"]) == 1
    assert 'writes no file: give output_from="message"' in capsys.readouterr().out


class Plain(Backend):
    """A coding agent that cannot launch without tools."""

    name = binary = "plain"

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        raise AssertionError("never launched")


def test_routing_refuses_a_coding_agent_that_cannot_launch_light_on_any_hop(tmp_path):
    config = PipelineConfig({"defaults": {"agent": "claude"}, "tasks": {"judge": {"fallbacks": [{"agent": "plain", "model": "p"}]}}})
    backends = {"claude": ClaudeBackend(), "plain": Plain()}
    declared = {"judge": {"max_turns": 1, "timeout_s": 1}}
    with pytest.raises(RoutingError, match=r"judge hop 2/2 plain/p: the task has no tools \(tools=\(\)\), and plain cannot"):
        RoutingPlan.build(config, ["judge"], backends, declared=declared, light=["judge"])
    RoutingPlan.build(config, ["judge"], backends, declared=declared)  # with tools, every hop is fine


def test_the_journal_holds_the_input_of_the_first_call():
    res = LaunchResult(label="x", stop=Stop.COMPLETED, ok=True)
    res.usage = Usage(calls=[CallUsage("m", input=600, cache_read=40, cache_creation=4, output=9), CallUsage("m", 900, 0, 0, 5)])
    u = res.usage.totals()
    assert u is not None and u.resident == 644 and u.input == 1500


def test_the_example_classifies_with_a_light_launch(tmp_path):
    from contraagent.docs.examples.light.flow import classify, items

    stub = StubAgent({"classify": lambda launch: {"category": "security", "promo": False}})
    report = run(tmp_path, lambda: items({"vpn": "Acme patches a VPN flaw"}), stub)
    assert report.ok, report.failed
    assert classify.light and stub.launches[0].launch.tools == ()
    out = json.loads(Path(report.run_dir / "out" / "classify" / "vpn.json").read_text())
    assert out == {"category": "security", "promo": False}
