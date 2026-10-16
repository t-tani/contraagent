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

import dataclasses
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
from typing import Any, Literal, TypeVar, overload

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter, ValidationError
from pydantic.errors import PydanticSchemaGenerationError

from contraagent._internal.contracts.pointers import schema_error, syntax_error
from contraagent._internal.contracts.rows import is_rows, rows_file, rows_model
from contraagent._internal.contracts.validators import Validator, validator_name
from contraagent._internal.dispatch.python_task import InvalidInput, checked_retries
from contraagent._internal.dispatch.task import Partial
from contraagent._internal.dispatch.templates import PARAM_FIELD
from contraagent._internal.pipeline.graph import Pending, current_graph
from contraagent._internal.plugins import Plugin, PluginError
from contraagent._internal.plugins.plugin import body
from contraagent._internal.routing.config import TASK_KEYS, ConfigError, PipelineConfig

Out = TypeVar("Out")

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


@dataclass(frozen=True, eq=False)
class AgentTask[Out]:
    """An agent task's interface. Build one with `agent_task`."""

    kind: str
    output: type | None
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
    output_of: AgentTask[Any] | PythonTask[Any] | None = None
    #: The base kind of an implementation kind (`agent_task(implementations=)`); empty for any other.
    base_kind: str = ""

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
        whose output file it writes (`output_of`), the parts of it to keep (`preserve`) and, for a light launch, that it has no tools."""
        return _digest(self._defined())

    def differences(self, other: AgentTask[Any]) -> list[str]:
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
        }

    def __call__(
        self,
        unit: str = "",
        *,
        key: str | None = None,
        after: Sequence[Pending[Any] | str] = (),
        priority: float = 0.0,
        credential: str | None = None,
        **params: Any,
    ) -> Pending[Out]:
        """Queue this task for `unit`. `params` may hold `Pending` outputs of other tasks.
        `priority` breaks ties in the queue, higher first (`WorkQueue`); it is not a parameter.
        `credential` names a `[credentials.<name>]` this task runs as on every route of its
        kind, failover hops included, in place of the kind's; None: the kind's. It outranks
        the kind's `[tasks.<kind>]` table and its declaration; a run-wide override
        (`Overrides(credential=)`) outranks it. A credential that does not exist or does not
        carry the traits the task `requires` is refused before the task launches."""
        if self.params is not None:
            _check_param_names(self.kind, self.params, params)
        words = {
            "key": _checked_key(self.kind, key),
            "after": _checked_after(self.kind, after),
            "priority": _checked_priority(self.kind, priority),
            "credential": _checked_credential(self.kind, credential),
        }
        return current_graph().add(self, unit=unit, params=params, **words)


@overload
def agent_task[Out](
    kind: str,
    *,
    output: type[Out] | Any | None = None,  # Any: `Annotated[str, Field(examples=[...])]` has no type
    params: type[BaseModel] | None = None,
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
    output_of: AgentTask[Any] | PythonTask[Any] | None = None,
    implementations: None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
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
) -> AgentTask[Out]: ...


@overload
def agent_task[Out](
    kind: str,
    *,
    output: type[Out] | Any | None = None,  # Any: `Annotated[str, Field(examples=[...])]` has no type
    params: type[BaseModel] | None = None,
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
    output_of: AgentTask[Any] | PythonTask[Any] | None = None,
    implementations: Mapping[str, str | Path],
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
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
) -> Mapping[str, AgentTask[Out]]: ...


def agent_task[Out](
    kind: str,
    *,
    output: type[Out] | Any | None = None,  # Any: `Annotated[str, Field(examples=[...])]` has no type
    params: type[BaseModel] | None = None,
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
    output_of: AgentTask[Any] | PythonTask[Any] | None = None,
    implementations: Mapping[str, str | Path] | None = None,
    agent: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    credential: str | None = None,
    model_failover: bool | None = None,
    fallbacks: Sequence[Mapping[str, Any]] | None = None,
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
) -> AgentTask[Out] | Mapping[str, AgentTask[Out]]:
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
    `output`: a pydantic model (a JSON file checked against it), `str` (a text
    document) or `Rows[Row]` (rows: a JSON Lines file, each line one `Row`, which the agent
    may write one row at a time; the flow receives a `Rows`, a list of `Row`);
    `Annotated[str, Field(examples=[...])]` is a text document with an example
    (the model's own example: `model_config = ConfigDict(json_schema_extra={"examples": [...]})`),
    which a stub run writes (`contraagent.testing.writes_example`). `validators` add checks the file must pass beyond its schema
    (`contraagent.Validator`: a Python function, `CommandValidator(["textlint", ...])`); a
    Python validator of rows is given the `Rows`.
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
    under it; one that starts with `!` leaves out what it matches and everything under it,
    `["**", "!.git/**"]`). Each attempt's changes under them are recorded in its journal row, and
    the files a failed attempt created are removed (but with `keep_failed_changes`, below).
    Tasks that run at once under one pattern cannot be told apart: put `{unit}` in it.
    `instructions`: a text put before the call protocol, for a task with no plugin. Such a
    task runs with the permissions of the plugin template's `settings.json` (Claude Code).
    `output_name`: the output file's path relative to `<run>/out/`, a template:
    `{unit}` is the unit, or the key when the task call gives `key=` (or no unit);
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
    `implementations`: one step done in several ways, by name: `{"python": "plugins/review-python",
    "go": "plugins/review-go"}` (plugin directories, relative as `plugin` is; it takes the place
    of `plugin`). Each is a kind of its own, `<kind>-<name>` (`review-go`), with that plugin
    and every other argument given here; `kind` is their **base kind**. A name is letters,
    digits and `_`. It returns a mapping of agent tasks by name: `review["go"](unit)`.
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
    `max_corrections`: the correction rounds after the first launch, 0 to 20 (default 3,
    or `[defaults].max_corrections`): how many times an output that fails its checks goes
    back to the same session with the errors before the task ends `invalid_output`; 0
    sends none back.
    """
    # The task table keys, as given (`TASK_KEYS`: a test holds them equal to these parameters).
    given = locals()
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
    if output is not None and rows is None and not is_text(output) and not (isinstance(output, type) and issubclass(output, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): output must be a pydantic model, str or Rows[Model], not {output!r}")
    if params is not None and not (isinstance(params, type) and issubclass(params, BaseModel)):
        raise TypeError(f"agent_task({kind!r}): params must be a pydantic model, not {params!r}")
    if params is not None and (taken := sorted(AGENT_CALL_WORDS & set(params.model_fields))):
        raise TypeError(
            f"agent_task({kind!r}): params {params.__name__} has a field named {', '.join(taken)}; "
            f"an agent task call takes {', '.join(sorted(AGENT_CALL_WORDS))} itself: rename the field"
        )
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
    checked_claims = _checked_claims(f"agent_task({kind!r})", claims)
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


class Implementations[Out](Mapping[str, AgentTask[Out]]):
    """One step declared with several implementations (`agent_task(implementations=)`): an
    agent task per implementation, by name. `review["go"]` is the kind `review-go`; call it as
    any agent task (`yield review["go"](unit)`). `kind` is their base kind."""

    def __init__(self, kind: str, tasks: Mapping[str, AgentTask[Out]]) -> None:
        self.kind = kind
        self._tasks = dict(tasks)

    @property
    def kinds(self) -> list[str]:
        """The implementation kinds, in the order declared (`review-python`, `review-go`)."""
        return [t.kind for t in self._tasks.values()]

    def __getitem__(self, name: str) -> AgentTask[Out]:
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
class PythonTask[Out]:
    """A Python function as a task. Build one with `@python_task`. Its kind is its name."""

    fn: Callable[..., Out]
    name: str
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
    #: What checks and converts its arguments against the function's annotations.
    _param_types: _ParamTypes = dataclasses.field(init=False, repr=False)

    #: Who executes it (`Task.executor`): this process, in Python.
    executor = "python"
    #: What its output file holds: `json`, or `jsonl` for a task that returns `Rows`.
    output_format = "json"

    def __post_init__(self) -> None:
        object.__setattr__(self, "_param_types", _ParamTypes(self.fn))  # once, at declaration
        if is_rows(self.output_schema):
            object.__setattr__(self, "output_format", "jsonl")

    @property
    def kind(self) -> str:
        return self.name

    def __call__(
        self,
        unit: str = "",
        *,
        key: str | None = None,
        after: Sequence[Pending[Any] | str] = (),
        priority: float = 0.0,
        **kwargs: Any,
    ) -> Pending[Out]:
        """Queue this Python task for `unit`; the function runs with `kwargs` (Pending resolved).
        A function with a `unit` parameter is given the unit too. `priority`, as for an
        agent task: a tie-breaker in the queue, higher first. A call the function could not
        take (a keyword it has no parameter for, a required parameter left out) raises
        TypeError here, and so does `credential=`: a Python task runs no coding agent, so
        it has no credential (unless its function has a parameter of that name)."""
        self._check_call(unit, kwargs)
        words = {
            "key": _checked_key(self.kind, key),
            "after": _checked_after(self.kind, after),
            "priority": _checked_priority(self.kind, priority),
        }
        return current_graph().add(self, unit=unit, params=kwargs, **words)

    def _check_call(self, unit: str, kwargs: dict[str, Any]) -> None:
        """TypeError when the function could not be called with `kwargs` (and the unit, for a
        `unit` parameter), as `invoke` would call it."""
        try:
            signature = inspect.signature(self.fn)
        except (TypeError, ValueError):  # a callable with no signature to read
            return
        if "credential" in kwargs and "credential" not in signature.parameters and not _takes_any_keyword(signature):
            raise TypeError(
                f"{self.kind}(...): credential= names the credential an agent task runs as, and a Python task runs no "
                "coding agent, so it has no credential: drop credential= (contraagent docs routing, A task call's credential)"
            )
        given = {**kwargs, "unit": unit} if unit and "unit" not in kwargs and "unit" in signature.parameters else kwargs
        try:
            signature.bind(**given)
        except TypeError as exc:
            raise TypeError(f"{self.kind}(...): the function cannot take this call: {exc} (contraagent docs tasks, Python tasks)") from None

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
        """The function's arguments: `kwargs` (every `Pending` already its output) and the
        unit for a `unit` parameter, each checked and converted against its parameter's
        annotation (`_ParamTypes`). `InvalidInput` when one does not match."""
        if unit and "unit" not in kwargs and "unit" in inspect.signature(self.fn).parameters:
            kwargs = {**kwargs, "unit": unit}
        return self._param_types.convert(kwargs)

    def invoke(self, unit: str, kwargs: dict[str, Any]) -> Any:
        """Call the function with its `arguments`; `InvalidInput` before the call when one
        does not match its annotation."""
        return self.fn(**self.arguments(unit, kwargs))


class _ParamTypes:
    """A Python task's parameters as types: one pydantic `TypeAdapter` per annotated
    parameter, built once, when the task is declared. `convert` validates each argument
    in pydantic's lax mode and gives the converted value: a dict given to a model
    parameter becomes the model, a list of dicts given to `list[Model]` a list of models,
    `"3"` given to `int` 3. An unannotated parameter, or one annotated `Any`, takes its
    argument as it is; so does every parameter of a function whose annotations do not
    resolve. A class pydantic has no schema for is checked with `isinstance`. Annotations
    that name a type defined after the function resolve at the first call instead."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self._fn = fn
        self._adapters: dict[str, TypeAdapter[Any]] | None = None
        try:
            self._adapters = _param_adapters(fn)
        except NameError:  # a type defined later in its module: resolved at the first call
            pass

    def adapters(self) -> dict[str, TypeAdapter[Any]]:
        """The adapters by parameter name."""
        if self._adapters is None:
            try:
                self._adapters = _param_adapters(self._fn)
            except Exception:  # annotations that do not resolve take every argument as it is
                self._adapters = {}
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


def _param_adapters(fn: Callable[..., Any]) -> dict[str, TypeAdapter[Any]]:
    """A `TypeAdapter` per annotated named parameter of `fn` (not `Any`). `NameError` when an
    annotation names a type not defined yet."""
    hints = typing.get_type_hints(fn)
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return {}
    named = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    adapters: dict[str, TypeAdapter[Any]] = {}
    for p in params:
        ann = hints.get(p.name, Any)
        if p.kind not in named or ann is Any:
            continue
        adapter = _adapter(ann)
        if adapter is not None:
            adapters[p.name] = adapter
    return adapters


def _adapter(ann: Any) -> TypeAdapter[Any] | None:
    """A `TypeAdapter` for `ann`; for a class pydantic has no schema for, an `isinstance`
    check; None when it can build neither (the argument is taken as it is)."""
    try:
        return TypeAdapter(ann)
    except PydanticSchemaGenerationError:
        try:
            return TypeAdapter(ann, config=ConfigDict(arbitrary_types_allowed=True))
        except Exception:
            return None
    except Exception:
        return None


def _param_errors(name: str, exc: ValidationError) -> list[str]:
    """Each error of a parameter's argument in one line: `parameter items[0].service: Field required`."""
    lines = []
    for err in exc.errors(include_url=False):
        where = name + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in err["loc"])
        lines.append(f"parameter {where}: {err['msg']}")
    return lines


