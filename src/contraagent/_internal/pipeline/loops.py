"""The loops of flow code, and the pass of each, counted as the code runs.

A **loop** is a `for` or `while` statement of a generator in flow code, named by
its first line. Its **pass** is one iteration: 1 when the loop is entered, plus 1
each time control goes back to the loop's start (a back edge: the end of the
body, or `continue`), in that frame activation. When a loop goes back to its
start, the passes of the loops inside it are reset: they start again at 1 when
next entered. A comprehension is not a loop: its tasks are a fan-out and have
no pass of their own.

**Static part** (`loops_of(code)`, once per code object). From the function's
source, the `for` and `while` statements (not those of nested functions), each
with its span; the region that runs once per pass excludes a `for`'s iterable
(evaluated once, before the first pass) and an `else` clause. From the
bytecode, the instructions a back edge goes to (a loop's **heads**): a `for`'s
`FOR_ITER`, and a `while`'s first instruction of its test and of its first
statement. Comprehension code is skipped. Code with no source falls back to the
bytecode alone: each backward jump target is a loop (a `for` when the target is a
`FOR_ITER`, else a `while`), named by the target's line; a `while` takes the
smaller line of its target and of its back jumps, which is its `while` line on
every Python version. Targets on one line are one loop. `is_while(file, line)`
says which loops are `while` loops: `max_passes` bounds those only.

**Runtime part** (`LoopCounter`, `counting`). A `sys.monitoring` tool (the
first free id of 3 and 4, named `contraagent`) receives the `JUMP` events of
the process while a counter is active. A jump that is not a backward jump to a
head of flow code returns `DISABLE`, so each such location reports once and
never again; a back edge to a head adds a pass to its loop for the jumping
frame. The counts belong to the active `LoopCounter` (a context variable) and,
within it, to the flow call whose code is running, and are dropped when that
flow call ends. The tool id is freed when the last counter stops. With no free
tool id nothing is counted and every pass is None.

Cost: about 1 µs per back edge in flow code; nothing per back edge elsewhere
after the first.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import dis
import inspect
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import CodeType, FrameType

from contraagent._internal.dispatch.records import Loop
from contraagent._internal.pipeline.origin import flow_code

#: The tool ids tried, in order: 0, 1, 2 and 5 are the debugger's, coverage's, the profiler's and the optimizer's.
TOOL_IDS = (3, 4)
TOOL_NAME = "contraagent"

Pos = tuple[int, int]  # (line, column)


@dataclass(frozen=True)
class _Loop:
    line: int  # its first line: its name
    start: Pos
    end: Pos
    once: tuple[tuple[Pos, Pos], ...]  # spans inside it that do not run once per pass: a `for`'s iterable, an `else`
    inner: tuple[int, ...]  # the lines of the loops inside it
    while_: bool = False  # a `while` loop (`max_passes` bounds these only)
    test: tuple[Pos, Pos] | None = None  # a `while`'s test
    body: int | None = None  # a `while`: the offset of its first statement's first instruction


@dataclass
class _Code:
    """What one code object's loops are."""

    loops: dict[int, _Loop] = field(default_factory=dict)  # by line
    heads: dict[int, int] = field(default_factory=dict)  # instruction offset -> loop line
    ranges: dict[int, tuple[int, int]] = field(default_factory=dict)  # bytecode only: loop line -> (first, last offset)
    positions: list = field(default_factory=list)  # per instruction (offset // 2): (line, end line, col, end col)


_NONE = _Code()
_codes: dict[CodeType, _Code] = {}
_whiles: set[tuple[str, int]] = set()  # (file, line) of each `while` loop of the code analysed


def is_while(file: str, line: int) -> bool:
    """Whether the loop of flow code at `file:line` is a `while` loop (`max_passes` bounds
    these; a `for` loop ends with its iterable)."""
    return (file, line) in _whiles


def loops_of(code: CodeType) -> _Code:
    """The loops of a generator's code in flow code; none for any other code."""
    info = _codes.get(code)
    if info is None:
        info = _codes[code] = _analyse(code) if code.co_flags & inspect.CO_GENERATOR and flow_code(code.co_filename) else _NONE
        _whiles.update((code.co_filename, loop.line) for loop in info.loops.values() if loop.while_)
    return info


def _analyse(code: CodeType) -> _Code:
    try:
        instructions = list(dis.get_instructions(code))
    except Exception:
        return _NONE
    info = _from_source(code, instructions)
    if info is None:
        info = _from_bytecode(instructions)
    if info.loops:
        info.positions = list(code.co_positions())
    return info


def _span(node: ast.AST, offset: int) -> tuple[Pos, Pos]:
    end_line = node.end_lineno if node.end_lineno is not None else node.lineno  # type: ignore[attr-defined]
    end_col = node.end_col_offset if node.end_col_offset is not None else 10**6  # type: ignore[attr-defined]
    return (node.lineno + offset, node.col_offset), (end_line + offset, end_col)  # type: ignore[attr-defined]


