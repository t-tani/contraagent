"""The import rules of AGENTS.md ("Public API and layers") hold: `lint-imports` checks the
contracts in pyproject.toml's `[tool.importlinter]`."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_every_import_contract_is_kept():
    lint = Path(sys.executable).with_name("lint-imports")
    done = subprocess.run([str(lint), "--no-cache", "--no-logo"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
