"""The public API: each public module re-exports, each object has one public path, and every
contraagent type a public signature, field or callback argument reaches is exported."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import pickle
import subprocess
import sys
import types
import typing
from collections.abc import Iterator

import pydantic
import pytest

PUBLIC = (
    "contraagent",
    "contraagent.config",
    "contraagent.backends",
    "contraagent.engine",
    "contraagent.plugins",
    "contraagent.monitor",
    "contraagent.monitor.api",
    "contraagent.testing",
)


def _exports() -> dict[int, tuple[str, str, object]]:
    """id(object) -> (module, name, object), over every public module's `__all__`."""
    out: dict[int, tuple[str, str, object]] = {}
    for module in PUBLIC:
        mod = importlib.import_module(module)
        for name in mod.__all__:
            obj = getattr(mod, name)
            out.setdefault(id(obj), (module, name, obj))
    return out


def _ours(cls: type) -> bool:
    return isinstance(cls, type) and cls.__module__.split(".")[0] == "contraagent" and not cls.__module__.startswith("contraagent.docs")


def _internal_names() -> dict[str, object]:
    """Every class and alias `_internal` defines, by name: what a string annotation naming
    something imported only for a type checker (`TYPE_CHECKING`) stands for."""
    found: dict[str, object] = {}
    for name, mod in list(sys.modules.items()):
        if name.startswith("contraagent._internal") and mod is not None:
            for key, value in vars(mod).items():
                if not key.startswith("__"):
                    found.setdefault(key, value)
    return found


class Walker:
    def __init__(self) -> None:
        self.fallback = _internal_names()
        self.seen: set[int] = set()
        self.reached: dict[type, str] = {}

    def resolve(self, value: object, globalns: dict, localns: dict | None = None) -> object:
        if isinstance(value, typing.ForwardRef):
            value = value.__forward_arg__
        if not isinstance(value, str):
            return value
        ns = {**self.fallback, **globalns, **(localns or {})}
        try:
            return eval(value, ns)
        except Exception:
            # One name at a time: the parts that resolve.
            names = [n.id for n in ast.walk(ast.parse(value, mode="eval")) if isinstance(n, ast.Name)]
            return tuple(ns[n] for n in names if n in ns)

    def types_in(self, value: object, globalns: dict, localns: dict | None = None) -> Iterator[object]:
        value = self.resolve(value, globalns, localns)
        if isinstance(value, tuple):
            for v in value:
                yield from self.types_in(v, globalns, localns)
            return
        if isinstance(value, typing.TypeAliasType):
            yield from self.types_in(value.__value__, globalns, localns)
            return
        if isinstance(value, typing.TypeVar):
            if value.__bound__ is not None:
                yield from self.types_in(value.__bound__, globalns, localns)
            return
        origin = typing.get_origin(value)
        if origin is typing.Literal:
            return
        if origin is typing.Annotated:
            yield from self.types_in(typing.get_args(value)[0], globalns, localns)
            return
        if origin is not None:
            yield origin
            for arg in typing.get_args(value):
                if arg is not Ellipsis:
                    yield from self.types_in(arg, globalns, localns)
            return
        if isinstance(value, list):  # Callable[[...], ...] args
            for v in value:
                yield from self.types_in(v, globalns, localns)
            return
        if isinstance(value, type):
            yield value

    def visit_type(self, value: object, globalns: dict, where: str, localns: dict | None = None) -> None:
        for t in self.types_in(value, globalns, localns):
            if isinstance(t, type) and _ours(t):
                self.reached.setdefault(t, where)
                self.visit(t, where)

    def visit_callable(self, fn: object, where: str) -> None:
        fn = inspect.unwrap(fn)  # type: ignore[arg-type]
        annotations = getattr(fn, "__annotations__", None)
        if not isinstance(annotations, dict):
            return
        globalns = getattr(fn, "__globals__", {})
        for name, value in annotations.items():
            self.visit_type(value, globalns, f"{where}({name})")

    def visit(self, obj: object, where: str) -> None:
        if id(obj) in self.seen:
            return
        self.seen.add(id(obj))
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            self.visit_callable(obj, where)
            return
        if not isinstance(obj, type):
            if typing.get_origin(obj) is not None or isinstance(obj, typing.TypeAliasType):
                self.visit_type(obj, {}, where)
            elif _ours(type(obj)):
                self.visit_type(type(obj), {}, where)
            return
        if not _ours(obj):
            return
        for cls in obj.__mro__:
            if not _ours(cls):
                continue
            globalns = vars(sys.modules[cls.__module__]) if cls.__module__ in sys.modules else {}
            # the module that defined it, before it was published
            defining = [m for m in sys.modules.values() if m is not None and m.__name__.startswith("contraagent._internal")]
            for m in defining:
                if vars(m).get(cls.__name__) is cls:
                    globalns = {**vars(m), **globalns}
                    break
            localns = {**vars(cls), cls.__name__: cls, **{p.__name__: p for p in getattr(cls, "__type_params__", ())}}
            for name, value in cls.__dict__.get("__annotations__", {}).items():
                if not name.startswith("_"):
                    self.visit_type(value, globalns, f"{obj.__qualname__}.{name}", localns)
            for name, member in cls.__dict__.items():
                if name.startswith("_") and name not in ("__init__", "__call__"):
                    continue
                if isinstance(member, (classmethod, staticmethod)):
                    member = member.__func__
                if isinstance(member, property):
                    member = member.fget
                if inspect.isfunction(member):
                    self.visit_callable(member, f"{obj.__qualname__}.{name}")
        if issubclass(obj, pydantic.BaseModel):
            for name, info in obj.model_fields.items():
                self.visit_type(info.annotation, {}, f"{obj.__qualname__}.{name}")


