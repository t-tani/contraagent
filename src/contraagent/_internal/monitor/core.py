"""What the monitor reads: runs, journal rows, the plan, task details, agent transcripts.

`Monitor` is the framework-neutral core (no web dependency): the HTTP
layer in `server.py` is a thin shell over its methods, so a CLI, a TUI or
a test can use the same views.

A domain extends it two ways, neither touching the framework:

* `panels` — named callables `fn(run) -> dict`, given the run's records (`RunRecords`:
  its journal, its other logs, the pipeline's own logs and documents). Each shows up as its own
  tab in the web UI and is pushed over the live feed whenever its value
  changes. A typed body (`api.PanelBody`: tiles, a table, charts, blocks of
  them) is drawn with the monitor's own elements; any other dict is shown as
  a JSON tree. A security-scan pipeline would register "findings" or
  "targets"; a data pipeline would register "datasets". A panel of `scope`
  "trends" is computed over the runs of a period instead (`fn(runs, period)`),
  served with the trends (`Monitor.trends`).
* `task_detail` — `fn(run, key, rows) -> dict` (`TaskDetailFn`), merged into the
  per-task view (a task's declared inputs/outputs, the state it wrote).

It reads runs only through a `RunSource` and a `Liveness` (`source.py`): by default
one host's `runs/` directory and `/proc`.
"""

from __future__ import annotations

import functools
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterable, Mapping, MutableMapping
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError

from contraagent._internal.backends.streams import normalize_stream_line, resolve_format
from contraagent._internal.contracts.input_file import OUT
from contraagent._internal.dispatch.records import DeferralCause, Rest, RestEvent, ServiceEvent, TimeBoxRecord
from contraagent._internal.execution.cursor import parse_cursor
from contraagent._internal.execution.estimates import TailKey, latest_finished, row_tail_key, run_shape
from contraagent._internal.execution.schemas import JournalRow
from contraagent._internal.monitor import trends
from contraagent._internal.monitor.aggregate import TOKENS, add_tokens, model_usage
from contraagent._internal.monitor.api import PanelBody
from contraagent._internal.monitor.trends import Period
from contraagent._internal.routing.preflight import PreflightRecord
from contraagent._internal.routing.quota import QuotaCap
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import parse_rows
from contraagent._internal.runs.liveness import Liveness, StaticLiveness
from contraagent._internal.runs.names import BadName, check_name
from contraagent._internal.runs.procs import ProcLiveness
from contraagent._internal.runs.source import PAGE_BYTES, DirectorySource, LogPosition, RunFile, RunSource
from contraagent._internal.runs.times import now, parse_iso


class PanelFn(Protocol):
    """A run panel's function: `fn(run)`, given the run's records (`RunRecords`), returns the
    panel's body: a typed body (`PanelBody`: tiles, a table, charts), as a model or as a dict
    with its `type`, or any other JSON object, shown as a tree (`Panel`)."""

    def __call__(self, run: RunRecords, /) -> PanelBody | BaseModel | Mapping[str, Any]: ...


class TrendsPanelFn(Protocol):
    """A trends panel's function: `fn(runs, period)`, given the runs of the period
    (`PeriodRuns`) and the `Period`, returns the panel's body, as a `PanelFn` does
    (`Panel(scope="trends")`)."""

    def __call__(self, runs: PeriodRuns, period: Period, /) -> PanelBody | BaseModel | Mapping[str, Any]: ...


def _document(source: RunSource, run: str, name: str) -> Any:
    text = source.document(run, layout.pipeline_document(name))
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


class RunRecords:
    """One run's records, as a run panel receives them, wherever the monitor reads them
    (a runs directory or a hub): a panel reads its run through this, never through a
    path of its own. `id` is the run's id."""

    def __init__(self, run: str, source: RunSource) -> None:
        self.id = run
        self._source = source

    def __repr__(self) -> str:
        return f"RunRecords({self.id!r})"

    def info(self) -> dict[str, Any]:
        """The run's `run.json`; empty when it has none."""
        return self._source.info(self.id) or {}

    def journal(self) -> list[dict[str, Any]]:
        """The run's journal rows (`JournalRow`s, as dicts), oldest first."""
        return self.records(layout.JOURNAL)

    def records(self, log: str) -> list[dict[str, Any]]:
        """The rows of one of the logs contraagent writes (`journal.jsonl`, `deferred.jsonl`,
        ...); a line that does not parse is skipped, a log the run does not have is empty."""
        return parse_rows(self._source.lines(self.id, log)[0])

    def log(self, name: str) -> list[dict[str, Any]]:
        """The rows of the pipeline log `name` (what `contraagent.log(name, row)` appended),
        oldest first; empty when the run has none."""
        return self.records(layout.pipeline_log(name))

    def document(self, name: str) -> Any:
        """The value of the pipeline document `name` (what `contraagent.save(name, value)`
        last wrote); None when the run has none."""
        return _document(self._source, self.id, name)

    def output(self, key: str) -> RunFile | None:
        """Task `key`'s output file (the first its contract names), as the host that drove
        the run saw it, wherever the monitor reads the run; None when the task declared
        none or its file does not exist. `.text` is its content as text, `.data` as bytes."""
        return _first_output(self._source, self.id, self._source.document(self.id, layout.task_entry(layout.CONTRACTS, key)))

    def dir(self) -> Path | None:
        """The run's directory on this host, for a file that is none of its records and no
        task's output; None when the runs are not in a directory here (a hub keeps them in
        its store)."""
        return self._source.dir(self.id)


def _first_output(source: RunSource, run: str, text: str | None) -> RunFile | None:
    try:
        record = json.loads(text) if text is not None else None
    except ValueError:
        return None
    outputs = record.get("outputs") if isinstance(record, dict) else None
    if not outputs or not isinstance(outputs[0], dict) or not isinstance(outputs[0].get("path"), str):
        return None
    return source.file(run, outputs[0]["path"])


class PeriodRuns(list[str]):
    """The run ids of a period, newest activity first, as a trends panel receives them, and
    their records wherever the monitor reads them (a runs directory or a hub): a panel
    reads a run through this, never through a path of its own. Each method is the
    `RunRecords` method of the same name, for run `run`; `run(run)` is its `RunRecords`."""

    def __init__(self, runs: Iterable[str], source: RunSource) -> None:
        super().__init__(runs)
        self._source = source

    def run(self, run: str) -> RunRecords:
        """Run `run`'s records."""
        return RunRecords(run, self._source)

    def info(self, run: str) -> dict[str, Any]:
        """The run's `run.json`; empty when it has none."""
        return self.run(run).info()

    def journal(self, run: str) -> list[dict[str, Any]]:
        """The run's journal rows (`JournalRow`s, as dicts), oldest first."""
        return self.run(run).journal()

    def records(self, run: str, log: str) -> list[dict[str, Any]]:
        """The rows of one of the logs contraagent writes (`journal.jsonl`, `deferred.jsonl`, ...)."""
        return self.run(run).records(log)

    def log(self, run: str, name: str) -> list[dict[str, Any]]:
        """The rows of the run's pipeline log `name`; empty when it has none."""
        return self.run(run).log(name)

    def document(self, run: str, name: str) -> Any:
        """The value of the run's pipeline document `name`; None when it has none."""
        return self.run(run).document(name)

    def output(self, run: str, key: str) -> RunFile | None:
        """Task `key`'s output file in run `run`; None when it has none."""
        return self.run(run).output(key)

    def dir(self, run: str) -> Path | None:
        """The run's directory; None when the runs are not in a directory here (a hub)."""
        return self.run(run).dir()


@dataclass
class Panel:
    """A named view a domain adds to the monitor.

    `fn` returns its body: a typed body (`api.PanelBody`, as a model or as a dict with
    its `type`) drawn as tiles, a table or charts, or any other dict, shown as a JSON
    tree. `scope` says what it is computed over: `run`, `fn(run)` (the run's `RunRecords`), a tab of each run;
    `trends`, `fn(runs, period)`, a view of the runs of a period. `title` and
    `description` label it and say what it shows; `icon` is a short glyph. `tab` names
    the tab of the Trends page a trends panel is shown on, with the other panels of that
    `tab`, in the order the first of them comes; a trends panel of no `tab` is shown
    under the trends, on the first tab. A run panel is a tab of its own and takes none.
    A bare callable works too, as a run panel (the dict key becomes the title).
    """

    fn: PanelFn | TrendsPanelFn
    title: str = ""
    description: str = ""
    icon: str = "▤"
    scope: Literal["run", "trends"] = "run"
    tab: str = ""

    def __post_init__(self) -> None:
        if self.tab and self.scope != "trends":
            raise ValueError(f"Panel {self.title or self.fn!r}: tab= is for a trends panel; a run panel is a tab of its own")

    def info(self, name: str) -> dict[str, Any]:
        """What /api/info says of it (`api.PanelInfo`), as panel `name`."""
        title = self.title or name
        return {"name": name, "title": title, "description": self.description, "icon": self.icon, "scope": self.scope, "tab": self.tab}

    def __call__(self, *args: Any) -> dict[str, Any]:
        return panel_body(self.fn(*args))


