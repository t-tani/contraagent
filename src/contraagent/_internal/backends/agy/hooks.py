"""A plugin's hooks on agy: one bridge command per event, in a `hooks.json` of the launch's own.

`contraagent plugin render` writes `agy/hooks.json` in Claude Code's hook format
(`{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": ...}]}]}}`), each command
one that reads Claude Code's input on stdin and objects by exiting 2. agy's own hooks
differ (checked against agy 1.5.9): a `hooks.json` holds named hooks, a hook reads agy's
input (`hookEventName`, `toolCall`, camelCase) and answers with JSON on stdout
(`{"decision": "deny", "reason": ...}` before a tool, `{"decision": "continue", "reason":
...}` at a stop), and a hook that exits nonzero fails the tool call it was asked about.

So a launch gets a `hooks.json` of its own (`native_hooks`): for each plugin with rendered
hooks, one named hook whose handlers all run the bridge, `contraagent plugin hook --agent
agy --root <plugin>`. The bridge reads the event on stdin, runs the commands the plugin's
`agy/hooks.json` declares for it and answers in agy's terms (`plugins.hooks.run_agy_hook`).

A hook's words reach the agent in two ways agy's stream does not show, so the bridge keeps
them in a directory of the launch (`STATE_ENV`): each objection of a stop hook, which the
launch's result reports (`LaunchResult.hook_errors`), and each objection of a `post_tool`
hook until the next `PreInvocation` hands it to the model (agy takes no words from a
`PostToolUse` hook).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

#: Where a plugin's hooks are, rendered for agy (`contraagent plugin render`).
HOOKS_FILE = "agy/hooks.json"
#: The variable that names the launch's hook state directory, for the bridge.
STATE_ENV = "CONTRAAGENT_AGY_HOOK_STATE"
#: The objections of the stop hooks, one JSON text per line, in the state directory.
OBJECTIONS = "objections.jsonl"
#: The objections of `post_tool` hooks the model has not been given yet.
PENDING = "pending.txt"
#: A handler's time limit in seconds: agy's own is 30, less than an output check may take.
TIMEOUT_S = 600
#: agy's events a plugin's hooks run at, by Claude Code's event; `PreInvocation` hands a
#: `post_tool` hook's objection to the model.
EVENTS = ("PreToolUse", "PostToolUse", "Stop")


def declared(plugin_dir: str | Path) -> dict[str, list[dict]]:
    """The hook groups a plugin's `agy/hooks.json` declares, by event; empty when the file
    is missing or holds none."""
    try:
        hooks = json.loads((Path(plugin_dir) / HOOKS_FILE).read_text(encoding="utf-8")).get("hooks") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(hooks, dict):
        return {}
    found = {event: groups for event, groups in hooks.items() if event in EVENTS and isinstance(groups, list)}
    return {event: [g for g in groups if isinstance(g, dict)] for event, groups in found.items()}


def command_line(args: list[str]) -> str:
    """`args` as one command line of the shell agy runs a hook under (`sh -c`; `cmd /c` on Windows)."""
    return subprocess.list2cmdline(args) if sys.platform == "win32" else shlex.join(args)


def native_hooks(plugin_dirs: tuple[str, ...] | list[str], python: str) -> dict[str, dict]:
    """The launch's `hooks.json`, in agy's format: for each plugin with rendered hooks, a
    named hook that runs the bridge (`python -m contraagent plugin hook --agent agy`) at
    each event the plugin has a hook for. Empty when no plugin has one."""
    out: dict[str, dict] = {}
    for n, plug in enumerate(plugin_dirs):
        root = Path(plug).resolve()
        events = declared(root)
        if not any(events.values()):
            continue
        handler = {
            "type": "command",
            "command": command_line([python, "-m", "contraagent", "plugin", "hook", "--agent", "agy", "--root", str(root)]),
            "timeout": TIMEOUT_S,
        }
        hook: dict = {}
        for event in ("PreToolUse", "PostToolUse"):
            if events.get(event):
                hook[event] = [{"matcher": "*", "hooks": [handler]}]
        if events.get("PostToolUse"):
            hook["PreInvocation"] = [handler]
        if events.get("Stop"):
            hook["Stop"] = [handler]
        out[f"contraagent-{n}-{root.name}"] = hook
    return out


def state_dir(env: dict[str, str] | None = None) -> Path | None:
    """The launch's hook state directory (`STATE_ENV`), when the hook runs in a launch of contraagent."""
    path = (os.environ if env is None else env).get(STATE_ENV, "")
    return Path(path) if path else None


def note_objection(state: Path | None, said: str) -> None:
    """Record one objection of a stop hook, for the launch's result. Never raises."""
    if state is None:
        return
    try:
        with open(state / OBJECTIONS, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(said, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_objections(state: Path) -> list[str]:
    """Every objection the stop hooks made in the launch, in order."""
    try:
        lines = (state / OBJECTIONS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            said = json.loads(line)
        except ValueError:
            continue
        if isinstance(said, str) and said:
            out.append(said)
    return out


def hold(state: Path | None, said: str) -> None:
    """Keep a `post_tool` hook's objection until the model is called next (`take`). Never raises."""
    if state is None:
        return
    try:
        with open(state / PENDING, "a", encoding="utf-8", newline="\n") as f:
            f.write(said.rstrip("\n") + "\n")
    except OSError:
        pass


def take(state: Path | None) -> str:
    """The objections held since the model was called last, removed; '' when there are none."""
    if state is None:
        return ""
    held = state / PENDING
    taken = state / f"{PENDING}.{os.getpid()}"
    try:
        os.replace(held, taken)  # a hook that objects meanwhile starts a new file
        text = taken.read_text(encoding="utf-8")
        taken.unlink()
    except OSError:
        return ""
    return text.strip()
