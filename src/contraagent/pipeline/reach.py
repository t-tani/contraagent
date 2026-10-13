"""The task declarations a flow's code can reach, found without running it.

A generator flow creates tasks as it runs, so the kinds of a run are known
only at its end. Its code says which it can create: `reachable(flow, ...)`
follows what the code of each function refers to, starting from the roots
(the flow and its arguments), and returns every `AgentTask` and `PythonTask`
it meets, in the order it meets them.

What a function's code refers to: the global names its code (and the code
nested in it: inner functions, lambdas, comprehensions) uses, an attribute
of a module it uses by one of those names (`tasks.review`), the values its
closure holds, and its default arguments. Each value found is followed the
same way when it is a function of flow code (`origin.flow_code`), a bound
method, a `functools.partial`, an object whose class defines `__call__` in
flow code, or a list, tuple, set or dict (its items). A Python task's own
function is not followed: it runs as a task and creates none.

A task declared while the flow runs (inside the flow's body) is not reached;
`Pipeline` routes it when it is created. What is reached is what the flow can
create, not what it creates: a function's default argument and the
declaration its caller passes instead are both reached (`Graph.reached`,
`Graph.declare`).
"""

from __future__ import annotations

import functools
from collections import deque
from collections.abc import Iterable
from types import BuiltinFunctionType, CodeType, FunctionType, MethodType, ModuleType
from typing import Any

from contraagent.pipeline.origin import flow_code
from contraagent.pipeline.spec import AgentTask, PythonTask


def reachable(*roots: Any) -> list[AgentTask | PythonTask]:
    """The task declarations reachable from `roots`, in the order found (each once)."""
    found: list[AgentTask | PythonTask] = []
    seen: set[int] = set()
    keep: list[Any] = []  # what `seen` names stays alive, so an id is not reused
    work: deque[Any] = deque(roots)
    while work:
        obj = work.popleft()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        keep.append(obj)
        if isinstance(obj, (AgentTask, PythonTask)):
            found.append(obj)
        elif isinstance(obj, FunctionType):
            work.extend(_function_refs(obj))
        elif isinstance(obj, MethodType):
            work.append(obj.__func__)
        elif isinstance(obj, functools.partial):
            work.extend((obj.func, *obj.args, *obj.keywords.values()))
        elif isinstance(obj, dict):
            work.extend(obj.values())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            work.extend(obj)
        elif not isinstance(obj, (type, ModuleType, BuiltinFunctionType, str, bytes, int, float)) and _own_call(obj):
            work.append(type(obj).__call__)
    return found


def _function_refs(fn: FunctionType) -> Iterable[Any]:
    """What a function of flow code refers to; nothing for any other function."""
    if not flow_code(fn.__code__.co_filename):
        return []
    refs: list[Any] = []
    refs += _code_refs(fn.__code__, fn.__globals__)
    refs += [cell.cell_contents for cell in fn.__closure__ or () if _filled(cell)]
    refs += list(fn.__defaults__ or ())
    refs += list((fn.__kwdefaults__ or {}).values())
    wrapped = getattr(fn, "__wrapped__", None)
    if wrapped is not None:
        refs.append(wrapped)
    return refs


def _code_refs(code: CodeType, globals_: dict[str, Any]) -> list[Any]:
    """The globals `code` and the code nested in it name, and those names' attributes of
    the modules among them (`pkg.sub.task`: `pkg`, then `sub`, then `task`)."""
    names: dict[str, None] = {}
    stack = [code]
    while stack:
        c = stack.pop()
        names.update(dict.fromkeys(c.co_names))
        stack += [k for k in c.co_consts if isinstance(k, CodeType)]
    refs = [globals_[n] for n in names if n in globals_]
    modules = [m for m in refs if isinstance(m, ModuleType)]
    seen = {id(m) for m in modules}
    while modules:
        module = modules.pop()
        for n in names:
            value = getattr(module, n, None)
            if value is None or id(value) in seen:
                continue
            refs.append(value)
            if isinstance(value, ModuleType):
                seen.add(id(value))
                modules.append(value)
    return refs


def _filled(cell: Any) -> bool:
    try:
        cell.cell_contents  # noqa: B018 (an empty cell raises)
    except ValueError:
        return False
    return True


def _own_call(obj: Any) -> bool:
    """An instance whose class defines `__call__` in flow code."""
    call = getattr(type(obj), "__call__", None)  # noqa: B004 (the class's, not the instance's)
    return isinstance(call, FunctionType) and flow_code(call.__code__.co_filename)
