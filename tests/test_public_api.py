"""The public API: each public module re-exports, each object has one public path, every
contraagent type a public signature, field or callback argument reaches is exported (a class,
a protocol or a named alias; an alias of literal values is not), no public
docstring names `_internal`, and the public modules import without the extras. Who imports
`_internal` is checked by `tests/test_layers.py`."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.metadata
import inspect
import pickle
import shutil
import subprocess
import sys
import types
import typing
from collections.abc import Iterator
from pathlib import Path

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


def _is_alias(value: object) -> bool:
    """A type alias: a `type X = ...` statement, or a typing construct bound to a name
    (`X = Callable[...]`, `X = A | B`, `X = Literal[...]`)."""
    if isinstance(value, typing.TypeAliasType):
        return True
    return not isinstance(value, type) and (typing.get_origin(value) is not None or isinstance(value, types.UnionType))


def _names_no_type(value: object) -> bool:
    """An alias that names no type of its own: of literal values (`Literal["a", "b"]`; its
    annotation lists them), or a field's validation over a type (`Annotated[Secret, ...]`;
    the walk reaches the type under it)."""
    if isinstance(value, typing.TypeAliasType):
        value = value.__value__
    if typing.get_origin(value) is typing.Annotated:
        return isinstance(typing.get_args(value)[0], type)
    return typing.get_origin(value) is typing.Literal


def _internal_aliases() -> dict[int, list[str]]:
    """id(alias) -> `module.name`, for every alias a module of `_internal` defines: a name its
    source binds at the top level to a type alias (not one it imports)."""
    found: dict[int, list[str]] = {}
    for name, mod in list(sys.modules.items()):
        if not name.startswith("contraagent._internal") or mod is None or not getattr(mod, "__file__", None):
            continue
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        bound = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                bound |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                bound.add(node.target.id)
            elif isinstance(node, ast.TypeAlias):
                bound.add(node.name.id)
        for key in bound:
            value = vars(mod).get(key)
            if value is not None and _is_alias(value):
                found.setdefault(id(value), []).append(f"{name}.{key}")
    return found


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
        self.aliases = _internal_aliases()
        self.seen: set[int] = set()
        self.reached: dict[type, str] = {}
        #: id(alias) -> (the alias, where it was first reached)
        self.reached_aliases: dict[int, tuple[object, str]] = {}
        self.where = ""

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
        if id(value) in self.aliases:
            self.reached_aliases.setdefault(id(value), (value, self.where))
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
        self.where = where
        for t in list(self.types_in(value, globalns, localns)):
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
            for name, member in list(cls.__dict__.items()):
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


def test_every_alias_a_public_signature_reaches_is_exported():
    """A named type alias a public signature, field or callback argument reaches is exported
    too, as a class is; an alias that names no type of its own (literal values, a field's
    validation) is not."""
    exports = _exports()
    walker = Walker()
    for module, name, obj in exports.values():
        walker.visit(obj, f"{module}.{name}")
    assert walker.aliases, "no alias found: the walk would check nothing"
    missing = sorted(
        f"{' / '.join(walker.aliases[key])} (reached from {where})"
        for key, (alias, where) in walker.reached_aliases.items()
        if key not in exports and not _names_no_type(alias)
    )
    assert missing == []


def test_a_callable_a_user_writes_is_a_protocol_with_its_call_documented():
    """A function a user passes (a rule, a scope, a validator, a panel, a callback) has a
    named type: a `Protocol` whose docstring states the call and whose `__call__` is the
    signature, so `help()` and a type checker both show it."""
    callables = {
        "contraagent": ["QuotaRule", "TaskScope", "Validator"],
        "contraagent.engine": ["AccountOf", "Answer", "BetweenPasses", "FollowUp", "OnEvent", "OnFlowCall", "OnResult", "WaitsFor"],
        "contraagent.monitor": ["PanelFn", "TaskDetailFn", "TrendsPanelFn"],
        "contraagent.backends": ["Sink"],
    }
    for module, names in callables.items():
        mod = importlib.import_module(module)
        for name in names:
            obj = getattr(mod, name)
            assert name in mod.__all__ and getattr(obj, "_is_protocol", False), (module, name)
            assert "__call__" in vars(obj) and (obj.__doc__ or "").strip(), (module, name)


def test_the_quota_rule_documents_its_arguments():
    from contraagent import QuotaRule

    doc = QuotaRule.__doc__ or ""
    assert "[credentials.<name>]" in doc and "QuotaReading" in doc and "None" in doc
    params = list(inspect.signature(QuotaRule.__call__).parameters.values())[1:]
    positional = inspect.Parameter.POSITIONAL_ONLY
    assert [(p.name, p.kind) for p in params] == [("credential", positional), ("reading", positional)]


def _public_members(obj: object) -> Iterator[tuple[str, object]]:
    """An exported object and the functions and properties its class defines, by name."""
    yield "", obj
    if isinstance(obj, type):
        for name, member in list(vars(obj).items()):  # help() may add `__annotate_func__` (3.14)
            if name.startswith("_") and name not in ("__init__", "__call__"):
                continue
            if isinstance(member, (classmethod, staticmethod)):
                member = member.__func__
            if isinstance(member, property) or (inspect.isfunction(member) and member.__module__.startswith("contraagent")):
                yield f".{name}", member


def test_no_public_docstring_names_internal():
    """A docstring a user reads (`help()`) names public paths only: `contraagent._internal`
    is not public, so a docstring names the public object instead."""
    found = []
    for module, name, obj in _exports().values():
        for member, value in _public_members(obj):
            doc = getattr(value, "__doc__", None) or ""
            if isinstance(doc, str) and "_internal" in doc:  # `contraagent._internal`, or a path under it
                found.append(f"{module}.{name}{member}")
    assert found == []


def test_help_of_a_public_function_or_method_shows_public_paths_only():
    """`help()` of a public function, or of a function a public class defines, names its
    public module. (A class's implementation bases keep their own paths: they are not public.)"""
    import pydoc

    found = []
    for module, name, obj in _exports().values():
        if not (isinstance(obj, type) or inspect.isfunction(obj)):
            continue
        for member, value in _public_members(obj):
            target = value.fget if isinstance(value, property) else value
            if target is None or isinstance(target, type):
                continue
            if target.__module__ != module:
                found.append(f"{module}.{name}{member}: __module__ {target.__module__}")
            text = pydoc.render_doc(target, renderer=pydoc.plaintext)
            if "contraagent._internal" in text:
                line = next(line for line in text.splitlines() if "contraagent._internal" in line)
                found.append(f"{module}.{name}{member}: {line.strip()}")
    assert found == []


#: The `**` parameters a public signature keeps: a task's own parameters, the flow's
#: arguments, the fields of a record merged in, the arguments of a class picked by name.
#: Any other argument is a named, typed parameter.
VAR_KEYWORD_KEPT = {
    "contraagent.AgentTask.__call__": "params",
    "contraagent.PythonTask.__call__": "kwargs",
    "contraagent.Pipeline.check": "kwargs",
    "contraagent.Pipeline.run": "kwargs",
    "contraagent.Pipeline.run_async": "kwargs",
    "contraagent.TimeBox.cause": "fields",
    "contraagent.config.KindConfig.with_": "changes",
    "contraagent.config.QuotaReading.from_windows": "fields",
    "contraagent.backends.EventFold.launch_result": "fields",
    "contraagent.backends.create_backend": "kwargs",
    "contraagent.engine.OnEvent.__call__": "fields",
    "contraagent.engine.Run.update_info": "fields",
    "contraagent.Validator.__call__": "kwargs",
}


def test_no_public_signature_takes_arguments_it_does_not_name():
    found = {}
    for module, name, obj in _exports().values():
        if not (isinstance(obj, type) or inspect.isfunction(obj)) or name in ("serve", "create_app"):
            continue
        for member, value in _public_members(obj):
            if not inspect.isfunction(value) or value.__module__ == "typing":
                continue
            for p in inspect.signature(value).parameters.values():
                if p.kind is p.VAR_KEYWORD:
                    found[f"{module}.{name}{member}"] = p.name
    assert found == VAR_KEYWORD_KEPT


def _keywords(fn: object, *, leave: tuple[str, ...] = ()) -> dict[str, object]:
    """`fn`'s keyword parameters and their defaults, but `self` and `leave`."""
    params = inspect.signature(fn).parameters.values()  # type: ignore[arg-type]
    return {p.name: p.default for p in params if p.name != "self" and p.name not in leave and p.kind is not p.VAR_KEYWORD}


def test_agent_task_takes_each_task_table_key_by_name():
    """Each key of a `[tasks.<kind>]` table is an `agent_task` parameter of its own, None by
    default (the kind's default, given or not), and nothing else is."""
    from contraagent import agent_task
    from contraagent._internal.routing.config import TASK_KEYS

    declaration = {
        "kind", "output", "params", "plugin", "skills_from", "role", "instructions", "validators", "output_name", "output_from",
        "unwrap", "requires", "claims", "changes", "tools", "rerun_on_resume", "preserve", "output_of", "implementations", "outside_state",
    }  # fmt: skip
    keywords = _keywords(agent_task)
    assert set(keywords) - declaration == set(TASK_KEYS)
    assert {key: keywords[key] for key in TASK_KEYS} == dict.fromkeys(TASK_KEYS)
    for overload in typing.get_overloads(agent_task):
        assert set(_keywords(overload)) == set(keywords)


def test_the_scheduling_arguments_are_the_queues():
    """`Pipeline`'s scheduling arguments, and `Run.queue`'s, are `WorkQueue`'s, with its
    defaults; `Run.agent_runner`'s are `AgentRunner`'s and `Run.credential_rests`' are
    `CredentialRests`'."""
    from contraagent import Pipeline
    from contraagent.engine import AgentRunner, CredentialRests, Run, WorkQueue

    queue = _keywords(WorkQueue, leave=("runner",))
    pipeline = _keywords(Pipeline)
    scheduling = {"deadline_s", "grace_s", "slack_s", "finishing_kinds", "overdue_s", "claim_capacity", "retry_wait_s", "throttle_s"}
    assert {k: pipeline[k] for k in scheduling} == {k: queue[k] for k in scheduling}
    run_queue = _keywords(Run.queue, leave=("runner", "resume"))
    assert set(run_queue) == set(queue) - {"on_event", "on_result", "between_passes"}  # `FlowDriver.attach` sets it
    assert [k for k in run_queue if run_queue[k] != queue[k]] == ["retry_on", "throttle_on"]  # a coding agent's stops
    assert _keywords(Run.agent_runner) == _keywords(AgentRunner, leave=("run_dir", "run_id"))
    assert _keywords(Run.credential_rests) == _keywords(CredentialRests, leave=("on_change", "now", "clock"))


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


PUBLISHED_ANNOTATIONS = """
import importlib, inspect, sys
import pydantic
modules = [importlib.import_module(m) for m in sys.argv[1:]]
classes = {id(o): o for m in modules for o in (getattr(m, n) for n in m.__all__) if isinstance(o, type)}
read = []
if sys.version_info >= (3, 14):
    import annotationlib
    read.append(lambda c: annotationlib.get_annotations(c, format=annotationlib.Format.FORWARDREF))
    read.append(lambda c: annotationlib.get_annotations(c, format=annotationlib.Format.VALUE))
read.append(inspect.get_annotations)
read_alike = rebuilt = 0
for cls in classes.values():
    # A class `publish` replaced the annotations of (a NamedTuple on 3.14 keeps an `__annotate__` instead).
    if "__annotations__" in cls.__dict__:
        for get in read:
            assert get(cls) == cls.__dict__["__annotations__"], cls.__qualname__
        read_alike += 1
    if issubclass(cls, pydantic.BaseModel) and cls.__module__.startswith("contraagent"):
        before = {name: field.annotation for name, field in cls.model_fields.items()}
        assert cls.model_rebuild(force=True) is not False, cls.__qualname__
        assert {name: field.annotation for name, field in cls.model_fields.items()} == before, cls.__qualname__
        rebuilt += 1
print(read_alike, rebuilt)
"""


def test_published_annotations_read_alike_and_a_model_rebuilds_after_publish():
    """`publish` replaces a class's string annotations with the values they name and moves
    its `__module__` to a public module. That stays safe while (1) every way of reading
    annotations (`inspect.get_annotations`; on 3.14 `annotationlib.get_annotations` in each
    format, PEP 649/749) gives the replaced dict, and (2) a pydantic model rebuilt after the
    move (`model_rebuild`, which looks names up in the module `__module__` names) still
    resolves every field to the same type. A fresh interpreter, so no rebuild touches the
    classes the other tests use. (A rebuild of a model that holds a self-referencing one,
    `Procs` and its `ProcNode`, names that model's `$defs` entry twice in its JSON Schema:
    the old reference carries the module the model had before `publish`. Nothing in
    contraagent rebuilds a published model.)"""
    out = subprocess.run([sys.executable, "-c", PUBLISHED_ANNOTATIONS, *PUBLIC], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    read_alike, rebuilt = map(int, out.stdout.split())
    assert read_alike > 50 and rebuilt > 50


IMPORT_WITHOUT_EXTRAS = """
import importlib.util, sys
sys.path.insert(0, sys.argv[1])
extras = ("fastapi", "uvicorn", "sse_starlette", "httpx2", "psycopg", "boto3", "zstandard")
assert [m for m in extras if importlib.util.find_spec(m)] == [], "not a fresh environment"
import contraagent, contraagent.config, contraagent.backends, contraagent.engine, contraagent.plugins, contraagent.testing
import contraagent.monitor, contraagent.monitor.api
for module in (contraagent, contraagent.config, contraagent.backends, contraagent.engine, contraagent.plugins, contraagent.testing,
               contraagent.monitor.api):
    [getattr(module, name) for name in module.__all__]
[getattr(contraagent.monitor, name) for name in contraagent.monitor.__all__ if name not in ("serve", "create_app")]
print("ok")
"""


def test_the_public_modules_import_in_an_environment_without_the_extras(tmp_path):
    """A fresh virtual environment holding only the dependencies (pydantic, psutil) and the source:
    the extras' packages are absent there, not only left unimported."""
    uv = shutil.which("uv")
    assert uv is not None, "uv makes the environment"
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "--quiet", "--python", sys.executable, str(venv)], check=True, capture_output=True)
    python = venv / "Scripts" / "python.exe" if sys.platform == "win32" else venv / "bin" / "python"
    pins = [f"{name}=={importlib.metadata.version(name)}" for name in ("pydantic", "psutil")]
    install = [uv, "pip", "install", "--quiet", "--python", str(python), *pins]
    if subprocess.run([*install, "--offline"], capture_output=True).returncode != 0:
        done = subprocess.run(install, capture_output=True, text=True, encoding="utf-8")
        assert done.returncode == 0, done.stderr
    src = Path(__file__).parents[1] / "src"
    done = subprocess.run([str(python), "-I", "-c", IMPORT_WITHOUT_EXTRAS, str(src)], capture_output=True, text=True, encoding="utf-8")
    assert (done.returncode, done.stdout.strip()) == (0, "ok"), done.stderr


