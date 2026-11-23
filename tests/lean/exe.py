"""What the Lean specification answers for scenarios: `lake exe contraagent-lean <what>` reads
one scenario on each line of its input, as JSON, and prints one line for each."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: Where elan keeps the Lean it installed: the home of the user running this, read before a
#: test is given an empty home of its own, where elan would install Lean again.
ELAN_HOME = os.environ.get("ELAN_HOME") or str(Path.home() / ".elan")


def specified(what: str, given: list[dict[str, Any]]) -> list[Any]:
    """What the specification answers for each scenario of `given` (`what`: `queue`, `router`)."""
    text = "".join(json.dumps(sc, separators=(",", ":")) + "\n" for sc in given)
    done = subprocess.run(
        ["lake", "exe", "contraagent-lean", what],
        cwd=ROOT / "lean",
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "ELAN_HOME": ELAN_HOME},
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr)
    return [json.loads(line) for line in done.stdout.splitlines()]


def rewrite(file: Path, what: str, given: list[dict[str, Any]]) -> None:
    """Write `file`: each scenario of `given` with what the specification answers for it."""
    played = zip(given, specified(what, given), strict=True)
    lines = [json.dumps({"scenario": sc, "specified": answer}, separators=(",", ":")) for sc, answer in played]
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
