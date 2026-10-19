"""Which code is flow code: the rule `FlowDriver` numbers flow calls by, and the flow path
(`pipeline/origin.py`) keeps frames by.

`flow_code(filename)` holds for code that is neither contraagent's own (its shipped
examples excepted) nor the standard library. Installed packages are flow code, so a
pipeline installed as a package, and the examples shipped with contraagent, count like
any other. `loop_runner(frame)` is the frame that runs one callback of an asyncio event
loop: the bottom of every asyncio Task's stack.
"""

from __future__ import annotations

import asyncio.events
import sysconfig
from pathlib import Path
from types import FrameType

_PACKAGE = Path(__file__).resolve().parents[2]
_EXAMPLES = _PACKAGE / "docs" / "examples"
_STDLIB = tuple({Path(p).resolve() for name in ("stdlib", "platstdlib") if (p := sysconfig.get_paths().get(name))})
_RUN_CALLBACK = asyncio.events.Handle._run.__code__

_paths: dict[str, Path | None] = {}


def path_of(filename: str) -> Path | None:
    """`filename` resolved, once; None for code with no file (`<string>`)."""
    if filename not in _paths:
        _paths[filename] = None if filename.startswith("<") else Path(filename).resolve()
    return _paths[filename]


def flow_code(filename: str) -> bool:
    """Whether code from `filename` is flow code: neither contraagent's own (its shipped
    examples excepted) nor the standard library. Code with no file (`<string>`) is."""
    return not contraagent_file(filename) and not stdlib_file(filename)


def contraagent_file(filename: str) -> bool:
    """contraagent's own code, its shipped examples excepted."""
    path = path_of(filename)
    return path is not None and path.is_relative_to(_PACKAGE) and not path.is_relative_to(_EXAMPLES)


def stdlib_file(filename: str) -> bool:
    path = path_of(filename)
    return path is not None and any(path.is_relative_to(p) for p in _STDLIB) and "site-packages" not in path.parts


def loop_runner(f: FrameType) -> bool:
    """Whether `f` runs one callback of an asyncio event loop (a step of a Task): no frame
    below it belongs to the Task's code."""
    return f.f_code is _RUN_CALLBACK
