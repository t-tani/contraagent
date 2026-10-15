"""`contraagent monitor export`: the monitor's views of some runs, written as files.

An export is the page (`index.html`, `app.js`, `ja.js`) and `data/`, the JSON each
route of the API would answer, one file per route:

    data/info.json                       /api/info, with `export` (`api.ExportInfo`)
    data/runs.json                       /api/runs: the runs it holds
    data/runs/<run>/journal.json         /api/runs/<run>/journal (every row)
    data/runs/<run>/plan.json            /api/runs/<run>/plan
    data/runs/<run>/outputs.json         /api/runs/<run>/outputs
    data/runs/<run>/definitions.json     /api/runs/<run>/definitions
    data/runs/<run>/cursor.json          /api/runs/<run>/cursor
    data/runs/<run>/tasks/<key>.json     /api/runs/<run>/task/<key>, without its `rows` and
                                         `definition` (journal.json and definitions.json hold
                                         them; the export client puts them back)
    data/runs/<run>/panels/<name>.json   /api/runs/<run>/panels/<name>
    data/trends/panels/<name>.json       /api/trends/panels/<name>: a panel of `scope="trends"`
    data/<file>                          each route of no run in `SITE_ROUTES` (`trends.json`)

The page reads them with no server (`<ca-monitor export="data/">`, `createExportClient`
in `@contraagent/api`): any static file server, or a site, serves an export.

What it never holds: transcripts (`/stream`), process trees (`/procs`), and the launches
running at the time (a task's `launches`). What it takes out by default (`REDACTED`):

* `paths`: a path under the run's directory, the run's working directory or the runs
  directory is made relative to it, and one under the home directory starts with `~`,
  everywhere; outside a document's contents (`content`, `text`), any other path of a
  person's or a temporary directory (`/home`, `/Users`, `/root`, `/tmp`, ...) is
  `<path>`. A system path (`/etc/hosts`) is not this machine's and stays;
* `host`: `host_id`, the host's name.

`keep` puts either back; `exclude` takes out a key wherever it appears (`params`, say).
A new route of the API is one entry here (`ROUTES` for a run's, `SITE_ROUTES` for one of
no run) and one method in `createExportClient`.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from pydantic import TypeAdapter

from contraagent.monitor import api
from contraagent.monitor.core import Monitor, row_extras
from contraagent.monitor.trends import Period

STATIC = Path(__file__).parent / "static"

#: What the page needs beside `data/`.
PAGE_FILES = ("index.html", "app.js", "ja.js")

#: What an export takes out by default; `keep` puts them back.
REDACTED = ("paths", "host")

#: The views an export never holds.
LEFT_OUT = ("transcripts", "processes")

#: Absolute paths of a person's or a temporary directory left in a string after the known
#: roots were made relative. A system path (`/etc/hosts`) says nothing about the machine.
_ABSOLUTE = re.compile(r"(?<![\w.:/~-])/(?:home|Users|root|tmp|private|var/folders)/[^\s\"'`<>|,;)\]]*")

#: Keys whose value is a document's contents (a file shown as it is): this machine's paths in
#: it are made relative, and nothing else in it is changed.
CONTENT_KEYS = frozenset({"content", "text"})


@dataclass(frozen=True)
class Route:
    """One route of the API as a file of the export: `file` under `data/` (a site route)
    or `data/runs/<run>/` (a run route), `read(monitor, run)` its body (`run` is '' for a
    site route), `model` the contract it is checked against."""

    file: str
    read: Callable[[Monitor, str], Any]
    model: Any


@dataclass(frozen=True)
class SiteRoute:
    """One route of no run as a file under `data/`: `read(monitor, period)` its body, over
    the export's period, `model` its contract."""

    file: str
    read: Callable[[Monitor, Period], Any]
    model: Any


#: The routes of no run, beside `info.json` and `runs.json` (which the export writes
#: itself: they say what it holds); panels of `scope="trends"` are written under
#: `trends/panels/` (`_panels`).
SITE_ROUTES: tuple[SiteRoute, ...] = (SiteRoute("trends.json", lambda m, period: m.trends(period), api.Trends),)

