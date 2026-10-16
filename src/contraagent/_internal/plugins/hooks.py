"""Plugin hooks: declared once in `hooks.toml`, rendered into each coding agent's own hook system.

A task's behaviour includes hooks: a script that gates a tool call, one that
reacts to a result, a check when the agent is about to stop. Each coding agent
wires hooks its own way (Claude Code in `hooks/hooks.json`, Codex in its own
`hooks.json`, omp and pi each in a TypeScript extension, opencode in a JavaScript
plugin), so written by hand they
exist once per agent and drift. A plugin declares
them once, agent-neutrally, in `hooks.toml`:

    [[hooks]]
    on = "stop"
    run = "validate"            # the call file's output check, inside the session

    [[hooks]]
    on = "pre_tool"
    tool = "bash"
    match = "rm -rf"
    script = "hooks/pre-tool-use.sh"

and `contraagent plugin render` (`write`) writes what each agent needs, so the
hooks run *inside* the coding agent, on its own machinery. The scripts stay
neutral: they read the JSON Claude Code sends hooks on stdin
(`{"tool_name": "Bash", "tool_input": {"command": ...}}`); the omp and pi
extensions, the opencode plugin and the Codex bridge (`run_codex_hook`) build the
same payload, so one script serves every agent. A `pre_tool` script blocks by
exiting 2 with the reason on stderr.

What each agent can do differs, and the difference is recorded rather than
hidden (`render` returns notes, `lint` shows them):

    event      claude (hooks/hooks.json)  omp (omp/index.ts), pi (pi/index.ts)  opencode (opencode/index.js)
    pre_tool   PreToolUse hook            `tool_call` event, `{block, reason}`  `tool.execute.before`, throws the reason
    post_tool  PostToolUse hook           `tool_result` event: exit 2 adds the  `tool.execute.after`: exit 2 adds the
                                          message to the result the agent sees  message to the tool's output
    stop       Stop hook (continues)      omp: `session_stop` event, the hooks  none: `opencode run` ends once the
                                          of `omp/hooks.json`; `{decision:      session is idle.
                                          "block", reason}` continues the
                                          session. pi: none, `pi -p` does not
                                          continue a session.
               For pi and opencode, the runner's own contract check resumes the session instead.

    Codex (codex/hooks.json, Codex's own format, passed as config by the Codex backend):
    `PreToolUse`, `PostToolUse` and `Stop` hooks with Claude Code's semantics (exit 2
    blocks, sends the words back, continues the session). A shell command reaches the
    script as `Bash`; a file change (`apply_patch`) as `Write` or `Edit` per file. Codex
    has no read, grep or glob tool: a hook for one does not run there.

A script reads the tool input in Claude Code's shape on every agent: each agent's
argument names are renamed to Claude Code's (`TOOL_ARGS`: opencode's `filePath`,
omp's and pi's `path` of read, write and edit become `file_path`; pi's one-edit
`edits` becomes `old_string` and `new_string`). A file path is absolute, as Claude Code
always passes it: omp, pi and opencode pass on the path the model wrote, which may be
relative to the session's directory (`notes/a.md`), so each bridge resolves `PATH_ARGS`
against that directory (and `~` against the home directory).

A new coding agent registers a renderer with `register_renderer`.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from contraagent._internal.backends.codex.hooks import HOOKS_FILE as CODEX_HOOKS_FILE
from contraagent._internal.backends.omp.backend import HOOKS_FILE as OMP_HOOKS_FILE
from contraagent._internal.platform.commands import commands

if TYPE_CHECKING:
    from contraagent._internal.plugins.plugin import Plugin

EVENTS = ("stop", "pre_tool", "post_tool")
CLAUDE_TOOL = {"bash": "Bash", "read": "Read", "write": "Write", "edit": "Edit", "grep": "Grep", "glob": "Glob"}
#: Each coding agent's tool argument names as Claude Code's, by the agent's tool name:
#: what a hook script reads in `tool_input` (checked against omp 18.3's, pi 1.2.0's and
#: opencode 1.19.0's tool schemas). Arguments not named keep their names: `command`,
#: `pattern`, `content` and the `path` of a search are already Claude Code's.
TOOL_ARGS: dict[str, dict[str, dict[str, str]]] = {
    "omp": {tool: {"path": "file_path"} for tool in ("read", "write", "edit")},
    "pi": {tool: {"path": "file_path"} for tool in ("read", "write", "edit")},
    "opencode": {
        "read": {"filePath": "file_path"},
        "write": {"filePath": "file_path"},
        "edit": {"filePath": "file_path", "oldString": "old_string", "newString": "new_string", "replaceAll": "replace_all"},
    },
}
#: pi's `edit` takes `edits: [{oldText, newText}]`: one edit reads as Claude Code's
#: `old_string` and `new_string` (several stay in `edits`).
EDIT_ENTRY_ARGS = {"pi": {"oldText": "old_string", "newText": "new_string"}}
#: The arguments, under Claude Code's names, that Claude Code always passes as absolute paths.
PATH_ARGS = ("file_path", "notebook_path")
#: What a `post_tool` hook's exit 2 adds to the tool's result, before the script's words.
FEEDBACK = "A task hook objected to this call (exit 2):\\n"
#: What the built-in `{"on": "stop", "run": "validate"}` runs.
STOP_VALIDATE = '"${CONTRAAGENT_PYTHON:-python3}" -m contraagent call validate'

Rendered = tuple[dict[str, str], list[str]]  # ({relative path: content}, notes)
Renderer = Callable[["Plugin"], Rendered]
RENDERERS: dict[str, Renderer] = {}
#: The files each agent's renderer writes, relative to the plugin: those it writes for any
#: hook, and those it writes only for a `pre_tool` or `post_tool` hook.
RENDERED_FILES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}


def register_renderer(agent: str, fn: Renderer, files: tuple[str, ...] = (), tool_files: tuple[str, ...] = ()) -> None:
    """Teach `contraagent plugin render` a coding agent's native hook wiring. `files` and
    `tool_files` name what `fn` writes (`RENDERED_FILES`)."""
    RENDERERS[agent] = fn
    RENDERED_FILES[agent] = (files, tool_files)


def hook_errors(hooks) -> list[str]:
    """What is wrong with the `hooks` declarations of a `hooks.toml`. Empty when nothing is."""
    errs = []
    for i, h in enumerate(hooks):
        where = f"hooks.toml hooks[{i}]"
        if not isinstance(h, dict) or h.get("on") not in EVENTS:
            errs.append(f"{where}: 'on' must be one of {', '.join(EVENTS)}")
            continue
        if h["on"] == "stop":
            if h.get("run") != "validate" and not h.get("script"):
                errs.append(f'{where}: a stop hook needs run="validate" or a script')
        elif not h.get("script"):
            errs.append(f"{where}: {h['on']} hook needs a script")
    return errs


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def render_claude(plugin: Plugin) -> Rendered:
    """Hooks into the plugin's own `hooks/hooks.json`.

    Not into `settings.json`: `${CLAUDE_PLUGIN_ROOT}`, which the hook commands need to find
    their scripts, is defined for a plugin's hooks and not for hooks passed with `--settings`
    (checked by running `claude -p` both ways: the settings variant never ran). Permissions
    stay in `settings.json`; a `hooks` key left there by an earlier render is removed.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for h in plugin.hooks:
        if h["on"] == "stop":
            groups.setdefault(("Stop", ""), []).append({"type": "command", "command": stop_command(h)})
        else:
            event = "PreToolUse" if h["on"] == "pre_tool" else "PostToolUse"
            matcher = CLAUDE_TOOL.get(h.get("tool", ""), h.get("tool") or ".*")
            groups.setdefault((event, matcher), []).append({"type": "command", "command": f"${{CLAUDE_PLUGIN_ROOT}}/{h['script']}"})
    hooks: dict[str, list] = {}
    for (event, matcher), cmds in groups.items():
        entry = {"hooks": cmds}
        if matcher:
            entry = {"matcher": matcher, **entry}
        hooks.setdefault(event, []).append(entry)
    files: dict[str, str] = {}
    if hooks:
        files["hooks/hooks.json"] = json.dumps({"hooks": hooks}, indent=2) + "\n"
    settings = _read_json(plugin.root / "settings.json")
    if "hooks" in settings:
        settings.pop("hooks")
        files["settings.json"] = json.dumps(settings, indent=2) + "\n"
    return files, []


