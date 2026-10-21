"""Call files: how a run hands one agent task its parameters and its output contract.

An agent task's *procedure* lives in its plugin (the role's `agents/<role>.md`,
skills, hooks); what changes per task is data. The runner writes that data to
`runs/<run>/calls/<key>.json` and the prompt says only "carry out this call":

    {"key": "summarize-alpha", "kind": "summarize", "unit": "alpha",
     "params": {"path": "in/alpha.md"},
     "params_json_schema": {"title": "SummarizeParams", "type": "object", "properties": {...}},
     "output": {"path": ".../out/summarize/alpha.json", "format": "json", "from": "file",
                "json_schema": {...}, "schema_ref": {...}, "commands": [...], "preserve": [...]}}

The same file is what the plugin's Stop hook reads (`contraagent call validate`,
found through `CONTRAAGENT_CALL`), so the agent checks its output against the
same schema and the same command validators the runner checks after the turn.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from contraagent._internal.backends.launch import Launch
from contraagent._internal.contracts.contract import Check, OutputContract, check_file, correction_prompt
from contraagent._internal.contracts.rows import row_of, rows_file
from contraagent._internal.contracts.validators import CommandValidator
from contraagent._internal.dispatch.records import RecordModel
from contraagent._internal.platform import envvars
from contraagent._internal.runs.files import read_document, write_document


class SchemaRef(RecordModel):
    """Where the output schema can be imported from, so a hook validates with pydantic itself."""

    module: str
    qualname: str
    search_path: str | None = None


class CallOutput(RecordModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(serialize_by_alias=True)

    path: str
    #: `json`: one JSON document; `text`: any text; `jsonl`: rows, one JSON object per line,
    #: each meeting `json_schema` (`Rows`).
    format: Literal["json", "text", "jsonl"] = "json"
    #: `file`: the agent writes the output to `path`. `message`: its final message is the
    #: output, which the runner writes to `path` and checks there (`agent_task(output_from=)`).
    from_: Literal["file", "message"] = Field("file", validation_alias=AliasChoices("from", "from_"), serialization_alias="from")
    #: The output's JSON Schema; for rows, that of one line.
    json_schema: dict[str, Any] = Field(default_factory=dict)
    #: The model to import: the output's; for rows, the model of one line.
    schema_ref: SchemaRef | None = None
    #: Command validators (`validators.CommandValidator.to_dict()`); Python validators run in the runner only.
    commands: list[dict[str, Any]] = Field(default_factory=list)
    #: JSON pointers to the parts of the file the agent must keep as they are
    #: (`agent_task(preserve=)`): `*` is every member.
    preserve: list[str] = Field(default_factory=list)


class CallFile(RecordModel):
    """One agent task's call: who it is, what it is given, what it must leave behind."""

    version: int = 1
    run: str
    #: The task's key (`Task.key`).
    key: str
    kind: str
    unit: str = ""
    #: The task's params as JSON: the fields of its params model's instance, by name.
    params: dict[str, Any] = Field(default_factory=dict)
    #: The JSON Schema of its params model, each field's description and constraints in it;
    #: an object with no properties for a task that takes no params.
    params_json_schema: dict[str, Any] = Field(default_factory=dict)
    output: CallOutput | None = None
    #: The task's working directory: where its command validators run, in the runner and in the hook.
    cwd: str = ""

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return write_document(path, self.model_dump_json(indent=2) + "\n")

    @classmethod
    def read(cls, path: Path) -> CallFile:
        return cls.model_validate_json(read_document(path))

    @staticmethod
    def path_of(launch: Launch) -> Path | None:
        """The call file a launch hands its agent (`CONTRAAGENT_CALL` in its environment);
        None for a launch with none (a preflight's probe)."""
        path = launch.env.get(envvars.CALL)
        return Path(path) if path else None


def schema_ref_of(schema: type[BaseModel]) -> SchemaRef | None:
    """How to import `schema` again from another process, or None when it cannot be. A rows
    file's schema (`RowsFile`) is imported by its row: the call file says the format.

    A schema defined in a script (`__main__`) or inside a function has no import
    path; the hook then checks the JSON Schema's shape only through the
    runner, after the turn.
    """
    schema = row_of(schema)
    module = sys.modules.get(schema.__module__)
    if schema.__module__ == "__main__" or module is None or "<locals>" in schema.__qualname__:
        return None
    search_path = None
    file = getattr(module, "__file__", None)
    if file:
        # The directory the top-level package (or the module itself) sits in.
        depth = schema.__module__.count(".")
        search_path = str(Path(file).resolve().parents[depth])
    return SchemaRef(module=schema.__module__, qualname=schema.__qualname__, search_path=search_path)


def import_schema(ref: SchemaRef) -> type[BaseModel] | None:
    """The schema a `SchemaRef` names, or None when it cannot be imported here. Its
    `search_path` goes first on `sys.path`, as the directory of a script `python` runs does,
    and stays there: a validator of the schema may import a neighbour of its module when it
    runs. This runs in the hook's own short process, so no other code shares that path."""
    if ref.search_path and ref.search_path not in sys.path:
        sys.path.insert(0, ref.search_path)
    try:
        obj: Any = importlib.import_module(ref.module)
        for part in ref.qualname.split("."):
            obj = getattr(obj, part)
    except Exception:  # the runner's own check is the backstop
        return None
    return obj if isinstance(obj, type) and issubclass(obj, BaseModel) else None


