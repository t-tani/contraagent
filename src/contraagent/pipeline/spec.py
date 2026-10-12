"""Declaring tasks: what a pipeline's flow function calls.

* `agent_task(...)` declares an agent task's *interface*: its parameters, its
  output, its budget. Its implementation is a plugin (`contraagent.plugins`).
* `@python_task` turns a Python function into a Python task.

Both are called like functions inside a flow run by `Pipeline.run`; a call
queues a task and returns a `Pending` reference to its future output, which
can be passed to another task as a parameter (that is how dependencies are
written).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import typing
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, overload

from pydantic import BaseModel, RootModel

from contraagent.pipeline.graph import Pending, current_graph
from contraagent.plugins import Plugin
from contraagent.routing.config import ConfigError, PipelineConfig
from contraagent.validators import Validator, validator_name

Out = TypeVar("Out")


@dataclass(frozen=True, eq=False)
class AgentTask[Out]:
    """An agent task's interface. Build one with `agent_task`."""

    kind: str
    output: type | None
    params: type[BaseModel] | None
    plugin: Plugin | None
    role: str | None
    instructions: str | None
    config: dict
    validators: tuple[Validator, ...]
    output_name: str
    requires: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    #: Who executes it (`Task.executor`): a coding agent.
    executor = "agent"

    @property
    def output_schema(self) -> type[BaseModel] | None:
        """The schema the output file is checked against; None for a text output."""
        return self.output if isinstance(self.output, type) and issubclass(self.output, BaseModel) else None

    @property
    def output_format(self) -> str | None:
        if self.output is None:
            return None
        return "text" if self.output is str else "json"

    def digest(self) -> str:
        """A digest of what defines this kind of task, part of each task's fingerprint: its
        instructions, its role file's content, its output schema, its validators and its
        params schema."""
        role = ""
        if self.plugin is not None and self.role is not None:
            try:
                role = self.plugin.role_file(self.role).read_text()
            except OSError:
                pass
        params = _schema(self.params) if self.params is not None else None
        return _digest(
            {
                "instructions": self.instructions,
                "role": role,
                "output": _schema(self.output_schema) if self.output_schema is not None else self.output_format,
                "validators": [_validator_identity(v) for v in self.validators],
                "params": params,
            }
        )

    def __call__(self, unit: str = "", *, key: str | None = None, after: Sequence[Pending | str] = (), **params: Any) -> Pending[Out]:
        """Queue this task for `unit`. `params` may hold `Pending` outputs of other tasks."""
        if self.params is not None:
            _check_param_names(self.kind, self.params, params)
        return current_graph().add(self, unit=unit, key=key, after=after, params=params)