_EXTENSION_TEMPLATE = """// Generated by `contraagent plugin render` from hooks.toml. Do not edit by hand:
// change hooks.toml and render again. The hook scripts are the same ones Claude Code runs; this
// file only translates __AGENT__'s events into the JSON those scripts read on stdin.
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
__IMPORT__

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CLAUDE_TOOL: Record<string, string> = __CLAUDE_TOOL__;
const HOOK_TOOL: Record<string, string> = __HOOK_TOOL__;
const ARGS: Record<string, Record<string, string>> = __ARGS__;
const EDIT_ENTRY: Record<string, string> = __EDIT_ENTRY__;
const PATHS: string[] = __PATHS__;
const PRE = __PRE__;
const POST = __POST__;

type Hook = { tool?: string; match?: string; script: string };
type Input = Record<string, unknown>;

// A path as Claude Code passes it: absolute, a relative one taken from the session's directory.
function absolute(path: string, cwd: string): string {
  if (path === "~" || path.startsWith("~/")) return join(homedir(), path.slice(1));
  return resolve(cwd, path);
}

// The tool's arguments under Claude Code's names, as a hook script reads them.
function claudeInput(toolName: string, input: unknown, cwd: string): Input {
  const out: Input = { ...((input ?? {}) as Input) };
  for (const [from, to] of Object.entries(ARGS[toolName] ?? {})) {
    if (from in out && !(to in out)) {
      out[to] = out[from];
      delete out[from];
    }
  }
  const edits = out.edits;
  if (Array.isArray(edits) && edits.length === 1 && typeof edits[0] === "object" && edits[0] !== null) {
    for (const [from, to] of Object.entries(EDIT_ENTRY)) {
      if (from in (edits[0] as Input)) out[to] = (edits[0] as Input)[from];
    }
  }
  for (const key of PATHS) {
    if (typeof out[key] === "string" && out[key]) out[key] = absolute(out[key] as string, cwd);
  }
  return out;
}

function applies(h: Hook, toolName: string, input: Input): boolean {
  if (h.tool && (HOOK_TOOL[h.tool] ?? h.tool) !== (CLAUDE_TOOL[toolName] ?? toolName)) return false;
  return !h.match || String(input.command ?? "").includes(h.match);
}

function run(h: Hook, toolName: string, input: Input, cwd: string) {
  return spawnSync(process.env.CONTRAAGENT_BASH || "bash", [join(ROOT, h.script)], {
    cwd,
    encoding: "utf8",
    input: JSON.stringify({ tool_name: CLAUDE_TOOL[toolName] ?? toolName, tool_input: input }),
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: cwd },
  });
}
__HELPERS__
export default function (pi: __API__): void {
  if (PRE.length) {
    pi.on("tool_call", async (event, ctx) => {
      const input = claudeInput(event.toolName, event.input, ctx.cwd);
      for (const h of PRE as Hook[]) {
        if (!applies(h, event.toolName, input)) continue;
        const r = run(h, event.toolName, input, ctx.cwd);
        // exit 2 blocks the call and the agent sees the reason, as with Claude Code
        if (r.status === 2) return { block: true, reason: (r.stderr || "blocked by a task hook").trim() };
      }
    });
  }
  if (POST.length) {
    pi.on("tool_result", async (event, ctx) => {
      if (event.isError) return;
      const input = claudeInput(event.toolName, event.input, ctx.cwd);
      const said: string[] = [];
      for (const h of POST as Hook[]) {
        if (!applies(h, event.toolName, input)) continue;
        try {
          const r = run(h, event.toolName, input, ctx.cwd);
          // exit 2: what the script says goes back to the agent with the result, as with Claude Code
          if (r.status === 2) said.push((r.stderr || r.stdout || "").trim() || "a task hook objected");
        } catch {
          // fail-open: a hook crash never blocks the pipeline
        }
      }
      if (said.length) return { content: [...event.content, { type: "text", text: `__FEEDBACK__${said.join("\\n")}` }] };
    });
  }__STOP__
}
"""

