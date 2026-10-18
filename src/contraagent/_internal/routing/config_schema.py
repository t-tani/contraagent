"""The pipeline config file as pydantic models: the source of its JSON Schema
(`contraagent/docs/schemas/pipeline.schema.json`).

`PipelineConfig` reads the file itself, with messages that name the table and the key;
these models state the same tables and keys (`TABLES`, `DEFAULTS_KEYS`,
`TASK_ROUTING_KEYS`, `TASK_TABLE_KEYS`, `TASK_ATTEMPT_KEYS`, the credential types), so an editor or a CI step
can check a file with no contraagent installed.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, TypeAdapter, create_model

from contraagent._internal.backends.credentials import AnyCredential
from contraagent._internal.routing.kind_config import MAX_CORRECTIONS_LIMIT, TASK_TABLE_KEYS
from contraagent._internal.routing.preflight import PreflightPolicy

#: A `context_warn_pct`: a whole percent from 1 to 99.
WarnPct = Annotated[StrictInt, Field(ge=1, le=99)]
#: A `max_corrections`: correction rounds after the first launch.
Corrections = Annotated[StrictInt, Field(ge=0, le=MAX_CORRECTIONS_LIMIT)]


class _Table(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    comment: Any = Field(None, alias="_comment", description="a comment; never read")


class FallbackTable(_Table):
    """One block of a failover chain, `[[defaults.fallbacks]]` or `[[tasks.<kind>.fallbacks]]`:
    the next hop. Block order is hop order."""

    agent: str = Field(description="a registered coding agent")
    model: str
    credential: str = Field("", description="a `[credentials.<name>]`; without it, the kind's own")


class PerTaskTable(_Table):
    """What one running task that claims a name needs of the host (`PerTask`): give one or both."""

    memory_mb: StrictInt | None = Field(None, ge=1)
    cores: StrictInt | None = Field(None, ge=1)


class _Routing(_Table):
    agent: str | None = Field(None, description="a registered coding agent: claude, omp, omp-rpc, opencode, pi, codex")
    model: str | None = None
    effort: str | None = None
    credential: str | None = Field(None, description='a `[credentials.<name>]`; without it, "ambient"')
    model_failover: StrictBool | None = None
    fallbacks: list[FallbackTable] | None = Field(None, description="the failover chain; block order is hop order")


class DefaultsTable(_Routing):
    """`[defaults]`: run-wide routing, and what every kind without its own takes."""

    max_passes: StrictInt | None = Field(None, ge=1, description="the passes each `while` loop of flow code may make")
    preflight: PreflightPolicy | None = None
    claim_capacity: dict[str, Annotated[StrictInt, Field(ge=0)] | PerTaskTable] | None = Field(
        None, description="how many running tasks may claim each name, by the name or an fnmatch pattern"
    )
    context_warn_pct: WarnPct | None = None


def _budget(want: type | tuple[type, ...]) -> Any:
    """The annotation of a budget key that takes the types `want` (never a bool), or no value."""
    strict: dict[type, Any] = {int: StrictInt, float: StrictFloat}
    return Union[tuple(strict[w] for w in (want if isinstance(want, tuple) else (want,))) + (None,)]  # noqa: UP007


class _TaskRouting(_Routing):
    disallowed_tools: list[str] | None = Field(None, description='tools its launches may not use: "WebFetch", "Bash(git push:*)"')
    partial_on: list[Literal["timeout", "stalled"]] | None = Field(
        None,
        min_length=1,
        description="the stops after which a launch's output that passes every check is a partial result",
    )
    safety_stop_failover: list[Literal["response", "tool"]] | None = Field(
        None,
        description="the parts of a launch whose safety stop moves a launch that ended well to the next hop of the chain",
    )
    keep_failed_changes: StrictBool | None = Field(
        None, description="leave the files a failed attempt created under the kind's `changes` patterns in place"
    )


_TASK_FIELDS: dict[str, Any] = {key: (_budget(want), None) for key, want in TASK_TABLE_KEYS.items()}
_TASK_FIELDS["context_warn_pct"] = (Union[WarnPct, None], None)  # noqa: UP007
_TASK_FIELDS["max_corrections"] = (Union[Corrections, None], None)  # noqa: UP007

#: `[tasks.<kind>]`, a task table: one kind's routing and budgets.
TaskTable: type[BaseModel] = create_model(  # pyright: ignore[reportCallIssue]
    "TaskTable",
    __base__=_TaskRouting,
    __doc__="`[tasks.<kind>]`, a task table: one kind's routing, budgets and failover chain.",
    **_TASK_FIELDS,
)


class PipelineFile(_Table):
    """A pipeline config file (`pipeline.toml`)."""

    defaults: DefaultsTable | None = None
    tasks: dict[str, TaskTable] | None = Field(None, description="the task tables, by kind")  # pyright: ignore[reportInvalidTypeForm]
    credentials: dict[str, AnyCredential] | None = Field(
        None, description="identities a launch may authenticate as, by name; `ambient` is built in"
    )
    pipeline: dict[str, dict[str, Any]] | None = Field(None, description="the pipeline tables: a pipeline's own, never checked")


def _no_null(node: Any) -> Any:
    """`node` without `null`, which TOML cannot write: an optional key is one left out."""
    if isinstance(node, list):
        return [_no_null(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: _no_null(v) for k, v in node.items() if not (k == "default" and v is None)}
    options = [o for o in out.get("anyOf", ()) if o != {"type": "null"}]
    if "anyOf" in out and len(options) == 1:
        del out["anyOf"]
        out = {**options[0], **out}
    elif "anyOf" in out:
        out["anyOf"] = options
    return out


def config_schema() -> dict:
    """The JSON Schema of a pipeline config file. A credential table takes its name from
    the table, so its schema has no `name`, and it must give its `type`."""
    schema = _no_null(PipelineFile.model_json_schema(by_alias=True))
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    credential_types = TypeAdapter(AnyCredential).json_schema()["$defs"]
    for name, definition in schema["$defs"].items():
        if name in credential_types:
            definition["properties"].pop("name", None)
            definition["required"] = sorted({*definition.get("required", ()), "type"})
    return schema
