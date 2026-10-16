"""`contraagent plugin lint`: do the parts of a plugin still agree?

An agent file whose frontmatter names someone else, a skill without a
description, a hook script that is missing, rendered hook files out of date
with `hooks.toml`: each is a plugin that loads and runs and then does the
wrong thing, so each is reported here instead. A skill plugin (skills and
nothing else that acts) has no role and no hooks to agree with: only its
skills are checked.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from contraagent._internal.plugins import hooks
from contraagent._internal.plugins.plugin import HOOKS_TOML, PLUGIN_JSON, Plugin, frontmatter


def lint_plugin(plugin: Plugin) -> list[str]:
    """Disagreements between the parts of `plugin`. Empty when they agree."""
    errs: list[str] = []
    r = plugin.root
    errs += _json_errors(r / PLUGIN_JSON, required=("name",))
    errs += lint_skills(plugin)
    if plugin.skills_only:
        return errs
    if leftovers := plugin.render_leftovers():
        return errs + [f"{', '.join(leftovers)}: written by `contraagent plugin render`, which a skill plugin does not need; remove them"]
    if not plugin.roles:
        errs.append("agents/: no role (agents/<role>.md) — the task has no procedure")
    for role in plugin.roles:
        fm = frontmatter(plugin.role_file(role).read_text(encoding="utf-8"))
        if fm.get("name") != role:
            errs.append(f"agents/{role}.md: frontmatter name is {fm.get('name')!r}, expected {role!r}")
        if not fm.get("description"):
            errs.append(f"agents/{role}.md: frontmatter has no description")
    for opt in ("settings.json", "package.json", ".mcp.json"):
        if (r / opt).is_file():
            errs += _json_errors(r / opt)
    # hooks: declared once, rendered per coding agent
    hook_errs = hooks.hook_errors(plugin.hooks)
    errs += hook_errs
    for h in plugin.hooks:
        if isinstance(h, dict) and h.get("script") and not (r / h["script"]).is_file():
            errs.append(f"{HOOKS_TOML}: hook script {h['script']} is missing")
    if not any(isinstance(h, dict) and h.get("on") == "stop" and h.get("run") == "validate" for h in plugin.hooks):
        errs.append(
            f'{HOOKS_TOML}: no stop hook with run = "validate" — the agent will not check '
            "its own output before it stops (the runner still checks and resumes it)"
        )
    if not hook_errs:
        for rel in hooks.stale(plugin):
            errs.append(f"{rel}: out of date with {HOOKS_TOML} — run `contraagent plugin render {r}`")
    return errs


def lint_skills(plugin: Plugin) -> list[str]:
    """Each skill's frontmatter names it and says what it is for."""
    r = plugin.root
    errs: list[str] = []
    for skill in sorted((r / "skills").glob("*/SKILL.md")) if (r / "skills").is_dir() else []:
        fm = frontmatter(skill.read_text(encoding="utf-8"))
        for k in ("name", "description"):
            if not fm.get(k):
                errs.append(f"{skill.relative_to(r)}: frontmatter has no {k}")
    return errs


def _json_errors(path: Path, required: Sequence[str] = ()) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return [f"{path.name}: missing"]
    except ValueError as exc:
        return [f"{path.name}: not valid JSON: {exc}"]
    return [f"{path.name}: missing {k!r}" for k in required if not (isinstance(data, dict) and data.get(k))]