def _inside(p: tuple[Pos, Pos], span: tuple[Pos, Pos]) -> bool:
    return span[0] <= p[0] and p[1] <= span[1]


def _pos(ins: dis.Instruction) -> tuple[Pos, Pos] | None:
    p = ins.positions
    if p is None or p.lineno is None or p.col_offset is None:
        return None
    return (p.lineno, p.col_offset), (p.end_lineno or p.lineno, p.end_col_offset if p.end_col_offset is not None else p.col_offset)


def _from_source(code: CodeType, instructions: list[dis.Instruction]) -> _Code | None:
    """Loops and heads from the function's AST; None when its source cannot be read."""
    try:
        lines, first = inspect.getsourcelines(code)
        tree = ast.parse(textwrap.dedent("".join(lines)))
    except (OSError, TypeError, SyntaxError, IndentationError):
        return None
    func = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if func is None or func.name != code.co_name:
        return None
    # The source is dedented, so its columns are off by the indentation of its first line.
    indent = len(lines[0]) - len(lines[0].lstrip())
    offset = first - 1

    def span(node: ast.AST) -> tuple[Pos, Pos]:
        (sl, sc), (el, ec) = _span(node, offset)
        return (sl, sc + indent), (el, ec + indent)

    found: list[ast.For | ast.While] = []
    comprehensions: list[tuple[Pos, Pos]] = []
    stack: list[ast.AST] = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue  # another code object
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            comprehensions.append(span(node))
            continue
        if isinstance(node, (ast.For, ast.While)):
            found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    if not found:
        return _Code()
    spans = {id(n): span(n) for n in found}
    info = _Code()
    for n in found:
        s = spans[id(n)]
        once = [span(n.iter)] if isinstance(n, ast.For) else []
        if n.orelse:
            once.append((span(n.orelse[0])[0], span(n.orelse[-1])[1]))
        inner = tuple(m.lineno + offset for m in found if m is not n and _inside(spans[id(m)], s))
        info.loops[n.lineno + offset] = _Loop(n.lineno + offset, s[0], s[1], tuple(once), inner, isinstance(n, ast.While))

    def in_comprehension(p: tuple[Pos, Pos]) -> bool:
        return any(_inside(p, c) for c in comprehensions)

    def innermost(p: tuple[Pos, Pos], kinds: tuple[type, ...]) -> ast.For | ast.While | None:
        around = [n for n in found if isinstance(n, kinds) and _inside(p, spans[id(n)])]
        return max(around, key=lambda n: spans[id(n)][0], default=None)

    for ins in instructions:  # a `for` goes back to its FOR_ITER
        p = _pos(ins)
        if ins.opname != "FOR_ITER" or p is None or in_comprehension(p):
            continue
        loop = innermost(p, (ast.For,))
        if loop is not None:
            info.heads.setdefault(ins.offset, loop.lineno + offset)
    for n in found:  # a `while` goes back to its test or to its first statement
        if not isinstance(n, ast.While):
            continue
        firsts = []
        for part in (n.test, n.body[0]):
            s = span(part)
            at = [ins.offset for ins in instructions if (p := _pos(ins)) is not None and _inside(p, s) and not in_comprehension(p)]
            firsts.append(min(at) if at else None)
            if at:
                info.heads.setdefault(min(at), n.lineno + offset)
        line = n.lineno + offset
        info.loops[line] = dataclasses.replace(info.loops[line], test=span(n.test), body=firsts[1])
    return info


def _from_bytecode(instructions: list[dis.Instruction]) -> _Code:
    """Loops from backward jumps alone: each target is a loop, named by its line, spanning
    the offsets from it to its last backward jump."""
    line_at: dict[int, int] = {}
    last = 0
    for ins in instructions:
        p = ins.positions
        last = p.lineno if p is not None and p.lineno is not None else last
        line_at[ins.offset] = last
    for_heads = {ins.offset for ins in instructions if ins.opname == "FOR_ITER"}
    ends: dict[int, int] = {}
    lines: dict[int, int] = {}
    for ins in instructions:
        if _backward(ins):
            target = int(ins.argval)
            ends[target] = max(ends.get(target, 0), ins.offset)
            # A `for` goes back to its FOR_ITER, on its line. A `while` goes back to its
            # test, or (before 3.14) to its body from a copy of the test: the smaller
            # line of target and jump is the `while` line in both.
            here = line_at.get(target, 0)
            lines[target] = here if target in for_heads else min(lines.get(target, here), line_at.get(ins.offset, here))
    info = _Code()
    for target, end in sorted(ends.items()):
        line = lines[target]
        a, b = info.ranges.get(line, (target, end))  # targets on one line are one loop
        info.ranges[line] = (min(a, target), max(b, end))
        info.heads[target] = line
    for line, (a, b) in info.ranges.items():
        inner = tuple(m for m, (c, d) in info.ranges.items() if m != line and a <= c and d <= b)
        info.loops[line] = _Loop(line, (0, 0), (0, 0), (), inner, a not in for_heads)
    return info