def agent_task[Out](
    kind: str,
    *,
    output: type[Out] | None = None,
    params: type[BaseModel] | None = None,
    plugin: str | Path | None = None,
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    requires: Sequence[str] = (),
    tags: Sequence[str] = (),
    **config: Any,
) -> AgentTask[Out]:
    """Declare an agent task.

    `plugin`: the directory that implements it (`contraagent plugin new`), relative
    to the file that declares the task. Its role (`agents/<role>.md`) is the
    procedure; `role` picks one when the plugin has several.
    `params`: a pydantic model the task's parameters must satisfy (default: any
    JSON values). They reach the agent in its call file, never in the prompt.
    `output`: a pydantic model (a JSON file checked against it) or `str` (a text
    document). `validators` add checks the file must pass beyond its schema
    (`contraagent.validators`: a Python function, `CommandValidator(["textlint", ...])`).
    `requires`: traits the credential it runs under must carry (`["zdr"]` for a
    task whose data may only go to a zero-data-retention organization). Which
    credential that is, is the config's to say; a route that does not satisfy
    it, failover hops included, is refused before anything launches.
    `tags`: named resources each of its tasks holds while it runs (`["heavy"]`);
    `Pipeline(tag_capacity={"heavy": 1})` caps how many run at once.
    `instructions`: a text put before the call protocol, for a task with no plugin.
    `output_name`: the output file's name under `<run>/out/<kind>/`, a template:
    `{unit}` is the unit, or the key when the task call gives `key=` (or no unit);
    `{key}` and `{kind}`. Default `{unit}.json` (`{unit}.md` for a text output).
    `config`: defaults for its task table, any key a `[tasks.<kind>]` table takes
    (`max_turns`, `timeout_s`, `model`, `agent`, `effort` ...); the config file
    outranks them. Every kind needs `max_turns` and `timeout_s`, here or there;
    `contraagent docs routing` lists every key.
    """
    if plugin is None and instructions is None:
        raise TypeError(f"agent_task({kind!r}): give plugin= (its implementation) or, for a task without one, instructions=")
    if output is not None and output is not str and not (isinstance(output, type) and issubclass(output, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): output must be a pydantic model or str, not {output!r}")
    if params is not None and not (isinstance(params, type) and issubclass(params, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): params must be a pydantic model, not {params!r}")
    if config:
        # The same checks a [tasks.<kind>] table gets, so a typo is an error here too.
        try:
            PipelineConfig({"tasks": {kind: dict(config)}}).task_tables()
        except ConfigError as exc:
            raise ConfigError(str(exc).replace("<config>: [tasks.", "agent_task: [", 1)) from None
    loaded = Plugin.load(_relative_to_caller(plugin)) if plugin is not None else None
    resolved_role = loaded.resolve_role(role) if loaded is not None else role
    return AgentTask(
        kind=kind,
        output=output,
        params=params,
        plugin=loaded,
        role=resolved_role,
        instructions=instructions,
        config=dict(config),
        validators=tuple(validators),
        requires=tuple(requires),
        tags=tuple(tags),
        output_name=output_name or ("{unit}.md" if output is str else "{unit}.json"),
    )


@dataclass(frozen=True, eq=False)
class PythonTask[Out]:
    """A Python function as a task. Build one with `@python_task`. Its kind is its name."""

    fn: Callable[..., Out]
    name: str
    output_schema: type[BaseModel] | None
    validators: tuple[Validator, ...]
    tags: tuple[str, ...] = ()

    #: Who executes it (`Task.executor`): this process, in Python.
    executor = "python"
    output_format = "json"

    @property
    def kind(self) -> str:
        return self.name

    @property
    def output_name(self) -> str:
        return "{unit}.json"

    def __call__(self, unit: str = "", *, key: str | None = None, after: Sequence[Pending | str] = (), **kwargs: Any) -> Pending[Out]:
        """Queue this Python task for `unit`; the function runs with `kwargs` (Pending resolved).
        A function with a `unit` parameter is given the unit too."""
        return current_graph().add(self, unit=unit, key=key, after=after, params=kwargs)

    def digest(self) -> str:
        """A digest of what defines this kind of task, part of each task's fingerprint: the
        function's source (its bytecode when it has none), its output schema and its
        validators."""
        fn = inspect.unwrap(self.fn)
        try:
            source = inspect.getsource(fn)
        except (OSError, TypeError):
            code = getattr(fn, "__code__", None)
            source = repr((code.co_code, code.co_consts, code.co_names)) if code is not None else repr(fn)
        return _digest(
            {
                "source": source,
                "output": _schema(self.output_schema) if self.output_schema is not None else None,
                "validators": [_validator_identity(v) for v in self.validators],
            }
        )

    def definition(self, cwd: Path | None = None) -> dict:
        """What defines this kind of task, for the monitor (`definitions/<kind>.json`):
        where the function is, what it takes and returns, its docstring and source."""
        fn = inspect.unwrap(self.fn)
        body: dict[str, Any] = {
            "executor": "python",
            "function": f"{fn.__module__}.{fn.__qualname__}",
            "output": _type_name(self.output_schema) if self.output_schema is not None else "none",
            "validators": [getattr(v, "name", None) or getattr(v, "__name__", type(v).__name__) for v in self.validators],
        }
        try:
            try:  # annotations as written (`str`, not `'str'` under `from __future__ import annotations`)
                sig = inspect.signature(fn, eval_str=True)
            except Exception:
                sig = inspect.signature(fn)
            body["signature"] = f"{fn.__name__}{sig}"
            body["params"] = ", ".join(sig.parameters) or "none"
        except (TypeError, ValueError):
            pass
        if doc := inspect.getdoc(fn):
            body["doc"] = doc
        try:
            lines, start = inspect.getsourcelines(fn)
            file = Path(inspect.getsourcefile(fn) or "")
            try:
                shown = file.resolve().relative_to((cwd or Path.cwd()).resolve())
            except ValueError:
                shown = file
            body["file"], body["line"] = str(shown), start
            body["files"] = [{"path": str(shown), "part": "source", "text": "".join(lines)[:20_000]}]
        except (OSError, TypeError):
            pass  # a function without source (built-in, REPL): the facts above still say what it is
        return body

    def invoke(self, unit: str, kwargs: dict) -> Any:
        if unit and "unit" not in kwargs and "unit" in inspect.signature(self.fn).parameters:
            kwargs = {**kwargs, "unit": unit}
        return self.fn(**kwargs)


@overload
def python_task[Out](fn: Callable[..., Out], /) -> PythonTask[Out]: ...
@overload
def python_task(
    *, name: str | None = None, validators: Sequence[Validator] = (), tags: Sequence[str] = ()
) -> Callable[[Callable[..., Out]], PythonTask[Out]]: ...


def python_task(
    fn: Callable[..., Any] | None = None,
    /,
    *,
    name: str | None = None,
    validators: Sequence[Validator] = (),
    tags: Sequence[str] = (),
) -> PythonTask[Any] | Callable[[Callable[..., Any]], PythonTask[Any]]:
    """Turn a function into a Python task of kind `name` (default: the function's
    name). Its return annotation is its output: a pydantic model (the schema),
    any JSON-able type (kept as a JSON file), or None (no output). `tags`, as for
    `agent_task`: resources each of its tasks holds while it runs."""

    def wrap(f: Callable[..., Out]) -> PythonTask[Out]:
        return PythonTask(fn=f, name=name or f.__name__, output_schema=_output_schema_of(f), validators=tuple(validators), tags=tuple(tags))

    return wrap(fn) if fn is not None else wrap


def _output_schema_of(fn: Callable) -> type[BaseModel] | None:
    ann: Any
    try:
        ann = typing.get_type_hints(fn).get("return", inspect.Signature.empty)
    except Exception:  # an unresolvable annotation reads as "any JSON"
        ann = Any
    if ann is inspect.Signature.empty:
        ann = Any
    if ann is None or ann is type(None):
        return None
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann
    return RootModel[ann]


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=repr).encode()).hexdigest()


