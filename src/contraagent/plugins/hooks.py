"""Plugin hooks: declared once in `hooks.toml`, rendered into each coding agent's own hook system.

A task's behaviour includes hooks: a script that gates a tool call, one that
reacts to a result, a check when the agent is about to stop. Each coding agent
wires hooks its own way (Claude Code in `hooks/hooks.json`, omp in a TypeScript
extension), so written by hand they exist twice and drift. A plugin declares
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
(`{"tool_name": "Bash", "tool_input": {"command": ...}}`); the omp extension
builds the same payload, so one script serves both. A `pre_tool` script blocks
by exiting 2 with the reason on stderr.

What each agent can do differs, and the difference is recorded rather than
hidden (`render` returns notes, `lint` shows them):

    event      claude (hooks/hooks.json)  omp (omp/index.ts)
    pre_tool   PreToolUse hook            `tool_call` event, `{block, reason}`
    post_tool  PostToolUse hook           `tool_result` event
    stop       Stop hook (continues)      none: `omp -p` does not continue a session an
                                       extension resumes at `agent_end`. The runner's own
                                       contract check resumes the session instead.

A new coding agent registers a renderer with `register_renderer`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contraagent.plugins.plugin import Plugin

EVENTS = ("stop", "pre_tool", "post_tool")
CLAUDE_TOOL = {"bash": "Bash", "read": "Read", "write": "Write", "edit": "Edit", "grep": "Grep", "glob": "Glob"}
#: What the built-in `{"on": "stop", "run": "validate"}` runs.
STOP_VALIDATE = '"${CONTRAAGENT_PYTHON:-python3}" -m contraagent call validate'

Rendered = tuple[dict[str, str], list[str]]  # ({relative path: content}, notes)
Renderer = Callable[["Plugin"], Rendered]
RENDERERS: dict[str, Renderer] = {}


def register_renderer(agent: str, fn: Renderer) -> None:
    """Teach `contraagent plugin render` a coding agent's native hook wiring."""
    RENDERERS[agent] = fn


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
        data = json.loads(path.read_text())
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
            cmd = STOP_VALIDATE if h.get("run") == "validate" else f"${{CLAUDE_PLUGIN_ROOT}}/{h['script']}"
            groups.setdefault(("Stop", ""), []).append({"type": "command", "command": cmd})
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


_OMP_TEMPLATE = """// Generated by `contraagent plugin render` from hooks.toml. Do not edit by hand:
// change hooks.toml and render again. The hook scripts are the same ones Claude Code runs; this
// file only translates omp's events into the JSON those scripts read on stdin.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CLAUDE_TOOL: Record<string, string> = __CLAUDE_TOOL__;
const PRE = __PRE__;
const POST = __POST__;

type Hook = { tool?: string; match?: string; script: string };

function command(input: unknown): string {
  if (typeof input === "object" && input !== null && "command" in input) {
    return String((input as { command: unknown }).command);
  }
  return "";
}

function applies(h: Hook, toolName: string, input: unknown): boolean {
  if (h.tool && h.tool !== toolName) return false;
  return !h.match || command(input).includes(h.match);
}

function run(h: Hook, toolName: string, input: unknown, cwd: string) {
  return spawnSync("bash", [join(ROOT, h.script)], {
    cwd,
    encoding: "utf8",
    input: JSON.stringify({ tool_name: CLAUDE_TOOL[toolName] ?? toolName, tool_input: input }),
    env: { ...process.env, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: cwd },
  });
}

export default function (pi: HookAPI): void {
  if (PRE.length) {
    pi.on("tool_call", async (event, ctx) => {
      for (const h of PRE as Hook[]) {
        if (!applies(h, event.toolName, event.input)) continue;
        const r = run(h, event.toolName, event.input, ctx.cwd);
        // exit 2 blocks the call and the agent sees the reason, as with Claude Code
        if (r.status === 2) return { block: true, reason: (r.stderr || "blocked by a task hook").trim() };
      }
    });
  }
  if (POST.length) {
    pi.on("tool_result", async (event, ctx) => {
      if (event.isError) return;
      for (const h of POST as Hook[]) {
        if (!applies(h, event.toolName, event.input)) continue;
        try {
          run(h, event.toolName, event.input, ctx.cwd);
        } catch {
          // fail-open: a hook crash never blocks the pipeline
        }
      }
    });
  }
}
"""


def render_omp(plugin: Plugin) -> Rendered:
    """`package.json` (`omp.extensions`) and `omp/index.ts`, when there is a tool hook to translate."""
    notes: list[str] = []
    pre = [h for h in plugin.hooks if h["on"] == "pre_tool"]
    post = [h for h in plugin.hooks if h["on"] == "post_tool"]
    if any(h["on"] == "stop" for h in plugin.hooks):
        notes.append(
            "omp: a stop hook cannot continue a session in `omp -p`; the runner's contract check "
            "(run_until_valid, which resumes the session) does the same job"
        )
    pkg = _read_json(plugin.root / "package.json") or {"name": plugin.name, "version": "0.1.0"}
    files: dict[str, str] = {}
    if pre or post:

        def view(hs):
            return json.dumps([{k: h[k] for k in ("tool", "match", "script") if h.get(k)} for h in hs], indent=2)

        files["omp/index.ts"] = (
            _OMP_TEMPLATE.replace("__CLAUDE_TOOL__", json.dumps(CLAUDE_TOOL)).replace("__PRE__", view(pre)).replace("__POST__", view(post))
        )
        pkg["omp"] = {"extensions": ["./omp/index.ts"]}
    else:
        pkg.pop("omp", None)
    files["package.json"] = json.dumps(pkg, indent=2) + "\n"
    return files, notes


register_renderer("claude", render_claude)
register_renderer("omp", render_omp)


def render(plugin: Plugin, agents=None) -> Rendered:
    """Every agent's hook files for `plugin` (`agents`: default the plugin's own, else all)."""
    files: dict[str, str] = {}
    notes: list[str] = []
    for agent in agents or plugin.agents or sorted(RENDERERS):
        f, n = RENDERERS[agent](plugin)
        files.update(f)
        notes += n
    return files, notes


def stale(plugin: Plugin, agents=None) -> list[str]:
    """Files whose content differs from what the declaration renders to."""
    files, _ = render(plugin, agents)
    out = []
    for rel, text in files.items():
        p = plugin.root / rel
        if not p.is_file() or p.read_text() != text:
            out.append(rel)
    return out


def write(plugin: Plugin, agents=None) -> tuple[list[Path], list[str]]:
    """Write the rendered files that changed. Returns (written paths, notes)."""
    files, notes = render(plugin, agents)
    written = []
    for rel, text in files.items():
        p = plugin.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file() or p.read_text() != text:
            p.write_text(text)
            written.append(p)
    return written, notes