def panel_body(value: Any) -> dict[str, Any]:
    """A panel's return value as JSON data: a typed body given as a model, dumped."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value


class App(Protocol):
    """An ASGI application, `await app(scope, receive, send)`: a page of the pipeline's own,
    with its own routes and files, that the monitor serves under `apps/<name>/`
    (`Monitor(apps=)`). A Starlette or FastAPI app is one, and so is
    `starlette.staticfiles.StaticFiles(directory=...)` for a page that is only files. It is
    given the paths under `apps/<name>/` with `root_path` `/apps/<name>`, so a page that
    names its own files and routes by relative URLs works under any base path."""

    def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        /,
    ) -> Awaitable[None]: ...


class TaskDetailFn(Protocol):
    """The `Monitor(task_detail=)` function: `fn(run, key, rows)`, given the run's id, the
    task's key and its journal rows (one per attempt, as JSON objects), returns facts of the
    domain merged into the task's detail (`Monitor.task_detail`); None adds nothing."""

    def __call__(self, run: str, key: str, rows: list[dict[str, Any]], /) -> Mapping[str, Any] | None: ...


def _json_line(line: str) -> Any:
    """One line of a JSON Lines file, parsed; None for a blank line or one that does not parse."""
    if not line.strip():
        return None
    try:
        return json.loads(line)
    except ValueError:
        return None


def _running_keys(snap: dict[str, Any]) -> set:
    """Keys of every task running now: agent launches and Python tasks."""
    return {lc.get("key") for lc in snap.get("launches", [])} | {pt.get("key") for pt in snap.get("python_tasks", [])}


def _first_last(readings: list[dict[str, Any]]) -> dict[str, Any]:
    """Per credential and account (`QuotaReading.account`: `ambient` on two coding agents is
    two accounts), the run's first and last utilization reading, by when they were
    received; the account with the highest weekly utilization first."""
    by: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for q in sorted((q for q in readings if q.get("observed_at")), key=lambda q: q["observed_at"]):
        by.setdefault((q.get("credential") or "", q.get("account") or ""), []).append(q)
    accounts = [{"credential": c, "account": a, "first": qs[0], "last": qs[-1]} for (c, a), qs in by.items()]
    accounts.sort(key=lambda a: -(a["last"].get("seven_day_pct") or 0))
    return {"quota": accounts}


def _deferral_cause(cause: object) -> dict[str, Any] | None:
    """A `deferred.jsonl` row's `cause` (a `DeferralCause`) as the monitor serves it: its
    name, a deadline's figures, and each rest as the row recorded it. None for a row with no
    cause, or one that is not a `DeferralCause`."""
    try:
        c = DeferralCause.model_validate(cause)
    except ValidationError:
        return None
    return {**c.model_dump(mode="json", exclude={"rests"}), "rests": [r.model_dump(mode="json", exclude_unset=True) for r in c.rests]}


def _time_box(box: object) -> dict[str, Any] | None:
    """A flow call's time box as `flow_calls.jsonl` records it (a `TimeBoxRecord`); None
    for a flow call with none."""
    try:
        return TimeBoxRecord.model_validate(box).model_dump(mode="json") if box is not None else None
    except ValidationError:
        return None


@functools.lru_cache(maxsize=4096)
def _shown(file: str, cwd: Path | None) -> str:
    """A flow code file as the monitor serves it: relative to the run's working
    directory when under it, else as recorded. Kept for the files asked last: a run's
    plan names the same few files in every task's flow path."""
    path = Path(file)
    if cwd is not None and path.is_absolute() and path.is_relative_to(cwd):
        return path.relative_to(cwd).as_posix()
    return file


#: A log `Monitor._log_rows` keeps: its size when read up to the position, the position, its
#: first line, each line's row (None for a line that is no row), and the rows.
_HeldLog = tuple[int, LogPosition, str, list[dict[str, Any] | None], list[dict[str, Any]]]
#: How many views of runs `Monitor._kept` keeps (a run's plan and outputs are two).
KEPT_VIEWS = 16
#: How many logs `Monitor._log_rows` keeps the rows of (a run's journal and plan are two).
KEPT_LOGS = 8
#: How many bytes of a transcript `Monitor._stream_lines` reads at a time to count its lines.
COUNT_BYTES = 1 << 22
#: How long `Monitor.outputs` gives a value it checked without checking it again (seconds).
OUTPUTS_FRESH_S = 1.0
#: The records `Monitor.outputs` is made of, beside the files the contracts name.
_OUTPUT_RECORDS = (layout.RUN_INFO, layout.JOURNAL, layout.CONTRACTS)
#: The records a run's row of `Monitor.runs` is made of: it is made again when one changes.
_ROW_RECORDS = (layout.RUN_INFO, layout.JOURNAL, layout.PLAN, layout.DEFERRED, layout.FLOW_CALLS, layout.RESTS, layout.SERVICES)


def _shown_flow(flow: list[Any], cwd: Path | None) -> list[Any]:
    """A flow path with each frame's file as `_shown` gives it."""
    return [{**f, "file": _shown(f.get("file", ""), cwd)} for f in flow if isinstance(f, dict)]


