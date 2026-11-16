"""A plugin's hooks on agy: rendered into `agy/hooks.json` in Claude Code's format, and run
through the bridge that hands each script Claude Code's input and answers agy in its own terms.

The inputs are agy 1.5.9's: what it sent a hook of each event in live runs.
"""

import json
import os
import stat
import subprocess
import sys

import pytest

from contraagent._internal.backends.agy import hooks as agy_hooks
from contraagent._internal.plugins import hooks
from contraagent.plugins import Plugin, new_plugin

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the hook scripts are started as `${CLAUDE_PLUGIN_ROOT}/x.sh`")

CONVERSATION = "ed71f6de-4f8d-4984-b50c-38c624d3eba8"


def script(root, name: str, body: str) -> None:
    path = root / "hooks" / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def plugin(tmp_path):
    root = tmp_path / "plugins" / "noter"
    new_plugin(root)
    script(root, "guard.sh", 'cat > "$CLAUDE_PLUGIN_ROOT/seen-pre.json"; echo "no force push" >&2; exit 2')
    script(root, "note.sh", 'cat > "$CLAUDE_PLUGIN_ROOT/seen-post.json"; echo "the note has no title" >&2; exit 2')
    script(root, "quiet.sh", "exit 0")
    script(root, "done.sh", 'input=$(cat); echo "$input" >> "$CLAUDE_PLUGIN_ROOT/seen-stop.jsonl"\n'
           'case "$input" in *\'"stop_hook_active": true\'*) exit 0;; esac\necho "run the tests first" >&2; exit 2')  # fmt: skip
    (root / "hooks.toml").write_text(
        '[[hooks]]\non = "stop"\nscript = "hooks/done.sh"\n'
        '\n[[hooks]]\non = "pre_tool"\ntool = "bash"\nmatch = "push --force"\nscript = "hooks/guard.sh"\n'
        '\n[[hooks]]\non = "pre_tool"\nscript = "hooks/quiet.sh"\n'
        '\n[[hooks]]\non = "post_tool"\ntool = "write"\nscript = "hooks/note.sh"\n',
        encoding="utf-8",
        newline="\n",
    )
    hooks.write(Plugin.load(root))
    return root


def payload(event: str, tmp_path, **fields) -> str:
    """What agy sends a hook of `event` on stdin (its keys are camelCase)."""
    common = {
        "hookEventName": event,
        "conversationId": CONVERSATION,
        "cwd": str(tmp_path),
        "modelName": "gemini-3.8-flash-low",
        "transcriptPath": f"/home/user/.gemini/antigravity-cli/brain/{CONVERSATION}/.system_generated/logs/transcript_full.jsonl",
        "workspacePaths": [str(tmp_path)],
    }
    return json.dumps({**common, **fields})


def tool(name: str, **args) -> dict:
    return {"toolCall": {"id": "call_1", "name": name, "args": args}, "stepIdx": 2}


