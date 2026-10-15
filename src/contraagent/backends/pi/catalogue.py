"""pi's model catalogue: `pi --list-models`, read by `PiBackend.read_models`."""

from __future__ import annotations

import re

#: The command that lists the models (no network).
ARGS = ("--list-models", "--offline")
#: A row of `pi --list-models`: provider, then model id.
_ROW_RE = re.compile(r"^(\S+)\s+(\S+)\s+\S+\s+\S+\s+(?:yes|no)\s+(?:yes|no)\s*$")


def parse_models(stdout: str) -> dict[str, int | None]:
    """The provider-qualified ids of `pi --list-models`, in order, each window None: the list's
    own `context` column is rounded, so the windows come from pi's model files
    (`agent_dir.windows`)."""
    out: dict[str, int | None] = {}
    for line in stdout.splitlines():
        row = _ROW_RE.match(line.strip())
        if row and row.group(1) != "provider":
            out[f"{row.group(1)}/{row.group(2)}"] = None
    return out