# `Optional`, not `X | None`: a TypeAdapter's type must be a type, not a `UnionType` value.
ROUTES: tuple[Route, ...] = (
    Route("journal.json", lambda m, run: dict(zip(("entries", "total"), m.journal(run), strict=True)), api.JournalPage),
    Route("plan.json", lambda m, run: m.plan(run), api.Plan),
    Route("outputs.json", lambda m, run: m.outputs(run), api.Outputs),
    Route("definitions.json", lambda m, run: m.definitions(run), list[api.TaskDefinition]),
    Route("cursor.json", lambda m, run: m.cursor(run) or {}, Optional[api.CursorView]),  # noqa: UP045
)


def _dump(model: Any, value: Any) -> Any:
    """`value` as the route answers it: checked against its model, unset keys left out."""
    adapter = TypeAdapter(model)
    return json.loads(adapter.dump_json(adapter.validate_python(value), exclude_unset=True, by_alias=True))


class Redactor:
    """Takes out of a view what the export does not show (`REDACTED`, `exclude`)."""

    def __init__(self, roots: Iterable[Path], *, keep: Iterable[str] = (), exclude: Iterable[str] = ()) -> None:
        self.keep = set(keep)
        self.exclude = set(exclude)
        home = str(Path.home())
        # The longest root first, so a run directory wins over the runs directory around it.
        roots_ = sorted({str(r).rstrip("/") for r in roots if str(r) not in ("", "/")}, key=len, reverse=True)
        # A root only where a path name ends: `/runs/x` is not the start of `/runs/xy`.
        self.roots = [re.compile(re.escape(r) + r"(/|(?![\w.-]))") for r in roots_]
        self.home = home if home not in ("", "/") else ""

    def __call__(self, value: Any, content: bool = False) -> Any:
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if k in self.exclude:
                    continue
                if k == "host_id" and "host" not in self.keep:
                    v = ""
                out[k] = self(v, content or k in CONTENT_KEYS)
            return out
        if isinstance(value, list):
            return [self(v, content) for v in value]
        if isinstance(value, str) and "paths" not in self.keep:
            return self.path(value, content)
        return value

    def path(self, text: str, content: bool = False) -> str:
        """`text` with this machine's paths made relative; outside a document's contents,
        with any other path of a person's or a temporary directory as `<path>`."""
        if "/" not in text:
            return text
        for root in self.roots:
            text = root.sub(lambda m: "" if m.group(1) == "/" else ".", text)
        if self.home:
            text = text.replace(self.home + "/", "~/")
        return text if content else _ABSOLUTE.sub("<path>", text)


def _run_roots(monitor: Monitor, run: str) -> list[Path]:
    """The directories a run's paths are made relative to: its own and its working directory."""
    roots = [monitor.runs_dir / run, (monitor.runs_dir / run).resolve()]
    try:
        cwd = json.loads((monitor.runs_dir / run / "run.json").read_text()).get("cwd")
    except (OSError, ValueError, AttributeError):
        cwd = None
    if isinstance(cwd, str) and cwd:
        roots.append(Path(cwd))
    return roots


def _write(path: Path, body: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text)
    return len(text.encode())


def _page(title: str, data: str) -> str:
    """The monitor's page, reading the export from `data` instead of a server."""
    html = (STATIC / "index.html").read_text()
    html = html.replace("<ca-monitor></ca-monitor>", f'<ca-monitor export="{data}"></ca-monitor>', 1)
    return re.sub(r"<title>.*?</title>", f"<title>{_escape(title)}</title>", html, count=1)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


@dataclass
class ExportReport:
    """What `export` wrote: the runs, and the bytes of `data/` per run."""

    out: Path
    runs: list[str]
    bytes_by_run: dict[str, int]
    total_bytes: int


