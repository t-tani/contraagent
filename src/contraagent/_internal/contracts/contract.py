"""File contracts: what a task must leave behind (or read), checked where it is produced.

A task asks the agent to write its result to a file. Exit status says
nothing about that file: an agent can end its turn cleanly having written
no file, a truncated one, prose wrapped around the JSON, or a document
with a field renamed — and the stage that reads it next fails far from
the cause. So the file is checked where it is produced, against its
schema, a pydantic class (or, for a text output, for its existence), and then by any
validators (`contraagent._internal.contracts.validators`: a Python check, a linter), and an
off-contract file goes back to the same session with the errors as the
next turn. The agent still has the
whole task in its context, so a correction costs one short turn, not a
rerun.

    contract = OutputContract(Path("out/findings.json"), Findings)
    launch_result = run_until_valid(backend, launch, [contract])

Only a launch that ran to the end is sent back. A timeout, a 429 or an
auth failure is not a formatting problem, and resuming into it would
spend a launch to learn the same thing; those results return as they
are, with the contract errors attached, for the caller's own handling
(the Router's failover, for one). The agent runner calls `run_checked`, which also
says whether the outputs of a launch that did not end ok are kept: it stopped on one of
its kind's `partial_on` stops (its time limit, a stall).

A rows output (`rows.RowsFile`) is a JSON Lines file checked line by line
(`parse_rows`): each error names its line, and the rows are a `Rows`, a list.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from contraagent._internal.backends.base import Backend
from contraagent._internal.backends.launch import Launch, LaunchResult, Stop
from contraagent._internal.contracts import pointers
from contraagent._internal.contracts.rows import Rows, drop_unfinished, is_rows, row_of
from contraagent._internal.contracts.validators import CommandValidator, Validator, run_validators, validator_name, wanted_context
from contraagent._internal.dispatch.records import OtherModel
from contraagent._internal.dispatch.task import kind_name
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import write_document

_logger = logging.getLogger(__name__)

#: Correction rounds after the first launch, a kind's `max_corrections` when neither its
#: declaration nor the config gives one. Each one is a full agent turn, and an
#: LLM that misreads the schema three times in a row is not converging.
DEFAULT_MAX_CORRECTIONS = 3

#: Errors quoted per file in the correction prompt. Past this many the
#: agent has the shape wrong, not a field, and the schema says more.
_MAX_ERRORS = 20

#: Schema text quoted per file. A large schema would crowd out
#: the errors, which are the part that says what to change.
_MAX_SCHEMA_CHARS = 8_000


@dataclass(frozen=True)
class _FileContract:
    """A file at `path` (relative to the task's cwd unless absolute) and the
    schema (a pydantic class) its JSON must satisfy. `schema` None: a text file, any content."""

    path: Path
    schema: type[BaseModel] | None

    def resolve(self, cwd: Path) -> Path:
        p = Path(self.path)
        return p if p.is_absolute() else Path(cwd) / p


@dataclass(frozen=True)
class OutputContract(_FileContract):
    """One file the agent must leave behind, and the schema it must satisfy.

    With `fresh` (the default) a file that predates the launch and was never
    rewritten fails the check: a stale document from an earlier run is
    otherwise indistinguishable from this run's answer. `validators` run
    after the schema check, on the parsed value (`Validator`).
    `preserve`: JSON pointers (RFC 6901, a segment `*` for every member of an array or
    object) to the parts of a JSON file the launch must keep: each value they select in the file as it was before the launch
    (`before`) must be in it after, equal.
    """

    fresh: bool = True
    validators: tuple[Validator, ...] = ()
    #: The task's params, read when the file is checked, for validators that take `params`.
    params: Callable[[], Mapping[str, Any]] | None = None
    #: The task's call file (agent tasks), for validators that take `call`.
    call: Path | None = None
    #: The output is the agent's final message, not a file it writes: `run_until_valid`
    #: writes each round's final message to `path`, then checks it there.
    from_message: bool = False
    #: With `from_message`: the message may wrap the JSON document (`unwrap_json`); the
    #: document is written to `path`, the whole message beside it (`message_path`).
    unwrap: bool = False
    preserve: tuple[str, ...] = ()

    @property
    def compares(self) -> bool:
        """Some validator takes `before`: the file ahead of the task is read for it."""
        return any("before" in wanted_context(v) for v in self.validators)

    def before(self, cwd: Path) -> Before:
        """The file as it is now, ahead of a launch: its stamp and, for a contract that
        preserves parts, the values its pointers select. Its text is kept for a contract that
        preserves parts or `compares`. A file that is missing or does not parse as JSON
        preserves nothing."""
        path = self.resolve(cwd)
        since = time.time_ns()
        full = file_stamp(path)
        before = self._before(path, full, recent_digest(path, full, since))
        object.__setattr__(before, "_full_stamp", full)
        return before

    def _before(self, path: Path, full: Stamp | None, digest: str | None) -> Before:
        stamp = (full[0], full[1]) if full is not None else None
        if not (self.preserve or self.compares) or stamp is None:
            return Before(stamp, digest=digest)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return Before(stamp, digest=digest)
        if not self.preserve:
            return Before(stamp, text=text, digest=digest)
        try:
            document = json.loads(text)
        except ValueError:
            return Before(stamp, text=text if self.compares else None, digest=digest)
        return Before(stamp, pointers.select_all(document, self.preserve), text, digest)

    def message_path(self, cwd: Path) -> Path:
        """Where an unwrapped output's whole final message is kept: `<output>.message.txt`."""
        path = self.resolve(cwd)
        return path.with_name(path.name + ".message.txt")

    def check(self, cwd: Path, before: Before | None = None) -> Check:
        """This contract's verdict on its file now (`before`: the file ahead of the launch)."""
        params = self.params() if self.params is not None else None
        return check_file(
            self.resolve(cwd),
            self.schema,
            full_stamp(before),
            self.fresh,
            self.validators,
            params=params,
            call=self.call,
            cwd=cwd,
            preserved=before.preserved if before is not None else None,
            digest=before.digest if before is not None else None,
            before_value=(lambda: before.value(self.schema)) if before is not None else None,
        )


@dataclass(frozen=True)
class Before:
    """An output file ahead of a launch: its stamp (`file_stamp`; None, no file), the values
    its contract's `preserve` pointers select in it (by the pointer that names each one
    alone), its text when there is a value to keep or a validator takes `before`
    (`OutputContract.compares`), and the digest of its content when its stamp was recent
    (`recent_digest`): a rewrite at the same size and mtime differs from it there."""

    stamp: tuple[int, int] | None
    preserved: Mapping[str, Any] = field(default_factory=dict)
    text: str | None = None
    digest: str | None = None
    #: The whole stamp `OutputContract.before` took (`file_stamp`), ctime and inode
    #: included; None for one made otherwise (`full_stamp`).
    _full_stamp: tuple[int, ...] | None = field(default=None, init=False, repr=False, compare=False)

    def value(self, schema: type[BaseModel] | None) -> Any:
        """The text parsed as a check parses the file: the model instance (`schema`), or the
        text itself (None). None when there is no text, or it does not meet the schema."""
        if self.text is None or schema is None:
            return self.text
        try:
            return parse_value(schema, self.text)
        except ValueError:
            return None

    def restore(self, path: Path) -> None:
        """Put the file back as it was, when its text is kept (values to keep, a validator
        that takes `before`)."""
        if self.text is not None:
            write_document(path, self.text)


@dataclass(frozen=True)
class InputContract(_FileContract):
    """One file a task reads, and the schema it must satisfy before launch.

    With `required` False a missing file is fine (a file the task itself
    creates); a file that is present must still satisfy the schema.
    `producer` is the key of the task that writes it, named when it is missing.
    `producer_failure()` is the stop of that task when it finished and did not succeed
    (`invalid_output`, `error`, ...), else '': a file a failed task left behind is
    refused as an input even when it meets its schema.
    """

    required: bool = True
    producer: str = ""
    producer_failure: Callable[[], str] | None = field(default=None, compare=False)


def check_input(contract: InputContract, cwd: Path) -> list[str]:
    """Errors for one input before launch; empty when it passes."""
    path = contract.resolve(cwd)
    if not path.exists():
        if not contract.required:
            return []
        return [
            f"input from {contract.producer} is missing: {path.as_posix()}"
            if contract.producer
            else f"{path.as_posix()}: required input is missing"
        ]
    failure = contract.producer_failure() if contract.producer_failure is not None else ""
    if failure:
        return [f"input from {contract.producer} ended {failure}: {path.as_posix()}"]
    try:
        text = path.read_text(encoding="utf-8")
        if contract.schema is not None:
            parse_value(contract.schema, text)
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path.as_posix()}: unreadable: {exc}"]
    except ValueError as exc:
        return [f"{path.as_posix()}: {line}" for line in str(exc).splitlines()[:_MAX_ERRORS]]
    return []


