"""`Limits.disallowed_tools` inside omp: the rules of contraagent's own extension (`deny.ts`).

A task denies tools in Claude Code's names and patterns (`WebFetch`, `Bash(git push:*)`,
`Read(secrets/**)`). omp has no flag for it, but its extensions see every tool call before
it runs and may block it (`tool_call`, `{block, reason}`), and may change the tools the
model is offered (`setActiveTools`). `rules` turns the task's list into the extension's
rules; `problem` names what omp cannot be held to, and the routing check refuses a route on
omp for that alone (`OmpBackend.tool_deny_problem`). What each name becomes is in the
docstring of `OmpBackend` (checked against omp 18.9's built-in tools).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from contraagent._internal.backends.base import DENY_POINTER

#: The variable the extension reads its rules from, as JSON.
DENY_ENV = "CONTRAAGENT_OMP_DENY"
#: The extension, loaded with `-e` into a launch that denies a tool.
EXTENSION = Path(__file__).resolve().parent / "deny.ts"

#: Claude Code's tool names as omp's tools, for a tool denied whole.
TOOLS: dict[str, tuple[str, ...]] = {
    "Bash": ("bash",),
    "Read": ("read",),
    "Write": ("write",),
    "Edit": ("edit", "ast_edit"),
    "MultiEdit": ("edit", "ast_edit"),
    "Glob": ("glob", "find"),
    "Grep": ("grep", "ast_grep"),
    "WebSearch": ("web_search",),
    "Agent": ("task",),
    "Task": ("task",),
    "TodoWrite": ("todo",),
}
#: The tools whose pattern names the file a call reads or writes, and the omp tools it checks.
PATH_TOOLS: dict[str, tuple[str, ...]] = {
    "Read": ("read",),
    "Write": ("write",),
    "Edit": ("edit", "write"),
    "MultiEdit": ("edit", "write"),
}
#: The tools omp reaches through a URL its `read` tool is given: the schemes, and what the
#: pattern names (`domain:<host>`, a skill's name).
URL_TOOLS: dict[str, tuple[str, ...]] = {"WebFetch": ("http", "https"), "Skill": ("skill",)}

_RULE_RE = re.compile(r"^([\w.-]+)(?:\((.*)\))?$", re.S)
_SPECIAL = re.compile(r"([\\^$.|?*+()\[\]{}])")
#: A path pattern's wildcards as regular expressions, longest first: `**/` is any number of
#: directories, none included.
_GLOB = (("**/", "(.*/)?"), ("**", ".*"), ("*", "[^/]*"), ("?", "[^/]"))


def _escape(text: str) -> str:
    """`text` as a literal in a regular expression that Python and JavaScript read alike."""
    return _SPECIAL.sub(r"\\\1", text)


def _mcp_part(value: str, fallback: str) -> str:
    """One part of an MCP tool's name as omp writes it (lower case, `_` for the rest)."""
    part = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", value.lower())).strip("_")
    return part or fallback


def mcp_rule(name: str) -> dict:
    """An MCP tool (`mcp__server__tool`) or a whole server (`mcp__server`, `mcp__server__*`)
    as omp names it: `mcp__<server>_<tool>`, the server's name dropped from the tool's."""
    server, _, tool = name.removeprefix("mcp__").partition("__")
    srv = _mcp_part(server, "server")
    if not tool or tool == "*":
        return {"prefix": f"mcp__{srv}_"}
    own = _mcp_part(tool, "tool")
    return {"tools": [f"mcp__{srv}_{own.removeprefix(srv + '_')}"]}


def command_pattern(pattern: str) -> str:
    """A `Bash(...)` pattern as a regular expression of one command: `git push:*` is `git
    push` alone or followed by more words, a `*` any text, anything else the command exactly."""
    if pattern.endswith(":*"):
        return "^" + _escape(pattern[:-2].strip()) + r"(\s.*)?$"
    return "^" + ".*".join(_escape(part) for part in pattern.strip().split("*")) + "$"