def test_each_public_module_only_re_exports():
    for module in PUBLIC:
        mod = importlib.import_module(module)
        tree = ast.parse(inspect.getsource(mod))
        defined = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        assert [n.name for n in defined if n.name != "__getattr__"] == [], module
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("contraagent"):
                assert node.module.startswith("contraagent._internal"), (module, node.module)


def test_every_object_has_one_public_path():
    homes: dict[int, list[str]] = {}
    for module in PUBLIC:
        mod = importlib.import_module(module)
        assert sorted(mod.__all__) == sorted(set(mod.__all__)), module
        for name in mod.__all__:
            homes.setdefault(id(getattr(mod, name)), []).append(f"{module}.{name}")
    assert [paths for paths in homes.values() if len(paths) > 1] == []


def test_a_published_class_or_function_names_its_public_module():
    for module, name, obj in _exports().values():
        if isinstance(obj, type) or inspect.isfunction(obj):
            assert obj.__module__ == module, (name, obj.__module__)
            assert getattr(importlib.import_module(obj.__module__), obj.__qualname__) is obj


def test_every_type_a_public_signature_reaches_is_exported():
    exports = _exports()
    walker = Walker()
    for module, name, obj in exports.values():
        walker.visit(obj, f"{module}.{name}")
    missing = sorted(
        f"{t.__module__}.{t.__qualname__} (reached from {where})" for t, where in walker.reached.items() if id(t) not in exports
    )
    assert missing == []


def test_published_classes_keep_their_annotations_and_pickle():
    for _module, name, obj in _exports().values():
        if isinstance(obj, type):
            typing.get_type_hints(obj)
            if issubclass(obj, pydantic.BaseModel):
                assert obj.__pydantic_complete__, name
            if dataclasses.is_dataclass(obj):
                own = obj.__dict__.get("__annotations__", {})
                assert [f.name for f in dataclasses.fields(obj) if f.name in own and isinstance(f.type, str)] == [], name
    from contraagent import Task, TaskResult
    from contraagent.backends import LaunchResult, Stop

    result = TaskResult(
        task=Task("summarize", unit="alpha"), ok=True, stop="completed", launch_result=LaunchResult(label="alpha", stop=Stop.COMPLETED)
    )
    assert pickle.loads(pickle.dumps(result)) == result


def test_the_public_modules_import_without_the_monitor_extra():
    code = (
        "import sys, contraagent, contraagent.monitor, contraagent.monitor.api, contraagent.testing, contraagent.engine;"
        "print([m for m in ('fastapi', 'uvicorn', 'contraagent._internal.monitor.server') if m in sys.modules])"
    )
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "[]"


def test_serve_and_create_app_are_published_when_first_named():
    import contraagent.monitor

    assert contraagent.monitor.serve.__module__ == "contraagent.monitor"
    assert isinstance(contraagent.monitor.create_app, types.FunctionType)


@pytest.mark.parametrize(
    "name", ["make_python_task", "kind_name", "configs_from_tables", "require_budgets", "OMP_PREAMBLE", "STDIN_THRESHOLD"]
)
def test_internal_helpers_are_not_public(name):
    for module in PUBLIC:
        assert name not in importlib.import_module(module).__all__


def test_the_task_and_the_result_a_callback_is_given_are_frozen():
    from contraagent import Task, TaskResult

    task = Task("summarize", unit="alpha")
    result = TaskResult(task=task, ok=True, stop="completed")
    with pytest.raises(dataclasses.FrozenInstanceError):
        task.attempt = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ok = False  # type: ignore[misc]
    assert dataclasses.replace(result, ok=False).ok is False and result.ok