#: The omp extension's stop hooks: the commands of the plugin's `omp/hooks.json` (in Claude
#: Code's format) run at omp's `session_stop`, with the JSON Claude Code sends a Stop hook;
#: the first that exits 2 blocks the stop, and omp continues the session with its words.
_OMP_STOP = """
  const STOP = stopCommands();
  if (STOP.length) {
    pi.on("session_stop", async (event, ctx) => {
      const input = JSON.stringify({
        hook_event_name: "Stop",
        session_id: event.session_id,
        transcript_path: event.session_file ?? "",
        cwd: ctx.cwd,
        stop_hook_active: Boolean(event.stop_hook_active),
      });
      for (const command of STOP) {
        const r = spawnSync(process.env.CONTRAAGENT_BASH || "bash", ["-c", command], {
          cwd: ctx.cwd,
          encoding: "utf8",
          input,
          env: { ...process.env, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: ctx.cwd },
        });
        // exit 2: the agent goes on in the same session with what the hook said, as with Claude Code
        if (r.status === 2) return { decision: "block", reason: (r.stderr || "a stop hook objected").trim() };
      }
    });
  }"""

#: What the omp extension reads its stop hooks with.
_OMP_STOP_READER = """
// The commands of the Stop hooks in `omp/hooks.json`, in the order Claude Code runs them.
function stopCommands(): string[] {
  try {
    const declared = JSON.parse(readFileSync(join(ROOT, "__STOP_FILE__"), "utf8"));
    const groups: { hooks?: { command?: unknown }[] }[] = declared?.hooks?.Stop ?? [];
    return groups.flatMap(g => g.hooks ?? []).map(h => h.command).filter((c): c is string => typeof c === "string");
  } catch {
    return [];
  }
}
"""


