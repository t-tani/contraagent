"""Trends: what the runs of a period add up to, day by day.

A run's own views (`Monitor.plan`, `Monitor.runs`) say what one run did. Trends
say what the runs of a **period** (days `from`..`to`, inclusive, in a time zone)
did together: the cost of each day by kind, each kind's tasks, success and time,
each model's tokens and cost, the causes of failures, the tool calls refused,
each account's utilization, the rests and deferrals, and when runs start.

It works in two steps, so that any period, time zone or grouping costs little:

* `digest(source, run)`: the few fields of a run's logs the trends need (one per
  journal row, utilization reading, refused tool call, rest and deferral). A
  digest depends only on the run's files, so it is kept: in memory, keyed by the
  run's `signature`, and, for a finished run in a runs directory, in the run's
  `trends.json` (`rundir.TRENDS`), so a restarted monitor reads it back.
* `aggregate(digests, period, groups)`: the trends of a period over digests,
  with `bodies(view)`, the same numbers as panel bodies (`{"type": "blocks", ...}`)
  for a page that draws them without words of its own.

A journal row counts on the day of its `ts` (when the attempt ended) in the
period's time zone; a reading on the day it was received; a run start on the
day and hour of `run.json`'s `started_at` (the latest start of a resumed run).
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from contraagent import rundir

#: Bumped when a digest's shape changes: a kept digest of another version is made again.
DIGEST_VERSION = 1

#: The longest period, in days.
MAX_DAYS = 366

#: The period when none is given: the last 14 days, today included.
DEFAULT_DAYS = 14

#: The logs a digest reads; their sizes, with the run's start and finish, are its signature.
DIGEST_LOGS = (rundir.JOURNAL, rundir.LAUNCHES, rundir.RESTS, rundir.DEFERRED)

_TOKENS = ("input", "output", "cache_read", "cache_creation", "calls")
_WINDOWS = ("five_hour", "seven_day")
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class PeriodError(ValueError):
    """A period that cannot be read: a bad date, an unknown time zone, `from` after `to`, too long."""


@dataclass(frozen=True)
class Period:
    """Days `start`..`end`, both included, in the time zone `tz` (an IANA name)."""

    start: date
    end: date
    tz: str = "UTC"

    @classmethod
    def parse(cls, start: str = "", end: str = "", tz: str = "", *, today: date | None = None) -> Period:
        """A period from ISO dates (`YYYY-MM-DD`); `end` defaults to today in `tz`, `start`
        to `DEFAULT_DAYS` days before it (today included); `tz` defaults to UTC."""
        tz = tz or "UTC"
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise PeriodError(f"unknown time zone {tz!r}") from None
        try:
            last = date.fromisoformat(end) if end else (today or datetime.now(zone).date())
            first = date.fromisoformat(start) if start else last - timedelta(days=DEFAULT_DAYS - 1)
        except ValueError as exc:
            raise PeriodError(f"not a date (YYYY-MM-DD): {exc}") from None
        if first > last:
            raise PeriodError(f"from {first} is after to {last}")
        if (last - first).days + 1 > MAX_DAYS:
            raise PeriodError(f"{(last - first).days + 1} days: a period is at most {MAX_DAYS}")
        return cls(first, last, tz)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def days(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    @property
    def opens(self) -> datetime:
        """The period's first instant, as an aware time."""
        return datetime.combine(self.start, datetime.min.time(), self.zone)

    @property
    def closes(self) -> datetime:
        """The instant after the period."""
        return datetime.combine(self.end + timedelta(days=1), datetime.min.time(), self.zone)

    def day_of(self, ts: object) -> date | None:
        """The day of an ISO time in this period's time zone, when it is inside the period."""
        t = when(ts)
        if t is None or not (self.opens <= t < self.closes):
            return None
        return t.astimezone(self.zone).date()

    def as_dict(self) -> dict:
        return {"from": self.start.isoformat(), "to": self.end.isoformat(), "tz": self.tz, "days": [d.isoformat() for d in self.days]}


