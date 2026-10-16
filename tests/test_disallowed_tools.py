"""`disallowed_tools`: tools a kind's launches may not use, set in its task table or its declaration."""

import os

import pytest

from contraagent import ConfigError, PipelineConfig, RoutingError, agent_task
from contraagent.backends import ClaudeBackend, CodexBackend, Launch, OmpBackend, OpencodeBackend, PiBackend
from contraagent.config import Limits
from contraagent.engine import RoutingPlan

DENIED = ("Bash(rm:*)", "WebFetch")
BUDGET = {"max_turns": 1, "timeout_s": 1}


def test_a_task_table_and_a_declaration_take_it_and_check_it():
    tables = PipelineConfig({"tasks": {"w": {"disallowed_tools": list(DENIED)}}}).task_tables()
    assert tables == {"w": {"disallowed_tools": list(DENIED)}}
    spec = agent_task("w", instructions="x", disallowed_tools=list(DENIED), **BUDGET)
    plan = RoutingPlan.build(PipelineConfig({}), ["w"], {"claude": ClaudeBackend()}, declared={"w": spec.config})
    assert plan.configs["w"].disallowed_tools == DENIED
    assert plan.configs["w"].limits().disallowed_tools == DENIED
    for bad in (["no such tool"], [""], "WebFetch", [3]):
        with pytest.raises(ConfigError, match="disallowed_tools must be a list of tools or tool patterns"):
            PipelineConfig({"tasks": {"w": {"disallowed_tools": bad}}}).task_tables()
    with pytest.raises(ConfigError, match="disallowed_tools"):
        agent_task("w", instructions="x", disallowed_tools=["no such tool"], **BUDGET)


def test_the_config_file_s_list_outranks_the_declaration_s():
    spec = agent_task("w", instructions="x", disallowed_tools=["WebFetch"], **BUDGET)
    config = PipelineConfig({"tasks": {"w": {"disallowed_tools": ["WebSearch"]}}})
    plan = RoutingPlan.build(config, ["w"], {"claude": ClaudeBackend()}, declared={"w": spec.config})
    assert plan.configs["w"].disallowed_tools == ("WebSearch",)


def test_each_coding_agent_denies_them_its_own_way():
    launch = Launch(prompt="p", model="m", limits=Limits(disallowed_tools=DENIED))
    claude = ClaudeBackend().argv(launch)
    assert claude[claude.index("--disallowedTools") + 1 : claude.index("--disallowedTools") + 3] == list(DENIED)
    pi = PiBackend().argv(Launch(prompt="p", model="m", limits=Limits(disallowed_tools=("Bash", "WebFetch", "Glob"))))
    assert pi[pi.index("--exclude-tools") + 1] == "bash,webfetch,find"
    assert "--exclude-tools" not in PiBackend().argv(Launch(prompt="p", model="m", tools=(), limits=Limits(disallowed_tools=("Bash",))))


def test_routing_refuses_an_agent_that_cannot_deny_them_on_any_hop():
    config = PipelineConfig(
        {
            "defaults": {"agent": "claude"},
            "tasks": {"w": {"fallbacks": [{"agent": "opencode", "model": "anthropic/x"}, {"agent": "omp", "model": "anthropic/y"}]}},
        }
    )
    backends = {"claude": ClaudeBackend(), "opencode": OpencodeBackend(), "omp": OmpBackend()}
    declared = {"w": {**BUDGET, "disallowed_tools": DENIED}}
    with pytest.raises(
        RoutingError, match=r"w hop 3/3 omp/anthropic/y: the task denies Bash\(rm:\*\), WebFetch, and omp has no way to deny a tool"
    ):
        RoutingPlan.build(config, ["w"], backends, declared=declared)
    RoutingPlan.build(config, ["w"], backends, declared={"w": BUDGET})  # nothing denied: every hop is fine


def test_pi_denies_whole_tools_and_codex_none():
    assert PiBackend.tool_deny_problem(("Bash", "WebFetch")) is None
    assert PiBackend.tool_deny_problem(DENIED) == "pi denies whole tools only, not Bash(rm:*)"
    assert CodexBackend.tool_deny_problem(("WebFetch",)) == "codex has no way to deny a tool"
    assert CodexBackend.tool_deny_problem(()) is None
    assert OpencodeBackend.tool_deny_problem(DENIED) is None
    assert OpencodeBackend.tool_deny_problem(("Read(secrets/**)", "WebFetch(domain:x.com)", "Skill(deploy)")) is None
    assert OpencodeBackend.tool_deny_problem(("Grep(*.env)", "WebFetch(https://x.com)")) == (
        "opencode denies these tools whole only, not Grep(*.env), WebFetch(https://x.com)"
    )


def test_opencode_denies_a_pattern_after_the_rule_the_tool_had(tmp_path):
    from contraagent._internal.backends.opencode.backend import permission_rules

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "app").mkdir()
    denied = ("Read(secrets/**)", "Edit(//etc/hosts)", "Bash(git push:*)", "WebFetch(domain:x.com)")
    # No role: every tool is allowed but for the patterns; a path is matched from the worktree.
    assert permission_rules(denied, {}, repo / "app") == {
        "read": {"*": "allow", "app/secrets/**": "deny"},
        "edit": {"*": "allow", os.path.relpath("/etc/hosts", repo): "deny"},
        "bash": {"*": "allow", "git push*": "deny"},
        "webfetch": {"*": "allow", "https://x.com": "deny", "https://x.com/*": "deny", "http://x.com": "deny", "http://x.com/*": "deny"},
    }
    # A role that allows Read only: the pattern narrows read, bash stays denied whole.
    role = {"*": "deny", "read": "allow"}
    assert permission_rules(("Read(secrets/**)", "Bash(git push:*)"), role, tmp_path) == {
        "*": "deny",
        "read": {"*": "allow", f"{tmp_path.relative_to('/').as_posix()}/secrets/**": "deny"},  # outside git: from /
    }
    assert permission_rules(("Bash",), {"bash": {"*": "allow", "rm*": "deny"}}, tmp_path) == {"bash": "deny"}