def stop_command(hook: dict) -> str:
    """The command a `stop` hook runs, as Claude Code's `hooks/hooks.json` writes it."""
    return STOP_VALIDATE if hook.get("run") == "validate" else f"${{CLAUDE_PLUGIN_ROOT}}/{hook['script']}"


def render_omp(plugin: Plugin) -> Rendered:
    """`package.json` (`omp.extensions`), `omp/index.ts` and `omp/hooks.json`, when the plugin
    declares a hook. The extension runs the tool hooks at omp's `tool_call` and `tool_result`
    and the stop hooks of `omp/hooks.json` at its `session_stop`, which continues the session
    when one exits 2 (checked against omp 18.9.1, in `omp -p` and over RPC)."""
    pre = [h for h in plugin.hooks if h["on"] == "pre_tool"]
    post = [h for h in plugin.hooks if h["on"] == "post_tool"]
    stop = [stop_command(h) for h in plugin.hooks if h["on"] == "stop"]
    pkg = _read_json(plugin.root / "package.json") or {"name": plugin.name, "version": "0.1.0"}
    files: dict[str, str] = {}
    if pre or post or stop:
        files["omp/index.ts"] = _extension("omp", OMP_HOOK_API, OMP_CLAUDE_TOOL, pre, post, stop_file=OMP_HOOKS_FILE)
        declared = {"Stop": [{"hooks": [{"type": "command", "command": c} for c in stop]}]} if stop else {}
        files[OMP_HOOKS_FILE] = json.dumps({"hooks": declared}, indent=2) + "\n"
        pkg["omp"] = {"extensions": ["./omp/index.ts"]}
    else:
        pkg.pop("omp", None)
    files["package.json"] = json.dumps(pkg, indent=2) + "\n"
    return files, []


def render_pi(plugin: Plugin) -> Rendered:
    """`package.json` (`pi.extensions`) and `pi/index.ts`, when there is a tool hook to translate.

    pi's extension API is the one omp's was forked from: the same `tool_call` and
    `tool_result` events, the same `{block, reason}` (checked against pi 1.2.0's
    `ExtensionAPI` types)."""
    notes: list[str] = []
    pre = [h for h in plugin.hooks if h["on"] == "pre_tool"]
    post = [h for h in plugin.hooks if h["on"] == "post_tool"]
    if any(h["on"] == "stop" for h in plugin.hooks):
        notes.append(
            "pi: a stop hook cannot continue a session in `pi -p`; the runner's contract check "
            "(run_until_valid, which resumes the session) does the same job"
        )
    pkg = _read_json(plugin.root / "package.json") or {"name": plugin.name, "version": "0.1.0"}
    files: dict[str, str] = {}
    if pre or post:
        files["pi/index.ts"] = _extension("pi", PI_HOOK_API, PI_CLAUDE_TOOL, pre, post)
        pkg["pi"] = {"extensions": ["./pi/index.ts"]}
    else:
        pkg.pop("pi", None)
    files["package.json"] = json.dumps(pkg, indent=2) + "\n"
    return files, notes


