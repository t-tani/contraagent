"""The account of a Claude Code /login, read from the file Claude Code keeps it in."""

from __future__ import annotations

import json
from pathlib import Path

from contraagent.backends.launch import ACCOUNT_UUID, account_digest


def login_account(config_dir: str | None) -> str:
    """The account of the /login in `config_dir` (Claude Code keeps it in `.claude.json`
    there, or in `~/.claude.json` with none), as `account_digest` of its `accountUuid`; ''
    with no login."""
    path = Path(config_dir) / ".claude.json" if config_dir else Path.home() / ".claude.json"
    try:
        found = json.loads(path.read_text()).get("oauthAccount") or {}
    except (OSError, ValueError, AttributeError):
        return ""
    return account_digest(ACCOUNT_UUID, str(found.get("accountUuid") or "")) if isinstance(found, dict) else ""