def when(ts: object) -> datetime | None:
    """An ISO 8601 time as an aware datetime (a naive one is UTC); None when it is not one."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _num(v: object) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _parse(lines: Iterable[str]) -> list[dict]:
    out = []
    for line in lines:
        try:
            v = json.loads(line)
        except ValueError:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


# --- a run's digest --------------------------------------------------------------------


def signature(source, run: str) -> dict:
    """What a run's digest depends on: its logs' sizes, and when it started and finished."""
    info = source.info(run) or {}
    return {
        **{log: source.size(run, log) for log in DIGEST_LOGS},
        "started_at": info.get("started_at", ""),
        "finished_at": info.get("finished_at", ""),
    }


def _usage(v: object) -> dict | None:
    if not isinstance(v, dict):
        return None
    return {k: int(n) for k in _TOKENS if (n := _num(v.get(k))) is not None}


def digest(source, run: str) -> dict:
    """The fields of run `run`'s logs the trends need (see the module docstring)."""
    info = source.info(run) or {}
    rows = []
    kinds: dict[str, str] = {}
    quota = []
    for e in _parse(source.lines(run, rundir.JOURNAL)[0]):
        kinds[str(e.get("key", ""))] = str(e.get("kind", "?"))
        rows.append(
            {
                "ts": e.get("ts", ""),
                "key": e.get("key", ""),
                "kind": e.get("kind", "?"),
                "executor": e.get("executor") or "agent",
                "agent": e.get("agent", ""),
                "ok": bool(e.get("ok")),
                "stop": str(e.get("stop", "")),
                "wall_s": _num(e.get("wall_s")) or 0.0,
                "cost_usd": _num(e.get("cost_usd")),
                "usage": _usage(e.get("usage")),
                "hops": [
                    {
                        "agent": h.get("agent", ""),
                        "model": h.get("model", ""),
                        "cost_usd": _num(h.get("cost_usd")),
                        "wall_s": _num(h.get("wall_s")) or 0.0,
                        "usage": _usage(h.get("usage")),
                    }
                    for h in e.get("hops") or ()
                    if isinstance(h, dict)
                ],
            }
        )
        for q in e.get("quota") or ():
            if isinstance(q, dict) and q.get("observed_at"):
                quota.append(
                    {
                        "observed_at": q["observed_at"],
                        "credential": q.get("credential", ""),
                        **{f"{w}_pct": _num(q.get(f"{w}_pct")) for w in _WINDOWS},
                    }
                )
    denied = []
    for launch in _parse(source.lines(run, rundir.LAUNCHES)[0]):
        for d in launch.get("denied") or ():
            if isinstance(d, dict) and d.get("tool"):
                key = str(launch.get("label", ""))
                denied.append({"ts": launch.get("ts", ""), "key": key, "kind": kinds.get(key, ""), "tool": str(d["tool"])})
    rests = [
        {k: r.get(k) for k in ("ts", "event", "credential", "window", "pct", "cap", "rule", "until")}
        for r in _parse(source.lines(run, rundir.RESTS)[0])
    ]
    deferred = []
    for d in _parse(source.lines(run, rundir.DEFERRED)[0]):
        cause = d["cause"] if isinstance(d.get("cause"), dict) else {}
        deferred.append(
            {
                "ts": d.get("ts", ""),
                "key": d.get("key", ""),
                "kind": d.get("kind", ""),
                "cause": str(cause.get("cause") or ""),
                "reason": str(d.get("reason") or "")[:240],
            }
        )
    return {
        "version": DIGEST_VERSION,
        "run": run,
        "run_group": info.get("run_group") or run,
        "host_id": info.get("host_id", ""),
        "started_at": info.get("started_at", ""),
        "finished_at": info.get("finished_at", ""),
        "stub": info.get("stub") is True,
        "rows": rows,
        "quota": quota,
        "denied": denied,
        "rests": rests,
        "deferred": deferred,
    }


def in_period(info: Mapping, period: Period) -> bool:
    """Whether a run may have done something in `period`, by its `run.json` alone: started
    before it closes, and not finished before it opens. A run that does not say is kept."""
    started, finished = when(info.get("started_at")), when(info.get("finished_at"))
    if started is not None and started >= period.closes:
        return False
    return not (finished is not None and finished < period.opens)


# --- the trends of a period ------------------------------------------------------------


def _add_usage(into: dict, usage: dict | None) -> None:
    for k in _TOKENS:
        into[k] = into.get(k, 0) + int((usage or {}).get(k, 0))


def _round(v: float | None, n: int = 6) -> float | None:
    return round(v, n) if v is not None else None