def export(
    monitor: Monitor,
    out: str | Path,
    *,
    runs: int | None = 10,
    since: str | None = None,
    keep: Iterable[str] = (),
    exclude: Iterable[str] = (),
    period: Period | None = None,
    live: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ExportReport:
    """Write the monitor's views of the newest `runs` runs (None: every run; `since`, an
    ISO time: only runs active since then) to `out`: the page and `data/`, with the trends
    of `period` (default: the last 14 days in UTC) over every run. A run still running is
    left out (its views would stop half way: the run that writes the export, say), unless
    `live`. `data/` is written anew: a run no longer chosen leaves the export."""
    period = period or Period.parse()
    out = Path(out)
    summaries = monitor.runs()
    if not live:
        summaries = [s for s in summaries if not s.get("running")]
    if since:
        summaries = [s for s in summaries if (s.get("last_ts") or "") >= since]
    if runs is not None:
        summaries = summaries[: max(0, runs)]
    chosen = [s["run"] for s in summaries]
    keep, exclude = set(keep), set(exclude)
    base = Redactor([monitor.runs_dir, monitor.runs_dir.resolve()], keep=keep, exclude=exclude)
    data = out / "data"
    if data.exists():
        shutil.rmtree(data)
    sizes: dict[str, int] = {}
    for run in chosen:
        red = Redactor([*_run_roots(monitor, run), monitor.runs_dir, monitor.runs_dir.resolve()], keep=keep, exclude=exclude)
        d = data / "runs" / run
        n = 0
        for route in ROUTES:
            n += _write(d / route.file, red(_dump(route.model, route.read(monitor, run))))
        journal = monitor.journal(run)[0]
        outputs, plan_rows = monitor.outputs(run), monitor.plan_rows(run)
        keys = {k for k in [*(n.get("key") for n in plan_rows), *(e.get("key") for e in journal)] if isinstance(k, str) and k}
        for key in sorted(keys):
            rows = [e for e in journal if e.get("key") == key]
            detail = {
                "key": key,
                # In journal.json and definitions.json: `createExportClient` puts them back.
                "rows": [],
                "definition": None,
                # Never in an export: the launches running now (their commands, their pids) and the transcript.
                "launches": [],
                "stream": None,
                "io": monitor.task_io(run, key, outputs=outputs, plan_rows=plan_rows),
                "row_extras": row_extras(rows),
            }
            if monitor.task_detail_fn is not None:
                try:
                    detail.update(monitor.task_detail_fn(run, key, rows) or {})
                except Exception as exc:  # a domain's callback must not break the export
                    detail["task_detail_error"] = f"{type(exc).__name__}: {exc}"
            n += _write(d / "tasks" / f"{key}.json", red(_dump(api.TaskDetail, detail)))
        n += _panels(monitor, "run", run, d / "panels", red)
        sizes[run] = n
    total = sum(_write(data / route.file, base(_dump(route.model, route.read(monitor, period)))) for route in SITE_ROUTES)
    total += _panels(monitor, "trends", "", data / "trends" / "panels", base, period)
    redacted = sorted({r for r in REDACTED if r not in keep} | exclude)
    info = {
        "title": monitor.title,
        "panels": monitor.panel_info(),
        "api_version": api.API_VERSION,
        "hosts": False,
        "export": {"exported_at": now().isoformat(timespec="seconds"), "runs": chosen, "left_out": list(LEFT_OUT), "redacted": redacted},
    }
    total += _write(data / "info.json", _dump(api.Info, info))
    total += _write(data / "runs.json", base(_dump(list[api.RunSummary], [{**s, "running": False} for s in summaries])))
    for name in PAGE_FILES:
        if name != "index.html":
            shutil.copyfile(STATIC / name, out / name)
    (out / "index.html").write_text(_page(monitor.title, "data/"))
    return ExportReport(out=out, runs=chosen, bytes_by_run=sizes, total_bytes=total + sum(sizes.values()))


def _panels(monitor: Monitor, scope: str, run: str, where: Path, red: Redactor, period: Period | None = None) -> int:
    """Write each panel of `scope` under `where`, as its route answers it (`run`: the run
    `run`'s, `/api/runs/<run>/panels/<name>`; `trends`: over the runs of `period`,
    `/api/trends/panels/<name>`); the bytes written."""
    n = 0
    for name, panel in monitor.panels.items():
        if panel.scope != scope:
            continue
        try:
            body = api.panel_data(monitor.panel(name, run) if scope == "run" else monitor.trends_panel(name, period or Period.parse()))
        except Exception as exc:  # one bad panel (or a typed body that does not validate) must not stop the export
            body = {"error": f"{type(exc).__name__}: {exc}"}
        n += _write(where / f"{name}.json", red(json.loads(json.dumps(body, default=str))))
    return n


def _period(start: str, end: str, days: int, tz: str) -> Period:
    """The trends' period of the command line: `--from`/`--to`, else the last `days` days to `--to` (or today)."""
    if start:
        return Period.parse(start, end, tz)
    last = Period.parse("", end, tz).end
    return Period.parse((last - timedelta(days=max(1, days) - 1)).isoformat(), last.isoformat(), tz)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        prog="contraagent monitor export",
        description="Write the monitor's views of some runs as files a static server serves: no transcripts, no processes.",
    )
    ap.add_argument("--runs-dir", default="runs", help="directory holding runs/<run-id>/ (default: ./runs)")
    ap.add_argument("--out", required=True, help="the directory to write: index.html, app.js, ja.js and data/")
    ap.add_argument("--runs", type=int, default=10, help="how many runs, newest activity first (default: 10; 0: every run)")
    ap.add_argument("--since", default=None, metavar="ISO_TIME", help="only runs active since this time, e.g. 2026-10-01")
    ap.add_argument(
        "--panels",
        default=None,
        metavar="MODULE:ATTR",
        help="the pipeline's own views, as for `contraagent monitor`: path/to/views.py:PANELS or package.module:PANELS",
    )
    ap.add_argument(
        "--groups",
        default=None,
        metavar="MODULE:ATTR",
        help='the plan\'s columns and the trends\' groups: a list of {"id", "label", "kinds"}, as path/to/views.py:GROUPS',
    )
    ap.add_argument(
        "--task-detail",
        default=None,
        metavar="MODULE:ATTR",
        help="fn(run, key, rows) -> dict merged into each task's detail, as path/to/views.py:detail",
    )
    ap.add_argument("--include-live", action="store_true", help="write runs that are still running too (default: left out)")
    ap.add_argument("--title", default="contraagent")
    ap.add_argument("--days", type=int, default=14, help="the trends' period: the last N days, today included (default: 14)")
    ap.add_argument("--from", dest="start", default="", metavar="YYYY-MM-DD", help="the trends' first day, instead of --days")
    ap.add_argument("--to", dest="end", default="", metavar="YYYY-MM-DD", help="the trends' last day (default: today)")
    ap.add_argument("--tz", default="UTC", help="the time zone the trends' days are counted in (default: UTC)")
    ap.add_argument("--keep", action="append", default=[], choices=REDACTED, help="keep what is taken out by default: paths, host")
    ap.add_argument("--exclude", action="append", default=[], metavar="KEY", help="take out this key wherever it appears (e.g. params)")
    args = ap.parse_args(argv)
    from contraagent.monitor.server import load_attr

    extensions: dict[str, Any] = {}
    for name in ("panels", "groups", "task_detail"):
        spec = getattr(args, name)
        if not spec:
            continue
        try:
            extensions[name] = load_attr(spec)
        except Exception as exc:  # an import that fails is the user's to fix: say which
            flag = "--" + name.replace("_", "-")
            sys.stderr.write(f"contraagent monitor export: {flag} {spec}: {type(exc).__name__}: {exc}\n")
            return 2
    try:
        period = _period(args.start, args.end, args.days, args.tz)
    except ValueError as exc:
        sys.stderr.write(f"contraagent monitor export: {exc}\n")
        return 2
    monitor = Monitor(args.runs_dir, title=args.title, **extensions)
    report = export(
        monitor,
        args.out,
        runs=args.runs or None,
        since=args.since,
        keep=args.keep,
        exclude=args.exclude,
        period=period,
        live=args.include_live,
    )
    for run in report.runs:
        sys.stdout.write(f"  {run}: {report.bytes_by_run[run] / 1000:.0f} kB\n")
    sys.stdout.write(f"wrote {len(report.runs)} runs to {report.out} ({report.total_bytes / 1000:.0f} kB of data)\n")
    return 0