def parse_value(schema: type[BaseModel], text: str) -> Any:
    """`text` read as a check reads a file of `schema`: the model instance; for a rows file
    (`RowsFile`), the `Rows`. `ValueError` when it does not meet the schema, one error per line."""
    if is_rows(schema):
        rows, errors = parse_rows(text, row_of(schema))
        if errors:
            raise ValueError("\n".join(errors))
        return rows
    return schema.model_validate_json(text)


def parse_rows(text: str, row: type[BaseModel]) -> tuple[Rows[Any], list[str]]:
    """The rows of a JSON Lines `text`, and one error per thing wrong with it, each naming
    its line (`line 3: severity: Input should be ...`). A blank line is no row. A file that
    is one JSON array is named as such: the likeliest mistake."""
    rows: Rows[Any] = Rows()
    stripped = text.strip()
    if stripped.startswith("[") and isinstance(_loads(stripped), list):
        return rows, ["the file is one JSON array; write one JSON object per line instead, with no [ ] around them"]
    errors: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except ValueError as exc:
            errors.append(f"line {n}: not valid JSON: {exc}")
            continue
        try:
            rows.append(row.model_validate_json(line))
        except ValidationError as exc:
            errors += [f"line {n}: {e}" for e in _describe(exc)]
    return rows, errors


