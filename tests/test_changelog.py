"""The changelog: fragments in changelog.d/ that towncrier writes into CHANGELOG.md at a release."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = ROOT / "changelog.d"
TYPES = ("added", "changed", "deprecated", "removed", "fixed", "security")
NOT_FRAGMENTS = {"README.md", "template.md"}
NAME = re.compile(rf"\+?[a-z0-9][a-z0-9_-]*\.({'|'.join(TYPES)})\.md")


def test_the_fragment_types_are_keep_a_changelogs_sections_in_order():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["towncrier"]
    assert [(t["directory"], t["name"]) for t in config["type"]] == [(t, t.capitalize()) for t in TYPES]


def test_every_file_in_changelog_d_is_named_as_a_fragment():
    names = {p.name for p in FRAGMENTS.iterdir()} - NOT_FRAGMENTS
    assert all(not (FRAGMENTS / n).is_dir() for n in names)
    bad = sorted(n for n in names if not NAME.fullmatch(n))
    assert not bad, f"not <slug>.<type>.md (types: {', '.join(TYPES)}): {bad}"


def test_the_changelog_keeps_its_header_and_the_marker():
    text = (ROOT / "CHANGELOG.md").read_text()
    assert "https://keepachangelog.com/" in text and "https://semver.org/" in text
    assert text.count("<!-- towncrier release notes start -->") == 1
    assert "## [Unreleased]" not in text


def test_towncrier_renders_the_next_release():
    done = subprocess.run(
        [sys.executable, "-m", "towncrier", "build", "--draft", "--version", "9.9.9"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr + done.stdout
    out = done.stdout
    assert re.search(r"^## \[9\.9\.9\] - \d{4}-\d{2}-\d{2}$", out, re.M)
    fragments = [p for p in FRAGMENTS.iterdir() if p.name not in NOT_FRAGMENTS]
    for p in fragments:
        kind = p.name.split(".")[-2]
        assert f"### {kind.capitalize()}" in out
        first = p.read_text().strip().splitlines()[0]
        assert f"- {first}" in out, p.name
    # Sections in Keep a Changelog's order, and no issue reference after a bullet.
    headings = re.findall(r"^### (\w+)$", out, re.M)
    assert headings == sorted(headings, key=lambda h: TYPES.index(h.lower()))
    assert "====" not in out
