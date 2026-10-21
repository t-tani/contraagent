"""A task's changes: the files one attempt created, modified and deleted under the
patterns its task declares (`agent_task(changes=...)`, `TaskAdapter.changes`).

`ChangesEnricher` is the `ResultEnricher` every `AgentRunner` runs first: before the
dispatch it stamps each file the patterns match under the working directory
(`stamp_of`: its mtime and size, and on POSIX its ctime and inode; and the digest of a
file whose mtime is recent, which a rewrite at the same size within one timestamp tick
would leave as it was), after it compares, sets `TaskResult.changes`, and when the
attempt failed removes the files it created (and the directories it created for
them, once empty), so a retry or a later run starts from the tree as it was. A task
whose kind keeps a failed attempt's files (`keep_failed_changes`) leaves them in place
and lists them (`Changes.kept`): the next attempt starts from the tree with them in it.

A file is attributed to the task whose attempt was running when it changed. Two
tasks running at once under the same pattern cannot be told apart: give each its own
directory (`{unit}` in the pattern) or keep them from overlapping (a unit, a tag).
"""

from __future__ import annotations

import itertools
import logging
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from contraagent._internal.contracts.contract import Stamp, file_digest, recent_digest, stamp_of
from contraagent._internal.dispatch.records import Changes
from contraagent._internal.dispatch.task import Task, TaskResult

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """What the patterns matched before the dispatch: each file's stamp, the digest of
    each file whose stamp was recent (`recent_digests`), and the directories, by path
    relative to the working directory."""

    patterns: tuple[str, ...]
    files: dict[str, Stamp]
    dirs: frozenset[str]
    digests: dict[str, str]


#: What starts a pattern that leaves paths out (`"!.git/**"`).
EXCLUDE = "!"


def split(patterns: Sequence[str]) -> tuple[list[str], list[str]]:
    """`patterns` as the ones that cover paths and the ones that leave paths out, `!` taken off."""
    return [p for p in patterns if not p.startswith(EXCLUDE)], [p[len(EXCLUDE) :] for p in patterns if p.startswith(EXCLUDE)]


def _regex(pattern: str) -> re.Pattern[str]:
    """A `Path.glob` pattern as a regular expression over a POSIX path relative to the
    working directory: `**` any number of segments, `*` and `?` within one, `[...]` a set."""
    segments = pattern.replace("\\", "/").strip("/").split("/")
    out = ""
    for i, seg in enumerate(segments):
        last = i == len(segments) - 1
        if seg == "**" and last:
            out = out[:-1] + "(?:/[^/]+)*" if out else "(?:[^/]+(?:/[^/]+)*)?"
        elif seg == "**":
            out += "(?:[^/]+/)*"
        else:
            out += _segment(seg) + ("" if last else "/")
    return re.compile(out + r"\Z")


def _segment(seg: str) -> str:
    """One segment of a glob pattern as a regular expression that never crosses a `/`."""
    out, j = "", 0
    while j < len(seg):
        c = seg[j]
        end = seg.find("]", j + 2) if c == "[" else -1
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif end != -1:
            body = seg[j + 1 : end].replace("\\", "\\\\")  # a range (`a-z`) stays a range
            out += "[^/" + body[1:] + "]" if body[:1] in ("!", "^") else "[" + body.lstrip("^") + "]"
            j = end
        else:
            out += re.escape(c)
        j += 1
    return out


def matcher(patterns: Sequence[str]) -> Callable[[str], bool]:
    """Whether one of `patterns` (`Path.glob` patterns, with no `!`) matches a POSIX path
    relative to the working directory: the path itself, not a directory it is under."""
    regexes = [_regex(p) for p in patterns]
    return lambda rel: any(r.match(rel) for r in regexes)


def excluded(patterns: Sequence[str], rel: str) -> bool:
    """Whether the `!` patterns among `patterns` leave out `rel` (a POSIX path relative to
    the working directory): it, or a directory it is under, matches one."""
    leaving = split(patterns)[1]
    if not leaving:
        return False
    matches = matcher(leaving)
    parts = rel.split("/")
    return any(matches("/".join(parts[:n])) for n in range(1, len(parts) + 1))