class Monitor:
    """Read-only views over runs, shared by the web server and any other front end."""

    def __init__(
        self,
        runs_dir: str | Path = "runs",
        *,
        source: RunSource | None = None,
        liveness: Liveness | None = None,
        many_hosts: bool = False,
        title: str = "contraagent",
        panels: Mapping[str, Panel | PanelFn] | None = None,
        task_detail: TaskDetailFn | None = None,
        static_dir: str | Path | None = None,
        stream_formats: dict[str, str] | None = None,
        groups: list[dict[str, Any]] | None = None,
        keep_digests: bool = True,
        apps: Mapping[str, App] | None = None,
    ):
        """`groups` are the plan's columns (`[{"id", "label", "kinds": [...]}]`);
        without them each kind is a group of its own. The implementation kinds of one base
        kind (`agent_task(implementations=)`) that `groups` does not list are one group,
        named by the base kind.
        `static_dir` replaces the bundled web UI with the caller's own.
        `stream_formats` maps a custom coding agent's name to a built-in stream
        format (`claude`, `omp`) when the monitor runs in another process than
        the one that called `register_normalizer`.
        `source` and `liveness` replace where runs are read from (default: `runs_dir`
        and this host's `/proc`); a `source` given without `liveness` has no live run.
        `many_hosts`: the runs come from many hosts (a hub), so the UI offers its hosts.
        `keep_digests`: keep a finished run's trends digest in its directory
        (`layout.TRENDS`), so a restarted monitor reads it back instead of the logs;
        it is always kept in memory.
        `apps`: the pipeline's own pages (`App`), each served under `apps/<name>/` of the
        monitor, behind its base path; a panel shows one in a frame (`EmbedBody`). A name
        that is not a plain name raises `ValueError`."""
        self.many_hosts = many_hosts
        self.runs_dir: Path = Path(runs_dir).resolve()
        self.source: RunSource = source if source is not None else DirectorySource(self.runs_dir)
        if liveness is not None:
            self.liveness: Liveness = liveness
        elif source is None:
            self.liveness = ProcLiveness(self.runs_dir)
        else:
            self.liveness = StaticLiveness(source)
        self.title = title
        self.panels: dict[str, Panel] = {n: p if isinstance(p, Panel) else Panel(p, title=n) for n, p in (panels or {}).items()}
        self.task_detail_fn = task_detail
        self.apps: dict[str, App] = {}
        for name, app in (apps or {}).items():
            check_name(name, "app name")
            if not callable(app):
                raise ValueError(f"Monitor(apps=) {name!r} = {app!r} is not an ASGI app (a callable of scope, receive and send)")
            self.apps[name] = app
        self.static_dir: Path | None = Path(static_dir) if static_dir else None
        self.stream_formats: dict[str, str] = dict(stream_formats or {})
        self.group_defs: list[dict[str, Any]] = list(groups or [])
        self.keep_digests = keep_digests
        self._digests: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}  # run -> (signature, digest)
        self._infos: dict[str, tuple] = {}  # run -> (run.json's stat, run.json)
        self._shapes: dict[str, tuple[tuple, dict]] = {}  # run -> (its plan's and journal's stats, `run_shape`)
        self._run_rows: dict[str, tuple[tuple, dict[str, Any] | None]] = {}  # run -> (what its row was made of, the row)
        # The views kept between requests (`_kept`): (view, run) -> (what it was made of, the
        # value), and the lock of each, so one caller makes it at a time.
        self._views: OrderedDict[tuple[str, str], tuple[Any, Any, float]] = OrderedDict()  # ..., and when it was last checked
        self._view_locks: dict[tuple[str, str], threading.Lock] = {}
        self._view_texts: dict[tuple[str, str], tuple[Any, str]] = {}  # (view, run) -> (the value kept, its text)
        # By (run, log): the log's size when it was read up to `position`, that position, its
        # first line, each line's row (None for a line that is no row), and the rows (`_log_rows`).
        self._logs: OrderedDict[tuple[str, str], _HeldLog] = OrderedDict()
        self._logs_lock = threading.Lock()
        # By (run, transcript): its size when it was last counted, and the position after its
        # last complete line then (`_stream_lines`); its size when a page was last read, and
        # the position after it (`stream_from`).
        self._stream_counts: dict[tuple[str, str], tuple[int, LogPosition]] = {}
        self._stream_pages: dict[tuple[str, str], tuple[int, LogPosition]] = {}
        self._journal_agents: dict[str, tuple[int, dict[str, str]]] = {}  # run -> (journal lines read, `_agents`)
        self._trends: tuple[tuple, dict[str, Any]] | None = None  # the last trends, and what they were made of
        # Each trends panel's last body, and what it was made of; and those being made now,
        # so the same panel asked again (a page refreshes every few seconds) waits for it.
        self._trend_bodies: dict[tuple, tuple[tuple, dict[str, Any]]] = {}
        self._making: dict[tuple, Future] = {}
        self._lock = threading.Lock()

    def check_run(self, run: str) -> str:
        """`run` itself; `names.BadName` (a ValueError) when it is not a plain name."""
        return check_name(run, "run id")

    # --- runs --------------------------------------------------------------

    def runs(self) -> list[dict[str, Any]]:
        """One row per run directory, newest activity first. A run's row is made again
        only when a record it is made of changed, or whether it runs, or what runs in it."""
        out: list[dict[str, Any]] = []
        live = self.liveness.live()
        unresponsive = self.liveness.unresponsive()
        for run in self.source.runs():
            running = frozenset(_running_keys(self.liveness.snapshot(run))) if run in live else None
            sig = (tuple(self.source.stat(run, name) for name in _ROW_RECORDS), running)
            held = self._run_rows.get(run)
            if held is None or held[0] != sig:
                row = self._run_row(run, live=running is not None)
                held = (sig, row)
                if row is not None and row["attempts"]:  # one with no journal row shows its latest activity
                    self._run_rows[run] = held
            if held[1] is not None:
                out.append({**held[1], "running": run in live, "unresponsive": run in unresponsive})
        out.sort(key=lambda r: r["last_ts"], reverse=True)
        return out

    def _run_row(self, run: str, live: bool) -> dict[str, Any] | None:
        """A run's row of `runs`, but whether it runs or stopped reporting; None for a run
        with nothing to show yet."""
        info = self.source.info(run) or {}
        n = ok = partial = not_run = 0
        cost: float | None = None
        tokens = dict.fromkeys(TOKENS, 0)
        readings: list[dict[str, Any]] = []
        wall = 0.0
        last = ""
        run_group = info.get("run_group", "")
        kinds: dict[str, int] = {}
        extras: dict[str, None] = {}
        for e in self._read_journal(run):
            n += 1
            extras.update(dict.fromkeys(row_extras([e])))
            partial += e.get("stop") == "partial"
            ok += bool(e.get("ok")) and e.get("stop") != "partial"
            not_run += e.get("stop") in ("invalid_input", "skipped")
            if e.get("cost_usd") is not None:
                cost = (cost or 0.0) + float(e["cost_usd"])
            readings += [q for q in e.get("quota") or [] if isinstance(q, dict)]
            add_tokens(tokens, e.get("usage"))
            wall += float(e.get("wall_s") or 0)
            last = e.get("ts", last)
            kinds[e.get("kind", "?")] = kinds.get(e.get("kind", "?"), 0) + 1
            run_group = e.get("run_group") or run_group
        if not last:
            # A run on its first task has no journal row yet (rows land when
            # a task finishes); still list it once it has live evidence.
            if not info and not self.source.exists(run, layout.STREAMS):
                return None
            last = self.source.activity(run) or ""
            if not last:
                return None
        return {
            "run": run,
            "run_group": run_group or run,
            "attempts": n,
            "ok": ok,
            "partial": partial,
            "not_run": not_run,
            "tasks": self._task_counts(run, live=live),
            "cost_usd": round(cost, 6) if cost is not None else None,
            "tokens": tokens,
            **_first_last(readings),
            "wall_s": round(wall),
            "last_ts": last,
            "kinds": kinds,
            "host_id": info.get("host_id", ""),
            "run_uid": info.get("run_uid", ""),
            "started_at": info.get("started_at", ""),
            "stub": info.get("stub") is True,
            "replay": info.get("replay") if isinstance(info.get("replay"), str) else "",
            "row_extras": list(extras),
        }

    def hosts(self) -> dict[str, Any]:
        """The hosts that drive the runs, with their runs counted, and each account's first
        and last utilization reading over every run. A host that drives runs but does not
        report (it has no heartbeat) is listed as not up."""
        rows = self.runs()
        by_host: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_host.setdefault(row.get("host_id", ""), []).append(row)
        reported = {h["host_id"]: h for h in self.liveness.hosts()}
        hosts = []
        for host_id in sorted(set(reported) | {h for h in by_host if h}):
            mine = by_host.get(host_id, [])
            base = reported.get(host_id) or {"host_id": host_id, "up": False, "last_seen": "", "interval_s": None}
            hosts.append(
                {
                    **base,
                    "runs": len(mine),
                    "running": sum(1 for r in mine if r["running"]),
                    "unresponsive": sum(1 for r in mine if r["unresponsive"]),
                }
            )
        readings = [q for row in rows for a in row["quota"] for q in (a["first"], a["last"])]
        out = {"hosts": hosts, **_first_last(readings)}
        # The rests in force now: begun by a live run, not ended, not past their end.
        at = now()
        current = [
            r
            for row in rows
            if row["running"]
            for r in self._quota(row["run"])["rests"]
            if not r.get("ended") and not ((end := parse_iso(r.get("until"))) is not None and end <= at)
        ]
        for a in out["quota"]:
            a["rests"] = [
                r
                for r in current
                if r["credential"] == a["credential"] and (not r.get("account") or not a["account"] or r["account"] == a["account"])
            ]
        return out

    def _task_counts(self, run: str, live: bool = False) -> dict[str, Any]:
        """Tasks (not attempts) by how they ended, from the plan's states: the
        same numbers the run's own page shows. Running tasks are looked up only
        for a run that is `live`; a task deferred, or queued in a run that is not
        live, is `not_run` (it will not run), and only a live run's queued tasks wait."""
        names = ("total", "done", "partial", "failed", "not_started", "running", "waiting", "not_run", "skipped", "cancelled")
        counts: dict[str, int] = dict.fromkeys(names, 0)
        name = {
            "done": "done",
            "partial": "partial",
            "failed": "failed",
            "blocked": "not_started",
            "skipped": "skipped",
            "cancelled": "cancelled",
        }
        running = _running_keys(self.liveness.snapshot(run)) if live else set()
        # Made here and not kept: the list of runs keeps the counts, not every run's plan.
        for n in self._plan(run, {})["nodes"]:
            counts["total"] += 1
            state = name.get(n["state"], "waiting")
            if state == "waiting" and n.get("key") in running:
                state = "running"
            elif state == "waiting" and (n.get("deferred") or not live):
                # Deferred, or queued in a run that is over: it will not run.
                state = "not_run"
            counts[state] += 1
        return counts

    # --- journal -----------------------------------------------------------

    def _read_journal(self, run: str) -> list[dict[str, Any]]:
        """The run's journal rows, read on from where the last read ended (`_log_rows`). The
        list and its rows are shared by every caller, and none changes them."""
        return self._log_rows(run, layout.JOURNAL)[1]

    def journal(self, run: str, since: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Rows after line offset `since`, and the new total."""
        if self.source.size(run, layout.JOURNAL) < 0:
            return [], since
        by_line, _ = self._log_rows(run, layout.JOURNAL)
        return [r for r in by_line[since:] if r is not None], len(by_line)

    def _log_rows(self, run: str, log: str) -> tuple[list[dict[str, Any] | None], list[dict[str, Any]]]:
        """The rows of append-only `log` of `run`, by line (None for a line that is no row) and
        as a list, read on from the position the last read ended at: each line of a growing
        log is read and parsed once. A log shorter than then, or whose first line is another,
        is another log, read from its start. The `KEPT_LOGS` logs read last are kept."""
        key = (run, log)
        size = self.source.size(run, log)
        with self._logs_lock:
            held = self._logs.get(key)
            if size < 0:
                self._logs.pop(key, None)
                return [], []
            if held is not None and size >= held[0]:
                first = self.source.lines_at(run, log, LogPosition(0, 0), 1, 1)[0]
                if (first[0] if first else "") != held[2]:
                    held = None
            elif held is not None:
                held = None
            at, head, by_line, rows = (held[1], held[2], held[3], held[4]) if held is not None else (LogPosition(0, 0), "", [], [])
            got, after = self.source.lines_at(run, log, at)
            if got:
                parsed = [next(iter(parse_rows([line])), None) for line in got]
                by_line = by_line + parsed
                rows = rows + [r for r in parsed if r is not None]
                head = head or got[0] if at.line == 0 else head
            self._logs[key] = (size, after, head, by_line, rows)
            self._logs.move_to_end(key)
            while len(self._logs) > KEPT_LOGS:
                self._logs.popitem(last=False)
            return by_line, rows

    # --- plan (the pipeline, including work that has not started) ---------

    def plan_rows(self, run: str) -> list[dict[str, Any]]:
        """The run's `plan.jsonl`, one row per key: the first, as it was queued."""
        return [dict(r) for r in self._read_plan(run)]

    def _read_plan(self, run: str) -> list[dict[str, Any]]:
        """One plan row per key, the first: a list of the caller's own, its rows shared."""
        out, seen = [], set()
        for row in self._log_rows(run, layout.PLAN)[1]:
            # A key queued again (a retry, a re-dispatch) is the same node.
            if row.get("key") not in seen:
                seen.add(row.get("key"))
                out.append(row)
        return out

    def plan(self, run: str, live: dict[str, Any] | None = None) -> dict[str, Any]:
        """`_plan`, made again only when a record it is made of changed (`_ROW_RECORDS`),
        or what runs in the run (from `live`, the run's processes, else this host's). Every
        caller (each client's feed, the run's endpoint, the list of runs) is given the same
        value, which none changes."""
        snap = live if live is not None else self.liveness.snapshot(run)
        sig = (tuple(self.source.stat(run, name) for name in _ROW_RECORDS), frozenset(_running_keys(snap)))
        return self._kept("plan", run, lambda made: made == sig, lambda previous: (sig, self._plan(run, snap)))

    def _kept(
        self, view: str, run: str, current: Callable[[Any], bool], make: Callable[[Any], tuple[Any, Any]], fresh_s: float = 0.0
    ) -> Any:
        """A view of a run kept between requests: the value kept when `current(what it was
        made of)` says it still is, else the one `make(what the value kept was made of, or
        None)` gives with what it is made of. One caller makes it at a time; the others wait
        for it and are given it. A value checked less than `fresh_s` seconds ago is given
        unchecked: what many clients ask for in the same tick of their feeds is checked once.
        The `KEPT_VIEWS` views asked last are kept, and the text written of each
        (`_kept_text`), so memory does not grow with the runs a monitor has shown."""
        key = (view, run)
        with self._lock:
            lock = self._view_locks.setdefault(key, threading.Lock())
        with lock:
            held = self._views.get(key)
            at = time.monotonic()
            if held is not None and (at - held[2] < fresh_s or current(held[0])):
                with self._lock:
                    self._views[key] = (held[0], held[1], held[2] if at - held[2] < fresh_s else at)
                    self._views.move_to_end(key)
                return held[1]
            made, value = make(held[0] if held is not None else None)
            with self._lock:
                self._views[key] = (made, value, time.monotonic())
                self._views.move_to_end(key)
                self._view_texts.pop(key, None)
                while len(self._views) > KEPT_VIEWS:
                    gone, _ = self._views.popitem(last=False)
                    self._view_texts.pop(gone, None)
                    self._view_locks.pop(gone, None)
            return value

    def _kept_text(self, view: str, run: str, value: Any, write: Callable[[Any], str]) -> str:
        """`write(value)` for `value`, a view of `run` the monitor keeps (`plan`, `outputs`),
        written once while it is the one kept: each client's feed sends the same text. Only
        the text of the value kept now is held, so an older value is not kept alive."""
        key = (view, run)
        with self._lock:
            held = self._view_texts.get(key)
            if held is not None and held[0] is value:
                return held[1]
        text = write(value)
        with self._lock:
            kept = self._views.get(key)
            if kept is not None and kept[1] is value:
                self._view_texts[key] = (value, text)
        return text

    def _plan(self, run: str, live: dict[str, Any]) -> dict[str, Any]:
        """The pipeline as a graph: every task ever queued, its dependencies and
        state, plus the groups. `failed` is a task that ran and failed;
        `blocked` is one that did not start because an input was missing or
        off-contract (refused, `invalid_input`), or that waits for such a task
        or a failed one: it shows where a failure stopped the work.

        A run with no `plan.jsonl` (an older run, or one not made through
        `Run.queue`) falls back to the journal: finished tasks only, no edges.
        """
        journal = self._read_journal(run)
        last: dict[str, dict[str, Any]] = {}
        for e in journal:
            last[e.get("key", "")] = e
        rows = self._read_plan(run)  # its own list: the journal's tasks are added to it
        known = {r["key"] for r in rows}
        for e in journal:
            if e.get("key") not in known:
                known.add(e.get("key"))
                rows.append(
                    {
                        "key": e.get("key"),
                        "kind": e.get("kind", "?"),
                        "unit": e.get("unit", ""),
                        "after": [],
                        "executor": e.get("executor") or "agent",
                        "flow": [],
                        "created_from": [],
                        "flow_call": e.get("flow_call"),
                    }
                )
        # Why a task was deferred, unless a journal row came after (a resumed run ran it).
        deferred: dict[str, dict[str, Any]] = {}
        for d in parse_rows(self.source.lines(run, layout.DEFERRED)[0]):
            j = last.get(d.get("key", ""))
            if j is None or str(j.get("ts", "")) < str(d.get("ts", "")):
                deferred[d.get("key", "")] = d
        running = _running_keys(live)
        nodes = []
        for r in rows:
            j = last.get(r["key"])
            if r["key"] in running:
                state = "running"
            elif j is None:
                state = "pending"
            elif j.get("stop") == "skipped":
                state = "skipped"
            elif j.get("stop") == "invalid_input":
                state = "blocked"  # refused before launch: it never ran
            elif j.get("stop") == "partial":
                state = "partial"  # ok, its output a placeholder a resume makes again
            elif j.get("stop") == "cancelled":
                state = "cancelled"  # no flow call waited for it any longer
            else:
                state = "done" if j.get("ok") else "failed"
            node = {**r, "state": state}
            if state == "pending" and r["key"] in deferred:
                d = deferred[r["key"]]
                node["deferred"] = str(d.get("reason") or "")
                node["deferred_cause"] = _deferral_cause(d.get("cause"))
            if j:
                node.update(
                    {
                        "wall_s": j.get("wall_s", 0),
                        "stop": j.get("stop", ""),
                        "route": j.get("route", ""),
                        "attempts": j.get("attempt", 0) + 1,
                    }
                )
                if j.get("rerun"):
                    node["rerun"] = str(j["rerun"])
            nodes.append(node)
        by_key = {n["key"]: n for n in nodes}
        _block_behind(nodes)
        depth = _levels(nodes, by_key)
        cwd = self._cwd(run)
        for n in nodes:
            n["level"] = depth[n["key"]]
            n["group"] = self._group_name(n)
            if n.get("flow"):
                n["flow"] = _shown_flow(n["flow"], cwd)
        return {
            "nodes": nodes,
            "groups": self._groups(nodes),
            "flow_calls": self._flow_calls(run, cwd),
            **self._quota(run),
            "models": model_usage(journal),
            "services": self._services(run),
            **self._preflight(run),
        }

    # --- forecast (what the run is expected to create, from an earlier run) ---------

    def forecast(self, run: str) -> dict[str, Any]:
        """The tasks the run is expected to create and has not yet (`api.Forecast`): by
        tail key, the tasks of the run of the same flow that finished last before this one
        started (`latest_finished`), less those this run has created, with the earlier
        run's wall time and cost per task. A display only: the schedule never reads it."""
        infos = {r: self._info(r) for r in self.source.runs()}
        infos.setdefault(run, self._info(run))
        flow = infos[run].get("flow")
        earlier = latest_finished(run, infos)
        out: dict[str, Any] = {
            "flow": flow if isinstance(flow, str) else "",
            "earlier_run": earlier or "",
            "earlier_finished_at": str(infos[earlier].get("finished_at") or "") if earlier else "",
            "entries": [],
            "remaining": 0,
            "wall_s": 0.0,
            "cost_usd": None,
        }
        if earlier is None:
            return out
        created: dict[TailKey, int] = {}
        for row in self._read_plan(run):
            k = row_tail_key(row)
            created[k] = created.get(k, 0) + 1
        for (functions, kind, passes), part in self._shape(earlier).items():
            made = created.get((functions, kind, passes), 0)
            left = max(0, part["tasks"] - made)
            share = left / part["tasks"]
            cost = round(part["cost_usd"] * share, 6) if part["cost_usd"] is not None else None
            out["entries"].append(
                {
                    "kind": kind,
                    "group": self._group_name({"kind": kind, "base_kind": part["base_kind"]}),
                    "flow": list(functions),
                    "passes": list(passes),
                    "expected": part["tasks"],
                    "created": made,
                    "remaining": left,
                    "wall_s": round(part["wall_s"] * share, 3),
                    "cost_usd": cost,
                }
            )
            out["remaining"] += left
            out["wall_s"] += part["wall_s"] * share
            if cost is not None:
                out["cost_usd"] = (out["cost_usd"] or 0.0) + cost
        out["wall_s"] = round(out["wall_s"], 3)
        if out["cost_usd"] is not None:
            out["cost_usd"] = round(out["cost_usd"], 6)
        return out

    def _info(self, run: str) -> dict[str, Any]:
        """A run's `run.json` ({} for none), read again only when it changed."""
        return trends.run_info(self.source, run, self._infos)

    def _shape(self, run: str) -> dict[TailKey, dict[str, Any]]:
        """A run's `run_shape`, read again only when its plan or its journal changed."""
        sig = (self.source.stat(run, layout.PLAN), self.source.stat(run, layout.JOURNAL))
        held = self._shapes.get(run)
        if held is not None and held[0] == sig:
            return held[1]
        shape = run_shape(parse_rows(self.source.lines(run, layout.PLAN)[0]), self._read_journal(run))
        self._shapes[run] = (sig, shape)
        return shape

    def _preflight(self, run: str) -> dict[str, Any]:
        """`preflight`: what the run's preflight did (`run.json`), when it records it."""
        record = (self.source.info(run) or {}).get("preflight")
        if record is None:
            return {}
        try:
            return {"preflight": PreflightRecord.model_validate(record).model_dump(mode="json")}
        except ValidationError:
            return {}

    def _quota(self, run: str) -> dict[str, Any]:
        """The run's quota caps and rule (`run.json`), and each credential's rests
        (`rests.jsonl`): a start folded with its end, in start order."""
        info = self.source.info(run) or {}
        caps = info.get("quota_caps")
        quota_caps = []
        for c, v in caps.items() if isinstance(caps, dict) else ():
            try:
                quota_caps.append(QuotaCap.model_validate({**v, "credential": c}).model_dump(mode="json"))
            except (TypeError, ValidationError):
                continue
        rests: list[dict[str, Any]] = []
        open_: dict[tuple[str, str], dict[str, Any]] = {}
        for row in parse_rows(self.source.lines(run, layout.RESTS)[0]):
            try:
                event = RestEvent.model_validate(row)
            except ValidationError:
                continue
            name = (event.credential, event.account)
            if event.event == "start":
                rest = event.model_dump(mode="json", include=set(Rest.model_fields))
                open_[name] = {**rest, "since": event.ts, "ended": ""}
                rests.append(open_[name])
            elif name in open_:
                open_.pop(name)["ended"] = event.ts
        rule = info.get("quota_rule")
        return {"quota_caps": quota_caps, "quota_rule": rule if isinstance(rule, str) else "", "rests": rests}

    def _services(self, run: str) -> list[dict[str, Any]]:
        """Each start of a service (`services.jsonl`), folded with the stop that ended it, in
        start order. A stop ends the latest open start of its name; a start an earlier
        process of a resumed run never stopped (it was killed) stays without one."""
        spans: list[dict[str, Any]] = []
        up: dict[str, dict[str, Any]] = {}
        for row in parse_rows(self.source.lines(run, layout.SERVICES)[0]):
            try:
                event = ServiceEvent.model_validate(row)
            except ValidationError:
                continue
            if event.event == "start":
                span = {"name": event.name, "started_at": event.ts, "key": event.key or "", "address": event.address}
                span["start_s"] = event.wall_s
                if event.error is not None:
                    span["start_error"] = event.error
                else:
                    up[event.name] = span
                spans.append(span)
            elif event.name in up:
                span = up.pop(event.name)
                span.update(stopped_at=event.ts, stop_cause=event.cause, stop_error=event.error or "")
        return spans

    def _cwd(self, run: str) -> Path | None:
        """The run's working directory, as `run.json` records it."""
        cwd = (self.source.info(run) or {}).get("cwd")
        return Path(cwd) if isinstance(cwd, str) and cwd else None

    def _flow_calls(self, run: str, cwd: Path | None) -> list[dict[str, Any]]:
        """Each flow call of `flow_calls.jsonl` in start order, folded with its end. A
        resumed run starts its flow calls again: the latest start of an id counts."""
        calls: dict[str, dict[str, Any]] = {}
        for row in parse_rows(self.source.lines(run, layout.FLOW_CALLS)[0]):
            cid = row.get("id") if isinstance(row, dict) else None
            if not isinstance(cid, str):
                continue
            if row.get("event") == "start":
                flow = row.get("flow")
                calls[cid] = {
                    "id": cid,
                    "parent": row.get("parent"),
                    "function": row.get("function", ""),
                    "flow": _shown_flow(flow, cwd) if isinstance(flow, list) else [],
                    "state": "running",
                    "error": None,
                    "raised_at": None,
                    "raised_by": None,
                    "unawaited": [],
                    "time_box": _time_box(row.get("time_box")),
                }
            elif row.get("event") == "end" and cid in calls:
                at = row.get("raised_at")
                by = row.get("raised_by")
                unawaited = row.get("unawaited")
                calls[cid].update(
                    state=row.get("state") or "closed",
                    error=row.get("error"),
                    raised_at=_shown_flow([at], cwd)[0] if isinstance(at, dict) else None,
                    raised_by=by if isinstance(by, str) else None,
                    unawaited=[k for k in unawaited if isinstance(k, str)] if isinstance(unawaited, list) else [],
                )
        return list(calls.values())

    def _group_name(self, n: dict[str, Any]) -> str:
        """A node's group: the first of `groups` that lists its kind, else its base kind (an
        implementation kind's, `agent_task(implementations=)`), else its `Task.kind`."""
        for d in self.group_defs:
            if n["kind"] in d.get("kinds", ()):
                return d["id"]
        return n.get("base_kind") or n["kind"]

    def _groups(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        place = {id(n): i for i, n in enumerate(nodes)}

        def tally(sid: str, label: str, members: list[dict[str, Any]]) -> dict[str, Any]:
            states = ("done", "partial", "failed", "running", "pending", "skipped", "blocked", "cancelled")
            c = {s: sum(1 for n in members if n["state"] == s) for s in states}
            return {"id": sid, "label": label, "total": len(members), **c}

        if self.group_defs:
            by_kind: dict[str, list[dict[str, Any]]] = {}
            for n in nodes:
                by_kind.setdefault(n["kind"], []).append(n)
            out = []
            for d in self.group_defs:
                kinds = list(dict.fromkeys(d.get("kinds", ())))
                members = (
                    sorted((n for k in kinds for n in by_kind.get(k, ())), key=lambda n: place[id(n)])
                    if len(kinds) > 1
                    else by_kind.get(kinds[0], [])
                    if kinds
                    else []
                )
                out.append(tally(d["id"], d.get("label", d["id"]), members))
            listed = {k for d in self.group_defs for k in d.get("kinds", ())}
            bases: dict[str, list[dict[str, Any]]] = {}
            for n in nodes:  # the implementation kinds `groups` does not list: their base kind's group
                if n.get("base_kind") and n["kind"] not in listed:
                    bases.setdefault(n["base_kind"], []).append(n)
            return out + [tally(b, b, members) for b, members in bases.items()]
        groups: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            groups.setdefault(n["group"], []).append(n)
        order = sorted(groups, key=lambda g: (min(n["level"] for n in groups[g]), place[id(groups[g][0])]))
        return [tally(g, g, groups[g]) for g in order]

    def procs(self, run: str) -> dict[str, Any]:
        return self.liveness.snapshot(run)

    def task_detail(self, run: str, key: str) -> dict[str, Any]:
        """Journal rows, live launches and the stream file for one task, by its key."""
        check_name(key, "task key")
        rows = [dict(e) for e in self._read_journal(run) if e.get("key") == key]  # the callback's own
        snap = self.liveness.snapshot(run)
        launches = [
            {k: c.get(k) for k in ("key", "kind", "unit", "pid", "age_s", "plugin", "model", "role")}
            | {"cmd": (c.get("full_cmd") or "")[:600]}
            for c in snap.get("launches", [])
            if c.get("key") == key
        ]
        planned = next((n for n in self._read_plan(run) if n.get("key") == key), {})
        kind = (rows[-1].get("kind") if rows else None) or (launches[0].get("kind") if launches else None) or planned.get("kind")
        defs = {d.get("kind"): d for d in self.definitions(run)}
        detail = {
            "key": key,
            "rows": rows,
            "launches": launches,
            "definition": defs.get(kind),
            "io": self.task_io(run, key, rows=rows),
            "stream": key if self.source.size(run, layout.stream(key)) >= 0 else None,
            "row_extras": row_extras(rows),
        }
        if self.task_detail_fn is not None:
            try:
                detail.update(self.task_detail_fn(run, key, rows) or {})
            except Exception as exc:  # a domain's callback must not break the view
                detail["task_detail_error"] = f"{type(exc).__name__}: {exc}"
        return detail

    # --- agent transcript --------------------------------------------------

    def task_agent(self, run: str, key: str) -> str:
        """The coding agent a task ran on: its journal row, else its live process's
        executable name. Defaults to omp, whose normalizer is the lenient one."""
        agent = self._agents(run).get(key)
        if agent:
            return agent
        for c in self.liveness.snapshot(run).get("launches", []):
            if c.get("key") == key and c.get("full_cmd"):
                return c["full_cmd"].split()[0].rsplit("/", 1)[-1]
        return "omp"

    def _agents(self, run: str) -> dict[str, str]:
        """By task key, the coding agent of its last journal row that names one, read on
        from the line the last call read up to: a transcript's feed asks on every page."""
        held = self._journal_agents.get(run)
        count, agents = held if held is not None else (0, {})
        lines, total = self.source.lines(run, layout.JOURNAL, count)
        if total < count:  # another journal under the same name: read from its start
            lines, total = self.source.lines(run, layout.JOURNAL, 0)
            agents = {}
        agents = dict(agents)
        for e in parse_rows(lines):
            if e.get("key") and e.get("agent"):
                agents[e["key"]] = e["agent"]
        self._journal_agents[run] = (total, agents)
        return agents

    def stream_size(self, run: str, key: str) -> int:
        """A number that changes whenever task `key`'s transcript grows; -1 while it has
        none. `names.BadName` for a run id or task key that is not a plain name."""
        return self.source.size(run, layout.stream(check_name(key, "task key")))

    async def wait_stream(self, run: str, key: str, beyond: int, timeout: float) -> int:
        """Wait until task `key`'s transcript has grown past `beyond` (a value `stream_size`
        returned), or `timeout` seconds; return its `stream_size` then."""
        return await self.source.wait(run, layout.stream(check_name(key, "task key")), beyond, timeout)

    def stream(self, run: str, key: str, since: int, limit: int = 1500) -> tuple[dict[str, Any], int]:
        """A page of task `key`'s normalized transcript events.

        `since` is a line offset; the first call (`since=0`) returns the TAIL
        page so a huge stream never crosses the wire whole, and the client
        pages backward on demand. Always `{events, total, behind}`, including
        when the file is absent.
        """
        page, _ = self.stream_from(run, key, since if since > 0 else None, limit)
        return page, page["total"]

    def stream_from(self, run: str, key: str, since: int | None, limit: int = 1500) -> tuple[dict[str, Any], int]:
        """A page of task `key`'s normalized transcript events from line `since` (None:
        the tail page, the last `limit` lines), as `stream` gives it, and the line offset
        after the last line the page read: where the next page starts. The page stops at
        `limit` events or `PAGE_BYTES`, so that offset can be less than `total`. A last
        line still being written (no newline yet) is not read (`RunSource.lines`)."""
        log = layout.stream(check_name(key, "task key"))
        start = since or 0
        size = self.source.size(run, log)
        if size < 0:
            return {"events": [], "total": start, "behind": 0}, start
        total = self._stream_lines(run, log, size)
        behind = 0
        if since is None:
            behind = start = max(0, total - limit)
        held = self._stream_pages.get((run, log))
        at = held[1] if held is not None and held[1].line == start and held[0] <= size else self.source.position(run, log, start)
        if at.line < start:  # fewer lines than `since`: another log under the same name
            return {"events": [], "total": total, "behind": 0}, start
        lines, after = self.source.lines_at(run, log, at, limit * 4, max_bytes=PAGE_BYTES)
        total = max(total, after.line)
        fmt = resolve_format(self.task_agent(run, key), self.stream_formats)
        out: list[dict[str, Any]] = []
        tools: dict[str, str] = {}  # call id -> tool name: some formats name the tool only on its start
        end = start
        for line in lines:
            end += 1
            for ev in normalize_stream_line(fmt, line):
                if ev.get("type") == "tool_execution_start" and ev.get("call"):
                    tools[ev["call"]] = ev.get("tool") or ""
                elif ev.get("type") == "tool_execution_end" and not ev.get("tool"):
                    ev["tool"] = tools.get(ev.get("call") or "", "")
                out.append(ev)
            if len(out) >= limit:
                break
        if end == after.line:  # the page read every line it took: the next one starts there
            self._stream_pages[(run, log)] = (size, after)
        return {"events": out, "total": total, "behind": behind}, end

    def _stream_lines(self, run: str, log: str, size: int) -> int:
        """How many complete lines transcript `log` of `run` has, counted on from where the
        last count ended (`size` is the log's `size`; a smaller one than then is another log,
        counted from its start): while a log grows, each of its bytes is read once to count it."""
        held = self._stream_counts.get((run, log))
        at = held[1] if held is not None and held[0] <= size else LogPosition(0, 0)
        while True:
            got, after = self.source.lines_at(run, log, at, None, COUNT_BYTES)
            if not got:
                break
            at = after
        self._stream_counts[(run, log)] = (size, at)
        return at.line

    # --- contracts: the files tasks must leave behind ----------------------

    def outputs(self, run: str) -> dict[str, Any]:
        """`_outputs`, made again only when the journal, `run.json` or the contract records
        changed, what runs in the run, or one of the files the contracts name (their sizes
        and modification times). Every caller is given the same value, which none changes."""
        running = frozenset(_running_keys(self.liveness.snapshot(run)))
        sig = (tuple(self.source.stat(run, name) for name in _OUTPUT_RECORDS), running)

        def current(made: tuple) -> bool:
            return made[0] == sig and made[1] == self._file_stats(run, made[2])

        def make(previous: tuple | None) -> tuple[Any, Any]:
            # A file that did not change keeps its view: only the files that did are read again.
            kept: dict[str, tuple[Any, dict[str, Any]]] = previous[3] if previous is not None else {}
            views: dict[str, tuple[Any, dict[str, Any]]] = {}

            def view_of(path: str, rows: bool) -> dict[str, Any]:
                st = self.source.file_stat(run, path)
                held = kept.get(f"{rows}:{path}")
                view = held[1] if held is not None and held[0] == st and st is not None else self._file_view(run, path, rows=rows)
                views[f"{rows}:{path}"] = (st, view)
                return view

            value = self._outputs(run, running, view_of)
            paths = tuple(spec["path"] for rec in value["contracts"] for spec in rec.get("outputs", []) + rec.get("inputs", []))
            return (sig, self._file_stats(run, paths), paths, views), value

        # The outputs check thousands of files: checked at most once in a feed's tick.
        return self._kept("outputs", run, current, make, fresh_s=OUTPUTS_FRESH_S)

    def _file_stats(self, run: str, paths: Iterable[str]) -> tuple:
        return tuple(self.source.file_stat(run, path) for path in paths)

    def _outputs(self, run: str, running: frozenset[str], view_of: Callable[[str, bool], dict[str, Any]] | None = None) -> dict[str, Any]:
        """Every declared `OutputContract` / `InputContract` of the run: its file,
        the model it must satisfy, and where it stands.

        Status comes from the journal, which records what `run_until_valid`
        concluded: `pending` before the task finishes, `valid` (with the number
        of rounds it took when it needed a resume), `invalid` when the file
        was still off-contract after every resume, `refused` when an input was off-contract so
        the task never started, `failed` when the task ended for another reason before
        the check could pass.
        """
        last: dict[str, dict[str, Any]] = {}
        for e in self._read_journal(run):
            last[e.get("key", "")] = e
        records = [self._contract(run, rec, last, running, view_of) for rec in parse_rows(self.source.folder(run, layout.CONTRACTS))]
        outs = [o for r in records for o in r["outputs"]]
        tally = {s: sum(1 for o in outs if o["status"] == s) for s in ("valid", "invalid", "refused", "pending", "failed", "running")}
        return {"contracts": records, "tally": tally}

    def _contract(
        self,
        run: str,
        rec: dict[str, Any],
        last: Mapping[str, dict[str, Any]],
        running: frozenset[str],
        view_of: Callable[[str, bool], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """A contract record (`contracts/<key>.json`) as `outputs` shows it: each file with
        its fields (`view_of(path, rows)`, else `_file_view`), and each output's status from
        its task's last journal row in `last`."""
        row = last.get(rec.get("key", ""))
        for spec in rec.get("outputs", []) + rec.get("inputs", []):
            rows = spec.get("format") == "jsonl"
            spec["file"] = view_of(spec["path"], rows) if view_of is not None else self._file_view(run, spec["path"], rows=rows)
            props = (spec.get("schema") or {}).get("properties", {})
            req = set((spec.get("schema") or {}).get("required", []))
            spec["fields"] = [{"name": n, "type": self._type_of(p), "required": n in req} for n, p in props.items()]
            spec.pop("schema", None)
        for spec in rec.get("outputs", []):
            spec["status"], spec["rounds"], spec["errors"] = self._contract_status(row, spec["file"], rec.get("key") in running)
        return rec

    def _contracts_of(self, run: str, keys: Iterable[str]) -> list[dict[str, Any]]:
        """The contract records of the tasks `keys` alone, as `outputs` shows them."""
        records = []
        last: dict[str, dict[str, Any]] | None = None
        running: frozenset[str] = frozenset()
        for key in dict.fromkeys(keys):
            try:
                text = self.source.document(run, layout.task_entry(layout.CONTRACTS, key))
            except BadName:
                continue
            rows = parse_rows([text]) if text else []
            if not rows:
                continue
            if last is None:
                last = {e.get("key", ""): e for e in self._read_journal(run)}
                running = frozenset(_running_keys(self.liveness.snapshot(run)))
            records.append(self._contract(run, rows[0], last, running))
        return records

    @staticmethod
    def _type_of(prop: dict[str, Any]) -> str:
        if "$ref" in prop:
            return prop["$ref"].rsplit("/", 1)[-1]
        t = prop.get("type", "any")
        if t == "array":
            return f"list[{Monitor._type_of(prop.get('items', {}))}]"
        return "|".join(x.get("type", "any") for x in prop["anyOf"]) if "anyOf" in prop else str(t)

    def _file_view(self, run: str, path: str, limit: int = 20_000, *, rows: bool = False) -> dict[str, Any]:
        """A file as `FileView` shows it; with `rows`, a JSON Lines file whose content is the
        list of its lines that parse."""
        if isinstance(self.source, DirectorySource):  # reads a file's start alone: a large file is not held whole
            got = self.source._file_head(run, path, 4 * limit + 4)
            if got is None:
                return {"exists": False}
            text, size, mtime = got
        else:
            whole = self.source.file(run, path)
            if whole is None:
                return {"exists": False}
            text, size, mtime = whole.text, whole.size, whole.mtime
        out: dict[str, Any] = {"exists": True, "size": size, "mtime": mtime}
        if text is None:
            out["content"] = None
            return out
        out["truncated"] = len(text) > limit or size > len(text.encode())
        if rows:
            out["content"] = [row for line in text[:limit].splitlines() if (row := _json_line(line)) is not None]
            return out
        try:
            out["content"] = json.loads(text) if not out["truncated"] else text[:limit]
        except ValueError:  # a text output, or JSON that does not parse: the text itself
            out["content"] = text
        return out

    @staticmethod
    def _contract_status(row: dict[str, Any] | None, file: dict[str, Any], running: bool) -> tuple[str, int | None, list[str]]:
        if row is None:
            return ("running" if running else "pending"), None, []
        rounds = row.get("rounds")
        errors = (row.get("round_errors") or [[]])[-1] if row.get("stop") == "invalid_output" else []
        if row.get("stop") == "invalid_input":
            # the task never started: one of its inputs was off-contract
            return "refused", rounds, [row.get("reason", "")] if row.get("reason") else errors
        if row.get("stop") == "invalid_output":
            return "invalid", rounds, errors
        if row.get("ok") and file.get("exists"):
            return "valid", rounds, errors
        return "failed", rounds, errors

    # --- definitions and per-task input / output ------------------------------

    def definitions(self, run: str) -> list[dict[str, Any]]:
        """What defined each kind of task in this run (`definitions/<kind>.json`)."""
        return parse_rows(self.source.folder(run, layout.DEFINITIONS))

    def task_io(
        self,
        run: str,
        key: str,
        *,
        outputs: dict[str, Any] | None = None,
        plan_rows: list[dict[str, Any]] | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """One task's input and output: its params, the files it read, the files
        it left behind with the contract verdict, and how data flows around it.

        `upstream` are the tasks this one was given from (`given_from`), waits for (`after=`) or
        was created from (`created_from`), each with its output files (for a task that declares
        no `InputContract`, those of the tasks it was given from are what it reads) and its
        lineage. `downstream` are the tasks joined so to this one, each with its lineage.
        `input_files` are the input files among its params, each with the task it was given from
        whose output file it is, and its check as the task was about to start.
        `outputs`, `plan_rows` and `rows`, when given, are the run's (`outputs(run)`, its plan
        rows) and the task's journal rows, read once for many tasks.
        """
        plan = {n["key"]: n for n in (plan_rows if plan_rows is not None else self._read_plan(run))}
        node = plan.get(key, {})
        by_key = {c.get("key"): c for c in outputs["contracts"]} if outputs is not None else {}
        lineages = {k: lineage_of(n) for k, n in plan.items()}
        if outputs is None:  # the task's own contracts and those of the tasks around it, not the run's
            around = [key, *lineage_of(node), *(k for k, lin in lineages.items() if key in lin)]
            by_key = {c.get("key"): c for c in self._contracts_of(run, around)}
        rec = by_key.get(key) or {}
        upstream = []
        for dep, lineage in lineage_of(node).items():
            d = by_key.get(dep)
            upstream.append(
                {
                    "key": dep,
                    "kind": (plan.get(dep) or {}).get("kind", ""),
                    "unit": (plan.get(dep) or {}).get("unit", ""),
                    "executor": (plan.get(dep) or {}).get("executor", "agent"),
                    "outputs": (d or {}).get("outputs", []),
                    "lineage": lineage,
                }
            )
        downstream = []
        for k, n in plan.items():
            lineage = lineages[k].get(key)
            if lineage:
                neighbour = {"key": k, "kind": n.get("kind", ""), "unit": n.get("unit", ""), "executor": n.get("executor", "agent")}
                downstream.append({**neighbour, "lineage": lineage})
        return {
            "params": self._call_params(run, key, rec.get("params", {})),
            "inputs": rec.get("inputs", []),
            "input_files": _input_files(node, by_key, rows if rows is not None else self._rows(run, key)),
            "outputs": rec.get("outputs", []),
            "executor": rec.get("executor", node.get("executor", "agent")),
            "upstream": upstream,
            "downstream": downstream,
        }

    def _rows(self, run: str, key: str) -> list[dict[str, Any]]:
        return [dict(e) for e in self._read_journal(run) if e.get("key") == key]

    def _call_params(self, run: str, key: str, fallback: dict[str, Any]) -> dict[str, Any]:
        """What the task was given: the call file's params (every value, a value
        from an earlier task included), else the contract record's scalar ones."""
        try:
            params = json.loads(self.source.document(run, layout.task_entry(layout.CALLS, key)) or "").get("params")
        except (ValueError, AttributeError):
            return fallback
        return params if isinstance(params, dict) else fallback

    # --- resume cursor -------------------------------------------------------

    def cursor(self, run: str) -> dict[str, Any] | None:
        """The run's `CursorStore` (runs/<run>/cursor.json), or None when it keeps none:
        the stage it is in, the stages behind it, and each unit's step."""
        text = self.source.document(run, layout.CURSOR)
        cur = parse_cursor(text) if text is not None else None
        if cur is None:
            return None
        return {
            "stage": cur.stage,
            "completed_stages": cur.completed_stages,
            "history": [{"name": h.name, "at": h.at.isoformat()} for h in cur.history],
            "updated_at": cur.updated_at.isoformat(),
            "units": {
                u: {
                    "stage": c.stage,
                    "step": c.step,
                    "completed": c.completed,
                    "loop_pass": c.loop_pass,
                    "inflight": list(c.inflight.item_ids) if c.inflight else [],
                }
                for u, c in cur.units.items()
            },
            "markers": {k: v for k, v in cur.markers.items()},
        }

    # --- panels ------------------------------------------------------------

    def panel(self, name: str, run: str) -> dict[str, Any]:
        """Run panel `name`'s body for `run`: its `fn` given the run's records (`RunRecords`).
        KeyError: no run panel of that name."""
        panel = self.panels.get(name)
        if panel is None or panel.scope != "run":
            raise KeyError(name)
        return panel(RunRecords(run, self.source))

    def run_panels(self) -> list[str]:
        """The names of the panels computed per run: each run's tabs, and its live feed."""
        return [n for n, p in self.panels.items() if p.scope == "run"]

    def panel_info(self) -> list[dict[str, Any]]:
        """Every panel, in the order of the `panels` given."""
        return [p.info(n) for n, p in self.panels.items()]

    # --- trends --------------------------------------------------------------

    def trends(self, period: Period, *, run_group: str = "", stub: bool = False) -> dict[str, Any]:
        """What the runs of `period` add up to, with the same numbers as
        panel bodies (`bodies`) and the trend panels on offer (`panels`). `run_group` keeps
        the runs of one group; stub runs count only with `stub`."""
        held = self._period_digests(period)
        groups = self._group_of()
        # The same period over the same runs, as they were: the same trends (a page asks again and again).
        made_of = self._made_of(period, run_group, stub, held)
        if self._trends is not None and self._trends[0] == made_of:
            return self._trends[1]
        digests = [dg for _, _, dg in held if (not run_group or dg["run_group"] == run_group) and (stub or not dg["stub"])]
        view = trends.aggregate(digests, period, groups)
        out = {
            **view,
            "bodies": trends.bodies(view),
            "panels": [p.info(n) for n, p in self.panels.items() if p.scope == "trends"],
        }
        self._trends = (made_of, out)
        return out

    def _made_of(self, period: Period, run_group: str, stub: bool, held: list[tuple[str, dict[str, Any], dict[str, Any]]]) -> tuple:
        """What trends of `period` are made of: the period, the filters, the groups, and each
        run with the signature of its logs. The same, the same trends."""
        return (period, run_group, stub, tuple(sorted(self._group_of().items())), tuple((run, tuple(sig.items())) for run, sig, _ in held))

    def trends_panel(self, name: str, period: Period, *, run_group: str = "") -> dict[str, Any]:
        """Trends panel `name`'s body: its `fn(runs, period)` over the runs of `period`
        (`PeriodRuns`, newest activity first). Made once for the same period over the same
        runs, as they were, and kept: a page that asks again gets it back, and one that asks
        while it is being made waits for that one. KeyError: no trends panel of that name."""
        panel = self.panels.get(name)
        if panel is None or panel.scope != "trends":
            raise KeyError(name)
        held = self._period_digests(period)
        made_of = self._made_of(period, run_group, False, held)
        place = (name, period, run_group)
        with self._lock:
            kept = self._trend_bodies.get(place)
            if kept is not None and kept[0] == made_of:
                return kept[1]
            making = self._making.get((place, made_of))
            mine = making is None
            if mine:
                making = self._making[(place, made_of)] = Future()
        assert making is not None
        if not mine:
            return making.result()
        try:
            runs = PeriodRuns((r["run"] for r in self.trends(period, run_group=run_group)["runs"]), self.source)
            body = panel(runs, period)
        except BaseException as exc:
            with self._lock:
                self._making.pop((place, made_of), None)
            making.set_exception(exc)
            raise
        with self._lock:
            self._trend_bodies[place] = (made_of, body)
            self._making.pop((place, made_of), None)
        making.set_result(body)
        return body

    def _group_of(self) -> dict[str, str]:
        """Kind -> the label of the group it is in (`groups`); a kind in none is its own."""
        return {k: g.get("label") or g.get("id") or k for g in self.group_defs for k in g.get("kinds") or ()}

    def _period_digests(self, period: Period) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        """The runs that may have worked in `period` (by `run.json`), with their signatures
        and digests."""
        out = []
        live: set[str] | None = None

        def is_live(run: str) -> bool:  # only for a digest made now: it scans the processes
            nonlocal live
            if live is None:
                live = self.liveness.live()
            return run in live

        for run in self.source.runs():
            info, sig = trends.run_files(self.source, run, self._infos)
            if trends.in_period(info, period):
                out.append((run, sig, self._digest(run, sig, is_live)))
        return out

    def digest(self, run: str) -> dict[str, Any]:
        """Run `run`'s trends digest (`trends.digest`): from memory while its logs are the
        same, else from its `trends.json` when that was made from these logs, else from the
        logs (then kept: in memory, and in the directory of a finished run that is not live)."""
        return self._digest(run, trends.run_files(self.source, run, self._infos)[1], lambda r: r in self.liveness.live())

    def _digest(self, run: str, sig: dict[str, Any], is_live: Callable[[str], bool]) -> dict[str, Any]:
        held = self._digests.get(run)
        if held is not None and held[0] == sig:
            return held[1]
        kept = self._kept_digest(run, sig)
        dg = trends.from_kept(kept) if kept is not None else trends.digest(self.source, run)
        if kept is None and sig.get("finished_at") and not is_live(run):
            self._keep_digest(run, sig, trends.kept_form(dg))
        self._digests[run] = (sig, dg)
        return dg

    def _kept_digest(self, run: str, sig: dict[str, Any]) -> dict[str, Any] | None:
        """The digest the source keeps of the run (`RunSource.kept`), when it was made from
        the logs as they are (`sig`) by this digest version."""
        text = self.source.kept(run) if self.keep_digests else None
        try:
            kept = json.loads(text) if text is not None else None
        except ValueError:
            return None
        if not isinstance(kept, dict) or kept.get("signature") != sig or kept.get("digest", {}).get("version") != trends.DIGEST_VERSION:
            return None
        return kept["digest"]

    def _keep_digest(self, run: str, sig: dict[str, Any], dg: dict[str, Any]) -> None:
        """Keep a digest where the source keeps one (`RunSource.keep`: a runs directory's
        `trends.json`); it is in memory anyway."""
        if self.keep_digests:
            self.source.keep(run, json.dumps({"signature": sig, "digest": dg}))


def row_extras(rows: list[dict[str, Any]]) -> list[str]:
    """The columns of journal rows that are a pipeline's own (`Run(row_extras=)`): keys
    `JournalRow` does not name, in the order they first appear."""
    known = JournalRow.model_fields
    out: dict[str, None] = {}
    for row in rows:
        out.update(dict.fromkeys(k for k in row if k not in known))
    return list(out)


def _block_behind(nodes: list[dict[str, Any]]) -> None:
    """Make `blocked` each pending node that waits (`after`), directly or through other
    pending ones, for a failed or blocked one: from those, along the edges to the nodes
    that wait for them, each edge once."""
    waiting: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        for d in n["after"]:
            waiting.setdefault(d, []).append(n)
    todo = [n["key"] for n in nodes if n["state"] in ("failed", "blocked")]
    while todo:
        for n in waiting.get(todo.pop(), ()):
            if n["state"] == "pending":
                n["state"] = "blocked"
                todo.append(n["key"])


def _levels(nodes: list[dict[str, Any]], by_key: Mapping[str, dict[str, Any]]) -> dict[str, int]:
    """Each node's level: one more than the highest level of the nodes it comes after
    (`_earlier`), counting one that is not queued yet as level -1 (so 0), and -1 with none.
    A cycle is cut where the walk meets a node it is inside of, as a depth-first walk from
    each node in order meets it. Iterative, so a chain of any length."""
    depth: dict[str, int] = {}
    for start in nodes:
        if start["key"] in depth:
            continue
        on_path: set[str] = set()
        stack: list[list[Any]] = []  # [key, the dependencies left, the best level of those done]
        todo = [start["key"]]
        while todo or stack:
            if todo:
                key = todo.pop()
                after = _earlier(by_key.get(key, {}))
                deps = [d for d in after if d in by_key and d not in on_path]
                on_path.add(key)
                stack.append([key, deps, 0 if any(d not in by_key for d in after) else -1])
                continue
            frame = stack[-1]
            deps = frame[1]
            while deps and (deps[0] in depth or deps[0] in on_path):
                d = deps.pop(0)
                if d in depth:  # met inside the walk (a cycle): as the recursion left it out
                    frame[2] = max(frame[2], depth[d])
            if deps:
                todo.append(deps[0])
                continue
            stack.pop()
            on_path.discard(frame[0])
            depth[frame[0]] = 1 + frame[2]
    return depth


def _earlier(node: dict[str, Any]) -> list[str]:
    """The keys of the tasks a plan node comes after: those it waits for (`after`), then those
    it was given from (`given_from`), each once."""
    keys = [*(node.get("after") or []), *(node.get("given_from") or [])]
    return [k for k in dict.fromkeys(keys) if isinstance(k, str)]


def lineage_of(node: Mapping[str, Any]) -> dict[str, list[str]]:
    """The earlier tasks of a plan row by key, each with its lineage (`api.Lineage`): those it
    was given from (`given_from`), those it waits for and was not given from (`after`), then
    those it was created from (`created_from`); each key once, its lineage in that order."""
    given = [k for k in node.get("given_from") or () if isinstance(k, str)]
    out: dict[str, list[str]] = {k: ["given_from"] for k in given}
    for k in node.get("after") or ():
        if isinstance(k, str) and k not in out:
            out[k] = ["after"]
    for k in node.get("created_from") or ():
        if isinstance(k, str):
            lineage = out.setdefault(k, [])
            if "created_from" not in lineage:
                lineage.append("created_from")
    return out


def _input_files(node: Mapping[str, Any], records: Mapping[Any, Mapping[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A task's input files (its plan row's `input_files`), each with `writer`, the task it
    was given from whose output file it is (a file of the input root `out`, by its path
    under `out/`), and `check`: `refused` when its
    last journal row is a refusal (`invalid_input`) that names its path, `passed` when a
    journal row shows the task started, else `not_checked`."""
    last = rows[-1] if rows else None
    started = any(r.get("stop") not in ("invalid_input", "skipped") for r in rows)
    refusal = str(last.get("reason") or "") if last is not None and last.get("stop") == "invalid_input" else ""
    out = []
    for f in node.get("input_files") or ():
        if not isinstance(f, Mapping) or not isinstance(f.get("path"), str):
            continue
        path = f["path"]
        root = f.get("root") if isinstance(f.get("root"), str) else None
        # An output file of the run is of the root `out`; a run of an earlier release held it
        # by its path, relative to the working directory or absolute.
        written = f"{OUT}/{path}" if root == OUT else path if root is None else None
        writers = [
            k
            for k in node.get("given_from") or ()
            if written is not None and any(_same_file(o.get("path"), written) for o in (records.get(k) or {}).get("outputs", ()))
        ]
        check = "refused" if refusal and path in refusal else "passed" if started else "not_checked"
        out.append(
            {
                "param": str(f.get("param", "")),
                "root": root,
                "path": path,
                "sha256": str(f.get("sha256", "")),
                "writer": writers[0] if writers else None,
                "check": check,
                "reason": refusal if check == "refused" else "",
            }
        )
    return out


def _same_file(output: object, given: str) -> bool:
    """An output contract's path (absolute) names the file an input file's path (relative to
    the working directory, or absolute) names."""
    if not isinstance(output, str) or not output:
        return False
    if output == given:
        return True
    return not Path(given).is_absolute() and Path(output).as_posix().endswith("/" + Path(given).as_posix())
