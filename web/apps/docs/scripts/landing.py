"""Write src/fixtures/landing-outputs.json: what the CLI prints in the landing page's "how it works" scene.

    uv run python web/apps/docs/scripts/landing.py

Runs the commands the scene shows, on the demo pipeline of the package's examples
(`src/contraagent/docs/examples/demo`): `contraagent --version`, `contraagent docs`,
`contraagent docs --pointer`, `contraagent check` on a copy of the demo with the
agent's first mistakes and on the demo itself, and the demo's tests on a stub agent.
src/components/home/how.ts reads the file when the site renders; nothing there runs
a command.

Each output is shown as a reader sees it in their own project: a path under the
directory the command ran in is printed relative to it, and the directory itself as
`.`. A capture that names a directory of this machine (the repository, the system's
temporary files, the home directory), or whose shape is not the scene's (a check that
does not fail on the broken copy, a test that does not pass), stops the script. The
file holds no timings, so the same package writes the same file
(tests/test_docs.py checks it is current).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
OUT = HERE / "src" / "fixtures" / "landing-outputs.json"
DEMO = REPO / "src" / "contraagent" / "docs" / "examples" / "demo"

#: The demo's flow arguments, as the scene's commands give them (how.ts has the same).
KWARGS = '{"units": ["alpha", "beta"]}'
#: The mistakes the scene's agent makes on its first try, in a copy of the demo: the
#: units as one string, a kind's name misspelt in the config.
SLIP = {"kwargs": '{"units": "alpha"}', "from": "[tasks.summarize]", "to": "[tasks.sumarize]"}

#: The directories of this machine that no output on the page may name.
PRIVATE = sorted({str(REPO), tempfile.gettempdir(), os.path.realpath(tempfile.gettempdir()), str(Path.home())}, key=len, reverse=True)


def in_project(text: str, where: Path) -> str:
    """`text` with the paths under `where` relative to it, and `where` itself as `.`."""
    # The longer first: on macOS the real path (`/private/var/...`) holds the other.
    for d in sorted({str(where), os.path.realpath(where)}, key=len, reverse=True):
        text = text.replace(d + os.sep, "").replace(d, ".")
    return text


def published(what: str, text: str) -> str:
    """`text`, after it was checked to name none of this machine's directories."""
    for d in PRIVATE:
        if d in text:
            raise SystemExit(f"the landing page's {what} names {d}, a directory of this machine:\n{text}")
    return text


def run(args: list[str], cwd: Path = DEMO) -> str:
    """A Python module's command in `cwd`, and what it printed (whatever its exit status), its paths in the project."""
    env = {**os.environ, "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", *args], cwd=cwd, capture_output=True, text=True, env=env, check=False, encoding="utf-8")
    return in_project(f"{r.stdout}{r.stderr}".rstrip(), cwd)


def cli(*args: str, cwd: Path = DEMO) -> str:
    return run(["contraagent", *args], cwd)


def broken_check() -> str:
    """`contraagent check` on a copy of the demo with the mistakes of SLIP."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(DEMO, project, ignore=shutil.ignore_patterns("__pycache__"))
        toml = project / "pipeline.toml"
        text = toml.read_text(encoding="utf-8")
        if SLIP["from"] not in text:
            raise SystemExit(f"demo pipeline.toml has no {SLIP['from']}")
        toml.write_text(text.replace(SLIP["from"], SLIP["to"]), encoding="utf-8", newline="\n")
        out = cli("check", "tasks.py:docs", "--config", "pipeline.toml", "--stub", "--kwargs", SLIP["kwargs"], cwd=project)
    # Its shape, not its wording: more than one problem reported, and the first line says the check failed (✓ is a pass).
    problems = [line for line in out.splitlines() if re.match(r"^\s+(error|warning)\b", line, re.IGNORECASE)]
    if len(problems) < 2 or out.startswith("✓"):
        raise SystemExit(f"the broken copy's check did not report two problems:\n{out}")
    return out


def tests() -> list[str]:
    """The demo's tests on a stub agent: one line per test, then pytest's summary without its duration."""
    # pytest as a project without the repository's own pytest options runs it. Its temporary
    # directories are its own: in pytest's shared one, two sessions that end at once can
    # remove the same old directory, and the one that loses warns (an error here) after every
    # test passed.
    with tempfile.TemporaryDirectory() as tmp:
        out = run(["pytest", "test_demo.py", "-v", "-o", "addopts=", "-p", "no:cacheprovider", "--basetemp", str(Path(tmp) / "basetemp")])
    kept = re.compile(r"^test_demo\.py::\S+ (PASSED|FAILED)|^=+ \d+ (passed|failed)")
    lines = [line for line in out.splitlines() if kept.match(line)]
    lines = [re.sub(r"\s+\[\s*\d+%\]$", "", line) for line in lines]
    lines = [re.sub(r" in [\d.]+s( \([\d:]+\))?$", "", re.sub(r"^=+ | =+$", "", line)) for line in lines]
    if not any(re.search(r"\d+ passed", line) for line in lines) or any(re.search("FAILED|failed", line) for line in lines):
        raise SystemExit(f"test_demo.py did not pass:\n{out}")
    return lines


def outputs() -> dict[str, object]:
    # The commands are independent; run at once, they take as long as the slowest (the tests).
    with ThreadPoolExecutor() as pool:
        version = pool.submit(cli, "--version")
        docs = pool.submit(cli, "docs")
        pointer_ = pool.submit(cli, "docs", "--pointer")
        check_ = pool.submit(cli, "check", "tasks.py:docs", "--config", "pipeline.toml", "--stub", "--kwargs", KWARGS)
        slip = pool.submit(broken_check)
        passed = pool.submit(tests)
    topics = re.findall(r"^- \[([^\]]+)\]\(", docs.result(), re.MULTILINE)
    if len(topics) < 5:
        raise SystemExit("`contraagent docs` lists no topics")
    pointer = pointer_.result()
    if "contraagent docs" not in pointer:
        raise SystemExit(f"`contraagent docs --pointer` names no `contraagent docs`:\n{pointer}")
    check = check_.result()
    if not check.startswith("✓"):
        raise SystemExit(f"the demo's check did not pass:\n{check}")
    return {
        "version": published("version", version.result()),
        "topics": [published("topics of contraagent docs", t) for t in topics],
        "slip": {**SLIP, "output": published("first check", slip.result())},
        "pointer": published("pointer", pointer),
        "check": published("check", check),
        "tests": [published("tests", t) for t in passed.result()],
    }


def text(data: dict[str, object]) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    OUT.write_text(text(outputs()), encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {OUT}\n")


if __name__ == "__main__":
    main()
