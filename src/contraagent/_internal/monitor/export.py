"""`contraagent monitor export`: the monitor's views of some runs, written as files.

An export is the page (`index.html`, `app.js`, `ja.js`) and `data/`, the JSON each
endpoint of the API would answer, one file per endpoint:

    data/info.json                       /api/info, with `export` (`api.ExportInfo`)
    data/runs.json                       /api/runs: the runs it holds
    data/runs/<run>/<view>.json          /api/runs/<run>/<view>, for each view of `VIEWS` an
                                         export holds: journal (every row), plan, outputs,
                                         definitions, cursor
    data/runs/<run>/tasks/<file>.json    /api/runs/<run>/task/<key>, without its `rows` and
                                         `definition` (journal.json and definitions.json hold
                                         them; the export client puts them back); `<file>` is
                                         `file_name(key)`, the name the run's own files take
    data/runs/<run>/panels/<name>.json   /api/runs/<run>/panels/<name>
    data/trends/panels/<name>.json       /api/trends/panels/<name>: a panel of `scope="trends"`
    data/<file>                          each file of no run in `SITE_FILES` (`trends.json`)

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
A new view of a run is one entry in `VIEWS` (`views.py`), a new endpoint of no run one entry
in `SITE_FILES`; each is one method in `createExportClient`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contraagent._internal.commandline import CommandError, add_extensions, add_runs_dir, load_extensions
from contraagent._internal.monitor import api
from contraagent._internal.monitor.core import Monitor, row_extras
from contraagent._internal.monitor.trends import Period
from contraagent._internal.monitor.views import VIEWS, serialize
from contraagent._internal.runs.layout import file_name

#: The bundled web UI: the page and its scripts (`Monitor.static_dir` replaces it).
STATIC = Path(__file__).parent / "static"

#: What the page needs beside `data/`.
PAGE_FILES = ("index.html", "app.js", "ja.js")

#: The page's icons, copied when the web UI has them.
ICON_FILES = ("favicon.svg", "favicon-32.png", "apple-touch-icon.png")

#: What an export takes out by default; `keep` puts them back.
REDACTED = ("paths", "host")

#: The views an export never holds.
LEFT_OUT = ("transcripts", "processes")

#: Absolute paths of a person's or a temporary directory left in a string after the known
#: roots were made relative. A system path (`/etc/hosts`) says nothing about the machine.
_ABSOLUTE = re.compile(
    r"(?<![\w.:/~-])/(?:home|Users|root|tmp|private|var/folders)/[^\s\"'`<>|,;)\]]*"
    r"|(?<![\w.:\\/~-])[A-Za-z]:[\\/](?:Users|Windows[\\/]Temp)[\\/][^\s\"'`<>|,;)\]]*"  # Windows: C:\Users\..., C:/Users/...
)

#: What parts a path on this OS: `/`, and on Windows `\` as well.
_SEP = r"[\\/]" if os.sep == "\\" else "/"

#: Keys whose value is a document's contents (a file shown as it is): this machine's paths in
#: it are made relative, and nothing else in it is changed.
CONTENT_KEYS = frozenset({"content", "text"})


@dataclass(frozen=True)
class SiteExportFile:
    """One endpoint of no run as a file under `data/`: `read(monitor, period)` its body, over
    the export's period, `model` its contract."""

    file: str
    read: Callable[[Monitor, Period], Any]
    model: Any


#: The endpoints of no run, beside `info.json` and `runs.json` (which the export writes
#: itself: they say what it holds); panels of `scope="trends"` are written under
#: `trends/panels/` (`_panels`).
SITE_FILES: tuple[SiteExportFile, ...] = (SiteExportFile("trends.json", lambda m, period: m.trends(period), api.Trends),)


def _dump(model: Any, value: Any) -> Any:
    """`value` as the endpoint answers it (`serialize`), as JSON data."""
    return json.loads(serialize(model, value))


class Redactor:
    """Takes out of a view what the export does not show (`REDACTED`, `exclude`)."""

    def __init__(self, roots: Iterable[Path], *, keep: Iterable[str] = (), exclude: Iterable[str] = ()) -> None:
        self.keep = set(keep)
        self.exclude = set(exclude)
        home = str(Path.home())
        # The longest root first, so a run directory wins over the runs directory around it.
        roots_ = sorted({str(r).rstrip("/" + os.sep) for r in roots if str(r) not in ("", "/", os.sep)}, key=len, reverse=True)
        # A root only where a path name ends: `/runs/x` is not the start of `/runs/xy`.
        self.roots = [re.compile(_pattern(r) + rf"({_SEP}|(?![\w.-]))") for r in roots_]
        self.home = re.compile(_pattern(home) + rf"({_SEP})") if home not in ("", "/", os.sep) else None

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
        if "/" not in text and "\\" not in text:
            return text
        for root in self.roots:
            text = root.sub(lambda m: "" if m.group(1) else ".", text)
        if self.home:
            text = self.home.sub(lambda m: "~" + m.group(1), text)
        return text if content else _ABSOLUTE.sub("<path>", text)