def test_serve_and_create_app_are_published_when_first_named():
    import contraagent.monitor

    assert contraagent.monitor.serve.__module__ == "contraagent.monitor"
    assert isinstance(contraagent.monitor.create_app, types.FunctionType)


@pytest.mark.parametrize(
    "name",
    [
        "make_python_task",
        "kind_name",
        "configs_from_tables",
        "require_budgets",
        "OMP_PREAMBLE",
        "STDIN_THRESHOLD",
        "account_digest",
        "write_launch_marker",
        "lint_plugin",
        "Implementations",
        "TimeBoxed",
        "CredentialBase",
        "MemorySource",
        "PlanRow",
        "RestEvent",
    ],
)
def test_internal_helpers_are_not_public(name):
    for module in PUBLIC:
        assert name not in importlib.import_module(module).__all__


def test_the_monitor_api_holds_its_openapi_schemas():
    import json
    from pathlib import Path

    import contraagent.monitor.api

    openapi = Path(contraagent.__file__).parent / "_internal" / "monitor" / "openapi.json"
    schemas = set(json.loads(openapi.read_text(encoding="utf-8"))["components"]["schemas"])
    extra = {"API_VERSION", "AnyTranscriptEvent"}
    assert [n for n in contraagent.monitor.api.__all__ if n not in schemas | extra] == []
    homes = {name for module in PUBLIC for name in importlib.import_module(module).__all__}
    assert sorted(schemas - homes) == ["HTTPValidationError", "ValidationError"]  # FastAPI's own