#: The type of the object an extension's factory receives, per coding agent.
OMP_HOOK_API = ("HookAPI", 'import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";')
PI_HOOK_API = ("ExtensionAPI", 'import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";')
#: pi's built-in tools as Claude Code names them (`find` searches by glob pattern).
PI_CLAUDE_TOOL = {**CLAUDE_TOOL, "find": "Glob", "ls": "LS"}
#: omp's: its `find` lists files by glob pattern too.
OMP_CLAUDE_TOOL = {**CLAUDE_TOOL, "find": "Glob"}


def _extension(agent: str, api: tuple[str, str], tools: dict[str, str], pre: list[dict], post: list[dict], stop_file: str = "") -> str:
    """The extension that runs the plugin's tool hooks inside omp or pi, and with `stop_file`
    (omp) the stop hooks that file declares."""

    def view(hs):
        return json.dumps([{k: h[k] for k in ("tool", "match", "script") if h.get(k)} for h in hs], indent=2)

    imports = api[1] + ('\nimport { readFileSync } from "node:fs";' if stop_file else "")
    return (
        _EXTENSION_TEMPLATE.replace("__IMPORT__", imports)
        .replace("__HELPERS__", _OMP_STOP_READER.replace("__STOP_FILE__", stop_file) if stop_file else "")
        .replace("__STOP__", _OMP_STOP if stop_file else "")
        .replace("__API__", api[0])
        .replace("__AGENT__", agent)
        .replace("__CLAUDE_TOOL__", json.dumps(tools))
        .replace("__HOOK_TOOL__", json.dumps(CLAUDE_TOOL))
        .replace("__ARGS__", json.dumps(TOOL_ARGS[agent]))
        .replace("__EDIT_ENTRY__", json.dumps(EDIT_ENTRY_ARGS.get(agent, {})))
        .replace("__PATHS__", json.dumps(PATH_ARGS))
        .replace("__FEEDBACK__", FEEDBACK)
        .replace("__PRE__", view(pre))
        .replace("__POST__", view(post))
    )


_OPENCODE_TEMPLATE = """// Generated by `contraagent plugin render` from hooks.toml. Do not edit by hand:
// change hooks.toml and render again. The hook scripts are the same ones Claude Code runs; this
// file only translates opencode's tool events into the JSON those scripts read on stdin.
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CLAUDE_TOOL = __CLAUDE_TOOL__;
const HOOK_TOOL = __HOOK_TOOL__;
const ARGS = __ARGS__;
const PATHS = __PATHS__;
const PRE = __PRE__;
const POST = __POST__;

// A path as Claude Code passes it: absolute, a relative one taken from the session's directory.
function absolute(path, cwd) {
  if (path === "~" || path.startsWith("~/")) return join(homedir(), path.slice(1));
  return resolve(cwd, path);
}

// The tool's arguments under Claude Code's names, as a hook script reads them.
function claudeInput(tool, args, cwd) {
  const out = { ...(args ?? {}) };
  for (const [from, to] of Object.entries(ARGS[tool] ?? {})) {
    if (from in out && !(to in out)) {
      out[to] = out[from];
      delete out[from];
    }
  }
  for (const key of PATHS) {
    if (typeof out[key] === "string" && out[key]) out[key] = absolute(out[key], cwd);
  }
  return out;
}

function applies(h, tool, input) {
  if (h.tool && (HOOK_TOOL[h.tool] ?? h.tool) !== (CLAUDE_TOOL[tool] ?? tool)) return false;
  return !h.match || String(input.command ?? "").includes(h.match);
}

function run(h, tool, input, cwd) {
  return spawnSync(process.env.CONTRAAGENT_BASH || "bash", [join(ROOT, h.script)], {
    cwd,
    encoding: "utf8",
    input: JSON.stringify({ tool_name: CLAUDE_TOOL[tool] ?? tool, tool_input: input }),
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: cwd },
  });
}

export const ContraagentHooks = async ({ directory }) => ({
  "tool.execute.before": async (input, output) => {
    const args = claudeInput(input.tool, output.args, directory);
    for (const h of PRE) {
      if (!applies(h, input.tool, args)) continue;
      const r = run(h, input.tool, args, directory);
      // exit 2 blocks the call and the agent sees the reason, as with Claude Code
      if (r.status === 2) throw new Error((r.stderr || "blocked by a task hook").trim());
    }
  },
  "tool.execute.after": async (input, output) => {
    const args = claudeInput(input.tool, input.args, directory);
    const said = [];
    for (const h of POST) {
      if (!applies(h, input.tool, args)) continue;
      try {
        const r = run(h, input.tool, args, directory);
        // exit 2: what the script says goes back to the agent with the output, as with Claude Code
        if (r.status === 2) said.push((r.stderr || r.stdout || "").trim() || "a task hook objected");
      } catch {
        // fail-open: a hook crash never blocks the pipeline
      }
    }
    // opencode hands the agent this same object: the words go after the tool's own output
    if (said.length && output) output.output = `${output.output ?? ""}\\n\\n__FEEDBACK__${said.join("\\n")}`;
  },
});
"""