def scan(cwd: Path, patterns: Sequence[str]) -> tuple[dict[str, Stamp], frozenset[str]]:
    """The files `patterns` cover under `cwd`, with their stamps (`stamp_of`), and the
    directories, as POSIX paths relative to `cwd`. A pattern is a `Path.glob` pattern; one
    that matches a directory covers everything under it (`topics/alpha/**`, `topics/alpha`).
    A pattern that starts with `!` leaves out what it matches, and everything under a
    directory it matches, whatever the others cover; the walk does not enter such a
    directory."""
    files: dict[str, Stamp] = {}
    dirs: set[str] = set()
    covering, leaving = split(patterns)

    def add(p: Path) -> None:
        try:
            st = p.stat()
        except OSError:
            return
        files[p.relative_to(cwd).as_posix()] = stamp_of(st)

    if not leaving:
        for pattern in covering:
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

    out = [_regex(p) for p in leaving]
    for pattern in covering:
        inside = _regex(pattern)
        segments = pattern.replace("\\", "/").strip("/").split("/")
        literal = list(itertools.takewhile(lambda s: not any(c in s for c in "*?["), segments))
        base = cwd.joinpath(*literal) if literal else cwd
        rel_base = "/".join(literal)
        if rel_base and excluded(patterns, rel_base):
            continue
        if base.is_file():
            if inside.match(rel_base):
                add(base)
            continue
        if not base.is_dir():
            continue
        covered_at: set[str] = {rel_base} if rel_base and inside.match(rel_base) else set()
        for folder, subdirs, names in os.walk(base):
            rel = Path(folder).relative_to(cwd).as_posix()
            rel = "" if rel == "." else rel
            covered = rel in covered_at
            if covered:
                dirs.add(rel)
            keep = []
            for d in subdirs:
                sub = f"{rel}/{d}" if rel else d
                if any(r.match(sub) for r in out):
                    continue
                keep.append(d)
                if covered or inside.match(sub):
                    covered_at.add(sub)
            subdirs[:] = keep
            for name in names:
                sub = f"{rel}/{name}" if rel else name
                if not any(r.match(sub) for r in out) and (covered or inside.match(sub)):
                    add(Path(folder) / name)
    return files, frozenset(dirs)


def scan_tree(cwd: Path, skip: Callable[[Path], bool]) -> dict[str, Stamp]:
    """Every file under `cwd`, with its stamp (`stamp_of`), by POSIX path relative to `cwd`;
    `skip(path)` leaves out a file or a whole directory. Symbolic links to directories are
    not followed."""
    files: dict[str, Stamp] = {}
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
            files[path.relative_to(cwd).as_posix()] = stamp_of(st)
    return files


def recent_digests(cwd: Path, files: Mapping[str, Stamp], since_ns: int) -> dict[str, str]:
    """The content digest of each of `files` (stamps by path relative to `cwd`, taken at or
    after `since_ns`) whose stamp is recent (`recent_digest`)."""
    out = {}
    for rel, stamp in files.items():
        digest = recent_digest(cwd / rel, stamp, since_ns)
        if digest is not None:
            out[rel] = digest
    return out


def compare(
    before: Mapping[str, Stamp],
    after: Mapping[str, Stamp],
    digests: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Changes:
    """The files created, modified and deleted between two scans. A file is modified when
    its stamp moved, or when `digests` (`recent_digests`, taken with `before`) holds its
    digest and the file under `cwd` no longer has it."""

    def modified(rel: str) -> bool:
        if after[rel] != before[rel]:
            return True
        digest = (digests or {}).get(rel)
        return digest is not None and cwd is not None and file_digest(cwd / rel) != digest

    return Changes(
        created=tuple(sorted(set(after) - set(before))),
        modified=tuple(sorted(p for p in set(after) & set(before) if modified(p))),
        deleted=tuple(sorted(set(before) - set(after))),
    )


class ChangesEnricher:
    """The `ResultEnricher` that records a task's changes, and removes the files a failed
    attempt created. `patterns(task)`: the task's patterns, relative to `cwd`; none, and
    it does nothing. `keep(task)`: True leaves a failed attempt's files in place."""

    def __init__(self, patterns: Callable[[Task], Sequence[str]], cwd: Path, keep: Callable[[Task], bool] = lambda task: False) -> None:
        self._patterns = patterns
        self._cwd = Path(cwd)
        self._keep = keep

    def snapshot(self, task: Task) -> Snapshot | None:
        patterns = tuple(self._patterns(task))
        if not patterns:
            return None
        since = time.time_ns()
        files, dirs = scan(self._cwd, patterns)
        return Snapshot(patterns, files, dirs, recent_digests(self._cwd, files, since))

    def enrich(self, task: Task, before: Snapshot | None, result: TaskResult) -> TaskResult | None:
        if before is None:
            return None
        after, dirs = scan(self._cwd, before.patterns)
        changes = compare(before.files, after, before.digests, self._cwd)
        if not result.ok and changes.created and self._keep(task):
            changes = changes.model_copy(update={"kept": changes.created})
        elif not result.ok and changes.created:
            changes = changes.model_copy(update={"removed": self._remove(changes.created, dirs - before.dirs)})
        return replace(result, changes=changes)

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