def aggregate(digests: Iterable[dict], period: Period, groups: Mapping[str, str] | None = None) -> dict:
    """The trends of `period` over run `digests` (`digest`); `groups` maps a kind to the
    group it is counted in (the monitor's `groups`), each other kind being its own."""
    from contraagent.monitor.core import model_usage  # the per-model sums one run's plan shows

    group_of = dict(groups or {})
    days = [d.isoformat() for d in period.days]
    daily = {d: {"day": d, "cost_usd": {}, "attempts": 0, "ok": 0} for d in days}
    kinds: dict[str, dict] = {}
    walls: dict[str, list[float]] = {}
    tasks: dict[str, dict[tuple[str, str], bool]] = {}
    stops: dict[str, dict] = {}
    denied: dict[str, dict] = {}
    peaks: dict[tuple[str, str, str], float] = {}
    readings: dict[tuple[str, str], list[dict]] = {}
    rests, deferred, runs, rows_in = [], [], [], []
    starts = [[0] * 24 for _ in _WEEKDAYS]
    totals = {"runs": 0, "attempts": 0, "ok": 0, "cost_usd": None, "wall_s": 0.0, "tokens": dict.fromkeys(_TOKENS, 0)}
    for dg in digests:
        run = dg["run"]
        mine = [r for r in dg["rows"] if period.day_of(r["ts"]) is not None]
        started = period.day_of(dg.get("started_at"))
        if not mine and started is None:
            continue
        if started is not None:
            t = when(dg["started_at"]).astimezone(period.zone)  # type: ignore[union-attr]
            starts[t.weekday()][t.hour] += 1
        cost: float | None = None
        for r in mine:
            day = period.day_of(r["ts"]).isoformat()  # type: ignore[union-attr]
            kind = r["kind"]
            group = group_of.get(kind, kind)
            d = daily[day]
            d["attempts"] += 1
            d["ok"] += r["ok"]
            if r["cost_usd"] is not None:
                d["cost_usd"][group] = round(d["cost_usd"].get(group, 0.0) + r["cost_usd"], 6)
                cost = (cost or 0.0) + r["cost_usd"]
            k = kinds.setdefault(
                kind,
                {
                    "kind": kind,
                    "group": group,
                    "executor": r["executor"],
                    "tasks": 0,
                    "tasks_ok": 0,
                    "attempts": 0,
                    "ok": 0,
                    "wall_s": 0.0,
                    "wall_s_median": 0.0,
                    "cost_usd": None,
                    "tokens": dict.fromkeys(_TOKENS, 0),
                },
            )
            k["attempts"] += 1
            k["ok"] += r["ok"]
            k["wall_s"] += r["wall_s"]
            walls.setdefault(kind, []).append(r["wall_s"])
            if r["cost_usd"] is not None:
                k["cost_usd"] = (k["cost_usd"] or 0.0) + r["cost_usd"]
            _add_usage(k["tokens"], r["usage"])
            _add_usage(totals["tokens"], r["usage"])
            # A task is one key of one run; its last attempt in the period says how it ended.
            tasks.setdefault(kind, {})[(run, r["key"])] = r["ok"]
            s = stops.setdefault(r["stop"], {"stop": r["stop"], "attempts": 0, "kinds": {}})
            s["attempts"] += 1
            s["kinds"][kind] = s["kinds"].get(kind, 0) + 1
            totals["attempts"] += 1
            totals["ok"] += r["ok"]
            totals["wall_s"] += r["wall_s"]
            rows_in.append(r)
        if cost is not None:
            totals["cost_usd"] = (totals["cost_usd"] or 0.0) + cost
        for q in dg["quota"]:
            day = period.day_of(q["observed_at"])
            if day is None:
                continue
            for w in _WINDOWS:
                pct = q.get(f"{w}_pct")
                if pct is None:
                    continue
                readings.setdefault((q["credential"], w), []).append({"at": q["observed_at"], "pct": pct})
                key = (q["credential"], w, day.isoformat())
                peaks[key] = max(peaks.get(key, 0.0), pct)
        for x in dg["denied"]:
            if period.day_of(x["ts"]) is None:
                continue
            t = denied.setdefault(x["tool"], {"tool": x["tool"], "count": 0, "kinds": {}})
            t["count"] += 1
            if x["kind"]:
                t["kinds"][x["kind"]] = t["kinds"].get(x["kind"], 0) + 1
        rests += [{**x, "run": run} for x in dg["rests"] if period.day_of(x.get("ts")) is not None]
        deferred += [{**x, "run": run} for x in dg["deferred"] if period.day_of(x.get("ts")) is not None]
        totals["runs"] += 1
        runs.append(
            {
                "run": run,
                "run_group": dg["run_group"],
                "host_id": dg["host_id"],
                "started_at": dg["started_at"],
                "finished_at": dg["finished_at"],
                "last_ts": max((r["ts"] for r in mine), default=""),
                "attempts": len(mine),
                "ok": sum(r["ok"] for r in mine),
                "cost_usd": _round(cost),
                "wall_s": round(sum(r["wall_s"] for r in mine), 1),
                "stub": dg["stub"],
            }
        )
    for kind, k in kinds.items():
        ended = tasks.get(kind, {})
        k["tasks"], k["tasks_ok"] = len(ended), sum(ended.values())
        k["wall_s"] = round(k["wall_s"], 1)
        k["wall_s_median"] = round(statistics.median(walls[kind]), 1) if walls.get(kind) else 0.0
        k["cost_usd"] = _round(k["cost_usd"])
    totals["cost_usd"] = _round(totals["cost_usd"])
    totals["wall_s"] = round(totals["wall_s"], 1)
    runs.sort(key=lambda r: r["started_at"] or r["last_ts"], reverse=True)
    rests.sort(key=lambda r: r.get("ts") or "")
    deferred.sort(key=lambda r: r.get("ts") or "")
    causes: dict[str, int] = {}
    for d in deferred:
        causes[d["cause"]] = causes.get(d["cause"], 0) + 1
    quota = []
    for (credential, window), points in sorted(readings.items()):
        points.sort(key=lambda p: p["at"])
        quota.append(
            {
                "credential": credential,
                "window": window,
                "daily_peak": [peaks.get((credential, window, d)) for d in days],
                "points": points,
            }
        )
    return {
        "period": period.as_dict(),
        "totals": totals,
        "daily": [{**daily[d], "cost_usd": dict(sorted(daily[d]["cost_usd"].items()))} for d in days],
        "kinds": sorted(kinds.values(), key=lambda k: (-(k["cost_usd"] or 0.0), k["kind"])),
        "models": model_usage(rows_in),
        "stops": sorted(stops.values(), key=lambda s: (-s["attempts"], s["stop"])),
        "denials": sorted(denied.values(), key=lambda t: (-t["count"], t["tool"])),
        "quota": quota,
        "rests": rests,
        "deferred": deferred,
        "deferred_causes": dict(sorted(causes.items(), key=lambda c: -c[1])),
        "runs": runs,
        "starts": {"weekdays": list(_WEEKDAYS), "hours": list(range(24)), "counts": starts},
    }


