"""Where flow code created a task: its frames, and the loops around each call site.

`frames_here(start, loops)` walks the stack from `start` outward and keeps the frames
of flow code, outermost first. The walk starts at the first frame of flow code (past
the task call itself, or past the event loop's task factory) and ends at the first
frame of contraagent's own code below it (`Pipeline.run_async` for a flow that does not
wait), or at the bottom of an asyncio Task's stack (the event loop's callback runner)
for the code of a flow call. Within one Task, the coroutines of an `await` chain are
all on the stack, the awaiting ones below. Frames of the standard library and
comprehension frames between the two ends are skipped: they hold no flow code.
Installed packages are kept, so a pipeline installed as a package, and the examples
shipped with contraagent, are recorded like any other.

`suspended_frames(coro, loops)` are the frames of flow code of a suspended coroutine and
of each coroutine it awaits (its `cr_await` chain): where a flow call waits.

`loops(frame)` gives a frame's loops with their passes (`LoopCounter.loops`,
`loops.py`); without it, frames have no loops.

`flow_code(filename)` is that rule for one file: neither contraagent's own code (its
examples excepted) nor the standard library (`dispatch/code.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from types import FrameType
from typing import Any

from contraagent._internal.dispatch import flow
from contraagent._internal.dispatch.code import contraagent_file, flow_code, loop_runner, stdlib_file
from contraagent._internal.dispatch.records import Frame, Loop

__all__ = ["LoopsOf", "flow_code", "frame_of", "frames_here", "suspended_frames"]

_COMPREHENSIONS = frozenset({"<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>"})


LoopsOf = Callable[[FrameType], tuple[Loop, ...]]


def frames_here(start: FrameType | None, loops: LoopsOf | None = None) -> tuple[Frame, ...]:
    """The frames of flow code from `start` (a frame in the task call, or in the code that
    creates a Task) outward, outermost first."""
    f = start
    while f is not None and not loop_runner(f) and (_contraagent(f) or _stdlib(f)):
        f = f.f_back
    out: list[Frame] = []
    while f is not None and not _contraagent(f) and not loop_runner(f):
        if f.f_code.co_name not in _COMPREHENSIONS and not _stdlib(f):
            out.append(frame_of(f, loops))
        f = f.f_back
    return tuple(reversed(out))


def suspended_frames(coro: Any, loops: LoopsOf | None = None) -> tuple[Frame, ...]:
    """Where `coro` waits: the frames of flow code of it and of each coroutine of its
    `cr_await` chain, outermost first."""
    return tuple(frame_of(f, loops) for f in flow.suspended_frames(coro) if flow_code(f.f_code.co_filename))


def frame_of(f: FrameType, loops: LoopsOf | None = None) -> Frame:
    code = f.f_code
    module = f.f_globals.get("__name__", "")
    function = f"{module}.{code.co_qualname}" if module else code.co_qualname
    line = f.f_lineno or code.co_firstlineno
    return Frame(function=function, file=code.co_filename, line=line, loops=loops(f) if loops is not None else ())


def _contraagent(f: FrameType) -> bool:
    return contraagent_file(f.f_code.co_filename)


def _stdlib(f: FrameType) -> bool:
    return stdlib_file(f.f_code.co_filename)
