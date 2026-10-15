"""Validators: checks an output file must pass beyond its schema.

A validator is any callable `(path, value) -> errors`: `path` is the output
file, `value` the parsed and schema-checked content (the model instance for a
JSON output, the text for a text output), and the result an iterable of
error strings (empty or None means the file passes). The errors go back to the
agent exactly like schema errors: as the next turn of the same session.

    def has_points(path, summary: Summary):
        if not summary.points:
            return ["points: give at least one point"]

A validator that also declares `params` is given the task's params (an agent
task's as its call file holds them, a Python task's with every upstream value
resolved); one that declares `call` is given the path of an agent task's call
file; one that declares `cwd`, the task's working directory. A rule that relates
the output to the input needs them:

    def cites_real_lines(path, review: Review, *, params):
        n = len(Path(params["path"]).read_text().splitlines())
        return [f"findings.{i}.line: {f.line} is past the end ({n} lines)" for i, f in enumerate(review.findings) if f.line > n]

A validator that declares `before` is given the file as it was before the task,
parsed as `value` is (the model instance, or the text), or None when there was
no file or it did not pass its schema then. It is the file ahead of the task's
first round, on every correction round alike; the file is read only when some
validator of the contract declares `before`. A rule about what the task changed
needs it:

    def adds_an_item(path, backlog: Backlog, *, before: Backlog | None):
        if before is not None and len(backlog.items) <= len(before.items):
            return [f"items: add at least one item (still {len(backlog.items)})"]

    agent_task("summarize", ..., validators=[has_points, CommandValidator(["npx", "textlint", "{path}"])])

`CommandValidator` runs an external linter. Unlike a Python function it can be written
into a task's call file, so the in-session Stop hook runs it too: the agent
hears about it before it ends its turn, and the runner checks again after.
`{call}` in its arguments is the call file, so a script can read the params.
It is given no `before`: a command reads the file as it is.
"""

from __future__ import annotations

import inspect
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: `(path, value) -> errors`, optionally also taking any of `CONTEXT` by keyword.
Validator = Callable[..., Iterable[str] | None]

#: What a validator may declare, beyond `(path, value)`.
CONTEXT = ("params", "call", "cwd", "before")


def validator_name(v: Validator) -> str:
    return getattr(v, "name", "") or getattr(v, "__name__", "") or type(v).__name__


def wanted_context(v: Validator) -> tuple[str, ...]:
    """Which of `CONTEXT` the validator declares."""
    try:
        names = inspect.signature(v).parameters
    except (TypeError, ValueError):
        return ()
    return tuple(c for c in CONTEXT if c in names)


def run_validators(
    validators: Sequence[Validator],
    path: Path,
    value: Any,
    *,
    params: Mapping[str, Any] | None = None,
    call: Path | None = None,
    cwd: Path | None = None,
    before: Callable[[], Any] | None = None,
) -> list[str]:
    """Every validator's errors, each prefixed with the validator's name.

    `before` gives the file's value before the task (None: none); it is called once,
    and only when a validator declares `before`. A validator that raises reports the
    exception as its error: a crash is something to see, not a reason to pass the file.
    """
    context: dict[str, Any] = {"params": dict(params or {}), "call": call, "cwd": cwd}
    errors: list[str] = []
    for v in validators:
        name = validator_name(v)
        wanted = wanted_context(v)
        if "before" in wanted and "before" not in context:
            context["before"] = before() if before is not None else None
        try:
            found = list(v(path, value, **{c: context[c] for c in wanted}) or ())
        except Exception as exc:  # a validator's crash is its verdict
            found = [f"validator raised {type(exc).__name__}: {exc}"]
        errors += [f"{path}: [{name}] {e}" for e in found]
    return errors


@dataclass(frozen=True)
class CommandValidator:
    """An external command as a validator: exit 0 passes, anything else fails.

    `{path}` in `argv` is replaced by the output file; without it the path is
    appended. `{call}` is replaced by the task's call file (agent tasks only),
    which holds its params. It runs in the task's working directory, wherever
    the check runs (the runner, or the agent's stop hook). The failure's output (stdout, then stderr) becomes
    the errors, capped at `max_lines`, so a linter's own report is what the
    agent reads.
    """

    argv: tuple[str, ...]
    name: str = ""
    timeout_s: float = 120.0
    max_lines: int = 30

    def __init__(self, argv: Sequence[str], name: str = "", timeout_s: float = 120.0, max_lines: int = 30) -> None:
        object.__setattr__(self, "argv", tuple(argv))
        object.__setattr__(self, "name", name or Path(self.argv[0]).name if self.argv else "command")
        object.__setattr__(self, "timeout_s", timeout_s)
        object.__setattr__(self, "max_lines", max_lines)

    @property
    def needs_call(self) -> bool:
        return any("{call}" in a for a in self.argv)

    def command_for(self, path: Path, call: Path | None = None) -> list[str]:
        argv = [a.replace("{call}", str(call)) for a in self.argv] if call is not None else list(self.argv)
        if any("{path}" in a for a in argv):
            return [a.replace("{path}", str(path)) for a in argv]
        return [*argv, str(path)]

    def __call__(self, path: Path, value: Any = None, *, call: Path | None = None, cwd: Path | None = None) -> list[str]:
        if self.needs_call and call is None:
            return ["{call} names the task's call file, and this task has none (a Python task)"]
        argv = self.command_for(Path(path), call)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout_s, cwd=cwd)
        except FileNotFoundError:
            return [f"command not found: {argv[0]}"]
        except subprocess.TimeoutExpired:
            return [f"timed out after {self.timeout_s:g}s"]
        if proc.returncode == 0:
            return []
        lines = [ln for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
        if not lines:
            return [f"exited {proc.returncode}"]
        more = len(lines) - self.max_lines
        return lines[: self.max_lines] + ([f"… and {more} more lines"] if more > 0 else [])

    def to_dict(self) -> dict:
        return {"name": self.name, "argv": list(self.argv), "timeout_s": self.timeout_s, "max_lines": self.max_lines}

    @classmethod
    def from_dict(cls, d: dict) -> CommandValidator:
        return cls(d["argv"], name=d.get("name", ""), timeout_s=d.get("timeout_s", 120.0), max_lines=d.get("max_lines", 30))
