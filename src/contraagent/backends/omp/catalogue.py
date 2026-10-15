"""omp's model catalogue: `omp models --json`, read by `OmpBackend.read_models`."""

from __future__ import annotations

import json

from contraagent.backends.wire import positive_int

#: The command that lists the models.
ARGS = ("models", "--json")


def parse_models(stdout: str) -> dict[str, int | None]:
    """Each model of `omp models --json` (`{"models": [{"selector", "contextWindow"}]}`),
    by its provider-qualified selector, with its context window (None where omp lists
    none). Empty when the output is not that document."""
    try:
        doc = json.loads(stdout)
    except ValueError:
        return {}
    rows = doc.get("models") if isinstance(doc, dict) else None
    out: dict[str, int | None] = {}
    for m in rows if isinstance(rows, list) else ():
        if not isinstance(m, dict):
            continue
        selector = m.get("selector") or (f"{m['provider']}/{m['id']}" if m.get("provider") and m.get("id") else None)
        if isinstance(selector, str):
            out[selector] = positive_int(m.get("contextWindow"))
    return out