def call_prompt(call_path: Path, call: CallFile, instructions: str = "") -> str:
    """The prompt of an agent task: a fixed protocol, no task knowledge.

    What to do is the plugin's (its role and skills); what to do it *with* is
    the call file's. `instructions` is the escape hatch for a task without a plugin.
    """
    unit = f" for unit `{call.unit}`" if call.unit else ""
    lines = [
        f"Task call: `{call.kind}`{unit}.",
        "",
        f"The call file `{call_path.as_posix()}` holds your parameters (`params`) and the output "
        "you must leave behind (`output`); `params_json_schema` says what each parameter is. "
        "Read it first, then carry out the task as your instructions describe.",
    ]
    if call.output is not None:
        what = {
            "json": "one JSON document matching `output.json_schema` exactly (no prose, no code fences)",
            "jsonl": "JSON Lines: one JSON object per line, each matching `output.json_schema` exactly (no prose, "
            "no code fences, no [ ] around them)",
        }.get(call.output.format, "the document the task asks for")
        if call.output.from_ == "message":
            lines += [
                "",
                f"Your final message is the output: end with {what}, as your whole message, "
                "and write no file. It is checked after you stop; if the check fails you will "
                "be sent the errors, so reply again with the corrected output.",
            ]
        else:
            lines += [
                "",
                f"Write {what} to `{call.output.path}`. It is checked when you stop; if the "
                "check fails you will be sent the errors, so fix the file and stop again.",
            ]
            if call.output.format == "jsonl":
                lines += [
                    "",
                    "Add each row to the end of the file as soon as you have it, one line at a time, "
                    "instead of writing the whole file at the end.",
                ]
        if call.output.preserve and call.output.from_ == "file":
            kept = ", ".join(f"`{p}`" for p in call.output.preserve)
            lines += [
                "",
                f"The file may already hold values you must keep exactly as they are: {kept} "
                "(JSON pointers; `*` is every member of an array or object). Read the file first, "
                "keep those values, and fill in the rest.",
            ]
    if instructions:
        lines = [instructions.rstrip(), "", *lines]
    return "\n".join(lines)


def inline_prompt(call: CallFile, instructions: str = "") -> str:
    """The prompt of a light launch (`agent_task(tools=())`): the agent has no tool to read
    a call file with, so the call is in the prompt itself: its params as JSON with their
    JSON Schema and, for a JSON output, its JSON Schema. Its final message is the output."""
    unit = f" for unit `{call.unit}`" if call.unit else ""
    params = json.dumps(call.params, ensure_ascii=False, indent=1)
    lines = [f"Task call: `{call.kind}`{unit}.", "", "Your parameters:", "```json", params, "```"]
    if call.params_json_schema.get("properties"):
        described = json.dumps(call.params_json_schema, ensure_ascii=False, indent=1)
        lines += ["", "What each parameter is, as a JSON Schema:", "```json", described, "```"]
    out = call.output
    if out is not None and out.format in ("json", "jsonl"):
        schema = json.dumps(out.json_schema, ensure_ascii=False, indent=1)
        what = (
            "one JSON document matching this JSON Schema exactly"
            if out.format == "json"
            else "JSON Lines, one JSON object per line, each matching this JSON Schema exactly"
        )
        lines += [
            "",
            f"Your final message is the output: {what}, as your whole message, with no prose and no code fences around it.",
            "```json",
            schema,
            "```",
        ]
    elif out is not None:
        lines += ["", "Your final message is the output: the document the task asks for, as your whole message."]
    lines += [
        "",
        "It is checked after you reply; if the check fails you will be sent the errors, so reply again with the corrected output.",
    ]
    if instructions:
        lines = [instructions.rstrip(), "", *lines]
    return "\n".join(lines)


def validate_call(call_path: str | Path | None = None, stdin_text: str = "", env: dict | None = None) -> tuple[int, str]:
    """What a plugin's Stop hook runs. Returns (exit_code, message).

    Exit 2 with the errors tells the coding agent to keep going and fix the
    file in the same turn. `stop_hook_active` (this hook already blocked once)
    ends the loop: the runner checks again after the turn and resumes the
    session if it must. Freshness and the parts to keep (`output.preserve`) are
    the runner's to judge; the hook sees no "before".
    """
    env = dict(os.environ if env is None else env)
    try:
        if json.loads(stdin_text or "{}").get("stop_hook_active"):
            return 0, ""
    except ValueError:
        pass
    path = call_path or env.get(envvars.CALL)
    if not path:
        return 0, f"no call file ({envvars.CALL} is unset): nothing to check"
    call = CallFile.read(Path(path))
    if call.output is None or call.output.from_ == "message":
        return 0, ""  # an output in the final message exists only after the turn: the runner checks it
    out = call.output
    schema = None
    if out.format in ("json", "jsonl") and out.schema_ref is not None:
        schema = import_schema(out.schema_ref)
        if schema is None:
            return 0, (f"cannot import {out.schema_ref.module}.{out.schema_ref.qualname} here; the runner checks the output after the turn")
        if out.format == "jsonl":
            schema = rows_file(schema)
    commands = tuple(CommandValidator.from_dict(c) for c in out.commands)
    contract = OutputContract(Path(out.path), schema, fresh=False, validators=commands)
    cwd = Path(call.cwd) if call.cwd else None
    chk = check_file(Path(out.path), schema, validators=commands, params=call.params, call=Path(path), cwd=cwd)
    if chk.ok and out.format == "json" and schema is None:
        # No importable schema (defined in a script): at least the JSON must parse.
        try:
            json.loads(Path(out.path).read_text(encoding="utf-8"))
        except ValueError as exc:
            chk = Check(Path(out.path), False, [f"{out.path}: not valid JSON: {exc}"])
    if chk.ok:
        return 0, ""
    return 2, correction_prompt([contract], [chk])