def test_hooks_toml_is_rendered_in_claude_code_s_format_for_the_bridge(plugin):
    files, notes = hooks.render(Plugin.load(plugin), ["agy"])
    assert notes == [] and list(files) == [agy_hooks.HOOKS_FILE]
    assert (plugin / "agy" / "hooks.json").read_text(encoding="utf-8") == files["agy/hooks.json"]
    rendered = json.loads(files["agy/hooks.json"])["hooks"]
    assert rendered["Stop"] == [{"hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/done.sh"}]}]
    assert rendered["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/guard.sh", "match": "push --force"}]},
        {"hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/quiet.sh"}]},  # no tool: every tool
    ]
    assert rendered["PostToolUse"] == [
        {"matcher": "Write", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/note.sh"}]}
    ]
    assert not [e for e in Plugin.load(plugin).lint() if "agy" in e]
    assert agy_hooks.declared(plugin) == rendered and agy_hooks.declared(plugin / "none") == {}
    # The built-in output check is the command Claude Code runs.
    template = plugin.parent / "template"
    new_plugin(template)
    assert (
        json.loads((template / "agy" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]["command"]
        == hooks.STOP_VALIDATE
    )


def test_a_pre_tool_script_that_exits_2_denies_the_call_with_its_words(plugin, tmp_path):
    env = {"PATH": os.environ["PATH"]}
    out = hooks.run_agy_hook(
        payload("PreToolUse", tmp_path, **tool("run_command", CommandLine="git push --force", WaitMsBeforeAsync=5000)), plugin, env
    )
    assert json.loads(out) == {"decision": "deny", "reason": "no force push"}
    seen = json.loads((plugin / "seen-pre.json").read_text(encoding="utf-8"))  # Claude Code's input, under its names
    assert seen == {
        "hook_event_name": "PreToolUse",
        "session_id": CONVERSATION,
        "transcript_path": json.loads(payload("PreToolUse", tmp_path))["transcriptPath"],
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force", "WaitMsBeforeAsync": 5000},
    }
    # No objection prints nothing: agy's own permissions decide. An empty object would deny the call.
    assert hooks.run_agy_hook(payload("PreToolUse", tmp_path, **tool("run_command", CommandLine="git status")), plugin, env) == ""
    assert hooks.run_agy_hook(payload("PreToolUse", tmp_path, **tool("read_file", Path="a.md")), plugin, env) == ""


def test_a_post_tool_script_s_words_are_held_until_the_model_is_called(plugin, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    env = {"PATH": os.environ["PATH"], agy_hooks.STATE_ENV: str(state)}
    written = tool("write_file", Path="notes/a.md", Content="x", Overwrite=True)
    assert hooks.run_agy_hook(payload("PostToolUse", tmp_path, error="", **written), plugin, env) == "{}"  # agy takes no words here
    seen = json.loads((plugin / "seen-post.json").read_text(encoding="utf-8"))
    assert seen["tool_name"] == "Write" and seen["tool_input"] == {
        "file_path": str(tmp_path / "notes" / "a.md"),
        "content": "x",
        "Overwrite": True,
    }
    assert hooks.run_agy_hook(payload("PostToolUse", tmp_path, **tool("run_command", CommandLine="ls")), plugin, env) == "{}"  # not a write
    said = json.loads(hooks.run_agy_hook(payload("PreInvocation", tmp_path, invocationNum=1), plugin, env))
    assert said == {
        "injectSteps": [{"systemMessage": {"systemMessage": "A task hook objected to this call (exit 2):\nthe note has no title"}}]
    }
    assert hooks.run_agy_hook(payload("PreInvocation", tmp_path, invocationNum=2), plugin, env) == "{}"  # handed over once
    # Outside a launch of contraagent there is nowhere to hold them.
    assert hooks.run_agy_hook(payload("PostToolUse", tmp_path, **written), plugin, {"PATH": env["PATH"]}) == "{}"
    assert hooks.run_agy_hook(payload("PreInvocation", tmp_path), plugin, {"PATH": env["PATH"]}) == "{}"


def test_a_stop_hook_that_exits_2_continues_the_session_once(plugin, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    env = {"PATH": os.environ["PATH"], agy_hooks.STATE_ENV: str(state)}
    first = hooks.run_agy_hook(
        payload("Stop", tmp_path, executionNum=0, continuationActive=False, terminationReason="NO_TOOL_CALL"), plugin, env
    )
    assert json.loads(first) == {"decision": "continue", "reason": "run the tests first"}
    # agy 1.5.9 leaves `continuationActive` false in a headless run; `executionNum` counts the stops.
    again = hooks.run_agy_hook(payload("Stop", tmp_path, executionNum=1, continuationActive=False), plugin, env)
    assert again == "{}"
    seen = [json.loads(line) for line in (plugin / "seen-stop.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(s["hook_event_name"], s["stop_hook_active"], s["session_id"]) for s in seen] == [
        ("Stop", False, CONVERSATION),
        ("Stop", True, CONVERSATION),
    ]
    assert hooks.run_agy_hook(payload("Stop", tmp_path, executionNum=0, continuationActive=True), plugin, env) == "{}"
    assert agy_hooks.read_objections(state) == ["run the tests first"]  # what the launch's result reports


def test_each_agy_tool_reaches_a_script_under_claude_code_s_name_and_arguments(tmp_path):
    cwd = str(tmp_path)
    assert hooks.agy_input("edit_file", {"Path": "a.md", "Target": "beta", "Replacement": "BETA"}, cwd) == {
        "file_path": str(tmp_path / "a.md"),
        "old_string": "beta",
        "new_string": "BETA",
    }
    assert hooks.agy_input("read_file", {"Path": "/abs/a.md", "StartLine": 1}, cwd) == {"file_path": "/abs/a.md", "StartLine": 1}
    assert hooks.agy_input("search_web", {"query": "x"}, cwd) == {"query": "x"} and hooks.agy_input("run_command", None, cwd) == {}
    names = hooks.AGY_CLAUDE_TOOL
    assert [names[t] for t in ("run_command", "read_file", "write_file", "edit_file", "search_web")] == [
        "Bash",
        "Read",
        "Write",
        "Edit",
        "WebSearch",
    ]
    assert [names[t] for t in ("view_file", "write_to_file", "replace_file_content", "grep_search", "find_by_name")] == [
        "Read",
        "Write",
        "Edit",
        "Grep",
        "Glob",
    ]


def test_an_input_the_bridge_cannot_read_never_fails_the_hook(plugin, tmp_path):
    env = {"PATH": os.environ["PATH"]}
    assert hooks.run_agy_hook("not json", plugin, env) == "{}"
    assert hooks.run_agy_hook("[]", plugin, env) == "{}"
    assert hooks.run_agy_hook(payload("SessionStart", tmp_path), plugin, env) == "{}"
    assert hooks.run_agy_hook(payload("PreToolUse", tmp_path), plugin, env) == ""  # no tool call named: no objection
    assert hooks.run_agy_hook(payload("Stop", tmp_path), tmp_path / "no-plugin", env) == "{}"


def test_the_command_agy_runs_is_the_bridge_and_always_exits_0(plugin, tmp_path):
    native = agy_hooks.native_hooks((str(plugin),), sys.executable)
    [hook] = native.values()
    command = hook["Stop"][0]["command"]
    assert command == agy_hooks.command_line(
        [sys.executable, "-m", "contraagent", "plugin", "hook", "--agent", "agy", "--root", str(plugin.resolve())]
    )
    assert agy_hooks.native_hooks((str(tmp_path),), sys.executable) == {}  # a plugin with no rendered hooks
    stdin = payload("PreToolUse", tmp_path, **tool("run_command", CommandLine="git push --force origin main"))
    proc = subprocess.run(command, shell=True, input=stdin, capture_output=True, text=True, encoding="utf-8", cwd=tmp_path)
    assert proc.returncode == 0 and json.loads(proc.stdout) == {"decision": "deny", "reason": "no force push"}
    codex = subprocess.run(
        [sys.executable, "-m", "contraagent", "plugin", "hook", "--agent", "codex", "--root", str(plugin)], capture_output=True, text=True
    )
    assert codex.returncode == 2 and "needs the hook script" in codex.stderr