def path_pattern(pattern: str, cwd: Path, home: Path | None = None) -> str:
    """A path pattern as a regular expression of an absolute path, with `/` between its parts."""
    home = home or Path.home()
    if pattern.startswith("//"):
        base, rest = "/", pattern[2:]
    elif pattern == "~" or pattern.startswith("~/"):
        base, rest = home.as_posix(), pattern[2:]
    else:
        base, rest = cwd.resolve().as_posix(), pattern.lstrip("/").removeprefix("./")
    under = rest.endswith("/") or rest.endswith("/**") or rest == "**"
    rest = rest.removesuffix("**").rstrip("/")
    # os.path, not pathlib: `normpath` folds `..` without following a link.
    full = os.path.normpath(os.path.join(base, rest)).replace("\\", "/") if rest else base.rstrip("/") or "/"
    out, i = [], 0
    while i < len(full):
        for token, regex in _GLOB:
            if full.startswith(token, i):
                out.append(regex)
                i += len(token)
                break
        else:
            out.append(_escape(full[i]))
            i += 1
    return "^" + "".join(out) + ("(/.*)?$" if under else "$")


def problem(denied: tuple[str, ...]) -> str | None:
    """What of `denied` omp cannot be held to: a pattern of a tool other than `Bash`, `Read`,
    `Write`, `Edit`, `MultiEdit`, `WebFetch` (`domain:`) and `Skill`; None when it can
    deny all of it."""
    odd = []
    for rule in denied:
        m = _RULE_RE.match(rule.strip())
        if m is None:
            odd.append(rule)
            continue
        name, pattern = m.group(1), m.group(2)
        if pattern is None or name.startswith("mcp__"):
            continue
        if name == "Bash" or name in PATH_TOOLS or name == "Skill" or (name == "WebFetch" and pattern.startswith("domain:")):
            continue
        odd.append(rule)
    if not odd:
        return None
    return (
        f"omp cannot hold {', '.join(odd)}: it holds a pattern of Bash, Read, Write, Edit, MultiEdit, Skill and "
        f"WebFetch(domain:...) only; deny such a tool whole {DENY_POINTER}"
    )


def rules(denied: tuple[str, ...], cwd: Path, home: Path | None = None) -> list[dict]:
    """The extension's rules for `denied`, in order; each names the task's rule it comes from
    (`rule`), which a blocked call is told. A rule holds the omp tools it applies to
    (`tools`, or every tool whose name starts with `prefix`) and at most one of: `command`, a
    regular expression of one shell command; `path`, one of a path; `schemes` (and `host`),
    the URLs a `read` reaches. A rule with none of them denies its tools whole. A rule
    `problem` names is left out."""
    out: list[dict] = []
    for raw in denied:
        rule = raw.strip()
        m = _RULE_RE.match(rule)
        if m is None:
            continue
        name, pattern = m.group(1), m.group(2)
        if name.startswith("mcp__"):
            out.append({"rule": rule, **mcp_rule(name)})
        elif name in URL_TOOLS:
            if name == "WebFetch" and pattern is not None and not pattern.startswith("domain:"):
                continue
            found: dict = {"rule": rule, "tools": ["read"], "schemes": list(URL_TOOLS[name])}
            if pattern:
                found["host"] = pattern.removeprefix("domain:").strip().lower()
            out.append(found)
        elif pattern is None:
            out.append({"rule": rule, "tools": list(TOOLS.get(name, (name.lower(),)))})
        elif name == "Bash":
            out.append({"rule": rule, "tools": ["bash"], "command": command_pattern(pattern)})
        elif name in PATH_TOOLS:
            out.append({"rule": rule, "tools": list(PATH_TOOLS[name]), "path": path_pattern(pattern, cwd, home)})
            if name in ("Edit", "MultiEdit"):
                out.append({"rule": rule, "tools": ["ast_edit"]})
    return out


def env(denied: tuple[str, ...], cwd: Path) -> dict[str, str]:
    """The launch's variable that holds the rules; empty when it denies nothing."""
    found = rules(denied, cwd)
    return {DENY_ENV: json.dumps(found, ensure_ascii=False)} if found else {}


def args(denied: tuple[str, ...]) -> list[str]:
    """`-e <deny.ts>` for a launch that denies a tool."""
    return ["-e", str(EXTENSION)] if denied else []
