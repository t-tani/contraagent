"""A user's type checker infers the public types: `tests/typing/public_types.py` passes
`mypy --strict` and pyright `strict` (the repository's own pyright mode is `standard`), and
refuses each line marked `# type: ignore[...]`: both checkers report an ignore that
silences nothing."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CHECKED = ROOT / "tests" / "typing" / "public_types.py"


def test_mypy_strict_infers_the_public_types(tmp_path: Path):
    mypy = Path(sys.executable).with_name("mypy")
    command = [str(mypy), "--strict", "--cache-dir", str(tmp_path), "--python-executable", sys.executable, str(CHECKED)]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_pyright_strict_infers_the_public_types(tmp_path: Path):
    config = tmp_path / "pyrightconfig.json"
    config.write_text(json.dumps({"typeCheckingMode": "strict", "pythonVersion": "3.12", "reportUnnecessaryTypeIgnoreComment": "error"}))
    pyright = Path(sys.executable).with_name("pyright")
    command = [str(pyright), "--project", str(config), "--pythonpath", sys.executable, str(CHECKED)]
    # Without it the pyright package asks PyPI for its latest version before every check.
    env = {**os.environ, "PYRIGHT_PYTHON_IGNORE_WARNINGS": "1"}
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
