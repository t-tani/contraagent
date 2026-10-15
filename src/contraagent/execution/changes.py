"""A task's changes: the files one attempt created, modified and deleted under the
patterns its task declares (`agent_task(changes=...)`, `TaskAdapter.changes`).

`ChangesEnricher` is the `ResultEnricher` every `AgentRunner` runs first: before the
dispatch it stamps each file the patterns match under the working directory
(`(mtime_ns, size)`), after it compares, sets `TaskResult.changes`, and when the
attempt failed removes the files it created (and the directories it created for
them, once empty), so a retry or a later run starts from the tree as it was.

A file is attributed to the task whose attempt was running when it changed. Two
tasks running at once under the same pattern cannot be told apart: give each its own
directory (`{unit}` in the pattern) or keep them from overlapping (a unit, a tag).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from contraagent.dispatch.task import Changes, Task, TaskResult

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """What the patterns matched before the dispatch: each file's stamp, and the
    directories, by path relative to the working directory."""

    patterns: tuple[str, ...]
    files: dict[str, tuple[int, int]]
    dirs: frozenset[str]


def scan(cwd: Path, patterns: Sequence[str]) -> tuple[dict[str, tuple[int, int]], frozenset[str]]:
    """The files `patterns` cover under `cwd`, with their `(mtime_ns, size)`, and the
    directories, as POSIX paths relative to `cwd`. A pattern is a `Path.glob` pattern; one
    that matches a directory covers everything under it (`topics/alpha/**`, `topics/alpha`)."""
    files: dict[str, tuple[int, int]] = {}
    dirs: set[str] = set()

    def add(p: Path) -> None:
        try:
            st = p.stat()
        except OSError:
            return
        files[p.relative_to(cwd).as_posix()] = (st.st_mtime_ns, st.st_size)

    for pattern in patterns:
        for p in cwd.glob(pattern):
            if p.is_file():
                add(p)
            elif p.is_dir():
                dirs.add(p.relative_to(cwd).as_posix())
                for sub in p.rglob("*"):
                    if sub.is_file():
                        add(sub)
                    elif sub.is_dir():
                        dirs.add(sub.relative_to(cwd).as_posix())
    return files, frozenset(dirs)


def scan_tree(cwd: Path, skip: Callable[[Path], bool]) -> dict[str, tuple[int, int]]:
    """Every file under `cwd`, with its `(mtime_ns, size)`, by POSIX path relative to `cwd`;
    `skip(path)` leaves out a file or a whole directory. Symbolic links to directories are
    not followed."""
    files: dict[str, tuple[int, int]] = {}
    pending = [cwd]
    while pending:
        folder = pending.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            if skip(path):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            files[path.relative_to(cwd).as_posix()] = (st.st_mtime_ns, st.st_size)
    return files


def compare(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> Changes:
    """The files created, modified (stamp moved) and deleted between two scans."""
    return Changes(
        created=tuple(sorted(set(after) - set(before))),
        modified=tuple(sorted(p for p in set(after) & set(before) if after[p] != before[p])),
        deleted=tuple(sorted(set(before) - set(after))),
    )


class ChangesEnricher:
    """The `ResultEnricher` that records a task's changes, and removes the files a failed
    attempt created. `patterns(task)`: the task's patterns, relative to `cwd`; none, and
    it does nothing."""

    def __init__(self, patterns: Callable[[Task], Sequence[str]], cwd: Path) -> None:
        self._patterns = patterns
        self._cwd = Path(cwd)

    def snapshot(self, task: Task) -> Snapshot | None:
        patterns = tuple(self._patterns(task))
        if not patterns:
            return None
        files, dirs = scan(self._cwd, patterns)
        return Snapshot(patterns, files, dirs)

    def enrich(self, task: Task, before: Snapshot | None, result: TaskResult) -> None:
        if before is None:
            return
        after, dirs = scan(self._cwd, before.patterns)
        changes = compare(before.files, after)
        if not result.ok and changes.created:
            changes = Changes(changes.created, changes.modified, changes.deleted, self._remove(changes.created, dirs - before.dirs))
        result.changes = changes

    def _remove(self, created: Sequence[str], new_dirs: frozenset[str]) -> tuple[str, ...]:
        """Remove `created`, then each of `new_dirs` (directories the patterns match that did
        not exist before) left empty, deepest first. Returns the files removed."""
        removed = []
        for rel in created:
            try:
                (self._cwd / rel).unlink()
                removed.append(rel)
            except OSError as exc:
                _logger.warning(f"[changes] could not remove {rel}: {exc}")
        for d in sorted(new_dirs, key=lambda d: d.count("/"), reverse=True):
            try:
                (self._cwd / d).rmdir()  # only an empty one
            except OSError:
                pass
        return tuple(removed)
