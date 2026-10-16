"""opencode's model catalogue: `opencode models --verbose`, read by `OpencodeBackend.read_models`."""

from __future__ import annotations

import json
import re

from contraagent._internal.backends.wire import positive_int

#: The command that lists the models with their details.
ARGS = ("models", "--verbose")
#: A model's line in `opencode models`: `provider/model`.
_MODEL_LINE = re.compile(r"[\w.-]+/\S+")
_SPACE = re.compile(r"\s*")


def parse_models(stdout: str) -> dict[str, int | None]:
    """Each model of `opencode models --verbose` (a `provider/model` line, then the
    model's JSON with `limit.context`), with its context window; None where the JSON
    gives none. Plain `opencode models` (the lines alone) parses too, every window
    None."""
    out: dict[str, int | None] = {}
    decoder = json.JSONDecoder()
    pos = 0
    for line in stdout.splitlines(keepends=True):
        pos += len(line)
        name = line.strip()
        if line[:1].isspace() or not _MODEL_LINE.fullmatch(name):
            continue
        at = _SPACE.match(stdout, pos).end()  # type: ignore[union-attr]
        try:
            doc = decoder.raw_decode(stdout, at)[0] if stdout.startswith("{", at) else None
        except ValueError:
            doc = None
        limit = doc.get("limit") if isinstance(doc, dict) else None
        out[name] = positive_int(limit.get("context")) if isinstance(limit, dict) else None
    return out
