"""File contracts: what a task must leave behind (or read), checked where it is produced.

A task asks the agent to write its result to a file. Exit status says
nothing about that file: an agent can end its turn cleanly having written
no file, a truncated one, prose wrapped around the JSON, or a document
with a field renamed — and the stage that reads it next fails far from
the cause. So the file is checked where it is produced, against its
schema, a pydantic class (or, for a text output, for its existence), and then by any
validators (`contraagent.validators`: a Python check, a linter), and an
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
(the Router's failover, for one).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from contraagent import rundir
from contraagent.backends.base import Backend
from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.dispatch.task import kind_name
from contraagent.validators import CommandValidator, Validator, run_validators, validator_name

_logger = logging.getLogger(__name__)

#: Resumes after the first launch. Each one is a full agent turn, and an
#: LLM that misreads the schema three times in a row is not converging.
DEFAULT_MAX_RESUMES = 3

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
    after the schema check, on the parsed value (`contraagent.validators`).
    """

    fresh: bool = True
    validators: tuple[Validator, ...] = ()
    #: The task's params, read when the file is checked, for validators that take `params`.
    params: Callable[[], Mapping[str, Any]] | None = None
    #: The task's call file (agent tasks), for validators that take `call`.
    call: Path | None = None

    def check(self, cwd: Path, before: tuple[int, int] | None = None) -> Check:
        """This contract's verdict on its file now (`before`: its stamp ahead of the launch)."""
        params = self.params() if self.params is not None else None
        return check_file(self.resolve(cwd), self.schema, before, self.fresh, self.validators, params=params, call=self.call, cwd=cwd)


@dataclass(frozen=True)
class InputContract(_FileContract):
    """One file a task reads, and the schema it must satisfy before launch.

    With `required` False a missing file is fine (a file the task itself
    creates); a file that is present must still satisfy the schema.
    `producer` is the key of the task that writes it, named when it is missing.
    """

    required: bool = True
    producer: str = ""


def check_input(contract: InputContract, cwd: Path) -> list[str]:
    """Errors for one input before launch; empty when it passes."""
    path = contract.resolve(cwd)
    if not path.exists():
        if not contract.required:
            return []
        return [f"input from {contract.producer} is missing: {path}" if contract.producer else f"{path}: required input is missing"]
    try:
        text = path.read_text(encoding="utf-8")
        if contract.schema is not None:
            contract.schema.model_validate_json(text)
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: unreadable: {exc}"]
    except ValueError as exc:
        return [f"{path}: {line}" for line in str(exc).splitlines()[:_MAX_ERRORS]]
    return []


@dataclass
class Check:
    """One contract's verdict. `value` is the parsed schema instance (or the text) when `ok`.
    `schema_ok`: the file was read and met its schema; only validators can have failed."""

    path: Path
    ok: bool
    errors: list[str]
    value: Any = None
    schema_ok: bool = False


