"""The one place a name from outside becomes part of a path.

Run ids, task keys and layout names arrive as URL segments, query parameters and
relays' requests, and each becomes part of a file path (`runs/<run>/journal.jsonl`,
`runs/<run>/streams/<file>.stream.jsonl`). Joined unchecked, `run=../x` reads outside
the runs directory. Every join goes through `under`, which accepts only plain names and
also checks the resolved path, so a symlink or a name this check did not foresee still
cannot leave `root`.
"""

from __future__ import annotations

from pathlib import Path


class BadName(ValueError):
    """A run id, task key or file name that is not a plain name. The HTTP layer answers it with 404."""


def is_plain(name: object) -> bool:
    """Whether `name` is a plain file-name component: a non-empty str with no path
    separator, NUL or other control character, no leading `.` and no `..` anywhere.

    Task keys legitimately contain `:` (`python:prepare-alpha`), `@`, `-`, `_` and `.`, so
    the check forbids what makes a name a path rather than allowing what a domain may use."""
    return (
        isinstance(name, str)
        and bool(name)
        and not name.startswith(".")
        and ".." not in name
        and not any(c in name for c in "/\\\0")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
    )


def check_name(name: str, what: str = "name") -> str:
    """`name` itself when it is a plain name (`is_plain`), else `BadName`."""
    if not is_plain(name):
        raise BadName(f"not a plain {what}: {name!r}")
    return name


def entry_parts(name: str) -> tuple[str, ...]:
    """A layout name (`streams/<file>.stream.jsonl`) as its checked parts."""
    return tuple(check_name(p, "file name") for p in name.split("/"))


def under(root: Path, *names: str, what: str = "name") -> Path:
    """`root/names...`, each checked by `check_name`, and refused when the resolved
    result is not inside `root`."""
    path = root.joinpath(*(check_name(n, what) for n in names))
    base = root.resolve()
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise BadName(f"{what} {names[-1]!r} leaves {root}")
    return path
