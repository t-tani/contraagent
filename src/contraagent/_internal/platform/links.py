"""A link to a file or a directory, made as the OS allows.

* POSIX (Linux, macOS): a symbolic link (`PosixLinks`).
* Windows: a symbolic link where the user may make one (Developer Mode, or an
  administrator); else a directory junction for a directory and a hard link for a file,
  which need no privilege but must be on one volume; else, for a file, a copy
  (`WindowsLinks`). A hard link or a copy is not a path: what replaces the source file
  (a login refreshed by writing a new file over it) is not seen through it.

`links` is this OS's; each takes the calls it makes in its constructor, so each can be
tested on any OS.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class Links(Protocol):
    def link(self, source: Path, link: Path) -> None:
        """Make `link` lead to `source`, a file or a directory. Raises `OSError`."""
        ...


class PosixLinks:
    def link(self, source: Path, link: Path) -> None:
        os.symlink(source, link, target_is_directory=source.is_dir())


def _junction(source: str, link: str) -> None:
    import _winapi  # type: ignore[import-not-found]

    _winapi.CreateJunction(source, link)  # type: ignore[attr-defined]


class WindowsLinks:
    """`symlink`, `junction`, `hardlink` and `copy` (each `(source, link)`) are given in a test."""

    def __init__(
        self,
        symlink: Callable[..., None] | None = None,
        junction: Callable[[str, str], None] | None = None,
        hardlink: Callable[[str, str], None] | None = None,
        copy: Callable[[str, str], object] | None = None,
    ) -> None:
        self._symlink = symlink or os.symlink
        self._junction = junction or _junction
        self._hardlink = hardlink or os.link
        self._copy = copy or shutil.copy2

    def link(self, source: Path, link: Path) -> None:
        directory = source.is_dir()
        try:
            self._symlink(str(source), str(link), target_is_directory=directory)
            return
        except OSError:
            pass  # no privilege to make one
        if directory:
            self._junction(str(source), str(link))
            return
        try:
            self._hardlink(str(source), str(link))
        except OSError:
            self._copy(str(source), str(link))


#: This OS's links.
links: Links = WindowsLinks() if sys.platform == "win32" else PosixLinks()