def _loads(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


@dataclass
class Check:
    """One contract's verdict. `value` is the parsed schema instance (the text of a text file,
    the `Rows` of a rows file) when `ok`.
    `schema_ok`: the file was read and met its schema; only validators can have failed."""

    path: Path
    ok: bool
    errors: list[str]
    value: Any = None
    schema_ok: bool = False


#: How close to a stamp's taking a file's mtime must be for a rewrite at the same size to
#: keep that mtime: a file system moves mtime in ticks (about 16 ms on NTFS, coarser on some).
RECENT_NS = 2_000_000_000


#: A file's stamp (`stamp_of`): its mtime in nanoseconds first, its size second, then, on
#: POSIX, its ctime in nanoseconds and its inode.
Stamp = tuple[int, ...]


def stamp_of(st: os.stat_result) -> Stamp:
    """The stamp of a file whose status is `st`: `(mtime_ns, size)`, and on POSIX also
    `(ctime_ns, inode)`. A program can set a file's mtime back (`os.utime`, `cp -p`,
    `touch -r`) but not its ctime, which every write and every change of the mtime moves; a
    replace gives the file a new inode too. On Windows the ctime is the creation time, which a
    write leaves as it was, so the stamp there is the mtime and the size alone."""
    if sys.platform == "win32":
        return (st.st_mtime_ns, st.st_size)
    return (st.st_mtime_ns, st.st_size, st.st_ctime_ns, st.st_ino)


def file_stamp(path: Path) -> Stamp | None:
    """The stamp of `path` (`stamp_of`), or None when it does not exist."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return stamp_of(st)


def file_digest(path: Path) -> str | None:
    """The BLAKE2b digest of `path`'s content, or None when it cannot be read."""
    try:
        with open(path, "rb") as f:
            return hashlib.file_digest(f, "blake2b").hexdigest()
    except OSError:
        return None


def recent_digest(path: Path, stamp: Stamp | None, since_ns: int) -> str | None:
    """`file_digest(path)` when `stamp` (`path`'s, taken at or after `since_ns`, wall clock)
    has an mtime within `RECENT_NS` of `since_ns` or later: a rewrite in the same timestamp
    tick leaves such a stamp as it was, and only the content tells it. None otherwise."""
    if stamp is None or stamp[0] < since_ns - RECENT_NS:
        return None
    return file_digest(path)


def full_stamp(before: Before | None) -> Stamp | None:
    """The stamp `before` holds, ctime and inode included when `OutputContract.before` took
    it; `Before.stamp` for one made otherwise."""
    if before is None:
        return None
    return before._full_stamp if before._full_stamp is not None else before.stamp


def unwritten(path: Path, stamp: Stamp | None, before: Stamp | None, digest: str | None = None) -> bool:
    """Whether the file at `path`, whose stamp is now `stamp`, is as it was before a launch:
    its stamp then was `before` (compared as far as `before` goes: a `Before.stamp` holds
    the mtime and the size alone) and, when `digest` (`recent_digest`) was taken, its
    content still has that digest."""
    return before is not None and stamp is not None and stamp[: len(before)] == before and (digest is None or file_digest(path) == digest)


def check_file(
    path: Path,
    schema: type[BaseModel] | None,
    before: Stamp | None = None,
    fresh: bool = False,
    validators: Sequence[Validator] = (),
    *,
    params: Mapping[str, Any] | None = None,
    call: Path | None = None,
    cwd: Path | None = None,
    preserved: Mapping[str, Any] | None = None,
    digest: str | None = None,
    before_value: Callable[[], Any] | None = None,
) -> Check:
    """Validate the file at `path`: its JSON against `schema` (None: any text; a rows file,
    `RowsFile`: each line against its row, `parse_rows`), then every validator on the parsed
    value (a rows file's: the `Rows`).

    `before` is the file's stamp from ahead of the launch, `digest` its content's digest
    then when that stamp was recent (`Before.digest`); with `fresh`, a file whose stamp has
    not moved, and whose content still has that digest, counts as unwritten. `preserved`: values the
    JSON must still hold, by the pointer that names each (`OutputContract.before`);
    one it no longer holds is an error, reported with the schema's and the validators'.
    `before_value`: the file's value ahead of the task, for the validators that take
    `before` (called only for them).
    """
    path = Path(path)
    now = file_stamp(path)
    if now is None:
        return Check(path, False, [f"{path.as_posix()}: file was not written"])
    if fresh and unwritten(path, now, before, digest):
        return Check(path, False, [f"{path.as_posix()}: file predates this task and was not rewritten"])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Check(path, False, [f"{path.as_posix()}: unreadable: {exc}"])
    if schema is None:
        return _validated(path, text, validators, params, call, cwd, before=before_value)
    if is_rows(schema):
        rows, problems = parse_rows(text, row_of(schema))
        if problems:
            errors = [f"{path.as_posix()}: {e}" for e in problems]
            commands = [v for v in validators if isinstance(v, CommandValidator)]
            errors += run_validators(commands, path, None, params=params, call=call, cwd=cwd)
            return Check(path, False, errors)
        return _validated(path, rows, validators, params, call, cwd, before=before_value)
    try:
        document = json.loads(text)
    except ValueError as exc:
        # Reported apart from the schema errors: pydantic's own message for
        # a syntax error names no line, and "line 40 column 3" is the part
        # the agent needs to find a trailing comma.
        return Check(path, False, [f"{path.as_posix()}: not valid JSON: {exc}"])
    lost = [f"{path.as_posix()}: {e}" for e in pointers.kept(document, preserved)] if preserved else []
    try:
        value = schema.model_validate_json(text)
    except ValidationError as exc:
        errors = [f"{path.as_posix()}: {e}" for e in _describe(exc)] + lost
        # A command checks the file, not the model: it runs too, so one round reports every error.
        commands = [v for v in validators if isinstance(v, CommandValidator)]
        errors += run_validators(commands, path, None, params=params, call=call, cwd=cwd)
        return Check(path, False, errors)
    return _validated(path, value, validators, params, call, cwd, lost, before_value)


def _validated(
    path: Path,
    value: Any,
    validators: Sequence[Validator],
    params: Mapping[str, Any] | None,
    call: Path | None,
    cwd: Path | None,
    lost: Sequence[str] = (),
    before: Callable[[], Any] | None = None,
) -> Check:
    errors = [*lost, *run_validators(validators, path, value, params=params, call=call, cwd=cwd, before=before)]
    return Check(path, not errors, errors, value if not errors else None, schema_ok=True)


def _describe(exc: ValidationError) -> list[str]:
    """One line per error: `items.3.address: Field required (got: {...})`."""
    out = []
    for e in exc.errors(include_url=False):
        loc = ".".join(str(x) for x in e.get("loc") or ()) or "<root>"
        line = f"{loc}: {e.get('msg', '')}"
        if "input" in e and e.get("type") != "missing":
            got = json.dumps(e["input"], ensure_ascii=False, default=str)
            line += f" (got: {got[:120]}{'…' if len(got) > 120 else ''})"
        out.append(line)
    return out


def check_all(contracts: Sequence[OutputContract], cwd: Path, before: Mapping[Path, Before]) -> list[Check]:
    checks = []
    for c in contracts:
        p = c.resolve(cwd)
        checks.append(c.check(cwd, before.get(p)))
    return checks


def correction_prompt(contracts: Sequence[OutputContract], checks: Sequence[Check]) -> str:
    """The next turn: what is wrong, and the schema of each file that does not meet it.
    An output taken from the final message (`from_message`) is asked for again as the reply."""
    failing = [c for c, chk in zip(contracts, checks, strict=True) if not chk.ok and c.schema is not None and not chk.schema_ok]
    only_json = " A JSON output must contain only the JSON document, with no prose or code fences around it." if failing else ""
    if any(is_rows(c.schema) for c in failing):
        only_json += " A JSON Lines output holds one JSON object per line and nothing else."
    if any(c.from_message for c, chk in zip(contracts, checks, strict=True) if not chk.ok):
        parts = [
            "Your final message is the output, and it does not pass its checks. Reply again "
            "with the corrected output as your whole message, and nothing else. Do not redo "
            "the analysis; correct the output only." + only_json + "\n"
        ]
    else:
        parts = [
            "The output file(s) you wrote do not pass their checks. Fix them and "
            "write them again at the same path(s). Do not redo the analysis; correct "
            "the file contents only." + only_json + "\n"
        ]
    for c, chk in zip(contracts, checks, strict=True):
        if chk.ok:
            continue
        errors = chk.errors[:_MAX_ERRORS]
        more = len(chk.errors) - len(errors)
        parts.append("## Your final message\nErrors:" if c.from_message else f"## {chk.path.as_posix()}\nErrors:")
        parts += [f"- {e}" for e in errors]
        if more > 0:
            parts.append(f"- … and {more} more")
        if c.schema is None or chk.schema_ok:
            parts.append("")
            continue
        json_schema = json.dumps(row_of(c.schema).model_json_schema(), ensure_ascii=False, indent=1)
        if len(json_schema) > _MAX_SCHEMA_CHARS:
            json_schema = json_schema[:_MAX_SCHEMA_CHARS] + "\n…(truncated)"
        what = "Required JSON Schema of each line" if is_rows(c.schema) else "Required JSON Schema"
        parts.append(f"{what}:\n```json\n{json_schema}\n```\n")
    return "\n".join(parts)


def record_contracts(
    run_dir: Path, task, output_contracts: Sequence[OutputContract], input_contracts: Sequence[InputContract], cwd: Path
) -> None:
    """Write what `task` is declared to read and leave behind to
    `<run_dir>/contracts/<key>.json`, so the monitor can show each file, the
    schema it must satisfy and whether it validated. Shared by the agent path
    (`AgentRunner`) and the Python-task path (`PythonTaskRunner`): the same
    declaration covers both. Best-effort: a record the monitor cannot draw must
    never fail a launch."""
    params = {
        k: v for k, v in (getattr(task, "params", None) or {}).items() if isinstance(v, (str, int, float, bool)) and k not in ("preamble",)
    }
    if not (output_contracts or input_contracts or params):
        return

    def spec(c, role: str) -> dict:
        if c.schema is None:
            name, ref, json_schema, form = "text", "", {}, "text"
        else:
            # A rows file is named and drawn by its row: the schema each line meets.
            model = row_of(c.schema)
            form = "jsonl" if is_rows(c.schema) else "json"
            name = f"Rows[{model.__name__}]" if form == "jsonl" else model.__name__
            ref = f"{model.__module__}.{model.__qualname__}"
            try:
                json_schema = model.model_json_schema()
            except Exception:
                json_schema = {}
        return {
            "io": role,
            "path": c.resolve(cwd).as_posix(),
            "format": form,
            "schema_name": name,
            "schema_ref": ref,
            "schema": json_schema,
            "fresh": getattr(c, "fresh", None),
            "required": getattr(c, "required", None),
            "validators": [validator_name(v) for v in getattr(c, "validators", ())],
            "preserve": list(getattr(c, "preserve", ())),
            **({"producer": c.producer} if getattr(c, "producer", "") else {}),
        }

    record = {
        "key": task.key,
        "kind": kind_name(task.kind),
        "unit": task.declared_unit,
        "executor": task.executor,
        "params": params,
        "outputs": [spec(c, "output") for c in output_contracts],
        "inputs": [spec(c, "input") for c in input_contracts],
    }
    try:
        (Path(run_dir) / layout.CONTRACTS).mkdir(parents=True, exist_ok=True)
        write_document(Path(run_dir) / layout.task_entry(layout.CONTRACTS, task.key), json.dumps(record, default=str))
    except (OSError, TypeError):
        pass


def add_other_models(a: dict[str, OtherModel], b: dict[str, OtherModel]) -> dict[str, OtherModel]:
    """Two launches' `other_models`, summed per model."""
    out = dict(a)
    for m, v in b.items():
        had = out.get(m)
        out[m] = v if had is None else had.plus(v)
    return out


def fold_spend(total: LaunchResult | None, nxt: LaunchResult, *, resumed: bool = False, session_total: bool = False) -> LaunchResult:
    """Carry the spend, the web searches, the safety stops, the unread events, the unknown usage and a context warning from
    `total` into `nxt`, the launch after it; everything else is `nxt`'s, but for
    `context_window`: the window of the launch whose call is the peak context (the other
    launch's when that one reports none on the same model).

    `resumed`: `nxt` resumed `total`'s session (a correction round), else it is a session of its
    own (a failover hop, a pool member). The costs (and `other_models`) add up, but a resumed launch whose
    coding agent reports the session's cost so far (`session_total`,
    `Backend.cost_is_session_total`) already holds the earlier rounds', so it stands. The
    turns of a resumed session's rounds add up (`num_turns`); tokens and API calls are
    each launch's own and always add up."""
    if total is None:
        return nxt
    nxt.wall_s += total.wall_s
    if total.cost_usd is not None and not (resumed and session_total and nxt.cost_usd is not None):
        nxt.cost_usd = (nxt.cost_usd or 0.0) + total.cost_usd
    if resumed and total.num_turns is not None:
        nxt.num_turns = total.num_turns + (nxt.num_turns or 0)
    if not (resumed and session_total and nxt.other_models):
        nxt.other_models = add_other_models(total.other_models, nxt.other_models)
    peak, other = (total, nxt) if total.usage.peak_context > nxt.usage.peak_context else (nxt, total)
    same_model = peak.model == other.model
    nxt.context_window = peak.context_window or (other.context_window if same_model else None)
    nxt.usage.calls = total.usage.calls + nxt.usage.calls
    nxt.usage.output_total += total.usage.output_total
    nxt.quota = total.quota + nxt.quota
    nxt.hook_errors = total.hook_errors + nxt.hook_errors
    nxt.web_queries = total.web_queries + nxt.web_queries
    nxt.safety_stops = total.safety_stops + nxt.safety_stops
    nxt.context_warned = nxt.context_warned or total.context_warned
    for k, v in total.unread_events.items():
        nxt.unread_events[k] = nxt.unread_events.get(k, 0) + v
    if "tokens" in (total.usage_unknown, nxt.usage_unknown):
        nxt.usage_unknown = "tokens"
    else:
        nxt.usage_unknown = nxt.usage_unknown or total.usage_unknown
    for k, v in total.tool_uses.items():
        nxt.tool_uses[k] = nxt.tool_uses.get(k, 0) + v
    nxt.started_at = total.started_at or nxt.started_at
    return nxt


def run_until_valid(
    backend: Backend,
    launch: Launch,
    contracts: Sequence[OutputContract],
    max_corrections: int = DEFAULT_MAX_CORRECTIONS,
) -> LaunchResult:
    """Run `launch`, then resume its session until every contract holds.

    Returns the last round's `LaunchResult` with spend (wall, cost, usage,
    tool use, turns) over all rounds (`fold_spend`: a coding agent that reports a
    resumed session's cost so far is not counted twice), `round_costs` each
    round's own cost, `rounds` set to the number of launches and
    `round_errors` holding each failed round's errors. `max_corrections`: the correction
    rounds after the first launch (`KindConfig.max_corrections`; 0, none). A run that
    exhausts them, or whose session cannot be resumed,
    ends `INVALID_OUTPUT` and not ok. A round that did not complete keeps
    its own stop. Each check compares a file with the file as it was before the
    first round (`OutputContract.before`); a result that is not ok puts back a file
    that held parts to keep (`preserve`), so the next attempt starts from them.
    """
    return run_checked(backend, launch, contracts, max_corrections).result


@dataclass(frozen=True)
class CheckedLaunch:
    """What `run_checked` made of a launch: its `result` (as `run_until_valid` returns it),
    and `partial`, True when what it wrote is kept although it is not ok (it stopped on one
    of `partial_on`, and every output passed its checks)."""

    result: LaunchResult
    partial: bool = False


def run_checked(
    backend: Backend,
    launch: Launch,
    contracts: Sequence[OutputContract],
    max_corrections: int = DEFAULT_MAX_CORRECTIONS,
    *,
    partial_on: Collection[Stop] = (),
) -> CheckedLaunch:
    """`run_until_valid`, with the agent runner's verdicts beside the result.

    `partial_on`: stops after which what the launch wrote is kept (`agent_task(partial_on=)`).
    A round that ends on one of them is checked as any other, after the unfinished last
    line of a rows file is cut off (`rows.drop_unfinished`); when every output
    passes, the result keeps its stop, `partial` is set, and its files stay as
    they are. It is not resumed either way.
    """
    if not contracts:
        return CheckedLaunch(backend.run(launch))
    resumable = backend.resumable(launch)
    # Whatever was kept only for resuming goes with the run: a session dir
    # made here (omp), a transcript persisted here (claude). A session dir
    # or persistence the caller asked for is the caller's to keep.
    scratch = resumable.session_dir if resumable.session_dir != launch.session_dir else None
    checked: CheckedLaunch | None = None
    before = {c.resolve(launch.cwd): c.before(launch.cwd) for c in contracts}
    try:
        checked = _loop(backend, resumable, contracts, max_corrections, before, frozenset(partial_on))
        if not (checked.result.ok or checked.partial):
            for path, was in before.items():
                was.restore(path)
        return checked
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
        sid = (checked.result.session_id if checked else "") or launch.session_id or ""
        if sid:
            backend.discard_session(launch, sid)


def _loop(
    backend: Backend,
    launch: Launch,
    contracts: Sequence[OutputContract],
    max_corrections: int,
    before: Mapping[Path, Before],
    partial_on: frozenset[Stop] = frozenset(),
) -> CheckedLaunch:
    total: LaunchResult | None = None
    rounds = 0
    found: list[list[str]] = []  # each failed round's errors
    costs: list[float | None] = []  # each round's own cost
    session_total = bool(getattr(backend, "cost_is_session_total", False))
    while True:
        rounds += 1
        ran = backend.run(launch)
        so_far = total.cost_usd if total is not None else None
        own = ran.cost_usd
        if own is not None and so_far is not None and session_total:
            own = max(0.0, own - so_far)  # the session's cost so far, the earlier rounds' included
        costs.append(round(own, 6) if own is not None else None)
        total = fold_spend(total, ran, resumed=rounds > 1, session_total=session_total)
        total.round_costs = list(costs)
        if total.stop is Stop.COMPLETED:
            total.unwrapped = _write_messages(contracts, launch.cwd, total.result_text)
        stopped = total.stop in partial_on
        if stopped:
            for c in contracts:
                if _drop_unfinished(c, launch.cwd, before.get(c.resolve(launch.cwd))):
                    _logger.info(f"[partial] {launch.label}: cut off the unfinished last line of {c.resolve(launch.cwd).as_posix()}")
        checks = check_all(contracts, launch.cwd, before)
        if total.stop is Stop.COMPLETED and not total.result_text.strip():
            for c, chk in zip(contracts, checks, strict=True):
                if c.from_message:
                    chk.ok, chk.errors = False, ["the final message is empty"]
        errors = [e for chk in checks for e in chk.errors]
        found += [errors] if errors else []
        total.rounds = rounds
        total.round_errors = list(found)
        if not errors:
            if total.hollow and any(c.from_message for c in contracts):
                # The final message is the output, and it passed its checks: text that reads
                # like a tool call is part of the answer, not a sign of a hollow launch.
                total.hollow = False
                total.ok = total.stop is Stop.COMPLETED
            return CheckedLaunch(total, partial=stopped)
        if total.stop is not Stop.COMPLETED:
            return CheckedLaunch(total)
        nxt = backend.resumed(launch, total, correction_prompt(contracts, checks)) if rounds <= max_corrections else None
        if nxt is not None:
            more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            _logger.info(f"[correction] {launch.label}: round {rounds} failed its checks, sent back: {errors[0]}{more}")
        if nxt is None:
            total.stop = Stop.INVALID_OUTPUT
            total.ok = False
            return CheckedLaunch(total)
        launch = nxt


def _drop_unfinished(contract: OutputContract, cwd: Path, before: Before | None) -> bool:
    """Cut off the unfinished last line of a rows file the launch wrote (`RowsFile`): one
    with no newline after it that is not valid JSON, the row being written when the launch
    was stopped (`rows.drop_unfinished`). A file the launch did not write is left as it is.
    True when a line was cut off."""
    if not is_rows(contract.schema) or contract.from_message:
        return False
    path = contract.resolve(cwd)
    stamp = file_stamp(path)
    if stamp is None or (before is not None and unwritten(path, stamp, full_stamp(before), before.digest)):
        return False
    return drop_unfinished(path)


def _write_messages(contracts: Sequence[OutputContract], cwd: Path, message: str) -> bool:
    """Write the final message to the file of each contract that takes its output from it,
    in one replace: the check then reads it as it reads a file the agent wrote. A contract
    that `unwrap`s gets the JSON document taken out of the message, when there is one, and
    the whole message beside it. True when a document was taken out of a longer message."""
    if not message.strip():
        return False
    unwrapped = False
    for c in contracts:
        if not c.from_message:
            continue
        path = c.resolve(cwd)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = message
        if c.unwrap:
            write_document(c.message_path(cwd), message)
            document = unwrap_json(message)
            if document is not None:
                unwrapped = unwrapped or document != message.strip()
                text = document
        write_document(path, text)
    return unwrapped


_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)\n?[ \t]*```", re.S)


def unwrap_json(message: str) -> str | None:
    """The JSON document a final message wraps; None when it holds none.

    The last fenced block (`` ```json `` or unlabeled) whose content parses; else the
    longest JSON object or array in the message that parses (of two as long, the later),
    taken whole: never a value inside it, nor a `[1]` in a sentence after it. A sentence before or after the document, or a fence
    around it, is what this takes off; a message that is only the document is returned as
    it is."""
    for label, body in reversed(_FENCE.findall(message)):
        if label.lower() not in ("", "json"):
            continue
        if _parses(body):
            return body.strip()
    decoder = json.JSONDecoder()
    found: tuple[int, int] | None = None
    i = 0
    while i < len(message):
        if message[i] in "{[":
            try:
                _, end = decoder.raw_decode(message, i)
            except ValueError:
                i += 1
                continue
            if found is None or end - i >= found[1] - found[0]:
                found = (i, end)  # the longest; of two as long, the later
            i = end  # what is inside it is not a document of its own
            continue
        i += 1
    return message[found[0] : found[1]] if found is not None else None


def _parses(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def example(json_schema: Mapping[str, Any]) -> tuple[Any, list[str]]:
    """The example of `json_schema`, and the rules it could not build: what a stub run
    plays as each task's output (`contraagent.testing.writes_example`).

    One rule, at every node of the schema: the first entry of the node's `examples`,
    when it has one, else the smallest value the node accepts. So a model's own example
    (`model_config = ConfigDict(json_schema_extra={"examples": [...]})`) is the whole value,
    a field's (`Field(examples=[...])`) is that field's value, and a part with no example
    is the smallest. The smallest value is only what the schema requires: an object's
    required fields, a list's `minItems` elements, a string's `minLength` characters, a
    number's `minimum` (or just past an `exclusiveMinimum`), a field's `default`, an
    enum's or a `const`'s first value, the first branch of `anyOf`/`oneOf`, `allOf`
    merged, `$ref` into the schema's own `$defs`. A rule it does not build (`pattern`,
    `format`, `multipleOf`, `not`) is named in the second item by its location, and the
    value is built without it. An example is not checked here: `contraagent check`
    checks it against its model.
    """
    problems: list[str] = []
    root = dict(json_schema)

    def resolve(node: Mapping[str, Any], seen: frozenset[str]) -> tuple[Mapping[str, Any], frozenset[str]]:
        while isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            if ref in seen or not ref.startswith("#/"):
                problems.append(f"{ref}: a reference it does not follow")
                return {}, seen
            target: Any = root
            for part in ref[2:].split("/"):
                target = target.get(part, {}) if isinstance(target, Mapping) else {}
            node, seen = {**target, **{k: v for k, v in node.items() if k != "$ref"}}, seen | {ref}
        return node, seen

    def build(node: Mapping[str, Any], where: str, seen: frozenset[str]) -> Any:
        node, seen = resolve(node, seen)
        if isinstance(node.get("examples"), list) and node["examples"]:
            return copy.deepcopy(node["examples"][0])
        if "const" in node:
            return node["const"]
        if node.get("enum"):
            return node["enum"][0]
        if "default" in node:
            return node["default"]
        for key in ("anyOf", "oneOf"):
            if node.get(key):
                return build(node[key][0], where, seen)
        if node.get("allOf"):
            merged: dict[str, Any] = {}
            for part in node["allOf"]:
                merged.update(resolve(part, seen)[0])
            return build({**merged, **{k: v for k, v in node.items() if k != "allOf"}}, where, seen)
        for rule in ("pattern", "format", "multipleOf", "not"):
            if rule in node:
                problems.append(f"{where}: {rule} {node[rule]!r}")
        kind = node.get("type")
        if isinstance(kind, list):
            kind = next((t for t in kind if t != "null"), "null")
        if kind is None:
            kind = "object" if "properties" in node else "array" if "items" in node else "null"
        if kind == "object":
            props = node.get("properties") or {}
            return {name: build(props.get(name, {}), f"{where}.{name}", seen) for name in node.get("required") or ()}
        if kind == "array":
            prefix = node.get("prefixItems") or []
            items = node.get("items") or {}
            n = max(int(node.get("minItems") or 0), len(prefix) if node.get("items") is False else 0)
            return [build(prefix[i] if i < len(prefix) else items, f"{where}.{i}", seen) for i in range(n)]
        if kind == "string":
            return "x" * int(node.get("minLength") or 0)
        if kind in ("integer", "number"):
            return _smallest_number(node, integer=kind == "integer")
        if kind == "boolean":
            return False
        return None

    return build(root, "<root>", frozenset()), problems


def _smallest_number(node: Mapping[str, Any], *, integer: bool) -> int | float:
    """The number nearest zero within the node's bounds."""
    step = 1 if integer else 0.001
    low = node.get("minimum", node["exclusiveMinimum"] + step if "exclusiveMinimum" in node else None)
    high = node.get("maximum", node["exclusiveMaximum"] - step if "exclusiveMaximum" in node else None)
    value = 0 if low is None or low <= 0 else low
    if high is not None and value > high:
        value = high
    return int(value) if integer else value
