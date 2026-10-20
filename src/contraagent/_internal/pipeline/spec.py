"""Declaring tasks: what a pipeline's flow function calls.

* `agent_task(...)` declares an agent task's *interface*: its params model, its
  output, its budget. Its implementation is a plugin (`contraagent.plugins`).
* `@python_task` turns a Python function into a Python task.

Both are called inside a flow run by `Pipeline.run`: an agent task with its unit and an
instance of its params model (`summarize(unit, SummarizeParams(...))`), a Python task as
its function. A call queues a task and returns a `Pending` reference to its future
output, which an async flow awaits for the output. A task's call options (`key`,
`after`, `priority`, an agent task's `credential`, `cancellable`) are not arguments of
the call: `task.options(...)` returns the same task with them, and calling that is the
task call.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import inspect
import json
import math
import re
import string
import types
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Literal, ParamSpec, Protocol, Self, overload

from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError
from typing_extensions import TypeVar  # a default (PEP 696) before Python 3.13

from contraagent._internal.contracts.pointers import schema_error, syntax_error
from contraagent._internal.contracts.rows import is_rows, rows_file, rows_model
from contraagent._internal.contracts.validators import Validator, validator_name
from contraagent._internal.dispatch.code import flow_code
from contraagent._internal.dispatch.python_task import InvalidInput, checked_retries
from contraagent._internal.dispatch.task import GLOB_CHARACTERS, Partial
from contraagent._internal.dispatch.templates import PARAM_FIELD
from contraagent._internal.pipeline.graph import Pending, current_graph
from contraagent._internal.plugins import Plugin, PluginError
from contraagent._internal.plugins.plugin import body
from contraagent._internal.routing.config import TASK_KEYS, ConfigError, PipelineConfig

#: An agent task's params model, None when `agent_task` is given none.
ParamsT = TypeVar("ParamsT", bound=BaseModel | None, default=None)
#: An agent task's output, None when `agent_task` is given none.
OutT = TypeVar("OutT", default=None)
#: A Python task's parameters and output, in `@python_task(...)`'s decorator.
_P = ParamSpec("_P")
_Out = TypeVar("_Out")


class OutsideState(Protocol):
    """A function that returns a task's outside state: what its work depends on beside its
    params and its definition (`agent_task(outside_state=)`, `@python_task(outside_state=)`),
    such as what a task it waits for with `after=` changed in the working tree.
    `outside_state(unit, params)` is given the task's unit (empty for a task with none) and
    its params as JSON (the call file's `params`), and returns any JSON value: a digest of
    the files the task reads, a version, a list or a dict of them, a pydantic model. The
    task's fingerprint covers the value, so a resume runs the task again when it returns
    another. It is called when the task is about to start, once
    every task it waits for finished; one that raises, or returns what is not JSON, refuses
    the task (`invalid_input`)."""

    def __call__(self, unit: str, params: dict[str, Any], /) -> Any: ...


#: Where a task's JSON output file goes, relative to `<run>/out/` (`.md` for a text output,
#: `.jsonl` for rows).
DEFAULT_OUTPUT_NAME = "{kind}/{unit}.json"


def default_output_name(output: Any) -> str:
    """Where an output declared `output` goes by default: `{kind}/{unit}.json`, `.md` for a
    text output, `.jsonl` for rows (`Rows[Row]`)."""
    if is_text(output):
        return "{kind}/{unit}.md"
    if rows_model(output) is not None:
        return "{kind}/{unit}.jsonl"
    return DEFAULT_OUTPUT_NAME


def output_format_of(output: Any) -> str:
    """`text`, `jsonl` (rows) or `json`: what an output's file holds, as the call file says."""
    if is_text(output):
        return "text"
    return "jsonl" if rows_model(output) is not None else "json"


class _Keep(enum.Enum):
    """The default of each argument of `options`: an option not given keeps the value it
    had. A one-member enum, so a type checker knows `Literal[_Keep.KEEP]` and narrows it
    away with `is`."""

    KEEP = "keep"

    def __repr__(self) -> str:
        return "KEEP"


@dataclass(frozen=True)
class _CallOptions:
    """A task's call options as `options` gave them: what the graph is given beside the
    params at each call of the task."""

    key: str | None = None
    after: tuple[Pending[Any] | str, ...] = ()
    priority: float = 0.0
    #: An agent task's credential; empty: its kind's.
    credential: str = ""
    cancellable: bool = False

    def given(
        self,
        where: str,
        *,
        key: str | None | Literal[_Keep.KEEP],
        after: Sequence[Pending[Any] | str] | Literal[_Keep.KEEP],
        priority: float | Literal[_Keep.KEEP],
        credential: str | None | Literal[_Keep.KEEP],
        cancellable: bool | Literal[_Keep.KEEP],
    ) -> _CallOptions:
        """These options with each one given (not `_Keep.KEEP`) replaced, checked; `where` names
        the call in an error."""
        if cancellable is not _Keep.KEEP and not isinstance(cancellable, bool):
            raise TypeError(f"{where}(...): cancellable must be True or False, not {cancellable!r}")
        return _CallOptions(
            key=self.key if key is _Keep.KEEP else _checked_key(where, key),
            after=self.after if after is _Keep.KEEP else _checked_after(where, after),
            priority=self.priority if priority is _Keep.KEEP else _checked_priority(where, priority),
            credential=self.credential if credential is _Keep.KEEP else _checked_credential(where, credential),
            cancellable=self.cancellable if cancellable is _Keep.KEEP else cancellable,
        )


_NO_OPTIONS = _CallOptions()


@dataclass(frozen=True, eq=False)
class AgentTask[ParamsT: BaseModel | None, Out]:
    """An agent task's interface. Build one with `agent_task`. `ParamsT` is its params
    model (None for a task declared without one), `Out` its output (None for none)."""

    kind: str
    output: type | None
    #: Its params model (`agent_task(params=)`); None for a task that takes no params.
    params: type[BaseModel] | None
    plugin: Plugin | None
    role: str | None
    instructions: str | None
    config: dict[str, Any]
    validators: tuple[Validator, ...]
    output_name: str
    requires: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    #: Plugins whose skills the task loads too, after its own plugin (`agent_task(skills_from=)`).
    skills_from: tuple[Plugin, ...] = ()
    changes: tuple[str, ...] = ()
    #: Where the output arrives: `file` (the agent writes it) or `message` (its final message is it).
    output_from: str = "file"
    #: The final message may wrap the JSON output: it is taken out of the message (`unwrap_json`).
    unwrap: bool = False
    #: The agent's tools: None, those its role and settings allow; `()`, none (a light launch).
    tools: tuple[str, ...] | None = None
    #: A resume runs its tasks again even when an earlier attempt finished them.
    rerun_on_resume: bool = False
    #: JSON pointers to the parts of the output file a launch must keep (`agent_task(preserve=)`).
    preserve: tuple[str, ...] = ()
    #: The task declaration whose output file this kind writes (`agent_task(output_of=)`).
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None
    #: The base kind of an implementation kind (`agent_task(implementations=)`); empty for any other.
    base_kind: str = ""
    #: The function that returns its outside state, which its fingerprint covers (`agent_task(outside_state=)`).
    outside_state: OutsideState | None = None
    #: Its call options (`options`); none for a declaration.
    _options: _CallOptions = dataclasses.field(default=_NO_OPTIONS, init=False, repr=False)
    #: The declaration `options` made it from; None for a declaration itself.
    _declaration: AgentTask[Any, Any] | None = dataclasses.field(default=None, init=False, repr=False)

    #: Who executes it (`Task.executor`): a coding agent.
    executor = "agent"

    @property
    def output_schema(self) -> type[BaseModel] | None:
        """The schema the output file is checked against: the model; for rows (`Rows[Row]`)
        the file of them (`RowsFile[Row]`); None for a text output."""
        row = rows_model(self.output)
        if row is not None:
            return rows_file(row)
        return self.output if isinstance(self.output, type) and issubclass(self.output, BaseModel) else None

    @property
    def output_format(self) -> str | None:
        """`json`, `text` or `jsonl` (rows); None for a task with no output."""
        if self.output is None:
            return None
        return output_format_of(self.output)

    @property
    def output_json_schema(self) -> dict[str, Any]:
        """The output's JSON Schema, as the call file carries it: the model's; for rows, the
        row model's, which each line meets; for a text output `Annotated[str, Field(examples=[...])]`,
        the string's with its examples; else empty."""
        row = rows_model(self.output)
        if row is not None:
            return row.model_json_schema()
        if self.output_schema is not None:
            return self.output_schema.model_json_schema()
        if self.output is not None and self.output is not str:
            return TypeAdapter(self.output).json_schema()
        return {}

    @property
    def params_json_schema(self) -> dict[str, Any]:
        """The JSON Schema of its params, as the call file carries it (`params_json_schema`):
        its params model's, with each field's description and constraints; for a task that
        takes no params, an object with no properties."""
        if self.params is None:
            return {"type": "object", "properties": {}}
        return self.params.model_json_schema()

    @property
    def light(self) -> bool:
        """A light launch (`tools=()`): no tools, the role as the system prompt, the call in the prompt."""
        return self.tools == ()

    def system_prompt(self, instructions: str | None = None) -> str | None:
        """The system prompt of a light launch: the role's text without its frontmatter, else
        `instructions` (the task's own, filled in). None for any other launch."""
        if not self.light:
            return None
        if self.plugin is not None and self.role is not None:
            return body(self.plugin.role_file(self.role).read_text(encoding="utf-8")).strip()
        return (instructions if instructions is not None else self.instructions or "").strip()

    @property
    def plugins(self) -> tuple[Plugin, ...]:
        """Every plugin the task loads: its own first, then those of `skills_from`."""
        return ((self.plugin,) if self.plugin is not None else ()) + self.skills_from

    def digest(self) -> str:
        """A digest of what defines this kind of task, part of each task's fingerprint: its
        instructions, its role file's content, the skills of its plugins, its output schema,
        its validators, its params schema, its `changes` patterns, where its output arrives,
        whose output file it writes (`output_of`), the parts of it to keep (`preserve`), the name of
        its `outside_state` function and, for a light launch, that it has no tools."""
        return _digest(self._defined())

    def differences(self, other: AgentTask[Any, Any]) -> list[str]:
        """What `other`, a declaration of the same kind, declares otherwise: the parts of the
        digest, the plugin, `skills_from`, `config`, `requires`, `claims`, `output_name`,
        `rerun_on_resume` and `base_kind`. None:
        one kind, declared twice the same way."""
        if other is self:
            return []
        mine, theirs = self._defined(), other._defined()
        parts = [name for name in dict.fromkeys([*mine, *theirs]) if mine.get(name) != theirs.get(name)]
        if (self.plugin and self.plugin.root) != (other.plugin and other.plugin.root):
            parts.append("plugin")
        if [p.root for p in self.skills_from] != [p.root for p in other.skills_from]:
            parts.append("skills_from")
        return parts + [
            name
            for name in ("config", "requires", "claims", "output_name", "rerun_on_resume", "base_kind")
            if getattr(self, name) != getattr(other, name)
        ]

    def _defined(self) -> dict[str, Any]:
        role = ""
        if self.plugin is not None and self.role is not None:
            try:
                role = self.plugin.role_file(self.role).read_text(encoding="utf-8")
            except OSError:
                pass
        return {
            "instructions": self.instructions,
            "role": role,
            "skills": {f"{p.name}/{rel}": text for p in self.plugins for rel, text in p.skill_files()},
            "output": _schema(self.output_schema) if self.output_schema is not None else self.output_format,
            "validators": [_validator_identity(v) for v in self.validators],
            "params": _schema(self.params) if self.params is not None else None,
            "changes": list(self.changes),
            "output_from": self.output_from,
            **({"unwrap": True} if self.unwrap else {}),
            **({"preserve": list(self.preserve)} if self.preserve else {}),
            **({"output_of": self.output_of.kind} if self.output_of is not None else {}),
            **({"tools": list(self.tools)} if self.tools is not None else {}),
            **({"outside_state": _function_name(self.outside_state)} if self.outside_state is not None else {}),
        }

    @overload
    def __call__(self: AgentTask[None, Out], unit: str = "", /) -> Pending[Out]: ...
    @overload
    def __call__(self, params: ParamsT, /) -> Pending[Out]: ...
    @overload
    def __call__(self, unit: str, params: ParamsT, /) -> Pending[Out]: ...
    def __call__(self, *args: Any, **keywords: Any) -> Pending[Out]:
        """Queue this task, with its call options (`options`): `task(unit, params)`, or
        `task(params)` for a task with no unit; a task declared without a params model is
        called `task(unit)` or `task()`. The unit is a string, empty when left out. `params`
        is an instance of the task's params model itself (`agent_task(params=)`), not of a
        subclass, whose fields the model's JSON Schema does not describe. It is copied as
        JSON here and checked again under the model, so a value set on it after it was
        made is checked too; a `Pending` in it, at any depth, a value that is not JSON, or
        a value the model does not take raise TypeError. So does a call that gives params
        to a task without a model, leaves them out of a task with one, or gives keywords:
        a params model holds the params, `options` the call options. To give a task
        another task's output, await that task in an async def flow and pass the value."""
        unit, params = self._called(args, keywords)
        o = self._options
        return current_graph().add(
            declaration_of(self),
            unit=unit,
            params=params if params is not None else {},
            key=o.key,
            after=o.after,
            priority=o.priority,
            credential=o.credential,
            cancellable=o.cancellable,
        )

    def _called(self, args: tuple[Any, ...], keywords: dict[str, Any]) -> tuple[str, BaseModel | None]:
        """The unit and the params of a call `task(*args, **keywords)`; TypeError, saying
        how to write it, for a call this task does not take."""
        model = self.params
        shape = f"{self.kind}(unit, {model.__name__}(...))" if model is not None else f"{self.kind}(unit)"
        if keywords:
            _refuse_call_options(self.kind, keywords, set(), python=False)
            names = ", ".join(f"{k}=" for k in keywords)
            if model is None:
                raise TypeError(
                    f"{self.kind}(...): {names}: this task declares no params model, so it takes no params; declare one "
                    f"(agent_task({self.kind!r}, params=..., ...)) and pass an instance of it (contraagent docs tasks)"
                )
            raise TypeError(
                f"{self.kind}(...): {names}: an agent task takes its params as one instance of its params model, "
                f"not as keywords: {shape} (contraagent docs tasks)"
            )
        if len(args) > 2:
            raise TypeError(f"{self.kind}(...) takes a unit and its params, not {len(args)} arguments: {shape}")
        unit: Any = ""
        params: Any = None
        if len(args) == 2:
            unit, params = args
        elif len(args) == 1 and (isinstance(args[0], str) or (model is None and not isinstance(args[0], BaseModel))):
            unit = args[0]
        elif len(args) == 1:
            params = args[0]
        if not isinstance(unit, str):
            raise TypeError(f"{self.kind}(...): the unit is a string, not {unit!r}: {shape}")
        if model is None:
            if params is not None:
                raise TypeError(
                    f"{self.kind}(...): this task declares no params model, so it takes no params; declare one "
                    f"(agent_task({self.kind!r}, params=..., ...)) and pass an instance of it (contraagent docs tasks)"
                )
            return unit, None
        if params is None:
            raise TypeError(f"{self.kind}(...) takes its params, an instance of {model.__name__}: {shape}")
        if type(params) is not model:
            if isinstance(params, model):
                raise TypeError(
                    f"{self.kind}(...): params is a {type(params).__name__}, a subclass of {model.__name__}; give a "
                    f"{model.__name__} itself: the task's JSON Schema describes the fields of {model.__name__} only"
                )
            raise TypeError(f"{self.kind}(...): params is {type(params).__name__}, and this task takes a {model.__name__}: {shape}")
        return unit, params

    def options(
        self,
        *,
        key: str | None | Literal[_Keep.KEEP] = _Keep.KEEP,
        after: Sequence[Pending[Any] | str] | Literal[_Keep.KEEP] = _Keep.KEEP,
        priority: float | Literal[_Keep.KEEP] = _Keep.KEEP,
        credential: str | None | Literal[_Keep.KEEP] = _Keep.KEEP,
        cancellable: bool | Literal[_Keep.KEEP] = _Keep.KEEP,
    ) -> Self:
        """This task with call options: calling what it returns is a task call of this task,
        its declaration the same (one kind, one digest), so `summarize.options(key="k")(unit)`
        is `summarize(unit)` under key `k`. An option not given keeps the value it had
        (none at first); the task itself is not changed.

        `key`: the task's key in place of `<kind>-<unit>`; it names its output file in place of
        the unit too (`{unit}` of `output_name`), so two keys on one unit write two files.
        None clears it: the key is `<kind>-<unit>` again.
        `after`: tasks this one starts after, each a task call's `Pending` or a task's key,
        for an order with no output passed on. `priority`: breaks ties in the queue, higher
        first (`WorkQueue`). `credential` names a `[credentials.<name>]` this task runs as on
        every route of its kind, failover hops included, in place of the kind's; it outranks
        the kind's `[tasks.<kind>]` table and its declaration; a run-wide override
        (`Overrides(credential=)`) outranks it; None clears it, so the kind's credential is
        used. A credential that does not exist or does not carry the traits the task
        `requires` is refused before the task launches. `cancellable`: True cancels the task (stop `cancelled`) once the flow call that
        created it and every flow call that waited for it were closed and no flow call waits
        for it: a queued one is not launched, a running one's launch is stopped. False, the
        default: it runs to its end whatever happens to its flow calls. None of them is part
        of the task's fingerprint but `key`."""
        made = self._options.given(
            f"{self.kind}.options", key=key, after=after, priority=priority, credential=credential, cancellable=cancellable
        )
        return _with_options(self, made)


@overload
def agent_task(
    kind: str,
    *,
    output: type[OutT] | None = None,
    params: type[ParamsT] | None = None,
    plugin: str | Path | None = None,
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    unwrap: bool = False,
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    rerun_on_resume: bool = False,
    preserve: Sequence[str] = (),
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None,
    implementations: None = None,
    outside_state: OutsideState | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
    safety_stop_failover: Sequence[Literal["response", "tool"]] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    timeout_s: float | None = None,
    max_budget_usd: float | None = None,
    stall_s: float | None = None,
    context_budget: int | None = None,
    context_warn_pct: int | None = None,
    max_denials: int | None = None,
    max_concurrent: int | None = None,
    retries: int | None = None,
    retry_backoff_base: float | None = None,
    partial_on: Sequence[Literal["timeout", "stalled"]] | None = None,
    keep_failed_changes: bool | None = None,
    max_corrections: int | None = None,
) -> AgentTask[ParamsT, OutT]: ...


@overload
def agent_task(
    kind: str,
    *,
    output: Any,  # a text output, `Annotated[str, Field(examples=[...])]`, is not a type
    params: type[ParamsT] | None = None,
    plugin: str | Path | None = None,
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    unwrap: bool = False,
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    rerun_on_resume: bool = False,
    preserve: Sequence[str] = (),
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None,
    implementations: None = None,
    outside_state: OutsideState | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
    safety_stop_failover: Sequence[Literal["response", "tool"]] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    timeout_s: float | None = None,
    max_budget_usd: float | None = None,
    stall_s: float | None = None,
    context_budget: int | None = None,
    context_warn_pct: int | None = None,
    max_denials: int | None = None,
    max_concurrent: int | None = None,
    retries: int | None = None,
    retry_backoff_base: float | None = None,
    partial_on: Sequence[Literal["timeout", "stalled"]] | None = None,
    keep_failed_changes: bool | None = None,
    max_corrections: int | None = None,
) -> AgentTask[ParamsT, str]: ...


@overload
def agent_task(
    kind: str,
    *,
    output: type[OutT] | None = None,
    params: type[ParamsT] | None = None,
    plugin: str | Path | None = None,
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    unwrap: bool = False,
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    rerun_on_resume: bool = False,
    preserve: Sequence[str] = (),
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None,
    implementations: Mapping[str, str | Path],
    outside_state: OutsideState | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
    safety_stop_failover: Sequence[Literal["response", "tool"]] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    timeout_s: float | None = None,
    max_budget_usd: float | None = None,
    stall_s: float | None = None,
    context_budget: int | None = None,
    context_warn_pct: int | None = None,
    max_denials: int | None = None,
    max_concurrent: int | None = None,
    retries: int | None = None,
    retry_backoff_base: float | None = None,
    partial_on: Sequence[Literal["timeout", "stalled"]] | None = None,
    keep_failed_changes: bool | None = None,
    max_corrections: int | None = None,
) -> Implementations[ParamsT, OutT]: ...


@overload
def agent_task(
    kind: str,
    *,
    output: Any,  # a text output, `Annotated[str, Field(examples=[...])]`, is not a type
    params: type[ParamsT] | None = None,
    plugin: str | Path | None = None,
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    unwrap: bool = False,
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    rerun_on_resume: bool = False,
    preserve: Sequence[str] = (),
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None,
    implementations: Mapping[str, str | Path],
    outside_state: OutsideState | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
    safety_stop_failover: Sequence[Literal["response", "tool"]] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    timeout_s: float | None = None,
    max_budget_usd: float | None = None,
    stall_s: float | None = None,
    context_budget: int | None = None,
    context_warn_pct: int | None = None,
    max_denials: int | None = None,
    max_concurrent: int | None = None,
    retries: int | None = None,
    retry_backoff_base: float | None = None,
    partial_on: Sequence[Literal["timeout", "stalled"]] | None = None,
    keep_failed_changes: bool | None = None,
    max_corrections: int | None = None,
) -> Implementations[ParamsT, str]: ...


def agent_task(
    kind: str,
    *,
    output: Any = None,  # a type, or `Annotated[str, Field(examples=[...])]`, which is not one
    params: Any = None,  # a pydantic model, checked here
    plugin: str | Path | None = None,
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    unwrap: bool = False,
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    rerun_on_resume: bool = False,
    preserve: Sequence[str] = (),
    output_of: AgentTask[Any, Any] | PythonTask[..., Any] | None = None,
    implementations: Mapping[str, str | Path] | None = None,
    outside_state: OutsideState | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
    safety_stop_failover: Sequence[Literal["response", "tool"]] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    timeout_s: float | None = None,
    max_budget_usd: float | None = None,
    stall_s: float | None = None,
    context_budget: int | None = None,
    context_warn_pct: int | None = None,
    max_denials: int | None = None,
    max_concurrent: int | None = None,
    retries: int | None = None,
    retry_backoff_base: float | None = None,
    partial_on: Sequence[Literal["timeout", "stalled"]] | None = None,
    keep_failed_changes: bool | None = None,
    max_corrections: int | None = None,
) -> AgentTask[Any, Any] | Implementations[Any, Any]:
    """Declare an agent task.

    `kind`: the name of its class of work; it holds no `*`, `?` or `[`, which a pattern of
    kinds uses (`contraagent run --stub --execute PATTERN`).
    `plugin`: the directory that implements it (`contraagent plugin new`), relative
    to the file that declares the task. Its role (`agents/<role>.md`) is the
    procedure; `role` picks one when the plugin has several.
    `skills_from`: plugin directories (relative the same way) whose skills the task
    loads too, after its own plugin's: skills several tasks share. Such a plugin holds
    skills only; its agents, settings, tools and hooks would act on every task that
    loads it, so a plugin with any of them is refused here.
    `params`: the task's params model, a pydantic model: a task call passes an instance of
    it (`task(unit, Params(...))`), and the agent gets its fields as JSON in its call file
    (`params`), with the model's JSON Schema (`params_json_schema`) beside them, so each
    field's `Field(description=...)` tells the agent what it is; never in the prompt.
    Without it the task takes no params (`task(unit)`), and is typed `AgentTask[None, Out]`.
    `output`: a pydantic model (a JSON file checked against it), `str` (a text
    document) or `Rows[Row]` (rows: a JSON Lines file, each line one `Row`, which the agent
    may write one row at a time; the flow receives a `Rows`, a list of `Row`);
    `Annotated[str, Field(examples=[...])]` is a text document with an example
    (the model's own example: `model_config = ConfigDict(json_schema_extra={"examples": [...]})`),
    typed as `str`; any other `Annotated` output raises here. A stub run writes the example
    (`contraagent.testing.writes_example`). `validators` add checks the file must pass beyond its schema
    (`contraagent.Validator`: a Python function, `CommandValidator(["textlint", ...])`); a
    Python validator of rows is given the `Rows`.
    `requires`: traits the credential it runs under must carry (`["zdr"]` for a
    task whose data may only go to a zero-data-retention organization). Which
    credential that is, is the config's to say; a route that does not satisfy
    it, failover hops included, is refused before anything launches.
    `claims`: the names each of its tasks holds while it runs; one task holds a name at
    a time, unless `claim_capacity` (`Pipeline(claim_capacity=)`, `[defaults.claim_capacity]`)
    allows more. A claim is a template: `{unit}`, `{kind}`, `{key}` (the task's key, `~n`
    included) and `{params.<name>}`, a field of the params model, which raises here when
    the model has no such field (a list gives one name per element; an empty list raises at
    the call). So
    `["topic:{unit}"]` runs one task at a time on each topic, whatever its kind, and
    `["topic:{params.topics}"]` holds every topic a task names. A task that claims nothing
    runs beside any other.
    `changes`: `Path.glob` patterns, relative to the working directory, of the files its
    tasks may change beside their output (`["topics/{unit}/**"]`; `{unit}`, `{key}` and
    `{kind}` as in `output_name`; a pattern that matches a directory covers everything
    under it; one that starts with `!` leaves out what it matches and everything under it,
    `["**", "!.git/**"]`). Each attempt's changes under them are recorded in its journal row, and
    the files a failed attempt created are removed (but with `keep_failed_changes`, below).
    Tasks that run at once under one pattern cannot be told apart: put `{unit}` in it.
    `instructions`: a text put before the call protocol, for a task with no plugin. Such a
    task runs with the permissions of the plugin template's `settings.json` (Claude Code).
    `output_name`: the output file's path relative to `<run>/out/`, a template:
    `{unit}` is the unit, or the key when the task's call options give one (or no unit);
    `{key}` and `{kind}`. Default `{kind}/{unit}.json` (`{kind}/{unit}.md` for a text
    output, `{kind}/{unit}.jsonl` for rows); `"reports/{unit}.json"` writes `out/reports/alpha.json`. An absolute path, a
    `..`, `.` or empty segment, or another field raises here. Two kinds whose templates name
    one file, or two tasks given one file, raise when the flow reaches the second
    (`Pipeline.check` reports it before a run).
    `output_from`: `"file"` (default), the agent writes the output file; `"message"`, its
    final message is the output: the runner writes it to the output file and checks it
    there, and a message that fails its checks goes back to the same session. For a task
    that needs no tool (a classification in one turn), it saves the turn the `Write` takes.
    `unwrap`: with `output_from="message"` and a JSON output, the message may wrap the
    document (a sentence before it, a fenced block): the runner takes the document out of it
    (the last fenced block that parses, else the longest JSON value) and keeps the whole message beside the output file
    (`<output>.message.txt`). By default the whole message must be the document.
    `tools`: None (default), the tools its role and settings allow; `()`, none: a **light
    launch**, for a judgement in one turn. The role's text (without its frontmatter), or for a
    task with no plugin `instructions`, replaces the coding agent's own system prompt; the
    params and the output's JSON Schema are in the prompt (the agent cannot read a call file);
    no plugin, settings, skill, hook or MCP server is loaded. It needs `output_from="message"`.
    Tool names are each coding agent's own, so a list of them is not taken here: a role names
    its tools in its frontmatter, a plugin's `settings.json` what they may do.
    `preserve`: JSON pointers (RFC 6901, and a segment `*` for every member of an array or
    object: `["/items/*/id", "/source"]`) to the parts of the output file the agent must keep,
    for a task that fills in a file that holds values already (`output_of`). Each value they
    select in the file as it was before the launch must be in the file after it, equal; one
    that changed or was removed goes back to the agent as a check error (`/items/3/id
    changed`), and an attempt that does not pass leaves the file as it was. A file that is
    missing before the launch keeps nothing. It takes a JSON output (a pydantic model) the
    agent writes, and each pointer must name a part of its schema.
    `output_of`: another task declaration (`agent_task` or `@python_task`) whose output file
    this kind writes, for a task that fills in that file: the file of the latest task of that
    kind created so far for the same unit (or key=), else the file its `output_name` names for
    it (a `~n` of this task's own key does not change it). A task waits for the latest task
    created so far that writes that file, of any kind, so two never write it at once; one
    created later is not waited for. `output` is the schema of the whole file after this
    task, JSON or text as the other kind's; `output_name` is not taken with it.
    `rerun_on_resume`: a resume (`Pipeline.run(resume=True)`) runs its tasks again even when
    an earlier attempt of the run finished them, for a final step that reports or publishes
    the state of the work. A task that takes the output of a task that ran again already
    runs again, through its fingerprint.
    `outside_state`: a function of the task's unit and params (`OutsideState`) that returns
    what its work depends on beside its params and inputs, as a JSON value: a digest of a file
    its instructions or role tell the agent to read, a version of a state another process
    keeps. Its fingerprint covers the value, so a resume runs the task again when it returns
    another. It is called when the task is about to start, so it sees what the tasks it waits
    for wrote; `contraagent docs tasks` tells more.
    `implementations`: one step done in several ways, by name: `{"python": "plugins/review-python",
    "go": "plugins/review-go"}` (plugin directories, relative as `plugin` is; it takes the place
    of `plugin`). Each is a kind of its own, `<kind>-<name>` (`review-go`), with that plugin
    and every other argument given here; `kind` is their **base kind**. A name is letters,
    digits and `_`. It returns the agent tasks by name (`Implementations`): `review["go"](unit, params)`.
    Each implementation kind takes the `[tasks.<kind>]` table of the base kind, then its own
    `[tasks.<kind>-<name>]` table key by key (its `fallbacks` replace the base kind's); the
    monitor draws its tasks in the base kind's group, unless `Monitor(groups=)` lists the kind.

    The rest are the kind's defaults for its task table: each is a key of `[tasks.<kind>]`,
    and the config file outranks it there (None: not given here). Every kind needs
    `max_turns` and `timeout_s`, here or in the config; `contraagent docs routing` tells more.
    `agent`: the coding agent it runs on, a registered `Backend` name (`"claude"`, `"omp"`).
    `model`: the model, in its coding agent's own name; empty, the agent's default.
    `effort`: the reasoning effort, one of the agent's own levels (`Backend.effort_levels`).
    `credential`: the `[credentials.<name>]` it launches with; `"ambient"`, the host's own setup.
    `model_failover`: hand the same-agent models of its failover chain to the coding agent's own
    flag, so it may change model inside one launch.
    `fallbacks`: its failover chain, hop by hop, each a table as `[[tasks.<kind>.fallbacks]]`
    writes one (`{"agent": "omp", "model": "..."}`); it replaces `[[defaults.fallbacks]]`.
    `safety_stop_failover`: the parts of a launch (`"response"`, `"tool"`) whose safety stop
    (`SafetyStop`) moves a launch that ended well to the next hop of its failover chain,
    which starts it again; the last hop's result stands. A launch that failed fails over anyway.
    `disallowed_tools`: tools its launches may not use, in Claude Code's names and patterns
    (`["WebFetch", "Bash(git push:*)"]`).
    `max_turns`: turns per launch. `timeout_s`: seconds per launch. `max_budget_usd`: cost per
    launch, as the coding agent reports it. `stall_s`: stop a launch whose transcript is silent
    this many seconds. `context_budget`: stop a launch once one call's input passes this many
    tokens. `context_warn_pct`: warn once a launch's peak context passes this percent of
    `context_budget` (1 to 99); the launch goes on. `max_denials`: stop a launch after this
    many permission denials.
    `max_concurrent`: tasks of this kind running at once (`Pipeline(max_concurrent=)` caps the run).
    `retries`: fresh-session attempts after the first, each after one that made no progress;
    `retry_backoff_base`: the seconds before the first of them, doubled per attempt.
    `partial_on`: stops of a launch (`"timeout"`, `"stalled"`: the runner ended it for its
    `timeout_s` or its `stall_s`) after which the output the agent wrote is kept: when it
    exists, was written by this attempt and passes every check, the task finishes ok with
    stop `partial` and the stop as its reason, as a Python task that returns `Partial` does;
    its output is what the flow receives, and a resume runs it again. Rows keep the rows
    written so far (an unfinished last line is removed). Without it such a launch fails as
    any other. It takes an output the agent writes to a file.
    `keep_failed_changes`: leave the files a failed attempt created under `changes` in place,
    as the evidence of why it failed, instead of removing them; its journal row lists them
    as `changes.kept`. The next attempt, and a resume, start from the tree with them in it.
    `max_corrections`: the correction rounds after the first launch, 0 to 20 (default 3):
    how many times an output that fails its checks goes
    back to the same session with the errors before the task ends `invalid_output`; 0
    sends none back.
    """
    # The task table keys, as given (`TASK_KEYS`: a test holds them equal to these parameters).
    given = locals()
    _check_kind(f"agent_task({kind!r})", kind)
    table = {key: _table_value(given[key]) for key in TASK_KEYS if given[key] is not None}
    base = _caller_dir()
    if implementations is not None:
        plugins = _checked_implementations(kind, implementations, plugin, instructions)
        shared_dirs = [_relative_to(base, p) for p in ([skills_from] if isinstance(skills_from, (str, Path)) else skills_from)]
        return Implementations(
            kind,
            {
                name: dataclasses.replace(
                    agent_task(
                        f"{kind}-{name}",
                        output=output,
                        params=params,
                        plugin=_relative_to(base, path),
                        skills_from=shared_dirs,
                        role=role,
                        validators=validators,
                        output_name=output_name,
                        output_from=output_from,
                        unwrap=unwrap,
                        requires=requires,
                        claims=claims,
                        changes=changes,
                        tools=tools,
                        rerun_on_resume=rerun_on_resume,
                        preserve=preserve,
                        output_of=output_of,
                        outside_state=outside_state,
                        **table,
                    ),
                    base_kind=kind,
                )
                for name, path in plugins.items()
            },
        )
    if plugin is None and instructions is None:
        raise TypeError(f"agent_task({kind!r}): give plugin= (its implementation) or, for a task without one, instructions=")
    try:
        rows = rows_model(output)
    except TypeError as exc:
        raise TypeError(f"agent_task({kind!r}): output {exc}") from None
    if typing.get_origin(output) is typing.Annotated and not is_text(output):
        raise TypeError(
            f"agent_task({kind!r}): an Annotated output is a text output with an example, Annotated[str, Field(examples=[...])], "
            f"not {output!r}; a model's example is the model's own (model_config = ConfigDict(json_schema_extra=...))"
        )
    if output is not None and rows is None and not is_text(output) and not (isinstance(output, type) and issubclass(output, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): output must be a pydantic model, str or Rows[Model], not {output!r}")
    if params is not None and not (isinstance(params, type) and issubclass(params, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): params must be a pydantic model, not {params!r}")
    if output_from not in ("file", "message"):
        raise TypeError(f'agent_task({kind!r}): output_from must be "file" or "message", not {output_from!r}')
    if output_from == "message" and output is None:
        raise TypeError(f'agent_task({kind!r}): output_from="message" needs an output (a pydantic model or str)')
    if unwrap and (output_from != "message" or is_text(output) or rows is not None):
        raise TypeError(
            f'agent_task({kind!r}): unwrap takes a JSON output out of the final message: give output_from="message" and a pydantic model'
        )
    if partial_on is not None and (output is None or output_from != "file"):
        raise TypeError(
            f"agent_task({kind!r}): partial_on keeps the output file a stopped launch wrote; "
            'give an output the agent writes (output_from="file")'
        )
    checked_preserve = _checked_preserve(kind, preserve, output, output_from)
    _check_output_of(kind, output_of, output, output_name)
    if output_name is not None:
        _check_output_name(f"agent_task({kind!r})", output_name)
    checked_tools = _checked_tools(kind, tools)
    if checked_tools == () and output_from != "message":
        raise TypeError(f'agent_task({kind!r}): tools=() (a light launch) writes no file: give output_from="message" and an output')
    if checked_tools == () and skills_from:
        raise TypeError(f"agent_task({kind!r}): tools=() loads no skill: drop skills_from, or the tools=()")
    if table:
        # The same checks a [tasks.<kind>] table gets, so a wrong value is an error here too.
        try:
            PipelineConfig({"tasks": {kind: dict(table)}}).task_tables()
        except ConfigError as exc:
            raise ConfigError(str(exc).replace("<config>: [tasks.", "agent_task: [", 1)) from None
    changes = tuple(changes)
    for pattern in changes:
        _check_changes_pattern(kind, pattern)
    if changes and all(p.startswith("!") for p in changes):
        raise TypeError(f"agent_task({kind!r}): changes holds only patterns that leave paths out (`!`); give one that covers paths")
    if keep_failed_changes and not changes:
        raise TypeError(f"agent_task({kind!r}): keep_failed_changes keeps the files under changes=; give the patterns, or drop it")
    checked_claims = _checked_claims(f"agent_task({kind!r})", claims, _model_fields(params))
    _check_outside_state(f"agent_task({kind!r})", outside_state, rerun_on_resume)
    loaded = Plugin.load(_relative_to(base, plugin)) if plugin is not None else None
    shared = tuple(Plugin.load(_relative_to(base, p)) for p in ([skills_from] if isinstance(skills_from, (str, Path)) else skills_from))
    for p in shared:
        if others := p.besides_skills():
            why = "written by `contraagent plugin render`; remove them" if p.render_leftovers() else "a plugin it names holds skills only"
            raise PluginError(f"agent_task({kind!r}): skills_from {p.root} holds {', '.join(others)}; {why}")
    resolved_role = loaded.resolve_role(role) if loaded is not None else role
    if checked_tools == () and loaded is not None and resolved_role is None:
        raise TypeError(f"agent_task({kind!r}): tools=() takes its system prompt from the role, and {loaded.root} defines none")
    return AgentTask(
        kind=kind,
        output=output,
        params=params,
        plugin=loaded,
        role=resolved_role,
        instructions=instructions,
        config=table,
        validators=tuple(validators),
        requires=tuple(requires),
        claims=checked_claims,
        skills_from=shared,
        changes=changes,
        output_name=output_name or default_output_name(output),
        output_from=output_from,
        unwrap=bool(unwrap),
        tools=checked_tools,
        rerun_on_resume=bool(rerun_on_resume),
        preserve=checked_preserve,
        output_of=output_of,
        outside_state=outside_state,
    )


def _table_value(value: Any) -> Any:
    """An argument as a task table holds it: a list for a sequence (`fallbacks` a list of
    tables). A string stays a string, so the table's check refuses it."""
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [dict(v) if isinstance(v, Mapping) else v for v in value]
    return value


#: An implementation's name: what follows its base kind in its kind (`review-go`).
_IMPLEMENTATION_NAME = re.compile(r"[A-Za-z0-9_]+")


def _checked_implementations(kind: str, implementations: Any, plugin: Any, instructions: Any) -> dict[str, str | Path]:
    """`implementations` as declared: a non-empty mapping of names to plugin directories."""
    where = f"agent_task({kind!r})"
    if plugin is not None:
        raise TypeError(f"{where}: implementations names each implementation's plugin; drop plugin=")
    if instructions is not None:
        raise TypeError(f"{where}: implementations takes plugins, and instructions= is for a task without one; drop instructions=")
    if not isinstance(implementations, Mapping) or not implementations:
        raise TypeError(
            f'{where}: implementations takes a dict of names to plugin directories ({{"go": "plugins/{kind}-go"}}), not {implementations!r}'
        )
    for name, path in implementations.items():
        if not isinstance(name, str) or not _IMPLEMENTATION_NAME.fullmatch(name):
            raise TypeError(f"{where}: implementation name {name!r} is not letters, digits and _ (its kind is {kind}-<name>)")
        if not isinstance(path, (str, Path)):
            raise TypeError(f"{where}: implementation {name!r} takes a plugin directory, not {path!r}")
    return dict(implementations)


class Implementations[ParamsT: BaseModel | None, Out](Mapping[str, AgentTask[ParamsT, Out]]):
    """One step declared with several implementations (`agent_task(implementations=)`): an
    agent task per implementation, by name, each typed as the step (`AgentTask[ParamsT, Out]`).
    `review["go"]` is the kind `review-go`; call it as any agent task
    (`await review["go"](unit, params)`). `kind` is their base kind."""

    def __init__(self, kind: str, tasks: Mapping[str, AgentTask[ParamsT, Out]]) -> None:
        self.kind = kind
        self._tasks = dict(tasks)

    @property
    def kinds(self) -> list[str]:
        """The implementation kinds, in the order declared (`review-python`, `review-go`)."""
        return [t.kind for t in self._tasks.values()]

    def __getitem__(self, name: str) -> AgentTask[ParamsT, Out]:
        try:
            return self._tasks[name]
        except KeyError:
            raise KeyError(f"{self.kind} has no implementation {name!r}; its implementations: {', '.join(self._tasks)}") from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._tasks)

    def __len__(self) -> int:
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"Implementations({self.kind!r}, {', '.join(self.kinds)})"


def is_text(output: Any) -> bool:
    """Whether `output` declares a text output: `str`, or `Annotated[str, ...]` (its
    `Field(examples=[...])` the example a stub run writes)."""
    return output is str or (typing.get_origin(output) is typing.Annotated and typing.get_args(output)[0] is str)


def _check_output_of(kind: str, other: Any, output: Any, output_name: str | None) -> None:
    """`output_of`: a task declaration that writes an output file of the same format as `output`."""
    if other is None:
        return
    if not isinstance(other, (AgentTask, PythonTask)):
        raise TypeError(f"agent_task({kind!r}): output_of takes a task declaration (agent_task, @python_task), not {other!r}")
    if output_name is not None:
        raise TypeError(f"agent_task({kind!r}): output_of names the output file; drop output_name")
    if output is None:
        raise TypeError(f"agent_task({kind!r}): output_of needs output=, the schema of the whole file after this task")
    if other.kind == kind:
        raise TypeError(f"agent_task({kind!r}): output_of names this kind itself")
    if other.output_format is None or (other.executor == "python" and other.output_schema is None):
        raise TypeError(f"agent_task({kind!r}): output_of {other.kind!r} writes no output file")
    mine = output_format_of(output)
    if other.output_format != mine:
        raise TypeError(f"agent_task({kind!r}): output_of {other.kind!r} writes a {other.output_format} file, and this output is {mine}")


def _checked_preserve(kind: str, preserve: Sequence[str], output: Any, output_from: str) -> tuple[str, ...]:
    """`preserve` as declared, each pointer checked against its syntax and the output's schema."""
    if isinstance(preserve, str):
        raise TypeError(f"agent_task({kind!r}): preserve takes a list of JSON pointers, not one string: [{preserve!r}]")
    pointers = tuple(dict.fromkeys(preserve))
    if not pointers:
        return ()
    if not (isinstance(output, type) and issubclass(output, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): preserve keeps parts of a JSON document: give output= a pydantic model (not str or Rows)")
    if output_from != "file":
        raise TypeError(f'agent_task({kind!r}): preserve keeps parts of a file the agent writes, not of output_from="message"')
    json_schema = output.model_json_schema()
    for pointer in pointers:
        error = syntax_error(pointer) or schema_error(pointer, json_schema)
        if error:
            raise TypeError(f"agent_task({kind!r}): preserve {error}")
    return pointers


def _checked_tools(kind: str, tools: Sequence[str] | None) -> tuple[str, ...] | None:
    """`tools` as declared: None, or `()`. A list of tool names is refused: they are each
    coding agent's own (`Read` for Claude Code, `read` for omp), so a role names them."""
    if tools is None:
        return None
    if isinstance(tools, str) or not isinstance(tools, Sequence):
        raise TypeError(f"agent_task({kind!r}): tools must be () (no tools) or None, not {tools!r}")
    if tools:
        raise TypeError(
            f"agent_task({kind!r}): tools takes () (no tools) or None; the tools a task may use are its role's "
            "(`tools:` in agents/<role>.md) and its plugin's settings.json, in each coding agent's own names"
        )
    return ()


@dataclass(frozen=True, eq=False)
class PythonTask[**P, Out]:
    """A Python function as a task. Build one with `@python_task`. It is called as its
    function is (`P`, its parameters), and its output is `Out`."""

    fn: Callable[P, Any]
    #: Its kind: the function's name, unless `python_task(kind=)` names another.
    kind: str
    output_schema: type[BaseModel] | None
    validators: tuple[Validator, ...]
    claims: tuple[str, ...] = ()
    #: A resume runs its tasks again even when an earlier attempt finished them.
    rerun_on_resume: bool = False
    #: Fresh attempts after the first, each after an exception of `retry_on`.
    retries: int = 0
    #: The exception classes that give an attempt a fresh one; any other fails the task.
    retry_on: tuple[type[Exception], ...] = ()
    #: The output file's path relative to `<run>/out/`, a template (`python_task(output_name=)`).
    output_name: str = DEFAULT_OUTPUT_NAME
    #: The function that returns its outside state, which its fingerprint covers (`python_task(outside_state=)`).
    outside_state: OutsideState | None = None
    #: What checks and converts its arguments against the function's annotations.
    _param_types: _ParamTypes = dataclasses.field(init=False, repr=False)
    #: Its call options (`options`); none for a declaration.
    _options: _CallOptions = dataclasses.field(default=_NO_OPTIONS, init=False, repr=False)
    #: The declaration `options` made it from; None for a declaration itself.
    _declaration: PythonTask[..., Any] | None = dataclasses.field(default=None, init=False, repr=False)

    #: Who executes it (`Task.executor`): this process, in Python.
    executor = "python"
    #: What its output file holds: `json`, or `jsonl` for a task that returns `Rows`.
    output_format = "json"

    def __post_init__(self) -> None:
        object.__setattr__(self, "_param_types", _ParamTypes(self.kind, self.fn))  # once, at declaration
        if is_rows(self.output_schema):
            object.__setattr__(self, "output_format", "jsonl")

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Pending[Out]:
        """Queue this Python task, with its call options (`options`). It is called as its
        function is: the arguments are bound to the function's parameters, and the one named
        `unit`, a string, is the task's unit (a function without it makes tasks with no
        unit). The rest are its params, copied as JSON here (a `Pending` among them, at any
        depth, or a value that is not JSON raises TypeError) and converted to their
        parameters' annotations when the task runs. A call the function could not take (a
        keyword it has no parameter for, a required parameter left out) raises TypeError
        here, and so does a call option given as a keyword (`key=`) that the function has
        no parameter for: `options` gives it."""
        unit, params = self._bound(args, kwargs)
        o = self._options
        return current_graph().add(
            declaration_of(self),
            unit=unit,
            params=params,
            key=o.key,
            after=o.after,
            priority=o.priority,
            cancellable=o.cancellable,
        )

    def options(
        self,
        *,
        key: str | None | Literal[_Keep.KEEP] = _Keep.KEEP,
        after: Sequence[Pending[Any] | str] | Literal[_Keep.KEEP] = _Keep.KEEP,
        priority: float | Literal[_Keep.KEEP] = _Keep.KEEP,
        cancellable: bool | Literal[_Keep.KEEP] = _Keep.KEEP,
    ) -> Self:
        """This task with call options, as `AgentTask.options`: `key`, `after`, `priority`
        and `cancellable`. A Python task runs no coding agent, so it has no credential. A
        cancelled Python task that is running runs to its end: a thread cannot be stopped."""
        made = self._options.given(
            f"{self.kind}.options", key=key, after=after, priority=priority, credential=_Keep.KEEP, cancellable=cancellable
        )
        return _with_options(self, made)

    def _bound(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """The unit and the params of a call `task(*args, **kwargs)`: the arguments bound to
        the function's parameters, the one named `unit` taken out. TypeError when the function
        could not be called so, and, at the first call, when its annotations do not resolve."""
        signature = inspect.signature(self.fn)  # read at declaration (`_checked_signature`), so it reads
        _refuse_call_options(self.kind, kwargs, set(signature.parameters), python=True)
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            hint = ""
            if "unit" not in signature.parameters and args and isinstance(args[0], str):
                hint = "; a Python task is given its unit through a parameter named unit (def f(unit: str, ...))"
            raise TypeError(
                f"{self.kind}(...): the function cannot take this call: {exc}{hint} (contraagent docs tasks, Python tasks)"
            ) from None
        params = dict(bound.arguments)
        unit: Any = ""
        if "unit" in signature.parameters:
            default = signature.parameters["unit"].default
            unit = params.pop("unit") if "unit" in params else (default if default is not inspect.Parameter.empty else "")
            if not isinstance(unit, str):
                raise TypeError(f"{self.kind}(...): unit is the task's unit, a string, not {unit!r}")
        self._param_types.adapters()
        return unit, params

    def digest(self) -> str:
        """A digest of what defines this kind of task, part of each task's fingerprint: the
        function's source (its bytecode when it has none), its output schema, its
        validators and the name of its `outside_state` function."""
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
                **({"outside_state": _function_name(self.outside_state)} if self.outside_state is not None else {}),
            }
        )

    def definition(self, cwd: Path | None = None) -> dict[str, Any]:
        """What defines this kind of task, for the monitor (`definitions/<kind>.json`):
        where the function is, what it takes and returns, its docstring and source."""
        fn = inspect.unwrap(self.fn)
        body: dict[str, Any] = {
            "executor": "python",
            "function": f"{fn.__module__}.{fn.__qualname__}",
            "output": _type_name(self.output_schema) if self.output_schema is not None else "none",
            "validators": [getattr(v, "name", None) or getattr(v, "__name__", type(v).__name__) for v in self.validators],
        }
        if self.retries:
            body["retries"] = self.retries
            body["retry_on"] = [_class_name(c) for c in self.retry_on]
        if self.outside_state is not None:
            body["outside_state"] = _function_name(self.outside_state)
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
            body["file"], body["line"] = shown.as_posix(), start
            body["files"] = [{"path": shown.as_posix(), "part": "source", "text": "".join(lines)[:20_000]}]
        except (OSError, TypeError):
            pass  # a function without source (built-in, REPL): the facts above still say what it is
        return body

    def arguments(self, unit: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """The function's arguments: `kwargs` and the unit for a `unit` parameter, each checked and converted against its parameter's
        annotation (`_ParamTypes`). `InvalidInput` when one does not match."""
        if "unit" in inspect.signature(self.fn).parameters:
            kwargs = {**kwargs, "unit": unit}
        return self._param_types.convert(kwargs)

    def invoke(self, unit: str, kwargs: dict[str, Any]) -> Any:
        """Call the function with its `arguments`; `InvalidInput` before the call when one
        does not match its annotation."""
        fn: Callable[..., Any] = self.fn  # its arguments are bound by name (`arguments`)
        return fn(**self.arguments(unit, kwargs))


class _ParamTypes:
    """A Python task's parameters as types: one pydantic `TypeAdapter` per annotated
    parameter, built once. `convert` validates each argument in pydantic's lax mode and
    gives the converted value: a dict given to a model parameter becomes the model, a list
    of dicts given to `list[Model]` a list of models, `"3"` given to `int` 3. An
    unannotated parameter, or one annotated `Any`, takes its argument as it is. A Python
    task is given JSON, so an annotation pydantic has no JSON Schema for raises TypeError
    where the task is declared. Annotations that name a type defined after the function
    resolve at the first call instead; one that names what is not defined then (a type
    imported under `if TYPE_CHECKING:` only) raises TypeError at that call."""

    def __init__(self, kind: str, fn: Callable[..., Any]) -> None:
        self._kind = kind
        self._fn = fn
        self._adapters: dict[str, TypeAdapter[Any]] | None = None
        try:
            self._adapters = _param_adapters(kind, fn)
        except NameError:  # a type defined later in its module: resolved at the first call
            pass

    def adapters(self) -> dict[str, TypeAdapter[Any]]:
        """The adapters by parameter name. TypeError when an annotation does not resolve."""
        if self._adapters is None:
            try:
                self._adapters = _param_adapters(self._kind, self._fn)
            except NameError as exc:
                raise TypeError(
                    f"{self._kind}(...): an annotation of {_function_name(self._fn)} names {exc.name}, which is not defined "
                    "when the task is called; import it where Python runs it, not under `if TYPE_CHECKING:` only"
                ) from None
        return self._adapters

    def convert(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """`kwargs` with each annotated argument validated and converted; `InvalidInput`
        naming each parameter whose argument does not match."""
        adapters = self.adapters()
        out: dict[str, Any] = {}
        errors: list[str] = []
        for name, value in kwargs.items():
            adapter = adapters.get(name)
            if adapter is None:
                out[name] = value
                continue
            try:
                out[name] = adapter.validate_python(value)
            except ValidationError as exc:
                errors += _param_errors(name, exc)
        if errors:
            shown = errors[:3] + ([f"{len(errors) - 3} more errors"] if len(errors) > 3 else [])
            raise InvalidInput("; ".join(shown))
        return out


def _param_adapters(kind: str, fn: Callable[..., Any]) -> dict[str, TypeAdapter[Any]]:
    """A `TypeAdapter` per annotated parameter of `fn` (not `Any`). `NameError` when an
    annotation names a type not defined yet; TypeError for one pydantic has no JSON
    Schema for."""
    hints = typing.get_type_hints(fn, include_extras=True)
    adapters: dict[str, TypeAdapter[Any]] = {}
    for p in inspect.signature(fn).parameters.values():
        ann = hints.get(p.name, Any)
        if ann is Any:
            continue
        try:
            adapter: TypeAdapter[Any] = TypeAdapter(ann)
            adapter.json_schema()
        except Exception:
            raise TypeError(
                f"python_task({kind!r}): parameter {p.name} is annotated {ann!r}, which has no JSON Schema; a Python task "
                "is given JSON values: annotate it with a JSON type (str, int, a list, a dict) or a pydantic model"
            ) from None
        adapters[p.name] = adapter
    return adapters


def _checked_signature(owner: str, fn: Callable[..., Any]) -> inspect.Signature:
    """The signature of a Python task's function: named parameters only, since each one is
    a param by its name. TypeError for a positional-only parameter, `*args` or `**kwargs`."""
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        raise TypeError(f"{owner}: takes a function whose signature Python can read, not {fn!r}") from None
    for p in signature.parameters.values():
        if p.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise TypeError(f"{owner}: parameter {p.name} is positional-only; a Python task's params are named: drop the /")
        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            raise TypeError(f"{owner}: *{p.name}: a Python task's params are named; give each its own parameter, or take one list")
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            raise TypeError(f"{owner}: **{p.name}: a Python task's params are named; give each its own parameter, or take one dict")
    return signature


def _param_errors(name: str, exc: ValidationError) -> list[str]:
    """Each error of a parameter's argument in one line: `parameter items[0].service: Field required`."""
    lines = []
    for err in exc.errors(include_url=False):
        where = name + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in err["loc"])
        lines.append(f"parameter {where}: {err['msg']}")
    return lines


# A function that may return `Partial(value, ...)` is annotated `-> Out | Partial[Out]`: its
# tasks' output, what a flow receives at `await` and what `Pending.output` reads, is the
# value, an `Out`. The first overload is for a function that always returns `Partial`.
@overload
def python_task[**P, Out](fn: Callable[P, Partial[Out]], /) -> PythonTask[P, Out]: ...
@overload
def python_task[**P, Out](fn: Callable[P, Out | Partial[Out]], /) -> PythonTask[P, Out]: ...
@overload
def python_task(
    *,
    kind: str | None = None,
    validators: Sequence[Validator] = (),
    claims: Sequence[str] = (),
    rerun_on_resume: bool = False,
    retries: int = 0,
    retry_on: tuple[type[Exception], ...] = (),
    output_name: str | None = None,
    outside_state: OutsideState | None = None,
) -> Callable[[Callable[_P, _Out | Partial[_Out]]], PythonTask[_P, _Out]]: ...


def python_task(
    fn: Callable[..., Any] | None = None,
    /,
    *,
    kind: str | None = None,
    validators: Sequence[Validator] = (),
    claims: Sequence[str] = (),
    rerun_on_resume: bool = False,
    retries: int = 0,
    retry_on: tuple[type[Exception], ...] = (),
    output_name: str | None = None,
    outside_state: OutsideState | None = None,
) -> PythonTask[..., Any] | Callable[[Callable[..., Any]], PythonTask[..., Any]]:
    """Turn a function into a Python task of kind `kind` (default: the function's
    name; no `*`, `?` or `[`, as for `agent_task`). A task call calls it as the function is
    called (`PythonTask[P, Out]` keeps its parameters' types): its parameters are named
    (no positional-only parameter, `*args` or `**kwargs`, which raise here), each a param
    but the one named `unit`, which takes the task's unit; each annotation is a type
    pydantic has a JSON Schema for, since a task is given JSON
    (`Annotated[T, Field(description=...)]` documents one). Its return annotation is its output: a pydantic model (the schema),
    any JSON-able type (kept as a JSON file), or None (no output). A function that could do
    only part of its work returns `Partial(value, reason=)` (annotated `-> Out | Partial[Out]`):
    `value` is its output as usual, the task finishes ok with stop `partial`, and a resume
    runs it again. `claims` (templates), as for
    `agent_task`: the names each of its tasks holds while it runs. `rerun_on_resume`, as for
    `agent_task`: a resume runs its tasks again (a step that publishes the work's state).
    `output_name`, as for `agent_task`: the output file's path relative to `<run>/out/`
    (default `{kind}/{unit}.json`). `outside_state`, as for `agent_task`: a function that
    returns the state the function reads beside its arguments (a digest of a state file the
    pipeline keeps, of files another process wrote), which its fingerprint covers, so a
    resume runs the task again when it changed.

    `retries`: the fresh attempts a task may make after its first, each after an attempt
    that raised an instance of a class in `retry_on` (a tuple of exception classes,
    `(ConnectionError, TimeoutError)`); any other exception fails the task at once, and so
    do an off-contract input (`invalid_input`) and output (`invalid_output`). Each attempt is
    a journal row of its own. The two go together: `retries` above 0 with no `retry_on`, or
    `retry_on` with `retries=0`, raises here. A function that needs a server restores it
    itself at its start, so a fresh attempt finds it running."""

    def wrap(f: Callable[..., Any]) -> PythonTask[..., Any]:
        named = kind or f.__name__
        owner = f"python_task({named!r})"
        _check_kind(owner, named)
        signature = _checked_signature(owner, f)
        checked = _checked_claims(owner, claims, set(signature.parameters) - {"unit"})
        tries, on = checked_retries(owner, retries, retry_on)
        _check_outside_state(owner, outside_state, rerun_on_resume)
        if output_name is not None:
            _check_output_name(owner, output_name)
        schema = _output_schema_of(f)
        return PythonTask(
            fn=f,
            kind=named,
            output_schema=schema,
            validators=tuple(validators),
            claims=checked,
            rerun_on_resume=bool(rerun_on_resume),
            retries=tries,
            retry_on=on,
            output_name=output_name or ("{kind}/{unit}.jsonl" if is_rows(schema) else DEFAULT_OUTPUT_NAME),
            outside_state=outside_state,
        )

    return wrap(fn) if fn is not None else wrap


def _class_name(cls: type) -> str:
    """`ConnectionError` for a built-in class; `module.qualname` for any other."""
    return cls.__qualname__ if cls.__module__ == "builtins" else f"{cls.__module__}.{cls.__qualname__}"


def _output_schema_of(fn: Callable[..., Any]) -> type[BaseModel] | None:
    ann: Any
    try:
        ann = typing.get_type_hints(fn).get("return", inspect.Signature.empty)
    except Exception:  # an unresolvable annotation reads as "any JSON"
        ann = Any
    if ann is inspect.Signature.empty:
        ann = Any
    ann = _without_partial(ann)
    if ann is None or ann is type(None):
        return None
    row = rows_model(ann)
    if row is not None:
        return rows_file(row)
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann
    return RootModel[ann]


def _without_partial(ann: Any) -> Any:
    """A return annotation without its `Partial`: `Index | Partial[Index]` and
    `Partial[Index]` are `Index`, the output either way."""
    if ann is Partial or typing.get_origin(ann) is Partial:
        args = typing.get_args(ann)
        return args[0] if args else Any
    if typing.get_origin(ann) in (typing.Union, types.UnionType):
        members = typing.get_args(ann)
        kept = tuple(a for a in members if not (a is Partial or typing.get_origin(a) is Partial))
        if len(kept) != len(members):
            return typing.Union[kept] if kept else Any  # noqa: UP007 (a union built from a tuple)
    return ann


def _digest(body: dict[str, Any]) -> str:
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


#: The keywords a task call takes itself, so never a parameter of the task.
#: The call options (`options`): a task call given one of them as a keyword that is no
#: parameter of its task raises TypeError.
CALL_OPTIONS = ("key", "after", "priority", "credential", "cancellable")


def declaration_of[T: AgentTask[Any, Any] | PythonTask[..., Any]](task: T) -> T:
    """The declaration of `task`: itself, or the one `options` made it from."""
    # `options` sets `_declaration` to a task of the same class as the copy.
    return task._declaration if task._declaration is not None else task  # pyright: ignore[reportReturnType]


def _with_options[T: AgentTask[Any, Any] | PythonTask[..., Any]](task: T, options: _CallOptions) -> T:
    """`task` with `options`: a shallow copy that refers to the same declaration, so nothing
    the declaration built (a Python task's parameter types) is built again."""
    made = copy.copy(task)
    object.__setattr__(made, "_options", options)  # a frozen dataclass: set as its __init__ sets
    object.__setattr__(made, "_declaration", declaration_of(task))
    return made


def _refuse_call_options(kind: str, given: Mapping[str, Any], params: set[str], *, python: bool) -> None:
    """TypeError when a task call gives a call option as a keyword that is no parameter of
    the task (`params`): `options` gives it."""
    words = [w for w in CALL_OPTIONS if w in given and w not in params]
    if not words:
        return
    if python and words == ["credential"]:
        raise TypeError(
            f"{kind}(...): credential= names the credential an agent task runs as, and a Python task runs no "
            "coding agent, so it has no credential: drop credential= (contraagent docs routing, A task call's credential)"
        )
    shown = ", ".join(f"{w}=" for w in words)
    example = ", ".join(f"{w}=..." for w in words)
    one = len(words) == 1
    raise TypeError(
        f"{kind}(...): {shown} {'is a call option' if one else 'are call options'}, not a parameter of the task: "
        f"give {'it' if one else 'them'} with options(): {kind}.options({example})(unit, ...) "
        "(contraagent docs tasks, Call options)"
    )


def _checked_key(where: str, key: Any) -> str | None:
    """A task's `key` option: a string; None or empty: the kind and unit make it."""
    if key is not None and not isinstance(key, str):
        raise TypeError(f"{where}(...): key must be a string or None, not {key!r}")
    return key or None


def _checked_after(where: str, after: Any) -> tuple[Pending[Any] | str, ...]:
    """A task's `after` option: a list of tasks, each a `Pending` or a task's key."""
    if isinstance(after, (str, bytes, Pending)) or not isinstance(after, Iterable):
        raise TypeError(f"{where}(...): after takes a list of tasks (each a task call's result or a task key), not {after!r}")
    items = tuple(after)
    odd = [a for a in items if not isinstance(a, Pending) and not (isinstance(a, str) and a)]
    if odd:
        raise TypeError(f"{where}(...): after takes a list of tasks (each a task call's result or a task key), not {odd[0]!r} in it")
    return items


def _checked_priority(where: str, priority: Any) -> float:
    """A task's `priority` option: a finite number."""
    if isinstance(priority, bool) or not isinstance(priority, (int, float)) or not math.isfinite(priority):
        raise TypeError(f"{where}(...): priority must be a finite number, not {priority!r}")
    return float(priority)


def _checked_credential(where: str, credential: Any) -> str:
    """An agent task's `credential` option: the name of a `[credentials.<name>]`; None, its
    kind's (empty)."""
    if credential is None:
        return ""
    if not isinstance(credential, str) or not credential.strip() or credential != credential.strip():
        raise TypeError(f"{where}(...): credential must name a [credentials.<name>] or be None, not {credential!r}")
    return credential


def _checked_claims(owner: str, claims: Sequence[str], params: set[str] | None) -> tuple[str, ...]:
    """`claims` as declared, checked: each a non-empty template naming only `{unit}`, `{key}`,
    `{kind}` and `{params.<name>}`, `<name>` one of `params` (the task's params by name; None
    for a task that takes none)."""
    if isinstance(claims, str):
        raise TypeError(f"{owner}: claims must be a list of names, not the string {claims!r}")
    out = tuple(claims)
    for claim in out:
        if not isinstance(claim, str) or not claim:
            raise TypeError(f"{owner}: claims holds {claim!r}; each claim is a non-empty string")
        try:
            parts = list(string.Formatter().parse(claim))
        except ValueError as exc:
            raise ValueError(f"{owner}: claim {claim!r}: {exc}") from None
        for _, field, spec, conversion in parts:
            if field is None:
                continue
            if spec or conversion:
                raise ValueError(f"{owner}: claim {claim!r}: {{{field}}} takes no format or conversion")
            if field not in ("unit", "key", "kind") and not PARAM_FIELD.fullmatch(field):
                raise ValueError(f"{owner}: claim {claim!r} names {field}; it may name unit, key, kind and params.<name>")
            name = field.removeprefix("params.")
            if field.startswith("params.") and name not in (params or set()):
                has = f"its params are {', '.join(sorted(params))}" if params else "it takes no params"
                raise ValueError(f"{owner}: claim {claim!r} names params.{name}, and {has}")
    return out


def _model_fields(model: type[BaseModel] | None) -> set[str] | None:
    """The names a params model's JSON gives its fields: each field's name, and its alias
    when it has one. None for no model."""
    if model is None:
        return None
    names = set(model.model_fields)
    for f in model.model_fields.values():
        names |= {a for a in (f.alias, f.serialization_alias) if a}
    return names


def _check_kind(owner: str, kind: object) -> None:
    """A kind name holds none of the characters of a pattern of kinds."""
    if isinstance(kind, str) and GLOB_CHARACTERS & set(kind):
        raise TypeError(f"{owner}: a kind holds no *, ? or [ (a pattern of kinds, as --execute takes, uses them)")


def _check_output_name(owner: str, template: Any) -> None:
    """`output_name`: a relative path under `<run>/out/` naming only `{unit}`, `{key}` and
    `{kind}`, with no `..`, `.` or empty segment."""
    if not isinstance(template, str) or not template:
        raise TypeError(f"{owner}: output_name must be a path relative to the run's out/, not {template!r}")
    try:
        parts = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise ValueError(f"{owner}: output_name {template!r}: {exc}") from None
    for _, field, spec, conversion in parts:
        if field is None:
            continue
        if field not in ("unit", "key", "kind"):
            raise ValueError(f"{owner}: output_name {template!r} names {{{field}}}; it may name unit, key and kind")
        if spec or conversion:
            raise ValueError(f"{owner}: output_name {template!r}: {{{field}}} takes no format or conversion")
    if _rooted(template):
        raise ValueError(f"{owner}: output_name {template!r} is absolute; it is a path relative to the run's out/")
    if bad := [seg for seg in template.split("/") if seg in ("", ".", "..")]:
        segment = repr(bad[0]) if bad[0] else "empty"
        raise ValueError(f"{owner}: output_name {template!r} has a {segment} segment; it is a path inside the run's out/")


def _function_name(fn: Callable[..., Any]) -> str:
    """A function's `module.qualname`, as a definition names it."""
    fn = inspect.unwrap(fn)
    name = getattr(fn, "__qualname__", None) or type(fn).__qualname__
    return f"{getattr(fn, '__module__', '') or ''}.{name}".lstrip(".")


def _check_outside_state(owner: str, outside_state: Any, rerun_on_resume: bool) -> None:
    """`outside_state`: None, or a function; not beside `rerun_on_resume`, which runs every
    task of the kind again on a resume whatever it returns."""
    if outside_state is None:
        return
    if not callable(outside_state):
        raise TypeError(f"{owner}: outside_state must be a function of (unit, params), not {outside_state!r}")
    if rerun_on_resume:
        raise TypeError(
            f"{owner}: rerun_on_resume runs every task of it again on a resume, so outside_state changes nothing; drop one of them"
        )


def _check_changes_pattern(kind: str, pattern: str) -> None:
    """A `changes` pattern: relative, inside the working directory, naming only `{unit}`,
    `{key}` and `{kind}`; after a leading `!` for one that leaves paths out."""
    if not isinstance(pattern, str) or not pattern.removeprefix("!"):
        raise TypeError(f"agent_task({kind!r}): changes holds {pattern!r}, not a pattern")
    pattern = pattern.removeprefix("!")  # one that leaves paths out follows the same rules
    try:
        fields = {f for _, f, _, _ in string.Formatter().parse(pattern) if f is not None}
    except ValueError as exc:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r}: {exc}") from None
    unknown = sorted(fields - {"unit", "key", "kind"})
    if unknown:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r} names {', '.join(unknown)}; it may name unit, key and kind")
    if _rooted(pattern) or ".." in PureWindowsPath(pattern).parts:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r} is not inside the working directory")


def _caller_dir() -> Path | None:
    """The directory of the file that called `agent_task`: the module of the innermost
    frame of flow code on the stack (`code.flow_code`: neither contraagent's own code, its
    shipped examples excepted, nor the standard library), so a call that reaches
    `agent_task` through contraagent itself (`implementations=`) or through the standard
    library is placed by the user's file. None when that module has no file (a REPL,
    `exec`). A function of the user's own that calls `agent_task` for others is such a
    file: from another directory, a caller passes it an absolute path
    (`Path(__file__).parent / "plugins/x"`)."""
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    while caller is not None and not flow_code(caller.f_code.co_filename):
        caller = caller.f_back
    file = caller.f_globals.get("__file__") if caller is not None else None
    return Path(file).resolve().parent if file else None


def _rooted(path: str) -> bool:
    """Whether `path` starts at a root on some OS: `/`, `\\`, a drive (`C:`) or a share. Not a
    path inside the working directory on any of them, whichever OS reads it now."""
    return bool(PureWindowsPath(path).anchor)


def _relative_to(base: Path | None, path: str | Path) -> Path:
    """A relative plugin path is relative to the file that called `agent_task`."""
    p = Path(path)
    if p.is_absolute():
        return p
    return base / p if base is not None else p.resolve()
