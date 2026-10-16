"""The logins pi keeps in an agent directory (`auth.json`)."""

from __future__ import annotations

import json
from pathlib import Path


def pi_login(home: Path, provider: str) -> dict | None:
    """The login pi keeps for `provider` in agent directory `home` (`auth.json`); None when none."""
    try:
        login = json.loads((home / "auth.json").read_text(encoding="utf-8")).get(provider)
    except (OSError, ValueError, AttributeError):
        return None
    return login if isinstance(login, dict) else None