def _pattern(path: str) -> str:
    """A regular expression for `path` written with any of this OS's separators: a message
    names a path with `/` on every OS, a record may hold it as the OS writes it."""
    return _SEP.join(re.escape(part) for part in re.split(_SEP, path))


def _run_roots(monitor: Monitor, run: str) -> list[Path]:
    """The directories a run's paths are made relative to: its own and its working directory."""
    roots = [monitor.runs_dir / run, (monitor.runs_dir / run).resolve()]
    cwd = (monitor.source.info(run) or {}).get("cwd")
    if isinstance(cwd, str) and cwd:
        roots.append(Path(cwd))
    return roots


def _write(path: Path, body: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode())


def _page(static: Path, title: str, data: str) -> str:
    """The monitor's page, reading the export from `data` instead of a server."""
    html = (static / "index.html").read_text(encoding="utf-8")
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
        for view in VIEWS.values():
            if view.export:
                n += _write(d / f"{view.name}.json", red(_dump(view.model, view.read(monitor, run))))
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
            n += _write(d / "tasks" / f"{file_name(key)}.json", red(_dump(api.TaskDetail, detail)))
        n += _panels(monitor, "run", run, d / "panels", red)
        sizes[run] = n
    total = sum(_write(data / f.file, base(_dump(f.model, f.read(monitor, period)))) for f in SITE_FILES)
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
    static = monitor.static_dir or STATIC
    for name in PAGE_FILES:
        if name != "index.html":
            shutil.copyfile(static / name, out / name)
    for name in ICON_FILES:
        if (static / name).is_file():
            shutil.copyfile(static / name, out / name)
    (out / "index.html").write_text(_page(static, monitor.title, "data/"), encoding="utf-8", newline="\n")
    return ExportReport(out=out, runs=chosen, bytes_by_run=sizes, total_bytes=total + sum(sizes.values()))


def _panels(monitor: Monitor, scope: str, run: str, where: Path, red: Redactor, period: Period | None = None) -> int:
    """Write each panel of `scope` under `where`, as its endpoint answers it (`run`: the run
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


# --- the command -----------------------------------------------------------------------

HELP = "write the monitor's views of some runs as files a static server serves"


def add_arguments(ap: argparse.ArgumentParser) -> None:
    """`contraagent monitor export`."""
    ap.description = "Write the monitor's views of some runs as files a static server serves: no transcripts, no processes."
    add_runs_dir(ap)
    ap.add_argument("--out", required=True, help="the directory to write: index.html, app.js, ja.js and data/")
    ap.add_argument("--runs", type=int, default=10, help="how many runs, newest activity first (default: 10; 0: every run)")
    ap.add_argument("--since", default=None, metavar="ISO_TIME", help="only runs active since this time, e.g. 2026-10-01")
    add_extensions(ap)
    ap.add_argument("--include-live", action="store_true", help="write runs that are still running too (default: left out)")
    ap.add_argument("--title", default="contraagent")
    ap.add_argument("--days", type=int, default=14, help="the trends' period: the last N days, today included (default: 14)")
    ap.add_argument("--from", dest="start", default="", metavar="YYYY-MM-DD", help="the trends' first day, instead of --days")
    ap.add_argument("--to", dest="end", default="", metavar="YYYY-MM-DD", help="the trends' last day (default: today)")
    ap.add_argument("--tz", default="UTC", help="the time zone the trends' days are counted in (default: UTC)")
    ap.add_argument("--keep", action="append", default=[], choices=REDACTED, help="keep what is taken out by default: paths, host")
    ap.add_argument("--exclude", action="append", default=[], metavar="KEY", help="take out this key wherever it appears (e.g. params)")


def run(args: argparse.Namespace) -> int:
    """`contraagent monitor export`: needs no server, so not the `monitor` extra."""
    extensions = load_extensions(args)
    try:
        period = _period(args.start, args.end, args.days, args.tz)
    except ValueError as exc:
        raise CommandError(str(exc)) from None
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
    for name in report.runs:
        sys.stdout.write(f"  {name}: {report.bytes_by_run[name] / 1000:.0f} kB\n")
    sys.stdout.write(f"wrote {len(report.runs)} runs to {report.out} ({report.total_bytes / 1000:.0f} kB of data)\n")
    return 0
