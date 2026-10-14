"""Pipeline configuration: one TOML file.

    [defaults]              run-wide routing: agent, model, effort, credential, model_failover;
                            and max_passes
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
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from contraagent.backends.credentials import AMBIENT, CredentialError, parse_credentials
from contraagent.errors import ContraagentError, did_you_mean
from contraagent.routing.kind_config import TASK_TABLE_KEYS


class ConfigError(ContraagentError, ValueError):
    """A config file exists but cannot be read or is malformed."""


#: The top-level tables of a pipeline config.
TABLES = ("defaults", "tasks", "credentials", "_comment")


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


def _problem(errors: list[str] | None, message: str) -> None:
    if errors is None:
        raise ConfigError(message)
    errors.append(message)


def _section(data: dict, name: str) -> dict:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


def _as_bool(src, where: str, value) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{src}: {where}.model_failover = {value!r} is not a boolean; write true or false")


@dataclass(frozen=True)
class PipelineConfig:
    raw: dict = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> PipelineConfig:
        """Parse `path`. A missing file reads as empty; an unparsable one raises."""
        p = Path(path)
        try:
            raw = tomllib.loads(p.read_text())
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
        """A top-level table this file does not define (`[defaults]`, `[tasks.*]`, `[credentials.*]`)
        raises, or with `errors` is appended there."""
        unknown = set(self.raw) - set(TABLES)
        if unknown:
            _problem(errors, f"{self.source}: {_unknown_keys('the file', unknown, TABLES)}")

    def defaults(self, errors: list[str] | None = None) -> dict:
        """`[defaults]`: the run-wide routing default (agent, model, effort, credential,
        model_failover), and `max_passes` (`Pipeline(max_passes=)`). Its failover chain,
        `[[defaults.fallbacks]]`, is read by `fallbacks()`.
        An unknown key raises; with `errors`, it is appended there and the rest still read."""
        entry = _section(self.raw, "defaults")
        allowed = {"agent", "model", "effort", "credential", "model_failover", "max_passes", "fallbacks", "tag_capacity"}
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
        return out

    def tag_capacity(self, errors: list[str] | None = None) -> dict[str, int]:
        """`[defaults.tag_capacity]`: how many running tasks may hold each tag, by its name or
        an `fnmatch` pattern (`"topic:*" = 1`: each topic's tag, one task at a time), each a
        non-negative integer. `Pipeline(tag_capacity=)` outranks it, key by key. A malformed
        entry raises; with `errors`, it is appended there and the rest still read."""
        entry = _section(self.raw, "defaults").get("tag_capacity", {})
        if not isinstance(entry, dict):
            _problem(errors, f"{self.source}: [defaults].tag_capacity must be a table of tag = capacity")
            return {}
        out: dict[str, int] = {}
        for tag, value in entry.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _problem(errors, f"{self.source}: [defaults.tag_capacity] {tag!r} = {value!r} is not a non-negative integer")
            else:
                out[tag] = value
        return out

    def task_tables(self, errors: list[str] | None = None) -> dict[str, dict]:
        """`[tasks.<kind>]`, the task tables: routing keys, budgets and the kind's own `fallbacks`.

        A malformed table raises `ConfigError`; with `errors`, every problem is
        appended there instead and what is well-formed still read, so one pass
        reports them all.
        """
        out: dict[str, dict] = {}
        for kind, entry in _section(self.raw, "tasks").items():
            table = self._task_table(kind, entry, errors)
            if table:
                out[kind] = table
        return out

    def _task_table(self, kind: str, entry: object, errors: list[str] | None) -> dict:
        routing = ("agent", "model", "effort", "credential")
        allowed = set(routing) | set(TASK_TABLE_KEYS) | {"fallbacks", "model_failover", "_comment"}
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
        fb = entry.get("fallbacks")
        if fb is not None:
            if not isinstance(fb, list):
                _problem(errors, f"{self.source}: [tasks.{kind}].fallbacks must be an array of tables, written [[tasks.{kind}.fallbacks]]")
            else:
                table["fallbacks"] = fb
        return table

    def fallbacks(self) -> list[dict]:
        """`[[defaults.fallbacks]]`, in file order (raw tables; `router.parse_chain` validates)."""
        entries = _section(self.raw, "defaults").get("fallbacks")
        if entries is None:
            return []
        if not isinstance(entries, list):
            raise ConfigError(f"{self.source}: [defaults].fallbacks must be an array of tables, written [[defaults.fallbacks]]")
        return [e for e in entries if isinstance(e, dict)]

    def credentials(self) -> dict:
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

    def table(self, name: str) -> dict:
        """Any other top-level table a domain keeps in the same file."""
        return _section(self.raw, name)