def _schema(model: type[BaseModel]) -> Any:
    try:
        return model.model_json_schema()
    except Exception:  # a type pydantic cannot describe: its name
        return f"{model.__module__}.{model.__qualname__}"


def _validator_identity(v: Validator) -> Any:
    """A command validator's command; a function's `module.qualname`."""
    to_dict = getattr(v, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    fn = inspect.unwrap(v) if callable(v) else v
    return f"{getattr(fn, '__module__', '')}.{getattr(fn, '__qualname__', validator_name(v))}"


def _type_name(t: type) -> str:
    """`Prepared`, or `str` for a `RootModel[str]`: the name a reader knows."""
    if issubclass(t, RootModel):
        inner = t.model_fields["root"].annotation
        return getattr(inner, "__name__", None) or str(inner)
    return t.__name__


def _check_param_names(kind: str, model: type[BaseModel], params: dict) -> None:
    unknown = sorted(set(params) - set(model.model_fields))
    missing = sorted(n for n, f in model.model_fields.items() if f.is_required() and n not in params)
    if unknown or missing:
        bits = ([f"unknown {', '.join(unknown)}"] if unknown else []) + ([f"missing {', '.join(missing)}"] if missing else [])
        raise TypeError(f"{kind}(): parameters do not match {model.__name__}: {'; '.join(bits)}")


def _relative_to_caller(path: str | Path) -> Path:
    """A relative plugin path is relative to the file that called `agent_task`."""
    p = Path(path)
    if p.is_absolute():
        return p
    frame = inspect.currentframe()
    caller = frame.f_back.f_back if frame and frame.f_back else None
    file = caller.f_globals.get("__file__") if caller else None
    return (Path(file).resolve().parent / p) if file else p.resolve()