def test_no_alias_of_literal_values_is_exported():
    """A field or parameter of literal values lists them in its annotation; no name stands for them."""
    literal = [
        f"{module}.{name}"
        for module in PUBLIC
        for name in importlib.import_module(module).__all__
        if typing.get_origin(getattr(importlib.import_module(module), name)) is typing.Literal
    ]
    assert literal == []


def test_the_task_and_the_result_a_callback_is_given_are_frozen():
    from contraagent import Task, TaskResult

    task = Task("summarize", unit="alpha")
    result = TaskResult(task=task, ok=True, stop="completed")
    with pytest.raises(dataclasses.FrozenInstanceError):
        task.attempt = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ok = False  # type: ignore[misc]
    assert dataclasses.replace(result, ok=False).ok is False and result.ok


def _snapshot_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("api") / "snapshot.py"
    spec = importlib.util.spec_from_file_location("api_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_api_snapshot_is_current():
    snapshot = _snapshot_module()
    assert snapshot.PUBLIC == PUBLIC
    current = snapshot.render()
    committed = snapshot.SNAPSHOT.read_text(encoding="utf-8") if snapshot.SNAPSHOT.exists() else ""
    if current != committed:
        import difflib

        diff = "".join(difflib.unified_diff(committed.splitlines(True), current.splitlines(True), "committed", "sources", n=1))
        pytest.fail(f"tests/api/contraagent.api.txt is stale; regenerate it with `{snapshot.COMMAND}`:\n{diff[:4000]}")


def test_the_public_modules_are_fully_typed():
    """`pyright --verifytypes`: every symbol of a public module has a known type, declared
    rather than inferred. The examples under `contraagent.docs` are installed with the
    package, so pyright counts them too; they are documentation, not API, and are left out."""
    import json

    out = subprocess.run(
        [sys.executable, "-m", "pyright", "--verifytypes", "contraagent", "--ignoreexternal", "--outputjson"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    symbols = json.loads(out)["typeCompleteness"]["symbols"]
    incomplete = [
        f"{s['name']}: {'; '.join(d['message'].splitlines()[0] for d in s['diagnostics'] if d['severity'] == 'error')}"
        for s in symbols
        if s["isExported"] and not s["name"].startswith("contraagent.docs.") and (not s["isTypeKnown"] or s["isTypeAmbiguous"])
    ]
    assert len(symbols) > 200
    assert incomplete == []


def _lazy(name: str) -> object:
    if name == "lazy":
        return 42
    raise AttributeError(name)


@pytest.fixture
def old_module(monkeypatch):
    """A public module with a moved name, a removed name and a name of its own imported
    when first used."""
    from contraagent._internal.public import migration

    module = types.ModuleType("contraagent.old")
    module.__getattr__ = migration(  # type: ignore[attr-defined]
        "contraagent.old",
        moved={"OldRun": "contraagent.engine:Run"},
        removed={"helper": "use contraagent.engine.Run.cursor"},
        fallback=_lazy,
    )
    monkeypatch.setitem(sys.modules, "contraagent.old", module)
    return module


def test_a_moved_name_warns_and_gives_the_object_from_its_new_home(old_module):
    from contraagent import ContraagentDeprecationWarning
    from contraagent.engine import Run

    with pytest.warns(ContraagentDeprecationWarning, match=r"contraagent\.old\.OldRun moved to contraagent\.engine\.Run") as caught:
        assert old_module.OldRun is Run
    assert issubclass(ContraagentDeprecationWarning, DeprecationWarning)
    assert caught[0].filename == __file__
    with pytest.warns(ContraagentDeprecationWarning):
        from contraagent.old import OldRun  # type: ignore[import-not-found]
    assert OldRun is Run


def test_a_moved_name_is_an_error_in_the_tests_unless_expected(old_module):
    from contraagent import ContraagentDeprecationWarning

    with pytest.raises(ContraagentDeprecationWarning):
        old_module.OldRun


def test_a_removed_name_says_what_to_use(old_module):
    with pytest.raises(AttributeError, match=r"contraagent\.old\.helper was removed; use contraagent\.engine\.Run\.cursor"):
        old_module.helper
    assert old_module.lazy == 42
    with pytest.raises(AttributeError):
        old_module.never_there
    assert not hasattr(old_module, "never_there")


def test_a_migration_table_is_checked():
    from contraagent._internal.public import migration

    with pytest.raises(ValueError, match="both moved and removed"):
        migration("contraagent.old", moved={"a": "contraagent:Task"}, removed={"a": "gone"})
    with pytest.raises(ValueError, match="not 'module:name'"):
        migration("contraagent.old", moved={"a": "contraagent.Task"})
    plain = migration("contraagent.old")
    with pytest.raises(AttributeError, match="has no attribute 'x'"):
        plain("x")
