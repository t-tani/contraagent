"""A plugin's hooks on Codex: its `codex/hooks.json` passed as config, trusted by hash.

`contraagent plugin render` writes `codex/hooks.json` in Codex's own hook format (Claude
Code's: `{"hooks": {"Stop": [{"matcher": ..., "hooks": [{"type": "command", "command":
...}]}]}}`). A launch passes it as one `-c hooks={...}` value: Codex reads hooks from each
config layer (`hooks.<Event>` in a `config.toml`, the `-c` values being the layer of the
session's flags), so nothing is written into a `CODEX_HOME`, the user's own included.

Codex runs a hook that is not managed by an administrator only when the config names it
trusted (checked against codex-cli 0.162.1, `codex-rs/hooks/src/engine/discovery.rs`):
`hooks.state."<key>".trusted_hash` equal to the hook's hash, where

- the key is `<source>:<event>:<group index>:<handler index>` (`hook_key` in
  `codex-rs/hooks/src/lib.rs`), the source of `-c` values being the synthetic path
  `/<session-flags>/config.toml` (`config_toml_source_path`), the event in snake case
  (`hook_event_key_label`: `pre_tool_use`, `post_tool_use`, `stop`);
- the hash is `sha256:` and the hex SHA-256 of a compact JSON with sorted keys
  (`version_for_toml`, `codex-rs/config/src/fingerprint.rs`) of the normalized hook
  (`hook_hash`): `event_name`, the group's `matcher` (none for `Stop`) and its one handler
  with its `timeout` filled in (600 seconds when unset) and `async`.

On Windows the key's source is `C:\\<session-flags>\\config.toml` (the same path, resolved
against `C:\\`), and Codex runs a hook's command under the session's shell, not `sh`:
PowerShell (`pwsh`, else Windows PowerShell) with `-NoProfile -Command`, cmd.exe only where
there is no PowerShell (`build_hooks_config` in `codex-rs/core/src/session/mod.rs`,
`default_user_shell` in `codex-rs/shell-command/src/shell_detect.rs`, `build_command` in
`codex-rs/hooks/src/engine/command_runner.rs`). A rendered command is a bash command line,
so there it is wrapped into a PowerShell one that runs it under the bash every hook script
runs under (`commands.bash`, the bash of Git for Windows; `windows_command`); the hash is
taken of the wrapped command, as Codex takes it. Without that bash, a plugin's hooks are not
passed at all.

The same `hooks.state` table of the session's flags turns the user's own hooks off: every
key the user's `config.toml` trusts gets `enabled = false` (Codex merges the states of the
user's layer and the flags' field by field, later wins). A hook nobody trusts never runs,
and with any credential but `ambient` the user's config is not read at all.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path

from contraagent._internal.platform.commands import commands

#: Where a plugin's hooks are, rendered for Codex (`contraagent plugin render`).
HOOKS_FILE = "codex/hooks.json"
#: The source Codex names the hooks of `-c` values by in a hook's key.
SESSION_FLAGS_SOURCE = "/<session-flags>/config.toml"
#: The same source on Windows (`synthetic_layer_path`, resolved against `C:\`).
WINDOWS_SESSION_FLAGS_SOURCE = "C:\\<session-flags>\\config.toml"
#: Whether Codex runs its hooks as on Windows (`windows_command`).
WINDOWS = sys.platform == "win32"
#: The variable a Windows hook hands its bash command line to bash in (`windows_command`).
COMMAND_VARIABLE = "CONTRAAGENT_HOOK"
#: What bash runs on Windows: the command line in `COMMAND_VARIABLE`, as `eval "$..."` would,
#: but written without a double quote, which Windows PowerShell does not pass on to a program
#: intact. With field splitting and globbing off, the variable expands to one word; both are
#: turned on again before the command line runs.
BASH_EVAL = f"IFS=;set -f;eval set +f\\;unset IFS\\;${COMMAND_VARIABLE}"
#: The characters PowerShell reads as a single quote; each is doubled inside a quoted string.
_PS_QUOTES = re.compile("(['\u2018\u2019\u201a\u201b])")
#: Codex's events, as `hooks.json` names them, by the name in a hook's key.
EVENT_KEYS = {
    "PreToolUse": "pre_tool_use",
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreCompact": "pre_compact",
    "PostCompact": "post_compact",
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "UserPromptSubmit": "user_prompt_submit",
    "SubagentStart": "subagent_start",
    "SubagentStop": "subagent_stop",
    "Stop": "stop",
    "Interrupt": "interrupt",
}
#: Events whose matcher Codex ignores (`matcher_pattern_for_event`): their hash has none.
NO_MATCHER = ("UserPromptSubmit", "Stop", "Interrupt")
#: A command hook's timeout when the config sets none (seconds).
DEFAULT_TIMEOUT_S = 600
#: The plugin's directory in a rendered command, as Claude Code names it.
PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"


def trusted_hash(event: str, matcher: str | None, handler: dict) -> str:
    """The `trusted_hash` Codex expects for one command `handler` (`command`, `timeout`) of a
    group of `event`: a synchronous hook with neither a status message nor a context limit."""
    normalized = {"type": "command", "command": handler["command"], "timeout": handler.get("timeout") or DEFAULT_TIMEOUT_S}
    normalized["async"] = False
    identity: dict = {"event_name": EVENT_KEYS[event], "hooks": [normalized]}
    if matcher is not None and event not in NO_MATCHER:
        identity["matcher"] = matcher
    text = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def powershell_quote(text: str) -> str:
    """`text` as a single-quoted PowerShell string, which PowerShell reads as it is."""
    return "'" + _PS_QUOTES.sub(r"\1\1", text) + "'"


def windows_command(command: str, bash: str) -> str:
    """The PowerShell command line that Codex runs on Windows for the bash command line
    `command`: `command` handed to `bash` in `COMMAND_VARIABLE` (an argument would lose its
    double quotes on the way through Windows PowerShell), and bash's exit status returned as
    its own (PowerShell returns 1 for any failure, while 2 is a hook's objection)."""
    return (
        f"$env:{COMMAND_VARIABLE}={powershell_quote(command)}; "
        f"& {powershell_quote(bash)} -c {powershell_quote(BASH_EVAL)}; exit $LASTEXITCODE"
    )


def session_flags_source() -> str:
    """The source Codex names the hooks of `-c` values by, on this OS."""
    return WINDOWS_SESSION_FLAGS_SOURCE if WINDOWS else SESSION_FLAGS_SOURCE


def plugin_hooks(plugin_dirs: tuple[str, ...] | list[str], home: str) -> dict[str, list[dict]]:
    """The rendered hooks of the launch's plugins, by Codex event, in order: each plugin's
    `${CLAUDE_PLUGIN_ROOT}` replaced by its directory (as Codex does for a plugin's own
    hooks), and each command run with the user's `HOME` (Codex itself runs with one of its own).
    On Windows each runs under the bash of Git for Windows (`windows_command`); without that
    bash there are none."""
    bash = commands.bash() if WINDOWS else None
    if WINDOWS and bash is None:
        return {}

    def render(command: str, root: Path) -> str:
        line = f"HOME={shlex.quote(home)} " + command.replace(PLUGIN_ROOT, str(root))
        return windows_command(line, bash) if bash is not None else line

    out: dict[str, list[dict]] = {}
    for plug in plugin_dirs:
        root = Path(plug).resolve()
        try:
            declared = json.loads((root / HOOKS_FILE).read_text(encoding="utf-8")).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for event, groups in declared.items():
            if event not in EVENT_KEYS or not isinstance(groups, list):
                continue
            for group in groups:
                handlers = [
                    {
                        "type": "command",
                        "command": render(str(h["command"]), root),
                        **({"timeout": h["timeout"]} if isinstance(h.get("timeout"), int) else {}),
                    }
                    for h in group.get("hooks") or []
                    if isinstance(h, dict) and h.get("type") == "command" and h.get("command")
                ]
                if handlers:
                    out.setdefault(event, []).append({**({"matcher": group["matcher"]} if group.get("matcher") else {}), "hooks": handlers})
    return out


def trusted_keys(user_config: Path | None) -> list[str]:
    """The hooks the user's `config.toml` names trusted (its `hooks.state` keys with a
    `trusted_hash`): the only ones of the user's that Codex would run."""
    if user_config is None:
        return []
    try:
        state = tomllib.loads(user_config.read_text(encoding="utf-8")).get("hooks", {}).get("state", {})
    except (OSError, ValueError, AttributeError):
        return []
    return sorted(k for k, v in state.items() if isinstance(v, dict) and v.get("trusted_hash")) if isinstance(state, dict) else []


def hooks_config(plugin_dirs: tuple[str, ...] | list[str], home: str, user_config: Path | None) -> dict | None:
    """The `hooks` table a launch passes as `-c hooks=...`: the plugins' hooks, each trusted
    by its hash, and the user's own trusted hooks turned off. None when the plugins have none."""
    events = plugin_hooks(plugin_dirs, home)
    if not events:
        return None
    state: dict[str, dict] = {key: {"enabled": False} for key in trusted_keys(user_config)}
    source = session_flags_source()
    for event, groups in events.items():
        for g, group in enumerate(groups):
            for h, handler in enumerate(group["hooks"]):
                key = f"{source}:{EVENT_KEYS[event]}:{g}:{h}"
                state[key] = {"enabled": True, "trusted_hash": trusted_hash(event, group.get("matcher"), handler)}
    return {**events, "state": state}
