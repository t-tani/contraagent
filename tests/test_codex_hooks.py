"""A plugin's hooks on Codex: rendered into `codex/hooks.json`, passed as config with the trust
Codex asks for, and run through the bridge that hands each script Claude Code's input.

The shapes are codex-cli 0.162.1's: a hook's input as Codex sent it in a live run, the trust
key and hash as its hook discovery computes them (`codex-rs/hooks/src/engine/discovery.rs`).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from contraagent._internal.backends.codex import hooks as codex_hooks
from contraagent._internal.backends.codex.wire import read_rollout
from contraagent._internal.platform.commands import commands
from contraagent._internal.plugins import hooks
from contraagent.backends import CodexBackend, Launch
from contraagent.config import ApiKey
from contraagent.plugins import Plugin, new_plugin
from fake_cli import write_fake_cli

SESSION = "/<session-flags>/config.toml"


@pytest.fixture
def plugin(tmp_path):
    root = tmp_path / "plugins" / "noter"
    new_plugin(root)
    (root / "hooks" / "title.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (root / "hooks.toml").write_text(
        (root / "hooks.toml").read_text()
        + '\n[[hooks]]\non = "pre_tool"\ntool = "bash"\nmatch = "rm -rf"\nscript = "hooks/title.sh"\n'
        + "".join(f'\n[[hooks]]\non = "post_tool"\ntool = "{t}"\nscript = "hooks/title.sh"\n' for t in ("write", "edit", "grep"))
    )
    hooks.write(Plugin.load(root))
    return root


def test_hooks_toml_is_rendered_in_codex_s_own_format(plugin):
    files, notes = hooks.render(Plugin.load(plugin), ["codex"])
    rendered = json.loads(files["codex/hooks.json"])["hooks"]
    assert (plugin / "codex" / "hooks.json").read_text() == files["codex/hooks.json"]
    assert rendered["Stop"] == [{"hooks": [{"type": "command", "command": hooks.STOP_VALIDATE}]}]  # Claude Code's own check
    [pre] = rendered["PreToolUse"]
    assert pre["matcher"] == "Bash"
    assert pre["hooks"][0]["command"] == f"{hooks.CODEX_BRIDGE} --tool bash --match 'rm -rf' hooks/title.sh"
    [post] = rendered["PostToolUse"]  # write and edit are both Codex's apply_patch
    assert post["matcher"] == "apply_patch" and len(post["hooks"]) == 2
    assert notes == ["codex: no grep tool (it reads and searches with shell commands): hooks/title.sh does not run there"]
    assert Plugin.load(plugin).lint() == []


@pytest.fixture
def posix(monkeypatch):
    monkeypatch.setattr(codex_hooks, "WINDOWS", False)


class Bash:
    def __init__(self, path: str | None) -> None:
        self.path = path

    def bash(self, env=None) -> str | None:
        return self.path


GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(codex_hooks, "WINDOWS", True)
    monkeypatch.setattr(codex_hooks, "commands", Bash(GIT_BASH))


def test_a_rendered_hook_is_passed_as_config_and_trusted_by_its_hash(plugin, tmp_path, posix):
    user = tmp_path / "config.toml"
    user.write_text('[hooks.state."/u/.codex/hooks.json:session_start:0:0"]\ntrusted_hash = "sha256:x"\nenabled = true\n')
    table = codex_hooks.hooks_config((str(plugin),), "/home/me", user)
    assert table is not None
    stop = table["Stop"][0]["hooks"][0]
    assert stop == {"type": "command", "command": "HOME=/home/me " + hooks.STOP_VALIDATE}  # Codex's own HOME is not the user's
    post = table["PostToolUse"][0]["hooks"][1]["command"]
    assert f'--root "{plugin.resolve()}"' in post and "${CLAUDE_PLUGIN_ROOT}" not in post  # as Codex fills a plugin's own
    state = table["state"]
    assert state["/u/.codex/hooks.json:session_start:0:0"] == {"enabled": False}  # the user's own hook stays out
    assert sorted(k for k in state if k.startswith(SESSION)) == [
        f"{SESSION}:post_tool_use:0:0",
        f"{SESSION}:post_tool_use:0:1",
        f"{SESSION}:pre_tool_use:0:0",
        f"{SESSION}:stop:0:0",
    ]
    assert state[f"{SESSION}:stop:0:0"]["trusted_hash"] == codex_hooks.trusted_hash("Stop", None, stop)
    assert codex_hooks.hooks_config((str(tmp_path),), "/home/me", user) is None  # no plugin hooks: none


def test_the_trust_hash_is_codex_s(tmp_path):
    # The hash of a Stop hook `cat > /tmp/x/stop.json`, which codex-cli 0.162.1 ran when trusted
    # with it (and did not run with another).
    handler = {"type": "command", "command": "cat > /tmp/x/stop.json"}
    identity = '{"event_name":"stop","hooks":[{"async":false,"command":"cat > /tmp/x/stop.json","timeout":600,"type":"command"}]}'
    assert codex_hooks.trusted_hash("Stop", "ignored", handler) == "sha256:" + hashlib.sha256(identity.encode()).hexdigest()
    with_matcher = codex_hooks.trusted_hash("PostToolUse", "apply_patch", {**handler, "timeout": 30})
    assert with_matcher != codex_hooks.trusted_hash("PostToolUse", None, {**handler, "timeout": 30})


def test_on_windows_a_hook_runs_under_git_bash_from_powershell(plugin, windows):
    # Codex runs a hook there under PowerShell (`-NoProfile -Command`), and names the hooks of
    # `-c` values by `C:\<session-flags>\config.toml`.
    table = codex_hooks.hooks_config((str(plugin),), r"C:\Users\me", None)
    assert table is not None
    stop = table["Stop"][0]["hooks"][0]
    assert stop["command"] == (
        "$env:CONTRAAGENT_HOOK='HOME=''C:\\Users\\me'' \"${CONTRAAGENT_PYTHON:-python3}\" -m contraagent call validate'; "
        "& 'C:\\Program Files\\Git\\bin\\bash.exe' -c 'IFS=;set -f;eval set +f\\;unset IFS\\;$CONTRAAGENT_HOOK'; "
        "exit $LASTEXITCODE"
    )
    pre = table["PreToolUse"][0]["hooks"][0]["command"]
    assert "--match ''rm -rf''" in pre and f'--root "{plugin.resolve()}"' in pre
    state = table["state"]
    windows_source = "C:\\<session-flags>\\config.toml"
    assert all(k.startswith(windows_source) for k in state)
    assert state[f"{windows_source}:stop:0:0"]["trusted_hash"] == codex_hooks.trusted_hash("Stop", None, stop)


def test_on_windows_without_git_bash_no_hook_is_passed(plugin, windows, monkeypatch):
    monkeypatch.setattr(codex_hooks, "commands", Bash(None))
    assert codex_hooks.hooks_config((str(plugin),), r"C:\Users\me", None) is None


def test_a_powershell_string_doubles_every_single_quote():
    assert codex_hooks.powershell_quote("it's \u2018x\u2019") == "'it''s \u2018\u2018x\u2019\u2019'"


def test_bash_runs_the_handed_command_line_as_it_is(tmp_path):
    (tmp_path / "a b").touch()
    words = "v='p q'; printf '[%s]' 'two  spaces' '*' \"${CONTRAAGENT_PYTHON:-python3}\" $v *; exit 2"
    env = {k: v for k, v in os.environ.items() if k != "CONTRAAGENT_PYTHON"}
    env[codex_hooks.COMMAND_VARIABLE] = words
    proc = subprocess.run([commands.bash() or "bash", "-c", codex_hooks.BASH_EVAL], env=env, cwd=tmp_path, capture_output=True, text=True)
    # The quoted words as they are, and splitting and globbing on again for the unquoted ones.
    assert (proc.returncode, proc.stdout) == (2, "[two  spaces][*][python3][p][q][a b]")


POWERSHELLS = [p for p in (shutil.which("pwsh"), shutil.which("powershell")) if p]


@pytest.mark.skipif(sys.platform != "win32" or not POWERSHELLS, reason="Codex runs its hooks under PowerShell on Windows")
@pytest.mark.parametrize("shell", POWERSHELLS)
def test_a_windows_hook_runs_its_script_as_codex_runs_it(shell, tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "s.sh").write_text(
        '#!/usr/bin/env bash\ncat > "$CLAUDE_PLUGIN_ROOT/seen.json"\necho "home=$HOME"\necho "not yet" >&2\nexit 2\n', newline="\n"
    )
    stop = [{"hooks": [{"type": "command", "command": f"{hooks.CODEX_BRIDGE} hooks/s.sh"}]}]
    (root / "codex").mkdir()
    (root / "codex" / "hooks.json").write_text(json.dumps({"hooks": {"Stop": stop}}))
    home = tmp_path / "it's home"
    table = codex_hooks.hooks_config((str(root),), str(home), None)
    assert table is not None
    command = table["Stop"][0]["hooks"][0]["command"]
    payload = {"hook_event_name": "Stop", "cwd": str(tmp_path), "stop_hook_active": False}
    proc = subprocess.run(  # as `build_command` in codex-rs/hooks/src/engine/command_runner.rs
        [shell, "-NoProfile", "-Command", command],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "CONTRAAGENT_PYTHON": sys.executable},
    )
    assert proc.returncode == 2, proc
    assert proc.stderr.strip().endswith("not yet")
    assert json.loads((root / "seen.json").read_text()) == payload
    assert "it's home" in proc.stdout


CODEX = r"""
import json, os, sys
json.dump({"argv": sys.argv}, open(os.environ["FAKE_DUMP"], "w"))
print(json.dumps({"type": "thread.started", "thread_id": "01a13afd-d786-78c2-9439-7b6c086efc20"}))
print(json.dumps({"type": "turn.completed", "usage": {}}))
"""


def launch_argv(tmp_path, **kw) -> list[str]:
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "codex", CODEX)
    dump = tmp_path / "dump.json"
    base = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path / "home"), "XDG_CACHE_HOME": str(tmp_path / "cache")}
    base["MY_KEY"] = "sk-test"
    launch = Launch(prompt="hello", label="t", cwd=tmp_path, env={"FAKE_DUMP": str(dump)}, **kw)
    assert CodexBackend(base_env=base).run(launch).ok
    return json.loads(dump.read_text())["argv"]


def test_a_launch_turns_hooks_on_only_for_its_plugins_hooks(plugin, tmp_path):
    home = tmp_path / "home" / ".codex"
    home.mkdir(parents=True)
    (home / "config.toml").write_text('[hooks.state."/mine:stop:0:0"]\ntrusted_hash = "sha256:x"\n')
    argv = launch_argv(tmp_path)
    assert ["--disable", "hooks"] == argv[argv.index("hooks") - 1 : argv.index("hooks") + 1] and "--enable" not in argv
    argv = launch_argv(tmp_path, plugin_dirs=(str(plugin),))  # ambient: the user's config.toml is read
    assert "--enable" in argv and argv[argv.index("--enable") + 1] == "hooks" and "--disable" in argv  # plugins stay off
    value = next(a for a in argv if a.startswith("hooks="))
    table = tomllib.loads("x = " + value.removeprefix("hooks="))["x"]  # one TOML value, as `-c` parses it
    assert table["state"]["/mine:stop:0:0"] == {"enabled": False}
    assert hooks.STOP_VALIDATE in table["Stop"][0]["hooks"][0]["command"]
    argv = launch_argv(tmp_path, plugin_dirs=(str(plugin),), credential=ApiKey(name="k", provider="openai", key="env:MY_KEY"))
    value = next(a for a in argv if a.startswith("hooks="))
    assert "/mine" not in value  # an isolated launch reads no user config.toml: nothing to turn off


PATCH = """*** Begin Patch
*** Add File: notes/a.md
+green tea
+
*** Update File: notes/b.md
@@
 # Title