def file_stamp(path: Path) -> tuple[int, int] | None:
    """(mtime_ns, size) of `path`, or None when it does not exist."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def check_file(
    path: Path,
    schema: type[BaseModel] | None,
    before: tuple[int, int] | None = None,
    fresh: bool = False,
    validators: Sequence[Validator] = (),
    *,
    params: Mapping[str, Any] | None = None,
    call: Path | None = None,
    cwd: Path | None = None,
) -> Check:
    """Validate the file at `path`: its JSON against `schema` (None: any text),
    then every validator on the parsed value.

    `before` is the file's stamp from ahead of the launch; with `fresh`, a
    file whose stamp has not moved counts as unwritten.
    """
    path = Path(path)
    now = file_stamp(path)
    if now is None:
        return Check(path, False, [f"{path}: file was not written"])
    if fresh and before is not None and now == before:
        return Check(path, False, [f"{path}: file predates this task and was not rewritten"])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Check(path, False, [f"{path}: unreadable: {exc}"])
    if schema is None:
        return _validated(path, text, validators, params, call, cwd)
    try:
        json.loads(text)
    except ValueError as exc:
        # Reported apart from the schema errors: pydantic's own message for
        # a syntax error names no line, and "line 40 column 3" is the part
        # the agent needs to find a trailing comma.
        return Check(path, False, [f"{path}: not valid JSON: {exc}"])
    try:
        value = schema.model_validate_json(text)
    except ValidationError as exc:
        errors = [f"{path}: {e}" for e in _describe(exc)]
        # A command checks the file, not the model: it runs too, so one round reports every error.
        commands = [v for v in validators if isinstance(v, CommandValidator)]
        errors += run_validators(commands, path, None, params=params, call=call, cwd=cwd)
        return Check(path, False, errors)
    return _validated(path, value, validators, params, call, cwd)


def _validated(
    path: Path, value: Any, validators: Sequence[Validator], params: Mapping[str, Any] | None, call: Path | None, cwd: Path | None
) -> Check:
    errors = run_validators(validators, path, value, params=params, call=call, cwd=cwd)
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


def check_all(contracts: Sequence[OutputContract], cwd: Path, before: dict[Path, tuple[int, int] | None]) -> list[Check]:
    checks = []
    for c in contracts:
        p = c.resolve(cwd)
        checks.append(c.check(cwd, before.get(p)))
    return checks


def correction_prompt(contracts: Sequence[OutputContract], checks: Sequence[Check]) -> str:
    """The next turn: what is wrong, and the schema of each file that does not meet it."""
    failing_json = any(c.schema is not None and not chk.schema_ok for c, chk in zip(contracts, checks, strict=True) if not chk.ok)
    parts = [
        "The output file(s) you wrote do not pass their checks. Fix them and "
        "write them again at the same path(s). Do not redo the analysis; correct "
        "the file contents only."
        + (" A JSON output must contain only the JSON document, with no prose or code fences around it." if failing_json else "")
        + "\n"
    ]
    for c, chk in zip(contracts, checks, strict=True):
        if chk.ok:
            continue
        errors = chk.errors[:_MAX_ERRORS]
        more = len(chk.errors) - len(errors)
        parts.append(f"## {chk.path}\nErrors:")
        parts += [f"- {e}" for e in errors]
        if more > 0:
            parts.append(f"- … and {more} more")
        if c.schema is None or chk.schema_ok:
            parts.append("")
            continue
        json_schema = json.dumps(c.schema.model_json_schema(), ensure_ascii=False, indent=1)
        if len(json_schema) > _MAX_SCHEMA_CHARS:
            json_schema = json_schema[:_MAX_SCHEMA_CHARS] + "\n…(truncated)"
        parts.append(f"Required JSON Schema:\n```json\n{json_schema}\n```\n")
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
            name, ref, json_schema = "text", "", {}
        else:
            name, ref = c.schema.__name__, f"{c.schema.__module__}.{c.schema.__qualname__}"
            try:
                json_schema = c.schema.model_json_schema()
            except Exception:
                json_schema = {}
        return {
            "io": role,
            "path": str(c.resolve(cwd)),
            "schema_name": name,
            "schema_ref": ref,
            "schema": json_schema,
            "fresh": getattr(c, "fresh", None),
            "required": getattr(c, "required", None),
            "validators": [validator_name(v) for v in getattr(c, "validators", ())],
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
        d = Path(run_dir) / rundir.CONTRACTS
        d.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in task.key)
        rundir.write_document(d / f"{safe}.json", json.dumps(record, default=str))
    except (OSError, TypeError):
        pass


def fold_spend(total: LaunchResult | None, nxt: LaunchResult) -> LaunchResult:
    """Carry the spend, the web searches and the unread events across rounds; everything else is the last round's."""
    if total is None:
        return nxt
    nxt.wall_s += total.wall_s
    if total.cost_usd is not None:
        nxt.cost_usd = (nxt.cost_usd or 0.0) + total.cost_usd
    nxt.usage.calls = total.usage.calls + nxt.usage.calls
    nxt.usage.output_total += total.usage.output_total
    nxt.rate_limits = total.rate_limits + nxt.rate_limits
    nxt.hook_errors = total.hook_errors + nxt.hook_errors
    nxt.web_queries = total.web_queries + nxt.web_queries
    for k, v in total.unread_events.items():
        nxt.unread_events[k] = nxt.unread_events.get(k, 0) + v
    for k, v in total.tool_uses.items():
        nxt.tool_uses[k] = nxt.tool_uses.get(k, 0) + v
    nxt.started_at = total.started_at or nxt.started_at
    return nxt


def run_until_valid(
    backend: Backend, launch: Launch, contracts: Sequence[OutputContract], max_resumes: int = DEFAULT_MAX_RESUMES
) -> LaunchResult:
    """Run `launch`, then resume its session until every contract holds.

    Returns the last round's `LaunchResult` with spend (wall, cost, usage,
    tool use) summed over all rounds, `rounds` set to the number of
    launches, and `round_errors` holding each failed round's errors. A
    run that exhausts `max_resumes`, or whose session cannot be resumed,
    ends `INVALID_OUTPUT` and not ok. A round that did not complete keeps
    its own stop.
    """
    if not contracts:
        return backend.run(launch)
    resumable = backend.resumable(launch)
    # Whatever was kept only for resuming goes with the run: a session dir
    # made here (omp), a transcript persisted here (claude). A session dir
    # or persistence the caller asked for is the caller's to keep.
    scratch = resumable.session_dir if resumable.session_dir != launch.session_dir else None
    result: LaunchResult | None = None
    try:
        result = _loop(backend, resumable, contracts, max_resumes)
        return result
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
        sid = (result.session_id if result else "") or launch.session_id or ""
        if sid:
            backend.discard_session(launch, sid)


def _loop(backend: Backend, launch: Launch, contracts: Sequence[OutputContract], max_resumes: int) -> LaunchResult:
    before = {c.resolve(launch.cwd): file_stamp(c.resolve(launch.cwd)) for c in contracts}
    total: LaunchResult | None = None
    rounds = 0
    found: list[list[str]] = []  # each failed round's errors
    while True:
        rounds += 1
        total = fold_spend(total, backend.run(launch))
        checks = check_all(contracts, launch.cwd, before)
        errors = [e for chk in checks for e in chk.errors]
        found += [errors] if errors else []
        total.rounds = rounds
        total.round_errors = list(found)
        if not errors:
            return total
        if total.stop is not Stop.COMPLETED:
            return total
        nxt = backend.resumed(launch, total, correction_prompt(contracts, checks)) if rounds <= max_resumes else None
        if nxt is not None:
            more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
            _logger.info(f"[fix-up] {launch.label}: round {rounds} failed its checks, sent back: {errors[0]}{more}")
        if nxt is None:
            total.stop = Stop.INVALID_OUTPUT
            total.ok = False
            return total
        launch = nxt
