"""How a public module publishes what it re-exports.

A public module (`contraagent`, `contraagent.config`, ...) holds no definitions: it
imports names from `_internal` and calls `publish(__name__, __all__)`. Each class and
function then names that module as its `__module__`, so a repr, a traceback, pickle and
the documentation show the one path a user imports it from.

A class's annotations are strings (`from __future__ import annotations`) that resolve in
the module that defines it; `typing.get_type_hints` and pydantic look them up in the
module `__module__` names. So before a class moves, its own annotations, and its
dataclass fields' types, are resolved where they were written.
"""

from __future__ import annotations

import dataclasses
import inspect
import sys
from collections.abc import Iterable
from typing import Any

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
        obj.__module__ = module


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
