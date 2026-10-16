"""A check run as a command: the output file and the task's call file in, exit 0 to pass.

    python -m contraagent.docs.examples.demo.checks <note.md> <call.json>

What it prints when it fails is what the agent is sent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    note, call = argv if argv is not None else sys.argv[1:]
    unit = json.loads(Path(call).read_text(encoding="utf-8"))["params"]["summary"]["unit"]
    if unit not in Path(note).read_text(encoding="utf-8"):
        print(f"the note never names its unit {unit!r} (the call file's params.summary.unit)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