# --- the same numbers as panel bodies --------------------------------------------------


def _usd(v: float | None) -> str:
    return "—" if v is None else f"${v:,.2f}" if v >= 1 else f"${v:.4f}".rstrip("0").rstrip(".") if v else "$0"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def _tokens(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e3 else str(n)


def _blocks(*items: dict | None) -> dict:
    return {"type": "blocks", "blocks": [x for x in items if x is not None]}


def bodies(view: dict) -> dict[str, dict]:
    """The trends as panel bodies (`{"type": "blocks", "blocks": [...]}`), one per section, in
    English: for a page that draws them without words of its own (a static export, a
    pipeline's panel that reuses one). The monitor's own view draws `view` in its words."""
    t, days = view["totals"], view["period"]["days"]
    groups = sorted({g for d in view["daily"] for g in d["cost_usd"]})
    attempts = t["attempts"]
    per_day = t["cost_usd"] / len(days) if t["cost_usd"] is not None else None
    overview = {
        "type": "tiles",
        "tiles": [
            {"id": "cost", "label": "Cost", "value": _usd(t["cost_usd"]), "sub": [[f"{_usd(per_day)} a day"]]},
            {"id": "attempts", "label": "Attempts", "value": str(attempts), "sub": [[f"{t['runs']} runs"]]},
            {"id": "passed", "label": "Passed", "value": _pct(t["ok"] / attempts if attempts else None)},
            {
                "id": "tokens",
                "label": "Tokens",
                "value": _tokens(sum(t["tokens"][k] for k in ("input", "output", "cache_read", "cache_creation"))),
            },
        ],
    }
    cost = {
        "type": "columns",
        "title": "Cost per day",
        "x": [d[5:] for d in days],
        "series": [{"name": g, "values": [d["cost_usd"].get(g, 0.0) for d in view["daily"]]} for g in groups],
        "unit": "usd",
        "stacked": True,
    }
    kinds = {
        "type": "table",
        "columns": [
            {"id": "kind", "label": "Kind"},
            {"id": "tasks", "label": "Tasks", "align": "end"},
            {"id": "passed", "label": "Passed", "align": "end", "format": "pct"},
            {"id": "attempts", "label": "Attempts", "align": "end"},
            {"id": "wall", "label": "Median time", "align": "end", "format": "duration"},
            {"id": "tokens", "label": "Tokens", "align": "end", "format": "tokens"},
            {"id": "cost", "label": "Cost", "align": "end", "format": "usd", "bar": True},
        ],
        "rows": [
            {
                "kind": k["kind"],
                "tasks": k["tasks"],
                "passed": k["tasks_ok"] / k["tasks"] if k["tasks"] else None,
                "attempts": k["attempts"],
                "wall": k["wall_s_median"],
                "tokens": sum(k["tokens"][x] for x in ("input", "output", "cache_read", "cache_creation")),
                "cost": k["cost_usd"],
                **({"_tone": "failed"} if k["tasks"] and k["tasks_ok"] < k["tasks"] else {}),
            }
            for k in view["kinds"]
        ],
    }
    models = {
        "type": "table",
        "columns": [
            {"id": "model", "label": "Model"},
            {"id": "agent", "label": "Coding agent"},
            {"id": "sessions", "label": "Agent sessions", "align": "end"},
            *(
                {"id": k, "label": label, "align": "end", "format": "tokens"}
                for k, label in (("input", "Input"), ("output", "Output"), ("cache_read", "Cache read"), ("cache_creation", "Cache write"))
            ),
            {"id": "cost", "label": "Cost", "align": "end", "format": "usd", "bar": True},
        ],
        "rows": [
            {
                "model": m["model"],
                "agent": m["agent"],
                "sessions": m["sessions"],
                "input": m["input"],
                "output": m["output"],
                "cache_read": m["cache_read"],
                "cache_creation": m["cache_creation"],
                "cost": m["cost_usd"],
            }
            for m in view["models"]
        ],
    }
    failures = {
        "type": "table",
        "columns": [
            {"id": "stop", "label": "Outcome"},
            {"id": "attempts", "label": "Attempts", "align": "end", "bar": True},
            {"id": "kinds", "label": "Kinds"},
        ],
        "rows": [
            {"stop": s["stop"], "attempts": s["attempts"], "kinds": ", ".join(sorted(s["kinds"])), "_tone": "failed"}
            for s in view["stops"]
            if s["stop"] not in ("completed", "skipped")
        ],
    }
    denials = {
        "type": "table",
        "columns": [
            {"id": "tool", "label": "Tool"},
            {"id": "count", "label": "Refused", "align": "end", "bar": True},
            {"id": "kinds", "label": "Kinds"},
        ],
        "rows": [{"tool": d["tool"], "count": d["count"], "kinds": ", ".join(sorted(d["kinds"]))} for d in view["denials"]],
    }
    usage = {
        "type": "lines",
        "title": "Peak utilization per day",
        "x": [d[5:] for d in days],
        "series": [
            {
                "name": f"{q['credential'] or 'default'} {'5-hour' if q['window'] == 'five_hour' else 'weekly'}",
                "values": [p / 100 if p is not None else None for p in q["daily_peak"]],
            }
            for q in view["quota"]
        ],
        "unit": "pct",
    }
    starts = {
        "type": "heatmap",
        "title": "Run starts by weekday and hour",
        "x": [f"{h:02d}" for h in view["starts"]["hours"]],
        "y": view["starts"]["weekdays"],
        "values": view["starts"]["counts"],
    }
    deferred = {
        "type": "hbars",
        "title": "Deferred tasks by cause",
        "bars": [{"label": c or "unknown", "value": n} for c, n in view["deferred_causes"].items()],
    }
    runs = {
        "type": "table",
        "columns": [
            {"id": "run", "label": "Run"},
            {"id": "started", "label": "Started", "format": "datetime"},
            {"id": "attempts", "label": "Attempts", "align": "end"},
            {"id": "passed", "label": "Passed", "align": "end", "format": "pct"},
            {"id": "cost", "label": "Cost", "align": "end", "format": "usd"},
            {"id": "wall", "label": "Time", "align": "end", "format": "duration"},
        ],
        "rows": [
            {
                "run": r["run"],
                "started": r["started_at"],
                "attempts": r["attempts"],
                "passed": r["ok"] / r["attempts"] if r["attempts"] else None,
                "cost": r["cost_usd"],
                "wall": r["wall_s"],
            }
            for r in view["runs"]
        ],
    }
    return {
        "overview": _blocks(overview, cost),
        "kinds": _blocks(kinds),
        "models": _blocks(models),
        "failures": _blocks(failures, deferred if view["deferred_causes"] else None),
        "denials": _blocks(denials),
        "quota": _blocks(usage),
        "starts": _blocks(starts),
        "runs": _blocks(runs),
    }
