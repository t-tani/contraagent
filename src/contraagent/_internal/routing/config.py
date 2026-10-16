"""Pipeline configuration: one TOML file.

    [defaults]              run-wide routing: agent, model, effort, credential, model_failover;
                            max_passes; preflight; and context_warn_pct
    [defaults.claim_capacity]  how many running tasks may claim each name: a number, or a
                            table of what one needs of the host (`PerTask`)
    [[defaults.fallbacks]]  the failover chain every kind without its own shares
    [tasks.<kind>]          a task table: one kind's routing and budgets (see profile.TASK_TABLE_KEYS),
                            and optionally its own [[tasks.<kind>.fallbacks]] chain
    [credentials.<name>]    identities a launch may authenticate as (see backends/credentials.py)

Why TOML: the failover chain is an *ordered* list an operator reorders by
hand; array-of-tables with real comments reads that well, and `tomllib`
is in the standard library.

Everything else a domain wants in the file (its own tables) is ignored
here and reachable through `PipelineConfig.raw`.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contraagent._internal.backends.credentials import AMBIENT, CredentialError, parse_credentials
from contraagent._internal.errors import ContraagentError, did_you_mean
from contraagent._internal.routing.kind_config import TASK_TABLE_KEYS

#: A tool, or a tool with a pattern of what it is given, as Claude Code writes them: `WebFetch`,
#: `Bash(git push:*)` (`[tasks.<kind>].disallowed_tools`).
TOOL_RULE = re.compile(r"\w+(\(.+\))?")


class ConfigError(ContraagentError, ValueError):
    """A config file exists but cannot be read or is malformed."""


#: The top-level tables of a pipeline config. `[pipeline.<name>]` are the pipeline tables:
#: a pipeline's own, read by its code (`PipelineConfig.table`), their keys never checked.
TABLES = ("defaults", "tasks", "credentials", "pipeline", "_comment")

#: The routing keys of `[defaults]` and of a task table: where a kind runs.
ROUTING_KEYS = ("agent", "model", "effort", "credential", "model_failover", "fallbacks")

#: The keys of `[defaults]` (and `_comment`, anywhere).
DEFAULTS_KEYS = (*ROUTING_KEYS, "max_passes", "preflight", "claim_capacity", "context_warn_pct")

#: The keys of a task table beside `TASK_TABLE_KEYS` and `TASK_ATTEMPT_KEYS` (and `_comment`).
TASK_ROUTING_KEYS = (*ROUTING_KEYS, "disallowed_tools")

#: The keys of a task table that say what becomes of an attempt's work: booleans.
TASK_ATTEMPT_KEYS = ("keep_failed_changes",)

#: Every key of a task table (`[tasks.<kind>]`, but `_comment`); each is an `agent_task`
#: argument too, the kind's default.
TASK_KEYS = (*TASK_ROUTING_KEYS, *TASK_TABLE_KEYS, *TASK_ATTEMPT_KEYS)


def _unknown_keys(where: str, unknown: set[str], allowed, elsewhere: tuple[str, ...] = ()) -> str:
    """`elsewhere`: keys of another table, named when an unknown key is close to one of them."""
    named = sorted(k for k in allowed if k != "_comment")

    def hint(k: str) -> str:
        if guess := did_you_mean(k, named):
            return guess
        close = difflib.get_close_matches(k, elsewhere, n=1, cutoff=0.6)
        return f" ({close[0]} is a [tasks.<kind>] key, or an agent_task argument)" if close else ""

    keys = ", ".join(f"{k!r}{hint(k)}" for k in sorted(unknown))
    return f"{where} has unknown keys {keys}; expected {', '.join(named)}"


#: What a `context_warn_pct` that is not one says.
WARN_PCT_RANGE = "is not a whole percent from 1 to 99"


def _is_warn_pct(value: object) -> bool:
    """A `context_warn_pct`: an int from 1 to 99."""
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 99


def _problem(errors: list[str] | None, message: str) -> None:
    if errors is None:
        raise ConfigError(message)
    errors.append(message)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


def _as_bool(src, where: str, value) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{src}: {where}.model_failover = {value!r} is not a boolean; write true or false")


@dataclass(frozen=True)
class PerTask:
    """A claim capacity sized by the host: how much of it one running task that claims the
    name needs. `memory_mb`: memory in MB; `cores`: CPU cores. Give one or both, each a
    positive integer; a mistake raises `ConfigError`.

    Each time the queue tries to start a task that claims the name, the capacity is the
    tasks that hold it now plus as many more as the free memory holds, and at most the
    usable cores divided by `cores`; at least 1 while no task holds the name, so a run
    always goes on. Free memory is `MemAvailable` of `/proc/meminfo`, less `memory_mb` for
    each task with a `PerTask` claim started in the last 30 seconds (one just started has
    not grown yet); where there is no `/proc/meminfo` (not Linux), memory does not limit
    it. A pattern with a `PerTask` sizes each name it matches on its own: one name,
    claimed by every such task, shares one limit.
    """

    memory_mb: int | None = None
    cores: int | None = None

    def __post_init__(self) -> None:
        problem = per_task_problem(self.memory_mb, self.cores)
        if problem:
            raise ConfigError(f"PerTask: {problem}")


def per_task_problem(memory_mb: object, cores: object) -> str | None:
    """What is wrong with a `PerTask`'s fields, or None."""
    if memory_mb is None and cores is None:
        return "give memory_mb, cores, or both"
    for name, value in (("memory_mb", memory_mb), ("cores", cores)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
            return f"{name} = {value!r} is not a positive integer"
    return None


@dataclass(frozen=True)
class PipelineConfig:
    raw: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> PipelineConfig:
        """Parse `path`. A missing file reads as empty; an unparsable one raises."""
        p = Path(path)
        try:
            raw = tomllib.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls({}, p)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"{p}: {exc}") from exc
        return cls(raw, p)

    @property
    def source(self) -> str:
        """The file it was read from, as messages name it (`<config>` when built in code)."""
        return str(self.path) if self.path else "<config>"

    def unknown_tables(self, errors: list[str] | None = None) -> None:
        """A top-level table this file does not define (`[defaults]`, `[tasks.*]`,
        `[credentials.*]`, `[pipeline.*]`), or a value under `pipeline` that is not a table,
        raises, or with `errors` is appended there."""
        unknown = set(self.raw) - set(TABLES)
        if unknown:
            found = _unknown_keys("the file", unknown, TABLES)
            _problem(errors, f"{self.source}: {found}; a pipeline's own table goes under [pipeline.<name>]")
        if "pipeline" not in self.raw:
            return
        tables = self.raw["pipeline"]
        if not isinstance(tables, dict):
            _problem(errors, f"{self.source}: pipeline = {tables!r} is not a table; write [pipeline.<name>]")
            return
        for name, value in tables.items():
            if not isinstance(value, dict):
                _problem(errors, f"{self.source}: pipeline.{name} = {value!r} is not a table; write [pipeline.{name}]")

    def defaults(self, errors: list[str] | None = None) -> dict[str, Any]:
        """`[defaults]`: the run-wide routing default (agent, model, effort, credential,
        model_failover), `max_passes` (`Pipeline(max_passes=)`), `preflight`
        (`Pipeline(preflight=)`: `substitute`, `stop` or `off`) and `context_warn_pct` (the warning
        of every kind with a `context_budget` and none of its own). Its failover chain,
        `[[defaults.fallbacks]]`, is read by `fallbacks()`.
        An unknown key raises; with `errors`, it is appended there and the rest still read."""
        entry = _section(self.raw, "defaults")
        allowed = set(DEFAULTS_KEYS)
        unknown = set(entry) - allowed - {"_comment"}
        if unknown:
            _problem(errors, f"{self.source}: {_unknown_keys('[defaults]', unknown, allowed, tuple(TASK_TABLE_KEYS))}")
        out: dict[str, str | bool | int] = {
            k: str(entry[k]) for k in ("agent", "model", "effort", "credential") if entry.get(k) not in (None, "")
        }
        if entry.get("model_failover") is not None:
            out["model_failover"] = _as_bool(self.source, "[defaults]", entry["model_failover"])
        if entry.get("max_passes") is not None:
            value = entry["max_passes"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                _problem(errors, f"{self.source}: [defaults].max_passes = {value!r} is not a positive integer")
            else:
                out["max_passes"] = value
        if entry.get("context_warn_pct") is not None:
            value = entry["context_warn_pct"]
            if not _is_warn_pct(value):
                _problem(errors, f"{self.source}: [defaults].context_warn_pct = {value!r} {WARN_PCT_RANGE}")
            else:
                out["context_warn_pct"] = value
        if entry.get("preflight") is not None:
            from contraagent._internal.routing.preflight import check_policy

            try:
                out["preflight"] = check_policy(entry["preflight"], f"{self.source}: [defaults].preflight")
            except ValueError as exc:
                _problem(errors, str(exc))
        return out

    def claim_capacity(self, errors: list[str] | None = None) -> dict[str, int | PerTask]:
        """`[defaults.claim_capacity]`: how many running tasks may claim each name at once, by
        the name or an `fnmatch` pattern (`"heavy*" = 2`: each name it matches, two tasks at a
        time), each a non-negative integer or a table of what one task needs of the host
        (`index = { memory_mb = 1500, cores = 1 }`, a `PerTask`); a name no entry gives is
        claimed by one at a time. `Pipeline(claim_capacity=)` outranks it, key by key. A
        malformed entry raises; with `errors`, it is appended there and the rest still read."""
        entry = _section(self.raw, "defaults").get("claim_capacity", {})
        if not isinstance(entry, dict):
            _problem(errors, f"{self.source}: [defaults].claim_capacity must be a table of name = capacity")
            return {}
        where = f"{self.source}: [defaults.claim_capacity]"
        out: dict[str, int | PerTask] = {}
        for name, value in entry.items():
            if isinstance(value, dict):
                if unknown := set(value) - {"memory_mb", "cores"}:
                    _problem(errors, f"{where} {_unknown_keys(repr(name), unknown, ('memory_mb', 'cores'))}")
                elif problem := per_task_problem(value.get("memory_mb"), value.get("cores")):
                    _problem(errors, f"{where} {name!r}: {problem}")
                else:
                    out[name] = PerTask(memory_mb=value.get("memory_mb"), cores=value.get("cores"))
            elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _problem(errors, f"{where} {name!r} = {value!r} is not a non-negative integer or a table of memory_mb and cores")
            else:
                out[name] = value
        return out

    def task_tables(self, errors: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """`[tasks.<kind>]`, the task tables: routing keys, budgets and the kind's own `fallbacks`.

        A malformed table raises `ConfigError`; with `errors`, every problem is
        appended there instead and what is well-formed still read, so one pass
        reports them all.
        """
        out: dict[str, dict[str, Any]] = {}
        for kind, entry in _section(self.raw, "tasks").items():
            table = self._task_table(kind, entry, errors)
            if table:
                out[kind] = table
        return out

    def _task_table(self, kind: str, entry: object, errors: list[str] | None) -> dict[str, Any]:
        routing = ("agent", "model", "effort", "credential")
        allowed = set(TASK_KEYS) | {"_comment"}
        named = ", ".join(sorted(allowed - {"_comment"}))
        if not isinstance(entry, dict):
            _problem(errors, f"{self.source}: [tasks.{kind}] must be a table with any of {named}")
            return {}
        unknown = set(entry) - allowed
        if unknown:
            _problem(errors, f"{self.source}: {_unknown_keys(f'[tasks.{kind}]', unknown, allowed - {'_comment'})}")
        table = {k: entry[k] for k in routing if entry.get(k) not in (None, "")}
        if entry.get("model_failover") is not None:
            table["model_failover"] = _as_bool(self.source, f"[tasks.{kind}]", entry["model_failover"])
        for key in TASK_ATTEMPT_KEYS:
            val = entry.get(key)
            if val is None:
                continue
            if isinstance(val, bool):
                table[key] = val
            else:
                _problem(errors, f"{self.source}: [tasks.{kind}].{key} = {val!r} is not a boolean; write true or false")
        for key, want in TASK_TABLE_KEYS.items():
            val = entry.get(key)
            if val is None:
                continue
            wants = want if isinstance(want, tuple) else (want,)
            if isinstance(val, bool) or not isinstance(val, wants):
                _problem(
                    errors,
                    f"{self.source}: [tasks.{kind}].{key} = {val!r} is not a number (wanted {' or '.join(w.__name__ for w in wants)})",
                )
                continue
            table[key] = val
        if "context_warn_pct" in table and not _is_warn_pct(table["context_warn_pct"]):
            _problem(errors, f"{self.source}: [tasks.{kind}].context_warn_pct = {table.pop('context_warn_pct')!r} {WARN_PCT_RANGE}")
        denied = entry.get("disallowed_tools")
        if denied is not None:
            ok = isinstance(denied, list)
            bad = [d for d in denied if not isinstance(d, str) or not TOOL_RULE.fullmatch(d.strip())] if ok else [denied]
            if bad:
                _problem(
                    errors,
                    f"{self.source}: [tasks.{kind}].disallowed_tools must be a list of tools or tool patterns "
                    f'("WebFetch", "Bash(git push:*)"), not {", ".join(repr(b) for b in bad)}',
                )
            else:
                table["disallowed_tools"] = [d.strip() for d in denied]
        fb = entry.get("fallbacks")
        if fb is not None:
            if not isinstance(fb, list):
                _problem(errors, f"{self.source}: [tasks.{kind}].fallbacks must be an array of tables, written [[tasks.{kind}.fallbacks]]")
            else:
                table["fallbacks"] = fb
        return table

    def fallbacks(self) -> list[dict[str, Any]]:
        """`[[defaults.fallbacks]]`, in file order (raw tables; `router.parse_chain` validates)."""
        entries = _section(self.raw, "defaults").get("fallbacks")
        if entries is None:
            return []
        if not isinstance(entries, list):
            raise ConfigError(f"{self.source}: [defaults].fallbacks must be an array of tables, written [[defaults.fallbacks]]")
        return [e for e in entries if isinstance(e, dict)]

    def credentials(self) -> dict[str, Any]:
        """`[credentials.<name>]`, parsed, plus the built-in `ambient` (whatever each
        coding agent loads by default)."""
        tables = _section(self.raw, "credentials")
        for name, entry in tables.items():
            if name == "ambient":
                raise ConfigError(f"{self.source}: [credentials.ambient] is built in; pick another name")
            if not isinstance(entry, dict):
                raise ConfigError(f"{self.source}: [credentials.{name}] must be a table with a type")
        try:
            return {"ambient": AMBIENT, **parse_credentials(tables)}
        except CredentialError as exc:
            raise ConfigError(f"{self.source}: {exc}") from None

    def table(self, name: str) -> dict[str, Any]:
        """`[pipeline.<name>]`: a pipeline table, the pipeline's own settings in this file,
        as parsed; contraagent never checks its keys. Empty when the file has none; a
        `pipeline.<name>` that is not a table raises `ConfigError`."""
        value = _section(self.raw, "pipeline").get(name, {})
        if not isinstance(value, dict):
            raise ConfigError(f"{self.source}: pipeline.{name} = {value!r} is not a table; write [pipeline.{name}]")
        return value
