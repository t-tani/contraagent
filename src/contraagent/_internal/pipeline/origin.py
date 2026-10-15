"""Where flow code created a task: its frames, and the loops around each call site.

`frames_here(start, loops)` walks the stack from a task call outward and keeps
the frames of flow code, outermost first. The walk starts at the first frame
outside `contraagent/pipeline/` (the task call itself) and ends at the first
frame of contraagent's own code below it (`Pipeline.run` for a flow that does
not yield, `FlowDriver` for a step of a flow call). Frames of the standard
library and comprehension frames between the two are skipped: they hold no flow
code. Installed packages are kept, so a pipeline installed as a package, and the
examples shipped with contraagent, are recorded like any other.

`generator_frames(gen, loops)` are the frames of a suspended generator and its
`yield from` chain: where a parent flow call yielded a child.

`loops(frame)` gives a frame's loops with their passes (`LoopCounter.loops`,
`loops.py`); without it, frames have no loops.

`flow_code(filename)` is that rule for one file: neither contraagent's own
code (its examples excepted) nor the standard library.
"""

from __future__ import annotations

import sysconfig
from collections.abc import Callable
from pathlib import Path
from types import FrameType, GeneratorType

from contraagent._internal.dispatch.records import Frame, Loop

_PACKAGE = Path(__file__).resolve().parents[2]
_PIPELINE = Path(__file__).resolve().parent
_EXAMPLES = _PACKAGE / "docs" / "examples"
_STDLIB = tuple({Path(p).resolve() for name in ("stdlib", "platstdlib") if (p := sysconfig.get_paths().get(name))})
_COMPREHENSIONS = frozenset({"<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>"})

_paths: dict[str, Path | None] = {}


LoopsOf = Callable[[FrameType], tuple[Loop, ...]]


def frames_here(start: FrameType | None, loops: LoopsOf | None = None) -> tuple[Frame, ...]:
    """The frames of flow code from `start` (a frame in the task call) outward, outermost first."""
    f = start
    while f is not None and _within(f, _PIPELINE):
        f = f.f_back
    out: list[Frame] = []
    while f is not None and not _contraagent(f):
        if f.f_code.co_name not in _COMPREHENSIONS and not _stdlib(f):
            out.append(frame_of(f, loops))
        f = f.f_back
    return tuple(reversed(out))


def generator_frames(gen: GeneratorType, loops: LoopsOf | None = None) -> tuple[Frame, ...]:
    """Where `gen` is suspended: its frame, then each generator of its `yield from` chain."""
    out: list[Frame] = []
    g: object = gen
    while isinstance(g, GeneratorType) and g.gi_frame is not None:
        out.append(frame_of(g.gi_frame, loops))
        g = g.gi_yieldfrom
    return tuple(out)


def frame_of(f: FrameType, loops: LoopsOf | None = None) -> Frame:
    code = f.f_code
    module = f.f_globals.get("__name__", "")
    function = f"{module}.{code.co_qualname}" if module else code.co_qualname
    line = f.f_lineno or code.co_firstlineno
    return Frame(function=function, file=code.co_filename, line=line, loops=loops(f) if loops is not None else ())


def _path(filename: str) -> Path | None:
    if filename not in _paths:
        _paths[filename] = None if filename.startswith("<") else Path(filename).resolve()
    return _paths[filename]


def _within(f: FrameType, root: Path) -> bool:
    path = _path(f.f_code.co_filename)
    return path is not None and path.is_relative_to(root)


def _contraagent(f: FrameType) -> bool:
    return _contraagent_file(f.f_code.co_filename)


def _stdlib(f: FrameType) -> bool:
    return _stdlib_file(f.f_code.co_filename)


def flow_code(filename: str) -> bool:
    """Whether code from `filename` is flow code: neither contraagent's own (its shipped
    examples excepted) nor the standard library. Code with no file (`<string>`) is."""
    return not _contraagent_file(filename) and not _stdlib_file(filename)


def _contraagent_file(filename: str) -> bool:
    """contraagent's own code, its shipped examples excepted."""
    path = _path(filename)
    return path is not None and path.is_relative_to(_PACKAGE) and not path.is_relative_to(_EXAMPLES)


def _stdlib_file(filename: str) -> bool:
    path = _path(filename)
    return path is not None and any(path.is_relative_to(p) for p in _STDLIB) and "site-packages" not in path.parts
