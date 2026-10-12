"""The one place the monitor turns a client-supplied name into a path.

Run ids and task keys arrive as URL segments and query parameters, and each
becomes part of a file path (`runs/<run>/journal.jsonl`,
`runs/<run>/streams/<task>.stream.jsonl`). Joined unchecked, `run=../x`
reads outside the runs directory. Every join goes through `under`, which
accepts only plain names and also checks the resolved path, so a symlink or
a name this check did not foresee still cannot leave `root`.
"""

from __future__ import annotations

from pathlib import Path


class BadName(ValueError):
    """A run id or task key that is not a plain name. The HTTP layer answers it with 404."""


def check_name(name: str, what: str = "name") -> str:
    """`name` itself when it is a plain file-name component, else `BadName`.

    Plain means: not empty, no path separator or NUL, no control character,
    no leading `.` and no `..` anywhere. Task keys legitimately contain
    `:` (`python:prepare-alpha`), `@`, `-`, `_` and `.`, so the check forbids
    what makes a name a path rather than whitelisting what a domain may use.
    """
    if (
        not isinstance(name, str)
        or not name
        or name.startswith(".")
        or ".." in name
        or any(c in name for c in "/\\\0")
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        raise BadName(f"not a plain {what}: {name!r}")
    return name


def under(root: Path, *names: str, what: str = "name") -> Path:
    """`root/names...`, each checked by `check_name`, and refused when the
    resolved result is not inside `root`."""
    path = root.joinpath(*(check_name(n, what) for n in names))
    base = root.resolve()
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise BadName(f"{what} {names[-1]!r} leaves {root}")
    return path