def render_opencode(plugin: Plugin) -> Rendered:
    """`opencode/index.js`, an opencode plugin, when there is a tool hook to translate. The
    opencode backend loads it into every launch of a task of this plugin."""
    notes: list[str] = []
    pre = [h for h in plugin.hooks if h["on"] == "pre_tool"]
    post = [h for h in plugin.hooks if h["on"] == "post_tool"]
    if any(h["on"] == "stop" for h in plugin.hooks):
        notes.append(
            "opencode: a stop hook cannot continue a session in `opencode run`; the runner's contract check "
            "(run_until_valid, which resumes the session) does the same job"
        )
    if not (pre or post):
        return {}, notes

    def view(hs):
        return json.dumps([{k: h[k] for k in ("tool", "match", "script") if h.get(k)} for h in hs], indent=2)

    text = (
        _OPENCODE_TEMPLATE.replace("__CLAUDE_TOOL__", json.dumps(CLAUDE_TOOL))
        .replace("__HOOK_TOOL__", json.dumps(CLAUDE_TOOL))
        .replace("__ARGS__", json.dumps(TOOL_ARGS["opencode"]))
        .replace("__PATHS__", json.dumps(PATH_ARGS))
        .replace("__FEEDBACK__", FEEDBACK)
    )
    return {"opencode/index.js": text.replace("__PRE__", view(pre)).replace("__POST__", view(post))}, notes


#: Codex's tools, as its hooks name them (`tool_name`), for each tool `hooks.toml` names:
#: shell commands are `Bash`; a file written or edited goes through `apply_patch`. Codex has
#: no tool that only reads or searches: it reads and searches with shell commands.
CODEX_MATCHER = {"bash": "Bash", "write": "apply_patch", "edit": "apply_patch"}
#: What a Codex hook with a script runs: the bridge that hands the script Claude Code's input.
CODEX_BRIDGE = '"${CONTRAAGENT_PYTHON:-python3}" -m contraagent plugin hook --agent codex --root "${CLAUDE_PLUGIN_ROOT}"'


