"""The files of the repository check out on Linux, macOS and Windows, and name no
directory of the machine that wrote them."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: What Windows refuses in a file name: these characters, a control character, a
#: trailing `.` or space, a device name.
WINDOWS = re.compile(r'[<>:"|?*\\\x00-\x1f]|[. ]$|^(CON|PRN|AUX|NUL|COM\d|LPT\d)(\.|$)', re.IGNORECASE)


def tracked() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def test_every_tracked_name_is_a_valid_windows_file_name():
    bad = [p for p in tracked() if any(WINDOWS.search(part) for part in p.split("/"))]
    assert not bad, f"names Windows cannot check out: {bad[:10]}"


def test_no_two_tracked_paths_differ_only_in_case():
    seen: dict[str, str] = {}
    clashes = [(seen[p.lower()], p) for p in tracked() if seen.setdefault(p.lower(), p) != p]
    assert not clashes, f"paths that are one file on macOS and Windows: {clashes[:10]}"


def test_no_tracked_file_names_a_directory_of_this_machine(host_home):
    home = host_home
    # The home directory itself, and the checkout as the export writes it (`~/...`).
    private = {str(ROOT)}
    if home.parent != home:  # a filesystem root (HOME=/ in some containers) is no one's directory
        private.add(str(home) + "/")
        if ROOT.is_relative_to(home) and ROOT != home:
            private.add(f"~/{ROOT.relative_to(home).as_posix()}")
    found = []
    for p in tracked():
        try:
            text = (ROOT / p).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        found += [(p, d) for d in private if d in text]
    assert not found, f"files naming this machine's directories: {found[:10]}"
