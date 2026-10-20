"""How a public module publishes what it re-exports.

A public module (`contraagent`, `contraagent.config`, ...) holds no definitions: it
imports names from `_internal` and calls `publish(__name__, __all__)`. Each class and
function, and each function a class defines (its methods and properties), then names that
module as its `__module__`, so a repr, a traceback, pickle, `help()` and the documentation
show the one path a user imports it from.

A class's annotations are strings (`from __future__ import annotations`) that resolve in
the module that defines it; `typing.get_type_hints` and pydantic look them up in the
module `__module__` names. So before a class moves, its own annotations, and its
dataclass fields' types, are resolved where they were written. This stays safe while
every reader of annotations (`inspect.get_annotations`, and on 3.14 `annotationlib` in
each format) gives the dict put in their place, and a pydantic model rebuilt after the move
resolves each field to the same type; `tests/test_public_api.py` checks both on each
Python version CI runs. A class whose annotations are not in its `__dict__` (a
`NamedTuple` on 3.14, which keeps an `__annotate__` function) is left as it is.

A name that leaves a public module stays readable there for a deprecation period: the
module sets `__getattr__ = migration(__name__, moved={...}, removed={...})`. A moved name
warns `ContraagentDeprecationWarning` and gives the object from its new home; a removed
name raises `AttributeError` saying what to use instead.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import sys
import warnings
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from contraagent._internal.errors import ContraagentDeprecationWarning

_INTERNAL = __name__.rpartition(".")[0]


def publish(module: str, names: Iterable[str]) -> None:
    """Make `module` the home of each of `names` it holds that `_internal` defines."""
    namespace = vars(sys.modules[module])
    for name in names:
        obj = namespace[name]
        if not (inspect.isclass(obj) or inspect.isfunction(obj)):
            continue
        if not getattr(obj, "__module__", "").startswith(f"{_INTERNAL}."):
            continue
        if inspect.isclass(obj):
            _resolve_annotations(obj)
            _publish_members(obj, module)
        obj.__module__ = module


def _publish_members(cls: type, module: str) -> None:
    """Make `module` the home of the functions `cls` defines (methods, class and static
    methods, properties), so `help()` of one names the public module too."""
    for member in vars(cls).values():
        if isinstance(member, (classmethod, staticmethod)):
            member = member.__func__
        functions = [member.fget, member.fset, member.fdel] if isinstance(member, property) else [member]
        for fn in functions:
            if inspect.isfunction(fn) and fn.__module__.startswith(f"{_INTERNAL}."):
                fn.__module__ = module


def _resolve_annotations(cls: type) -> None:
    own = cls.__dict__.get("__annotations__")
    if not own:
        return
    globalns = vars(sys.modules[cls.__module__])
    localns: dict[str, Any] = {**vars(cls), cls.__name__: cls}
    params = getattr(cls, "__type_params__", ())
    localns.update({p.__name__: p for p in params})
    resolved = {}
    for name, value in own.items():
        if isinstance(value, str):
            try:
                value = eval(value, globalns, localns)
            except Exception:
                pass  # a name only a type checker sees: stays a string
        resolved[name] = value
    cls.__annotations__ = resolved
    if dataclasses.is_dataclass(cls):
        for field in cls.__dict__.get("__dataclass_fields__", {}).values():
            if field.name in own and isinstance(field.type, str):
                field.type = resolved[field.name]


def migration(
    module: str,
    *,
    moved: Mapping[str, str] | None = None,
    removed: Mapping[str, str] | None = None,
    fallback: Callable[[str], Any] | None = None,
) -> Callable[[str], Any]:
    """A `__getattr__` for public module `module` that answers for the names that left it.

    `moved`: an old name -> its new home, `"contraagent.engine:Run"`; reading the old name
    warns `ContraagentDeprecationWarning` and gives that object. `removed`: an old name ->
    what to use instead, in words; reading it raises `AttributeError` saying so.
    `fallback`: the module's own `__getattr__` for any other name (a name imported when
    first used); without it, any other name raises the usual `AttributeError`."""
    moved = dict(moved or {})
    removed = dict(removed or {})
    if overlap := sorted(set(moved) & set(removed)):
        raise ValueError(f"{module}: {', '.join(overlap)} both moved and removed")
    for name, target in moved.items():
        if target.count(":") != 1:
            raise ValueError(f"{module}.{name}: {target!r} is not 'module:name'")

    def __getattr__(name: str) -> Any:
        if name in moved:
            target_module, _, target_name = moved[name].partition(":")
            warnings.warn(
                f"{module}.{name} moved to {target_module}.{target_name}; import it from there",
                ContraagentDeprecationWarning,
                stacklevel=2,
            )
            return getattr(importlib.import_module(target_module), target_name)
        if name in removed:
            raise AttributeError(f"{module}.{name} was removed; {removed[name]}", name=name, obj=sys.modules.get(module))
        if fallback is not None:
            return fallback(name)
        raise AttributeError(f"module {module!r} has no attribute {name!r}", name=name, obj=sys.modules.get(module))

    return __getattr__