def render_codex(plugin: Plugin) -> Rendered:
    """`codex/hooks.json`, in Codex's own hook format. The Codex backend passes it into every
    launch of a task of this plugin as config, trusted (`backends.codex.hooks`).

    Codex sends its hooks Claude Code's input with its own tool names: a shell command is
    `Bash` with `command`, as on Claude Code; a file change is `apply_patch` with the patch as
    `command`. So a hook with a script runs through `contraagent plugin hook --agent codex`
    (`run_codex_hook`), which hands the script Claude Code's `Write` or `Edit` for each file
    the patch adds or updates. The stop hook runs as on Claude Code: Codex continues the
    session with what it says (checked against codex-cli 0.162.1)."""
    notes: list[str] = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for h in plugin.hooks:
        if h["on"] == "stop":
            cmd = STOP_VALIDATE if h.get("run") == "validate" else f"{CODEX_BRIDGE} {shlex.quote(h['script'])}"
            groups.setdefault(("Stop", ""), []).append({"type": "command", "command": cmd})
            continue
        tool = h.get("tool", "")
        if tool and tool not in CODEX_MATCHER:
            notes.append(f"codex: no {tool} tool (it reads and searches with shell commands): {h['script']} does not run there")
            continue
        args = [f"--tool {shlex.quote(tool)}"] if tool else []
        if h.get("match"):
            args.append(f"--match {shlex.quote(str(h['match']))}")
        event = "PreToolUse" if h["on"] == "pre_tool" else "PostToolUse"
        cmd = " ".join([CODEX_BRIDGE, *args, shlex.quote(h["script"])])
        groups.setdefault((event, CODEX_MATCHER.get(tool, "")), []).append({"type": "command", "command": cmd})
    if not groups:
        return {}, notes
    hooks: dict[str, list] = {}
    for (event, matcher), cmds in groups.items():
        hooks.setdefault(event, []).append({"matcher": matcher, "hooks": cmds} if matcher else {"hooks": cmds})
    return {CODEX_HOOKS_FILE: json.dumps({"hooks": hooks}, indent=2) + "\n"}, notes


#: An `apply_patch` patch's file operations (`*** Add File: <path>` and the others).
_PATCH_OP_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$")
_PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to: (.+)$")


def patch_inputs(patch: str, cwd: str) -> list[tuple[str, dict]]:
    """The Claude Code tool calls an `apply_patch` patch amounts to: `Write` with `file_path`
    and `content` for a file it adds; `Edit` with `file_path` (the path it moves the file to,
    when it moves it) for one it updates, and with `old_string` and `new_string` when the
    update is one hunk. A file it deletes has no Claude Code call. Paths are absolute,
    a relative one taken from `cwd`."""
    calls: list[tuple[str, dict]] = []
    op: list | None = None  # [kind, path, body lines]
    for line in patch.splitlines():
        found = _PATCH_OP_RE.match(line)
        if found or line.startswith("*** End Patch"):
            if op is not None:
                calls += _patch_call(op, cwd)
            op = [found.group(1), found.group(2).strip(), []] if found else None
        elif op is not None and (moved := _PATCH_MOVE_RE.match(line)):
            op[1] = moved.group(1).strip()
        elif op is not None:
            op[2].append(line)
    if op is not None:
        calls += _patch_call(op, cwd)
    return calls


def _patch_call(op: list, cwd: str) -> list[tuple[str, dict]]:
    kind, path, lines = op
    # os.path, not pathlib: `abspath` folds `..` without following a link.
    file_path = os.path.abspath(os.path.join(cwd, os.path.expanduser(path)))
    if kind == "Add":
        return [("Write", {"file_path": file_path, "content": "".join(f"{x[1:]}\n" for x in lines if x.startswith("+"))})]
    if kind == "Delete":
        return []
    hunks: list[list[str]] = [[]]
    for x in lines:
        if x.startswith("@@"):
            hunks.append([])
        elif x[:1] in (" ", "-", "+"):
            hunks[-1].append(x)
    hunks = [h for h in hunks if any(x[:1] in ("-", "+") for x in h)]
    tool_input: dict = {"file_path": file_path}
    if len(hunks) == 1:
        tool_input["old_string"] = "\n".join(x[1:] for x in hunks[0] if x[:1] != "+")
        tool_input["new_string"] = "\n".join(x[1:] for x in hunks[0] if x[:1] != "-")
    return [("Edit", tool_input)]


def codex_inputs(payload: dict) -> list[tuple[str, dict]]:
    """The tool calls, under Claude Code's names and in its shapes, of the input a Codex tool
    hook got: an `apply_patch` as one call per file (`patch_inputs`), any other tool as it is
    (a shell command is already Claude Code's `Bash` with `command`)."""
    name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if name == "apply_patch" and isinstance(tool_input, dict):
        return patch_inputs(str(tool_input.get("command") or ""), str(payload.get("cwd") or os.getcwd()))
    return [(name, tool_input if isinstance(tool_input, dict) else {})]