def _backward(ins: dis.Instruction) -> bool:
    """A backward jump that may close a loop: not `JUMP_BACKWARD_NO_INTERRUPT`, the send
    loop of `yield from` and `await`."""
    return "JUMP" in ins.opname and ins.opname != "JUMP_BACKWARD_NO_INTERRUPT" and isinstance(ins.argval, int) and ins.argval < ins.offset


def around(info: _Code, f: FrameType) -> list[tuple[int, int]]:
    """The loops of `info` whose pass `f` is in, outermost first: (line, 1 when `f` is in a
    `while`'s test after its body, which comes before the back edge, else 0)."""
    if info.ranges:
        return [(line, 0) for line, (a, b) in sorted(info.ranges.items(), key=lambda kv: kv[1][0]) if a <= f.f_lasti <= b]
    p = info.positions[f.f_lasti // 2] if 0 <= f.f_lasti // 2 < len(info.positions) else None
    if p is not None and p[0] is not None and p[2] is not None:
        here: tuple[Pos, Pos] = ((p[0], p[2]), (p[1] or p[0], p[3] if p[3] is not None else p[2]))
    else:
        line = f.f_lineno or 0
        here = ((line, 0), (line, 0))
    out = []
    for loop in info.loops.values():
        if _inside(here, (loop.start, loop.end)) and not any(_inside(here, s) for s in loop.once):
            out.append(loop)
    # A `while`'s test is compiled again after its body on some versions: evaluated there,
    # it belongs to the next pass, though the back edge that counts it comes after it.
    return [
        (loop.line, int(loop.test is not None and loop.body is not None and f.f_lasti > loop.body and _inside(here, loop.test)))
        for loop in sorted(out, key=lambda loop: loop.start)
    ]


# --- counting ----------------------------------------------------------------------


class LoopCounter:
    """The passes of the loops of flow code, per frame, for one run.

    `current()` names the flow call whose code is running (its counts are dropped with
    `drop(call)` when it ends). `loops(frame)`: the loops whose pass the frame is in,
    outermost first, with their passes (None while nothing is counted).
    """

    def __init__(self, current: Callable[[], object] = lambda: None) -> None:
        self._current = current
        self._counts: dict[FrameType, dict[int, int]] = {}
        self._frames: dict[object, list[FrameType]] = {}
        self.active = False

    def loops(self, f: FrameType) -> tuple[Loop, ...]:
        info = loops_of(f.f_code)
        if not info.loops:
            return ()
        counts = self._counts.get(f, {})
        return tuple(Loop(line=line, pass_=counts.get(line, 1) + ahead if self.active else None) for line, ahead in around(info, f))

    def drop(self, call: object) -> None:
        """Forget the counts of the frames of flow call `call`."""
        for f in self._frames.pop(call, ()):
            self._counts.pop(f, None)

    def clear(self) -> None:
        self._counts.clear()
        self._frames.clear()

    def _back_edge(self, f: FrameType, info: _Code, line: int) -> None:
        counts = self._counts.get(f)
        if counts is None:
            counts = self._counts[f] = {}
            self._frames.setdefault(self._current(), []).append(f)
        counts[line] = counts.get(line, 1) + 1
        for inner in info.loops[line].inner:
            counts.pop(inner, None)


_active: ContextVar[LoopCounter | None] = ContextVar("contraagent_loop_counter", default=None)
_lock = threading.Lock()
_users = 0
_tool: int | None = None


@contextlib.contextmanager
def counting(counter: LoopCounter) -> Iterator[LoopCounter]:
    """Count the passes of the flow code this thread runs into `counter` until the block ends."""
    _acquire()
    token = _active.set(counter)
    counter.active = _tool is not None
    try:
        yield counter
    finally:
        _active.reset(token)
        counter.active = False
        counter.clear()
        _release()


def _acquire() -> None:
    global _users, _tool
    with _lock:
        _users += 1
        if _users > 1:
            return
        mon = sys.monitoring
        for tool in TOOL_IDS:
            try:
                mon.use_tool_id(tool, TOOL_NAME)
            except ValueError:  # in use by another tool
                continue
            mon.register_callback(tool, mon.events.JUMP, _on_jump)
            mon.set_events(tool, mon.events.JUMP)
            _tool = tool
            return


def _release() -> None:
    global _users, _tool
    with _lock:
        _users -= 1
        if _users > 0 or _tool is None:
            return
        mon = sys.monitoring
        mon.set_events(_tool, 0)
        mon.register_callback(_tool, mon.events.JUMP, None)
        mon.free_tool_id(_tool)
        _tool = None


def _on_jump(code: CodeType, src: int, dst: int) -> object:
    info = _codes.get(code)
    if info is None:
        info = loops_of(code)
    line = info.heads.get(dst) if dst < src else None
    if line is None:
        return sys.monitoring.DISABLE  # never a back edge of flow code: not reported again
    counter = _active.get()
    if counter is not None:
        counter._back_edge(sys._getframe(1), info, line)
    return None
