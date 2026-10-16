"""The one place a name from outside becomes part of a path.

Run ids, task keys and layout names arrive as URL segments, query parameters and
relays' requests, and each becomes part of a file path (`runs/<run>/journal.jsonl`,
`runs/<run>/streams/<file>.stream.jsonl`). Joined unchecked, `run=../x` reads outside
the runs directory. Every join goes through `under`, which accepts only plain names and
also checks the resolved path, so a symlink or a name this check did not foresee still
cannot leave `root`. (`DirectorySource` reads an entry directly in a run directory by
two `lstat`s instead: no symbolic link on the way, so plain names stay under `root`.)
"""

from __future__ import annotations

import re
from pathlib import Path

_NOT_PLAIN = re.compile(r"[\x00-\x1f\x7f/\\]|\.\.|^\.")


class BadName(ValueError):
    """A run id, task key or file name that is not a plain name. The HTTP layer answers it with 404."""


def is_plain(name: object) -> bool:
    """Whether `name` is a plain file-name component: a non-empty str with no path
    separator, NUL or other control character, no leading `.` and no `..` anywhere.

    Task keys legitimately contain `:` (`python:prepare-alpha`), `@`, `-`, `_` and `.`, so
    the check forbids what makes a name a path rather than allowing what a domain may use."""
    return isinstance(name, str) and bool(name) and _NOT_PLAIN.search(name) is None


#: What Windows refuses in a file name that `is_plain` lets through: one of `<>:"|?*`, a
#: trailing `.` or space, a device name (`CON`, `nul.txt`, `COM1`) whatever its case and suffix.
_NOT_PORTABLE = re.compile(r'[<>:"|?*]|[. ]$|^(CON|PRN|AUX|NUL|COM[0-9\u00b9\u00b2\u00b3]|LPT[0-9\u00b9\u00b2\u00b3])(\.|$)', re.IGNORECASE)


def is_portable(name: object) -> bool:
    """Whether `name` is a plain name (`is_plain`) that is also a file name on every
    operating system: no `<`, `>`, `:`, `"`, `|`, `?` or `*`, no trailing `.` or space,
    and not a Windows device name such as `CON`, `NUL` or `COM1` (with any suffix, in
    any case). A run id must be one, so that a pipeline written on one system runs on
    the others."""
    return isinstance(name, str) and is_plain(name) and _NOT_PORTABLE.search(name) is None


def check_portable(name: str, what: str = "name") -> str:
    """`name` itself when it is portable (`is_portable`), else ValueError naming the fault."""
    if not is_portable(name):
        raise ValueError(
            f"{what} {name!r} is not a file name on every operating system: use letters, digits, '-', '_' and '.', "
            "with no leading '.', no '..', no trailing '.' or space, and no Windows device name (CON, NUL, COM1)"
        )
    return name


def safe_chars(name: str) -> str:
    """`name` with every character but a letter, a digit, `-`, `_` and `.` turned into
    `_`, as are a leading `.` and each `..`; `_` for an empty name. A plain name."""
    name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    name = re.sub(r"\.\.+", lambda m: "_" * len(m.group()), name)
    return "_" + name[1:] if name.startswith(".") else name or "_"


def portable(name: str) -> str:
    """`name` made portable (`is_portable`): `safe_chars`, then a trailing `.` turned into
    `_` and `_` put before a device name (`<lambda>` → `_lambda_`, `con` → `_con`)."""
    name = safe_chars(name)
    if name.endswith("."):
        name = name[:-1] + "_"
    return "_" + name if _NOT_PORTABLE.search(name) else name


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