def run_codex_hook(stdin_text: str, root: str | Path, script: str, tool: str = "", match: str = "") -> tuple[int, str, str]:
    """What a Codex hook with a script runs (`contraagent plugin hook --agent codex`): the
    script, once for each tool call of the input (`codex_inputs`) that `tool` and `match`
    select, or once for any other event, with the input on stdin in Claude Code's shape, in
    the session's directory, with `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PROJECT_DIR` set as Claude
    Code sets them. Returns (exit code, stdout, stderr): 2 and the reasons when a run exits
    2 (a `pre_tool` hook stops at the first), else the first other failure's code and words,
    else 0; stdout is the script's when it ran once."""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    event = payload.get("hook_event_name")
    cwd = str(payload.get("cwd") or os.getcwd())
    root = Path(root)
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PROJECT_DIR": cwd}
    runs = [payload]
    if event in ("PreToolUse", "PostToolUse"):
        runs = [
            {**payload, "tool_name": name, "tool_input": tool_input}
            for name, tool_input in codex_inputs(payload)
            if (not tool or CLAUDE_TOOL.get(tool, tool) == name) and (not match or match in str(tool_input.get("command") or ""))
        ]
    objections: list[str] = []
    failure: tuple[int, str] | None = None
    outs: list[str] = []
    for run in runs:
        proc = subprocess.run(
            [commands.bash() or "bash", str(root / script)],
            input=json.dumps(run),
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        outs.append(proc.stdout)
        if proc.returncode == 2:
            objections.append(proc.stderr.strip() or "a task hook objected")
            if event == "PreToolUse":
                break
        elif proc.returncode != 0 and failure is None:
            failure = (proc.returncode, proc.stderr.strip())
    stdout = outs[0] if len(outs) == 1 else ""
    if objections:
        return 2, stdout, "\n".join(objections)
    if failure is not None:
        return failure[0], stdout, failure[1]
    return 0, stdout, ""


register_renderer("claude", render_claude, files=("hooks/hooks.json",))
register_renderer("codex", render_codex, files=(CODEX_HOOKS_FILE,))
register_renderer("omp", render_omp, files=("package.json", "omp/index.ts", OMP_HOOKS_FILE))
register_renderer("opencode", render_opencode, tool_files=("opencode/index.js",))
register_renderer("pi", render_pi, files=("package.json",), tool_files=("pi/index.ts",))


def render(plugin: Plugin, agents=None) -> Rendered:
    """Every agent's hook files for `plugin` (`agents`: default the plugin's own, else all)."""
    files: dict[str, str] = {}
    notes: list[str] = []
    if plugin.skills_only or plugin.render_leftovers():
        return files, [f"{plugin.name} is a skill plugin: it declares no hooks, so nothing is rendered"]
    found = _read_json(plugin.root / "package.json")
    for agent in agents or plugin.agents or sorted(RENDERERS):
        f, n = RENDERERS[agent](plugin)
        for rel, text in f.items():
            # omp and pi each declare their extension in the one `package.json`: each
            # renderer's own changes to the file as found apply over the ones before it.
            if rel == "package.json" and rel in files:
                text = _merged(found, json.loads(files[rel]), json.loads(text))
            files[rel] = text
        notes += n
    return files, notes


def _merged(found: dict, before: dict, mine: dict) -> str:
    """`before` with the keys `mine` changed from `found` set or removed, as JSON text."""
    out = dict(before)
    for k in {**found, **mine}:
        if k not in mine:
            out.pop(k, None)
        elif mine[k] != found.get(k):
            out[k] = mine[k]
    return json.dumps(out, indent=2) + "\n"


def stale(plugin: Plugin, agents=None) -> list[str]:
    """Files whose content differs from what the declaration renders to."""
    files, _ = render(plugin, agents)
    out = []
    for rel, text in files.items():
        p = plugin.root / rel
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            out.append(rel)
    return out


def write(plugin: Plugin, agents=None) -> tuple[list[Path], list[str]]:
    """Write the rendered files that changed. Returns (written paths, notes)."""
    files, notes = render(plugin, agents)
    written = []
    for rel, text in files.items():
        p = plugin.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")
            written.append(p)
    return written, notes