-old line
+new line
*** Update File: /abs/c.md
*** Move to: moved/c.md
@@ one
-x
+y
@@ two
-p
+q
*** Delete File: gone.md
*** End Patch"""


def test_an_apply_patch_reaches_a_script_as_claude_code_s_write_and_edit(tmp_path):
    calls = hooks.patch_inputs(PATCH, str(tmp_path))
    assert calls == [
        ("Write", {"file_path": str(tmp_path / "notes" / "a.md"), "content": "green tea\n\n"}),
        ("Edit", {"file_path": str(tmp_path / "notes" / "b.md"), "old_string": "# Title\nold line", "new_string": "# Title\nnew line"}),
        ("Edit", {"file_path": str(tmp_path / "moved" / "c.md")}),  # two hunks: no single old and new string
    ]  # a deleted file has no Claude Code call
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
    assert hooks.codex_inputs(payload) == [("Bash", {"command": "ls"})]  # a shell command is Claude Code's already


@pytest.fixture
def script(tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "s.sh").write_text(
        '#!/usr/bin/env bash\ninput=$(cat)\necho "$input" >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"\n'
        'case "$input" in *b.md*) echo "$CLAUDE_PROJECT_DIR: add a title" >&2; exit 2 ;; esac\necho ok\n'
    )
    return root


def seen(root: Path) -> list[dict]:
    path = root / "seen.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_the_bridge_runs_the_script_per_file_and_returns_its_objection(script, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s",
        "cwd": str(work),
        "tool_name": "apply_patch",
        "tool_input": {"command": PATCH},
        "tool_response": "Success.",
    }
    code, out, err = hooks.run_codex_hook(json.dumps(payload), script, "hooks/s.sh", tool="edit")
    assert (code, out, err) == (2, "", f"{work}: add a title")  # two Edit calls ran; the second objected
    runs = seen(script)
    assert [(r["tool_name"], Path(r["tool_input"]["file_path"]).name) for r in runs] == [("Edit", "b.md"), ("Edit", "c.md")]
    assert all(r["session_id"] == "s" and r["tool_response"] == "Success." for r in runs)  # the rest of Codex's input stays
    (script / "seen.jsonl").unlink()
    code, out, err = hooks.run_codex_hook(json.dumps(payload), script, "hooks/s.sh", tool="write")
    assert (code, out, err) == (0, "ok\n", "") and [r["tool_name"] for r in seen(script)] == ["Write"]


def test_a_pre_tool_bridge_stops_at_the_first_objection_and_matches_the_command(script, tmp_path):
    pre = {"hook_event_name": "PreToolUse", "cwd": str(tmp_path), "tool_name": "apply_patch", "tool_input": {"command": PATCH}}
    code, _, _ = hooks.run_codex_hook(json.dumps(pre), script, "hooks/s.sh")
    assert code == 2 and [Path(r["tool_input"]["file_path"]).name for r in seen(script)] == ["a.md", "b.md"]
    (script / "seen.jsonl").unlink()
    bash = {"hook_event_name": "PreToolUse", "cwd": str(tmp_path), "tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    assert hooks.run_codex_hook(json.dumps(bash), script, "hooks/s.sh", tool="bash", match="rm -rf") == (0, "", "")
    assert seen(script) == []  # the command does not hold the match
    assert hooks.run_codex_hook(json.dumps(bash), script, "hooks/s.sh", tool="bash", match="-la")[0] == 0
    assert seen(script)[0]["tool_input"] == {"command": "ls -la"}


def test_the_bridge_is_a_command(script, tmp_path):
    (tmp_path / "b.md").mkdir()
    stop = {"hook_event_name": "Stop", "cwd": str(tmp_path / "b.md"), "stop_hook_active": False}
    proc = subprocess.run(
        [sys.executable, "-m", "contraagent", "plugin", "hook", "--agent", "codex", "--root", str(script), "hooks/s.sh"],
        input=json.dumps(stop),
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 2 and proc.stderr.strip().endswith("b.md: add a title")  # a Stop hook's input goes on as it is
    assert seen(script) == [stop]


def test_what_a_stop_hook_sent_back_is_read_from_the_rollout(tmp_path):
    said = "[heading] no heading"
    text = f'<hook_prompt hook_run_id="stop:2:/&lt;session-flags&gt;/config.toml">Fix it:\n- {said} &amp; &lt;more&gt;</hook_prompt>'
    lines = [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}},
    ]
    path = tmp_path / "rollout.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert read_rollout(path).hook_errors == [[f"{said} & <more>"]]