@overload
def python_task[Out](fn: Callable[..., Out], /) -> PythonTask[Out]: ...
@overload
def python_task(
    *,
    name: str | None = None,
    validators: Sequence[Validator] = (),
    claims: Sequence[str] = (),
    rerun_on_resume: bool = False,
    retries: int = 0,
    retry_on: tuple[type[Exception], ...] = (),
    output_name: str | None = None,
) -> Callable[[Callable[..., Out]], PythonTask[Out]]: ...


def python_task(
    fn: Callable[..., Any] | None = None,
    /,
    *,
    name: str | None = None,
    validators: Sequence[Validator] = (),
    claims: Sequence[str] = (),
    rerun_on_resume: bool = False,
    retries: int = 0,
    retry_on: tuple[type[Exception], ...] = (),
    output_name: str | None = None,
) -> PythonTask[Any] | Callable[[Callable[..., Any]], PythonTask[Any]]:
    """Turn a function into a Python task of kind `name` (default: the function's
    name). Its return annotation is its output: a pydantic model (the schema),
    any JSON-able type (kept as a JSON file), or None (no output). A function that could do
    only part of its work returns `Partial(value, reason=)` (annotated `-> Out | Partial[Out]`):
    `value` is its output as usual, the task finishes ok with stop `partial`, and a resume
    runs it again. `claims` (templates), as for
    `agent_task`: the names each of its tasks holds while it runs. `rerun_on_resume`, as for
    `agent_task`: a resume runs its tasks again (a step that publishes the work's state).
    `output_name`, as for `agent_task`: the output file's path relative to `<run>/out/`
    (default `{kind}/{unit}.json`).

    `retries`: the fresh attempts a task may make after its first, each after an attempt
    that raised an instance of a class in `retry_on` (a tuple of exception classes,
    `(ConnectionError, TimeoutError)`); any other exception fails the task at once, and so
    do an off-contract input (`invalid_input`) and output (`invalid_output`). Each attempt is
    a journal row of its own. The two go together: `retries` above 0 with no `retry_on`, or
    `retry_on` with `retries=0`, raises here. A function that needs a server restores it
    itself at its start, so a fresh attempt finds it running."""

    def wrap(f: Callable[..., Out]) -> PythonTask[Out]:
        kind = name or f.__name__
        owner = f"python_task({kind!r})"
        checked = _checked_claims(owner, claims)
        tries, on = checked_retries(owner, retries, retry_on)
        if output_name is not None:
            _check_output_name(owner, output_name)
        try:
            taken = sorted(RESERVED_PARAMS & set(inspect.signature(f).parameters))
        except (TypeError, ValueError):
            taken = []
        if taken:
            raise TypeError(
                f"{owner}: the function has a parameter named {', '.join(taken)}; "
                f"a task call takes {', '.join(sorted(RESERVED_PARAMS))} itself: rename the parameter"
            )
        schema = _output_schema_of(f)
        return PythonTask(
            fn=f,
            name=kind,
            output_schema=schema,
            validators=tuple(validators),
            claims=checked,
            rerun_on_resume=bool(rerun_on_resume),
            retries=tries,
            retry_on=on,
            output_name=output_name or ("{kind}/{unit}.jsonl" if is_rows(schema) else DEFAULT_OUTPUT_NAME),
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
RESERVED_PARAMS = frozenset({"key", "after", "priority"})
#: The keywords an agent task call takes itself: those of every task call, and `credential`.
AGENT_CALL_WORDS = RESERVED_PARAMS | {"credential"}


def _checked_key(kind: str, key: Any) -> str | None:
    """A task call's `key`: a string, or None (or empty): the kind and unit make it."""
    if key is not None and not isinstance(key, str):
        raise TypeError(f"{kind}(...): key must be a string (or None), not {key!r}")
    return key


def _checked_after(kind: str, after: Any) -> tuple[Pending[Any] | str, ...]:
    """A task call's `after`: a list of tasks, each a `Pending` or a task's key."""
    if isinstance(after, (str, bytes, Pending)) or not isinstance(after, Iterable):
        raise TypeError(f"{kind}(...): after takes a list of tasks (each a task call's result or a task key), not {after!r}")
    items = tuple(after)
    odd = [a for a in items if not isinstance(a, Pending) and not (isinstance(a, str) and a)]
    if odd:
        raise TypeError(f"{kind}(...): after takes a list of tasks (each a task call's result or a task key), not {odd[0]!r} in it")
    return items


def _takes_any_keyword(signature: inspect.Signature) -> bool:
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())


def _checked_priority(kind: str, priority: Any) -> float:
    """A task call's `priority`: a finite number."""
    if isinstance(priority, bool) or not isinstance(priority, (int, float)) or not math.isfinite(priority):
        raise TypeError(f"{kind}(...): priority must be a finite number, not {priority!r}")
    return float(priority)


def _checked_credential(kind: str, credential: Any) -> str:
    """An agent task call's `credential`: None, or the name of a `[credentials.<name>]`."""
    if credential is None:
        return ""
    if not isinstance(credential, str) or not credential.strip() or credential != credential.strip():
        raise TypeError(f"{kind}(...): credential must name a [credentials.<name>] (or be None), not {credential!r}")
    return credential


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
            if field not in ("unit", "key", "kind") and not PARAM_FIELD.fullmatch(field):
                raise ValueError(f"{owner}: claim {claim!r} names {field}; it may name unit, key, kind and params.<name>")
    return out


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


def _check_param_names(kind: str, model: type[BaseModel], params: dict[str, Any]) -> None:
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
