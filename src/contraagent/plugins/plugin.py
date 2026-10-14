"""A plugin: the implementation of an agent task, as the coding agent itself loads it.

The Python side declares a task's *interface* (`agent_task`: its parameters,
its output, its budget); the plugin holds everything about *how* the task is
done, in the form Claude Code and omp read natively through `--plugin-dir`:

    plugins/summarize/
      .claude-plugin/plugin.json   what makes the directory a plugin
      agents/<role>.md             the procedure: who the agent is and how it works
      skills/<name>/SKILL.md       detail the agent loads when it needs it
                                   (Claude Code names it `<plugin name>:<name>`)
      settings.json                what the agent may do
      .mcp.json                    tools it may call (optional)
      hooks.toml                   hooks, declared once for every coding agent
      hooks/*.sh                   the hook scripts
      hooks/hooks.json             hooks as Claude Code reads them   (rendered)
      package.json, omp/           hooks as omp reads them           (rendered)

Nothing in it names a run, a unit or a file path: those arrive per task in the
call file (`contraagent.calls`).

A plugin that holds skills and nothing else that acts (`besides_skills`) is a
skill plugin: tasks load it beside their own (`agent_task(skills_from=)`) to share
its skills.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from contraagent.errors import ContraagentError, did_you_mean

PLUGIN_JSON = Path(".claude-plugin") / "plugin.json"
HOOKS_TOML = "hooks.toml"

#: What a plugin holds besides skills that acts on the session that loads it: named
#: agents, slash commands, permissions, tools, hooks (each coding agent's rendering too).
NOT_SKILLS = ("agents", "commands", "settings.json", ".mcp.json", HOOKS_TOML, "hooks", "package.json", "omp")


class PluginError(ContraagentError):
    """A plugin that cannot be loaded (no plugin.json, a broken hooks.toml, an unknown role)."""


def is_plugin(path: str | Path) -> bool:
    """A directory with `.claude-plugin/plugin.json`."""
    return (Path(path) / PLUGIN_JSON).is_file()


@dataclass(frozen=True)
class Plugin:
    root: Path
    name: str
    hooks: tuple[dict, ...] = ()
    #: Coding agents the hooks are rendered for; empty means every registered renderer.
    agents: tuple[str, ...] = ()

    @classmethod
    def load(cls, root: str | Path) -> Plugin:
        root = Path(root).resolve()
        if not is_plugin(root):
            raise PluginError(f"{root}: not a plugin (no {PLUGIN_JSON})")
        try:
            meta = json.loads((root / PLUGIN_JSON).read_text())
        except ValueError as exc:
            raise PluginError(f"{root / PLUGIN_JSON}: {exc}") from exc
        hooks: dict = {}
        if (root / HOOKS_TOML).is_file():
            try:
                hooks = tomllib.loads((root / HOOKS_TOML).read_text())
            except tomllib.TOMLDecodeError as exc:
                raise PluginError(f"{root / HOOKS_TOML}: {exc}") from exc
        name = str(meta.get("name") or root.name) if isinstance(meta, dict) else root.name
        return cls(root=root, name=name, hooks=tuple(hooks.get("hooks", ())), agents=tuple(hooks.get("agents", ())))

    # --- roles -------------------------------------------------------------

    @property
    def roles(self) -> tuple[str, ...]:
        """The named agents this plugin defines (`agents/<role>.md`)."""
        d = self.root / "agents"
        return tuple(sorted(f.stem for f in d.glob("*.md"))) if d.is_dir() else ()

    def role_file(self, role: str) -> Path:
        return self.root / "agents" / f"{role}.md"

    def resolve_role(self, role: str | None) -> str | None:
        """`role`, checked; or the plugin's only role when none is named."""
        if role is None:
            if len(self.roles) > 1:
                raise PluginError(f"{self.root}: defines roles {', '.join(self.roles)}; name one (role=...)")
            return self.roles[0] if self.roles else None
        if role not in self.roles:
            raise PluginError(
                f"{self.root}: no role {role!r} (agents/{role}.md){did_you_mean(role, self.roles)}; "
                f"it defines: {', '.join(self.roles) or 'none'}"
            )
        return role

    # --- skills ------------------------------------------------------------

    def skill_files(self) -> list[tuple[str, str]]:
        """`(path relative to the plugin, text)` of every Markdown file under `skills/`."""
        return [(str(f.relative_to(self.root)), f.read_text()) for f in markdown_under(self.root / "skills")]

    def besides_skills(self) -> list[str]:
        """The parts it holds that act besides skills (`NOT_SKILLS`); empty for a skill plugin."""
        return [name for name in NOT_SKILLS if (self.root / name).exists()]

    @property
    def skills_only(self) -> bool:
        """A skill plugin: skills and nothing else that acts."""
        return (self.root / "skills").is_dir() and not self.besides_skills()

    # --- views -------------------------------------------------------------

    _PARTS = (
        (str(PLUGIN_JSON), "plugin"),
        ("settings.json", "settings"),
        (".mcp.json", "mcp"),
        (HOOKS_TOML, "hooks"),
        ("hooks/hooks.json", "hooks"),
        ("README.md", "readme"),
    )

    def definition(self, role: str | None, limit: int = 40_000) -> dict:
        """The plugin as plain data, for the monitor: its files and the role in use."""
        files = []
        for rel, part in self._PARTS:
            f = self.root / rel
            if f.is_file():
                files.append({"path": rel, "part": part, "text": f.read_text()[:limit]})
        for sub, part in (("agents", "agent"), ("skills", "skill")):
            for f in markdown_under(self.root / sub):
                files.append({"path": str(f.relative_to(self.root)), "part": part, "text": f.read_text()[:limit]})
        return {"plugin": True, "name": self.name, "root": str(self.root), "role": role, "plugin_dirs": [str(self.root)], "files": files}

    def lint(self) -> list[str]:
        """Disagreements between the parts of the plugin. Empty when they agree."""
        from contraagent.plugins.lint import lint_plugin

        return lint_plugin(self)


def markdown_under(d: Path) -> list[Path]:
    """Every Markdown file under `d`, sorted, through symbolic links to directories too
    (a skill linked in from elsewhere is the plugin's, as the coding agent loads it), each
    directory once; empty when `d` is not a directory. Paths stay under `d` as linked."""
    if not d.is_dir():
        return []
    out: list[Path] = []
    seen: set[str] = set()
    for top, dirs, files in os.walk(d, followlinks=True):
        real = os.path.realpath(top)
        if real in seen:  # a link back to a directory already read
            dirs[:] = []
            continue
        seen.add(real)
        out += [Path(top) / f for f in files if f.endswith(".md")]
    return sorted(out)


def body(text: str) -> str:
    """A Markdown file's text after its leading `---` frontmatter (all of it when it has none)."""
    m = re.match(r"^---\n.*?\n---[ \t]*\n?", text, re.S)
    return text[m.end() :] if m else text


def frontmatter(text: str) -> dict:
    """The `key: value` lines between the leading `---` fences of a Markdown file."""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in m.group(1).splitlines() if m else []:
        k, _, v = line.partition(":")
        if v.strip():
            out[k.strip()] = v.strip().strip("\"'")
    return out
