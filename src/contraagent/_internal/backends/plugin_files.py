"""The files of a plugin directory every backend reads alike: its MCP servers (`.mcp.json`)
and the extensions its `package.json` declares for one coding agent."""

from __future__ import annotations

import json
from pathlib import Path


def mcp_servers(path: str | Path) -> dict[str, dict]:
    """The servers of a Claude Code `.mcp.json` (`mcpServers`), by name, as written; empty
    when the file cannot be read or holds none. Each backend turns a server into its own form."""
    try:
        servers = json.loads(Path(path).read_text(encoding="utf-8")).get("mcpServers") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(servers, dict):
        return {}
    return {str(name): spec for name, spec in servers.items() if isinstance(spec, dict)}


def write_mcp_servers(path: Path, servers: dict[str, dict]) -> None:
    """Write `servers` as a Claude Code `.mcp.json` (`mcpServers`), which every backend reads
    as it reads a plugin's."""
    path.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8", newline="\n")


def extensions(plugin_dir: str | Path, agent: str) -> list[Path]:
    """The extension files a plugin's `package.json` lists under `<agent>.extensions` (the hooks
    `contraagent plugin render` writes for omp and pi), those that exist."""
    root = Path(plugin_dir)
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    own = pkg.get(agent) if isinstance(pkg, dict) else None
    listed = own.get("extensions") if isinstance(own, dict) else None
    return [root / rel for rel in listed or [] if (root / rel).is_file()]
