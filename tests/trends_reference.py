"""The trends as they were first computed, one journal row at a time: the reference the
bucketed digests of `contraagent.monitor.trends` must agree with (`test_trends.py`).
Only the utilization changed shape: each hour's highest reading instead of every reading.

Trends: what the runs of a period add up to, day by day.

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
  `trends.json` (`layout.TRENDS`), so a restarted monitor reads it back.
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

from contraagent.runs import layout

#: Bumped when a digest's shape changes: a kept digest of another version is made again.
DIGEST_VERSION = 1

#: The longest period, in days.
MAX_DAYS = 366

#: The period when none is given: the last 14 days, today included.
DEFAULT_DAYS = 14

#: The logs a digest reads; their sizes, with the run's start and finish, are its signature.
DIGEST_LOGS = (layout.JOURNAL, layout.LAUNCHES, layout.RESTS, layout.DEFERRED)

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
    for e in _parse(source.lines(run, layout.JOURNAL)[0]):
        kinds[str(e.get("key", ""))] = str(e.get("kind", "?"))
        rows.append(
            {
                "ts": e.get("ts", ""),
                "key": e.get("key", ""),
                "kind": e.get("kind", "?"),
                "executor": e.get("executor") or "agent",
                "agent": e.get("agent", ""),
                "ok": bool(e.get("ok")) and e.get("stop") != "partial",
                "partial": e.get("stop") == "partial",
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
                pcts = {w: _num(q.get(f"{w}_pct")) for w in _WINDOWS}
                for w, v in (q.get("windows") or {}).items():
                    if w not in pcts or pcts[w] is None:
                        pcts[w] = _num(v.get("pct")) if isinstance(v, dict) else None
                quota.append(
                    {
                        "observed_at": q["observed_at"],
                        "credential": q.get("credential", ""),
                        "account": q.get("account") or "",
                        "pcts": {w: p for w, p in pcts.items() if p is not None},
                    }
                )
    denied = []
    for launch in _parse(source.lines(run, layout.LAUNCHES)[0]):
        for d in launch.get("denied") or ():
            if isinstance(d, dict) and d.get("tool"):
                key = str(launch.get("label", ""))
                denied.append({"ts": launch.get("ts", ""), "key": key, "kind": kinds.get(key, ""), "tool": str(d["tool"])})
    rests = [
        {k: r.get(k) for k in ("ts", "event", "credential", "window", "pct", "cap", "rule", "until", "account", "reading") if k in r}
        for r in _parse(source.lines(run, layout.RESTS)[0])
    ]
    deferred = []
    for d in _parse(source.lines(run, layout.DEFERRED)[0]):
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
    from contraagent.monitor.aggregate import model_usage

    group_of = dict(groups or {})
    days = [d.isoformat() for d in period.days]
    daily = {d: {"day": d, "cost_usd": {}, "attempts": 0, "ok": 0, "partial": 0} for d in days}
    kinds: dict[str, dict] = {}
    walls: dict[str, list[float]] = {}
    tasks: dict[str, dict[tuple[str, str], int]] = {}
    stops: dict[str, dict] = {}
    denied: dict[str, dict] = {}
    peaks: dict[tuple[str, str, str], float] = {}
    readings: dict[tuple[str, str], dict[int, float]] = {}
    rests, deferred, runs, rows_in = [], [], [], []
    starts = [[0] * 24 for _ in _WEEKDAYS]
    totals = {"runs": 0, "attempts": 0, "ok": 0, "partial": 0, "cost_usd": None, "wall_s": 0.0, "tokens": dict.fromkeys(_TOKENS, 0)}
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
            d["partial"] += r["partial"]
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
                    "tasks_partial": 0,
                    "attempts": 0,
                    "ok": 0,
                    "partial": 0,
                    "wall_s": 0.0,
                    "wall_s_median": 0.0,
                    "cost_usd": None,
                    "tokens": dict.fromkeys(_TOKENS, 0),
                },
            )
            k["attempts"] += 1
            k["ok"] += r["ok"]
            k["partial"] += r["partial"]
            k["wall_s"] += r["wall_s"]
            walls.setdefault(kind, []).append(r["wall_s"])
            if r["cost_usd"] is not None:
                k["cost_usd"] = (k["cost_usd"] or 0.0) + r["cost_usd"]
            _add_usage(k["tokens"], r["usage"])
            _add_usage(totals["tokens"], r["usage"])
            # A task is one key of one run; its last attempt in the period says how it ended.
            tasks.setdefault(kind, {})[(run, r["key"])] = 2 if r["partial"] else int(r["ok"])
            s = stops.setdefault(r["stop"], {"stop": r["stop"], "attempts": 0, "kinds": {}})
            s["attempts"] += 1
            s["kinds"][kind] = s["kinds"].get(kind, 0) + 1
            totals["attempts"] += 1
            totals["ok"] += r["ok"]
            totals["partial"] += r["partial"]
            totals["wall_s"] += r["wall_s"]
            rows_in.append(r)
        if cost is not None:
            totals["cost_usd"] = (totals["cost_usd"] or 0.0) + cost
        for q in dg["quota"]:
            day = period.day_of(q["observed_at"])
            if day is None:
                continue
            for w, pct in q["pcts"].items():
                hour = int((when(q["observed_at"]) - period.opens).total_seconds() // 3600)  # type: ignore[operator]
                hourly = readings.setdefault((q["credential"], q["account"], w), {})
                hourly[hour] = max(hourly.get(hour, 0.0), pct)
                key = (q["credential"], q["account"], w, day.isoformat())
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
                "partial": sum(r["partial"] for r in mine),
                "cost_usd": _round(cost),
                "wall_s": round(sum(r["wall_s"] for r in mine), 1),
                "stub": dg["stub"],
            }
        )
    for kind, k in kinds.items():
        ended = tasks.get(kind, {})
        k["tasks"], k["tasks_ok"] = len(ended), sum(v == 1 for v in ended.values())
        k["tasks_partial"] = sum(v == 2 for v in ended.values())
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
    # Real hours: two times of one zone subtract as wall-clock times (a day of 25 hours gives 24).
    hours = int(period.closes.timestamp() - period.opens.timestamp()) // 3600
    quota = [
        {
            "credential": credential,
            "account": account,
            "window": window,
            "daily_peak": [peaks.get((credential, account, window, d)) for d in days],
            "hourly_peak": [hourly.get(h) for h in range(hours)],
        }
        for (credential, account, window), hourly in sorted(readings.items())
    ]
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
