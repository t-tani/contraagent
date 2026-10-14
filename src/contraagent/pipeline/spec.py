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
import string
import typing
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar, overload

from pydantic import BaseModel, RootModel

from contraagent.pipeline.graph import CLAIM_PARAM, Pending, current_graph
from contraagent.plugins import Plugin, PluginError
from contraagent.plugins.plugin import body
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
    claims: tuple[str, ...] = ()
    #: Plugins whose skills the task loads too, after its own plugin (`agent_task(skills_from=)`).
    skills_from: tuple[Plugin, ...] = ()
    changes: tuple[str, ...] = ()
    #: Where the output arrives: `file` (the agent writes it) or `message` (its final message is it).
    output_from: str = "file"
    #: The agent's tools: None, those its role and settings allow; `()`, none (a light launch).
    tools: tuple[str, ...] | None = None

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
            return body(self.plugin.role_file(self.role).read_text()).strip()
        return (instructions if instructions is not None else self.instructions or "").strip()

    @property
    def plugins(self) -> tuple[Plugin, ...]:
        """Every plugin the task loads: its own first, then those of `skills_from`."""
        return ((self.plugin,) if self.plugin is not None else ()) + self.skills_from

    def digest(self) -> str:
        """A digest of what defines this kind of task, part of each task's fingerprint: its
        instructions, its role file's content, the skills of its plugins, its output schema,
        its validators, its params schema, its `changes` patterns, where its output arrives and,
        for a light launch, that it has no tools."""
        return _digest(self._defined())

    def differences(self, other: AgentTask) -> list[str]:
        """What `other`, a declaration of the same kind, declares otherwise: the parts of the
        digest, the plugin, `skills_from`, `config`, `requires`, `claims` and `output_name`. None:
        one kind, declared twice the same way."""
        if other is self:
            return []
        mine, theirs = self._defined(), other._defined()
        parts = [name for name in dict.fromkeys([*mine, *theirs]) if mine.get(name) != theirs.get(name)]
        if (self.plugin and self.plugin.root) != (other.plugin and other.plugin.root):
            parts.append("plugin")
        if [p.root for p in self.skills_from] != [p.root for p in other.skills_from]:
            parts.append("skills_from")
        return parts + [name for name in ("config", "requires", "claims", "output_name") if getattr(self, name) != getattr(other, name)]

    def _defined(self) -> dict[str, Any]:
        role = ""
        if self.plugin is not None and self.role is not None:
            try:
                role = self.plugin.role_file(self.role).read_text()
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
            **({"tools": list(self.tools)} if self.tools is not None else {}),
        }

    def __call__(
        self,
        unit: str = "",
        *,
        key: str | None = None,
        after: Sequence[Pending | str] = (),
        **params: Any,
    ) -> Pending[Out]:
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
    skills_from: Sequence[str | Path] = (),
    role: str | None = None,
    instructions: str | None = None,
    validators: Sequence[Validator] = (),
    output_name: str | None = None,
    output_from: Literal["file", "message"] = "file",
    requires: Sequence[str] = (),
    claims: Sequence[str] = (),
    changes: Sequence[str] = (),
    tools: Sequence[str] | None = None,
    **config: Any,
) -> AgentTask[Out]:
    """Declare an agent task.

    `plugin`: the directory that implements it (`contraagent plugin new`), relative
    to the file that declares the task. Its role (`agents/<role>.md`) is the
    procedure; `role` picks one when the plugin has several.
    `skills_from`: plugin directories (relative the same way) whose skills the task
    loads too, after its own plugin's: skills several tasks share. Such a plugin holds
    skills only; its agents, settings, tools and hooks would act on every task that
    loads it, so a plugin with any of them is refused here.
    `params`: a pydantic model the task's parameters must satisfy (default: any
    JSON values). They reach the agent in its call file, never in the prompt.
    `output`: a pydantic model (a JSON file checked against it) or `str` (a text
    document). `validators` add checks the file must pass beyond its schema
    (`contraagent.validators`: a Python function, `CommandValidator(["textlint", ...])`).
    `requires`: traits the credential it runs under must carry (`["zdr"]` for a
    task whose data may only go to a zero-data-retention organization). Which
    credential that is, is the config's to say; a route that does not satisfy
    it, failover hops included, is refused before anything launches.
    `claims`: the names each of its tasks holds while it runs; one task holds a name at
    a time, unless `claim_capacity` (`Pipeline(claim_capacity=)`, `[defaults.claim_capacity]`)
    allows more. A claim is a template: `{unit}`, `{kind}`, `{key}` (the task's key, `~n`
    included) and `{params.<name>}`, a parameter of the call (a list gives one name per
    element; an empty list raises at the call). So
    `["topic:{unit}"]` runs one task at a time on each topic, whatever its kind, and
    `["topic:{params.topics}"]` holds every topic a task names. A task that claims nothing
    runs beside any other.
    `changes`: `Path.glob` patterns, relative to the working directory, of the files its
    tasks may change beside their output (`["topics/{unit}/**"]`; `{unit}`, `{key}` and
    `{kind}` as in `output_name`; a pattern that matches a directory covers everything
    under it). Each attempt's changes under them are recorded in its journal row, and
    the files a failed attempt created are removed. Tasks that run at once under one
    pattern cannot be told apart: put `{unit}` in it.
    `instructions`: a text put before the call protocol, for a task with no plugin. Such a
    task runs with the permissions of the plugin template's `settings.json` (Claude Code).
    `output_name`: the output file's name under `<run>/out/<kind>/`, a template:
    `{unit}` is the unit, or the key when the task call gives `key=` (or no unit);
    `{key}` and `{kind}`. Default `{unit}.json` (`{unit}.md` for a text output).
    `output_from`: `"file"` (default), the agent writes the output file; `"message"`, its
    final message is the output: the runner writes it to the output file and checks it
    there, and a message that fails its checks goes back to the same session. For a task
    that needs no tool (a classification in one turn), it saves the turn the `Write` takes.
    `tools`: None (default), the tools its role and settings allow; `()`, none: a **light
    launch**, for a judgement in one turn. The role's text (without its frontmatter), or for a
    task with no plugin `instructions`, replaces the coding agent's own system prompt; the
    params and the output's JSON Schema are in the prompt (the agent cannot read a call file);
    no plugin, settings, skill, hook or MCP server is loaded. It needs `output_from="message"`.
    Tool names are each coding agent's own, so a list of them is not taken here: a role names
    its tools in its frontmatter, a plugin's `settings.json` what they may do.
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
    if output_from not in ("file", "message"):
        raise TypeError(f'agent_task({kind!r}): output_from must be "file" or "message", not {output_from!r}')
    if output_from == "message" and output is None:
        raise TypeError(f'agent_task({kind!r}): output_from="message" needs an output (a pydantic model or str)')
    checked_tools = _checked_tools(kind, tools)
    if checked_tools == () and output_from != "message":
        raise TypeError(f'agent_task({kind!r}): tools=() (a light launch) writes no file: give output_from="message" and an output')
    if checked_tools == () and skills_from:
        raise TypeError(f"agent_task({kind!r}): tools=() loads no skill: drop skills_from, or the tools=()")
    if config:
        # The same checks a [tasks.<kind>] table gets, so a typo is an error here too.
        try:
            PipelineConfig({"tasks": {kind: dict(config)}}).task_tables()
        except ConfigError as exc:
            raise ConfigError(str(exc).replace("<config>: [tasks.", "agent_task: [", 1)) from None
    changes = tuple(changes)
    for pattern in changes:
        _check_changes_pattern(kind, pattern)
    checked_claims = _checked_claims(f"agent_task({kind!r})", claims)
    base = _caller_dir()
    loaded = Plugin.load(_relative_to(base, plugin)) if plugin is not None else None
    shared = tuple(Plugin.load(_relative_to(base, p)) for p in ([skills_from] if isinstance(skills_from, (str, Path)) else skills_from))
    for p in shared:
        if others := p.besides_skills():
            raise PluginError(f"agent_task({kind!r}): skills_from {p.root} holds {', '.join(others)}; a plugin it names holds skills only")
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
        config=dict(config),
        validators=tuple(validators),
        requires=tuple(requires),
        claims=checked_claims,
        skills_from=shared,
        changes=changes,
        output_name=output_name or ("{unit}.md" if output is str else "{unit}.json"),
        output_from=output_from,
        tools=checked_tools,
    )


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
class PythonTask[Out]:
    """A Python function as a task. Build one with `@python_task`. Its kind is its name."""

    fn: Callable[..., Out]
    name: str
    output_schema: type[BaseModel] | None
    validators: tuple[Validator, ...]
    claims: tuple[str, ...] = ()

    #: Who executes it (`Task.executor`): this process, in Python.
    executor = "python"
    output_format = "json"

    @property
    def kind(self) -> str:
        return self.name

    @property
    def output_name(self) -> str:
        return "{unit}.json"

    def __call__(
        self,
        unit: str = "",
        *,
        key: str | None = None,
        after: Sequence[Pending | str] = (),
        **kwargs: Any,
    ) -> Pending[Out]:
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
    *, name: str | None = None, validators: Sequence[Validator] = (), claims: Sequence[str] = ()
) -> Callable[[Callable[..., Out]], PythonTask[Out]]: ...


def python_task(
    fn: Callable[..., Any] | None = None,
    /,
    *,
    name: str | None = None,
    validators: Sequence[Validator] = (),
    claims: Sequence[str] = (),
) -> PythonTask[Any] | Callable[[Callable[..., Any]], PythonTask[Any]]:
    """Turn a function into a Python task of kind `name` (default: the function's
    name). Its return annotation is its output: a pydantic model (the schema),
    any JSON-able type (kept as a JSON file), or None (no output). `claims` (templates), as for
    `agent_task`: the names each of its tasks holds while it runs."""

    def wrap(f: Callable[..., Out]) -> PythonTask[Out]:
        kind = name or f.__name__
        checked = _checked_claims(f"python_task({kind!r})", claims)
        return PythonTask(fn=f, name=kind, output_schema=_output_schema_of(f), validators=tuple(validators), claims=checked)

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


def _checked_claims(owner: str, claims: Sequence[str]) -> tuple[str, ...]:
    """`claims` as declared, checked: each a non-empty template naming only `{unit}`, `{key}`,
    `{kind}` and `{params.<name>}`."""
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
            if field not in ("unit", "key", "kind") and not CLAIM_PARAM.fullmatch(field):
                raise ValueError(f"{owner}: claim {claim!r} names {field}; it may name unit, key, kind and params.<name>")
    return out


def _check_changes_pattern(kind: str, pattern: str) -> None:
    """A `changes` pattern: relative, inside the working directory, naming only `{unit}`,
    `{key}` and `{kind}`."""
    if not isinstance(pattern, str) or not pattern:
        raise TypeError(f"agent_task({kind!r}): changes holds {pattern!r}, not a pattern")
    try:
        fields = {f for _, f, _, _ in string.Formatter().parse(pattern) if f is not None}
    except ValueError as exc:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r}: {exc}") from None
    unknown = sorted(fields - {"unit", "key", "kind"})
    if unknown:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r} names {', '.join(unknown)}; it may name unit, key and kind")
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        raise ValueError(f"agent_task({kind!r}): changes pattern {pattern!r} is not inside the working directory")


def _check_param_names(kind: str, model: type[BaseModel], params: dict) -> None:
    unknown = sorted(set(params) - set(model.model_fields))
    missing = sorted(n for n, f in model.model_fields.items() if f.is_required() and n not in params)
    if unknown or missing:
        bits = ([f"unknown {', '.join(unknown)}"] if unknown else []) + ([f"missing {', '.join(missing)}"] if missing else [])
        raise TypeError(f"{kind}(): parameters do not match {model.__name__}: {'; '.join(bits)}")


def _caller_dir() -> Path | None:
    """The directory of the file that called `agent_task` (None from a REPL)."""
    frame = inspect.currentframe()
    caller = frame.f_back.f_back if frame and frame.f_back else None
    file = caller.f_globals.get("__file__") if caller else None
    return Path(file).resolve().parent if file else None


def _relative_to(base: Path | None, path: str | Path) -> Path:
    """A relative plugin path is relative to the file that called `agent_task`."""
    p = Path(path)
    if p.is_absolute():
        return p
    return base / p if base is not None else p.resolve()
