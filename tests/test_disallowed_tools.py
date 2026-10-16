"""`disallowed_tools`: tools a kind's launches may not use, set in its task table or its declaration."""

import json
import os
import re
from pathlib import Path

import pytest

from contraagent import ConfigError, PipelineConfig, RoutingError, agent_task
from contraagent.backends import ClaudeBackend, CodexBackend, Launch, OmpBackend, OmpRpcBackend, OpencodeBackend, PiBackend
from contraagent.config import Limits
from contraagent.engine import RoutingPlan

DENIED = ("Bash(rm:*)", "WebFetch")
BUDGET = {"max_turns": 1, "timeout_s": 1}

POINTER = "(contraagent docs agents, What each one does)"


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
            "tasks": {"w": {"fallbacks": [{"agent": "omp", "model": "anthropic/x"}, {"agent": "codex", "model": "gpt-y"}]}},
        }
    )
    backends = {"claude": ClaudeBackend(), "omp": OmpBackend(), "codex": CodexBackend()}
    declared = {"w": {**BUDGET, "disallowed_tools": DENIED}}
    with pytest.raises(
        RoutingError, match=r"w hop 3/3 codex/gpt-y: the task denies Bash\(rm:\*\), WebFetch, and codex has no way to deny a tool"
    ):
        RoutingPlan.build(config, ["w"], backends, declared=declared)
    RoutingPlan.build(config, ["w"], backends, declared={"w": BUDGET})  # nothing denied: every hop is fine


def test_pi_denies_whole_tools_and_codex_none():
    assert PiBackend.tool_deny_problem(("Bash", "WebFetch")) is None
    assert PiBackend.tool_deny_problem(DENIED) == f"pi cannot hold Bash(rm:*): it denies whole tools only {POINTER}"
    assert CodexBackend.tool_deny_problem(("WebFetch",)) == f"codex has no way to deny a tool {POINTER}"
    assert CodexBackend.tool_deny_problem(()) is None
    assert OpencodeBackend.tool_deny_problem(DENIED) is None
    assert OpencodeBackend.tool_deny_problem(("Read(secrets/**)", "WebFetch(domain:x.com)", "Skill(deploy)")) is None
    assert OpencodeBackend.tool_deny_problem(("Grep(*.env)", "WebFetch(https://x.com)")) == (
        "opencode cannot hold Grep(*.env), WebFetch(https://x.com): it holds a pattern of Bash, Read, Write, Edit, MultiEdit, "
        f"NotebookEdit, Skill and WebFetch(domain:...) only; deny such a tool whole {POINTER}"
    )


def test_opencode_denies_a_pattern_after_the_rule_the_tool_had(tmp_path):
    from contraagent._internal.backends.opencode.backend import permission_rules

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "app").mkdir()
    denied = ("Read(secrets/**)", "Edit(//etc/hosts)", "Bash(git push:*)", "WebFetch(domain:x.com)")
    hosts = Path(os.path.abspath("/etc/hosts"))
    # On another drive (Windows), no relative path reaches it: it stays absolute.
    edit = Path(os.path.relpath(hosts, repo)).as_posix() if hosts.drive == repo.drive else hosts.as_posix()
    # No role: every tool is allowed but for the patterns; a path is matched from the worktree.
    assert permission_rules(denied, {}, repo / "app") == {
        "read": {"*": "allow", "app/secrets/**": "deny"},
        "edit": {"*": "allow", edit: "deny"},
        "bash": {"*": "allow", "git push*": "deny"},
        "webfetch": {"*": "allow", "https://x.com": "deny", "https://x.com/*": "deny", "http://x.com": "deny", "http://x.com/*": "deny"},
    }
    # A role that allows Read only: the pattern narrows read, bash stays denied whole.
    role = {"*": "deny", "read": "allow"}
    assert permission_rules(("Read(secrets/**)", "Bash(git push:*)"), role, tmp_path) == {
        "*": "deny",
        "read": {
            "*": "allow",
            f"{tmp_path.relative_to(tmp_path.anchor).as_posix()}/secrets/**": "deny",
        },  # outside git: from the drive's root
    }
    assert permission_rules(("Bash",), {"bash": {"*": "allow", "rm*": "deny"}}, tmp_path) == {"bash": "deny"}


def test_omp_denies_whole_tools_and_the_patterns_its_extension_sees():
    assert OmpBackend.tool_deny_problem(DENIED) is None
    assert OmpRpcBackend.tool_deny_problem(DENIED) is None
    taken = ("Read(secrets/**)", "Edit(//etc/hosts)", "WebFetch(domain:x.com)", "Skill(deploy)", "mcp__srv__q")
    assert OmpBackend.tool_deny_problem(taken) is None
    assert OmpBackend.tool_deny_problem(("Grep(*.env)", "WebFetch(https://x.com)", "Agent(explore)")) == (
        "omp cannot hold Grep(*.env), WebFetch(https://x.com), Agent(explore): it holds a pattern of Bash, Read, Write, Edit, "
        f"MultiEdit, Skill and WebFetch(domain:...) only; deny such a tool whole {POINTER}"
    )


def test_omp_loads_its_deny_extension_with_the_rules_in_the_environment(tmp_path):
    from contraagent._internal.backends.omp import deny

    launch = Launch(prompt="p", model="anthropic/m", cwd=tmp_path, limits=Limits(disallowed_tools=DENIED))
    for backend in (OmpBackend(base_env={}), OmpRpcBackend(base_env={})):
        argv = backend.argv(launch)
        assert argv[argv.index(str(deny.EXTENSION)) - 1] == "-e" and deny.EXTENSION.is_file()
        rules = json.loads(backend.env(launch)[deny.DENY_ENV])
        assert [r["rule"] for r in rules] == list(DENIED)
    # Nothing denied, or no tools at all: no extension and no rules, whatever the host has set.
    host = OmpBackend(base_env={deny.DENY_ENV: "[]"})
    for quiet in (Launch(prompt="p", model="m", cwd=tmp_path), Launch(prompt="p", model="m", cwd=tmp_path, tools=(), limits=launch.limits)):
        assert str(deny.EXTENSION) not in host.argv(quiet)
        assert deny.DENY_ENV not in host.env(quiet)


def test_omp_s_rules_match_as_claude_code_s_patterns_do(tmp_path):
    from contraagent._internal.backends.omp import deny

    home = tmp_path / "home"
    work = tmp_path / "work"
    denied = (
        *("WebSearch", "Edit", "Bash(git push:*)", "Bash(npm * build)", "Read(secrets/**)", "Read(src/**/*.md)"),
        *("Write(~/notes.txt)", "Edit(//etc/hosts)", "WebFetch", "WebFetch(domain:x.com)", "Skill(deploy)"),
        *("mcp__Doc-Store__search", "mcp__other", "Glob(src/**)"),
    )
    rules = deny.rules(denied, work, home)
    by_rule = {r["rule"]: r for r in rules}
    assert "Glob(src/**)" not in by_rule  # not taken: `problem` names it
    assert by_rule["WebSearch"] == {"rule": "WebSearch", "tools": ["web_search"]}
    assert by_rule["Edit"]["tools"] == ["edit", "ast_edit"]
    # A command pattern is matched against each command of the line (the extension splits it).
    push = re.compile(by_rule["Bash(git push:*)"]["command"])
    assert push.match("git push") and push.match("git push origin main")
    assert not push.match("git pushy") and not push.match("git status")
    build = re.compile(by_rule["Bash(npm * build)"]["command"])
    assert build.match("npm run build") and not build.match("npm run test")

    def path(rule):
        return re.compile(next(r["path"] for r in rules if r["rule"] == rule and "path" in r))

    w = work.resolve().as_posix()
    assert path("Read(secrets/**)").match(f"{w}/secrets") and path("Read(secrets/**)").match(f"{w}/secrets/a/b.txt")
    assert not path("Read(secrets/**)").match(f"{w}/secretsx")
    md = path("Read(src/**/*.md)")
    assert md.match(f"{w}/src/a.md") and md.match(f"{w}/src/x/y/a.md") and not md.match(f"{w}/src/a.txt")
    assert path("Write(~/notes.txt)").match(f"{home.as_posix()}/notes.txt")
    assert path("Edit(//etc/hosts)").match("/etc/hosts") and not path("Edit(//etc/hosts)").match("/etc/hostsx")
    # An edit pattern holds edit and write to the path, and ast_edit whole (its glob is no path).
    edits = [r for r in rules if r["rule"] == "Edit(//etc/hosts)"]
    assert edits[0]["tools"] == ["edit", "write"] and edits[1] == {"rule": "Edit(//etc/hosts)", "tools": ["ast_edit"]}
    assert by_rule["WebFetch"] == {"rule": "WebFetch", "tools": ["read"], "schemes": ["http", "https"]}
    assert by_rule["WebFetch(domain:x.com)"]["host"] == "x.com"
    assert by_rule["Skill(deploy)"] == {"rule": "Skill(deploy)", "tools": ["read"], "schemes": ["skill"], "host": "deploy"}
    assert by_rule["mcp__Doc-Store__search"]["tools"] == ["mcp__doc_store_search"]
    assert by_rule["mcp__other"]["prefix"] == "mcp__other_"
