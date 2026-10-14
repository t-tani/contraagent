"""Trends: what the runs of a period add up to, day by day.

A run's own views (`Monitor.plan`, `Monitor.runs`) say what one run did. Trends
say what the runs of a **period** (days `from`..`to`, inclusive, in a time zone)
did together: the cost of each day by kind, each kind's tasks, success and time,
each model's tokens and cost, the causes of failures, the tool calls refused,
each account's utilization, the rests and deferrals, and when runs start.

It works in two steps, so that any period, time zone or grouping costs little:

* `digest(source, run)`: what a run did, summed by 15-minute slot of UTC (`SLOT_S`):
  per kind its attempts, passes, time, cost, tokens and outcomes, with every wall time,
  so a median stays exact; per model its spend; each account's
  highest reading. Every time zone's offset is a multiple of 15 minutes, so a slot
  lies in one day and one hour of any period: a digest answers any period exactly. It
  depends only on the run's files, so it is kept: in memory, keyed by the run's
  `signature`, and, for a finished run in a runs directory, in the run's `trends.json`
  (`rundir.TRENDS`), so a restarted monitor reads it back.
* `aggregate(digests, period, groups)`: the trends of a period over digests,
  with `bodies(view)`, the same numbers as panel bodies (`{"type": "blocks", ...}`)
  for a page that draws them without words of its own.

A journal row counts on the day of its `ts` (when the attempt ended) in the
period's time zone; a reading on the day and the hour it was received (each day's
and each hour's highest, not every reading); a run start on the day and hour of
`run.json`'s `started_at` (the latest start of a resumed run).
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from contraagent import rundir
from contraagent.monitor import paths
from contraagent.monitor.source import DirectorySource

#: Bumped when a digest's shape changes: a kept digest of another version is made again.
DIGEST_VERSION = 6

#: The runs the run list's panel body shows, the newest (`Trends.runs` holds every one).
BODY_RUNS = 50

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

#: A digest's time unit: 15 minutes of UTC. Every time zone's offset is a multiple of it,
#: so a slot lies in one day and one hour of any period's time zone.
SLOT_S = 900


def _slot(ts: object) -> int | None:
    t = when(ts)
    return int(t.timestamp() // SLOT_S) if t is not None else None


def run_dir(source: DirectorySource, run: str) -> str:
    """The run's directory, checked: a plain name that is no symbolic link, under the runs
    directory (which `DirectorySource` resolved), is inside it, one `lstat` for what
    `source.path` (every part resolved) would say; a link takes that full check."""
    base = os.path.join(source.root, paths.check_name(run, "run id"))
    try:
        if not stat.S_ISLNK(os.lstat(base).st_mode):
            return base
    except OSError:
        pass
    return str(source.path(run))


def run_files(source, run: str, infos: dict | None = None) -> tuple[dict, dict]:
    """A run's `run.json` and its `signature`: what its digest depends on (its logs' sizes,
    and when it started and finished). In a runs directory the run's directory is checked
    once, and `run.json` and each log are opened by name in it, not each path checked
    again: a period over hundreds of runs asks for thousands. `infos` keeps each run's
    `run.json` by its `stat`, so an unchanged one is not read again."""
    if isinstance(source, DirectorySource):
        base = run_dir(source, run)
        info = None
        try:
            path = os.path.join(base, rundir.RUN_INFO)
            st = os.stat(path)
            held = (infos or {}).get(run)
            if held is not None and held[0] == (st.st_mtime_ns, st.st_size):
                info = held[1]
            else:
                with open(path, encoding="utf-8") as f:
                    info = json.loads(f.read())
                if infos is not None:
                    infos[run] = ((st.st_mtime_ns, st.st_size), info)
        except (OSError, ValueError):
            pass
        sizes = {}
        for log in DIGEST_LOGS:
            try:
                sizes[log] = os.stat(os.path.join(base, log)).st_size
            except OSError:
                sizes[log] = -1
    else:
        info = source.info(run)
        sizes = {log: source.size(run, log) for log in DIGEST_LOGS}
    info = info if isinstance(info, dict) else {}
    return info, {**sizes, "started_at": info.get("started_at", ""), "finished_at": info.get("finished_at", "")}


def _usage(v: object) -> dict | None:
    if not isinstance(v, dict):
        return None
    return {k: int(n) for k in _TOKENS if (n := _num(v.get(k))) is not None}


def digest(source, run: str) -> dict:
    """What a run did, by 15-minute slot of UTC (`SLOT_S`), as much as its trends need.

    `slots`: `[slot, {"last_ts", "kinds": {kind: {n, ok, wall, cost, tokens, stops, walls}},
    "models": [...]}]`, oldest first: per kind its attempts, how many passed, their wall
    time, cost (null when none reported one), tokens (`_TOKENS` order), outcomes, and their
    wall times, sorted (a median over a period stays exact, and joining runs is a list's
    `extend` and one sort); per model what its hops spent (`model_usage`, in order of first use).
    `kinds`: per kind its executor, and its tasks and the tasks whose last attempt passed,
    over the whole run; `tasks`: per kind, per task, its attempts as `slot, ok, slot, ok ...`
    (each slot counted from `span[0]`; the last attempt of a slot), for a period that cuts
    the run. `span`: the first and last slot
    of an attempt; `total`: the slots summed, in the same shape, for a period that holds
    the whole run within one of its days (most runs: a period then adds one entry per run,
    not one per slot). `quota`: `[slot, credential, window, highest pct]`; `denied`: `[slot,
    tool, kind, count]`; `rests` and `deferred`: their rows."""
    from contraagent.monitor.core import model_usage  # the per-model sums one run's plan shows

    info = source.info(run) or {}
    slots: dict[int, dict] = {}
    rows_of: dict[int, list[dict]] = {}
    kinds: dict[str, dict] = {}
    key_kind: dict[str, str] = {}
    attempts: dict[str, dict[str, list[int]]] = {}
    peaks: dict[tuple[int, str, str], float] = {}
    for e in _parse(source.lines(run, rundir.JOURNAL)[0]):
        key, kind = str(e.get("key", "")), str(e.get("kind", "?"))
        key_kind[key] = kind
        slot = _slot(e.get("ts"))
        for q in e.get("quota") or ():
            qs = _slot(q.get("observed_at")) if isinstance(q, dict) else None
            if qs is None:
                continue
            for w in _WINDOWS:
                pct = _num(q.get(f"{w}_pct"))
                if pct is not None:
                    at = (qs, str(q.get("credential", "")), w)
                    peaks[at] = max(peaks.get(at, 0.0), pct)
        if slot is None:
            continue
        ok, wall, cost, usage = bool(e.get("ok")), _num(e.get("wall_s")) or 0.0, _num(e.get("cost_usd")), _usage(e.get("usage"))
        executor = e.get("executor") or "agent"
        s = slots.setdefault(slot, {"last_ts": "", "kinds": {}})
        s["last_ts"] = max(s["last_ts"], str(e.get("ts", "")))
        k = s["kinds"].setdefault(
            kind, {"n": 0, "ok": 0, "wall": 0.0, "cost": None, "tokens": [0] * len(_TOKENS), "stops": {}, "walls": []}
        )
        k["n"] += 1
        k["ok"] += ok
        k["wall"] += wall
        if cost is not None:
            k["cost"] = (k["cost"] or 0.0) + cost
        for i, name in enumerate(_TOKENS):
            k["tokens"][i] += int((usage or {}).get(name, 0))
        stop = str(e.get("stop", ""))
        k["stops"][stop] = k["stops"].get(stop, 0) + 1
        k["walls"].append(wall)
        kinds.setdefault(kind, {"executor": executor, "tasks": 0, "tasks_ok": 0})
        pairs = attempts.setdefault(kind, {}).setdefault(key, [])
        if pairs and pairs[-2] == slot:
            pairs[-1] = int(ok)
        else:
            pairs += [slot, int(ok)]
        hops = [
            {"agent": h.get("agent", ""), "model": h.get("model", ""), "cost_usd": _num(h.get("cost_usd")),
             "wall_s": _num(h.get("wall_s")) or 0.0, "usage": _usage(h.get("usage"))}
            for h in e.get("hops") or () if isinstance(h, dict)
        ]  # fmt: skip
        rows_of.setdefault(slot, []).append({"executor": executor, "agent": e.get("agent", ""), "usage": usage, "hops": hops})
    for kind, keys in attempts.items():
        kinds[kind]["tasks"] = len(keys)
        kinds[kind]["tasks_ok"] = sum(pairs[-1] for pairs in keys.values())
    total: dict = {"last_ts": "", "kinds": {}, "models": model_usage([r for slot in sorted(rows_of) for r in rows_of[slot]])}
    for slot in sorted(slots):
        s = slots[slot]
        total["last_ts"] = max(total["last_ts"], s["last_ts"])
        for kind, k in s["kinds"].items():
            k["walls"].sort()
            t = total["kinds"].setdefault(
                kind, {"n": 0, "ok": 0, "wall": 0.0, "cost": None, "tokens": [0] * len(_TOKENS), "stops": {}, "walls": []}
            )
            t["n"] += k["n"]
            t["ok"] += k["ok"]
            t["wall"] += k["wall"]
            if k["cost"] is not None:
                t["cost"] = (t["cost"] or 0.0) + k["cost"]
            t["tokens"] = [a + b for a, b in zip(t["tokens"], k["tokens"], strict=True)]
            for stop, c in k["stops"].items():
                t["stops"][stop] = t["stops"].get(stop, 0) + c
            t["walls"] += k["walls"]
        s["models"] = model_usage(rows_of[slot])
    for t in total["kinds"].values():
        t["walls"].sort()
    denied: dict[tuple[int, str, str], int] = {}
    for launch in _parse(source.lines(run, rundir.LAUNCHES)[0]):
        slot = _slot(launch.get("ts"))
        if slot is None:
            continue
        for d in launch.get("denied") or ():
            if isinstance(d, dict) and d.get("tool"):
                at = (slot, str(d["tool"]), key_kind.get(str(launch.get("label", "")), ""))
                denied[at] = denied.get(at, 0) + 1
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
    first = min(slots) if slots else 0
    return {
        "version": DIGEST_VERSION,
        "run": run,
        "run_group": info.get("run_group") or run,
        "host_id": info.get("host_id", ""),
        "started_at": info.get("started_at", ""),
        "finished_at": info.get("finished_at", ""),
        "stub": info.get("stub") is True,
        "span": [min(slots), max(slots)] if slots else None,
        "slots": [[slot, slots[slot]] for slot in sorted(slots)],
        "total": total,
        "kinds": kinds,
        "tasks": {kind: [[v - first if i % 2 == 0 else v for i, v in enumerate(p)] for p in ks.values()] for kind, ks in attempts.items()},
        "quota": [[slot, credential, window, pct] for (slot, credential, window), pct in sorted(peaks.items())],
        "denied": [[slot, tool, kind, n] for (slot, tool, kind), n in sorted(denied.items())],
        "rests": rests,
        "deferred": deferred,
    }


def kept_form(dg: dict) -> dict:
    """A digest as `trends.json` keeps it: its total without the wall times its slots hold
    (`restore` puts them back), so a file holds each one once."""
    total = {**dg["total"], "kinds": {k: {f: v for f, v in t.items() if f != "walls"} for k, t in dg["total"]["kinds"].items()}}
    return {**dg, "total": total}


def restore(dg: dict) -> dict:
    """A digest read from `trends.json` (`kept_form`) made whole again: its total's wall times."""
    walls: dict[str, list[float]] = {}
    for _, s in dg["slots"]:
        for kind, k in s["kinds"].items():
            walls.setdefault(kind, []).extend(k["walls"])
    for kind, t in dg["total"]["kinds"].items():
        t["walls"] = sorted(walls.get(kind, []))
    return dg


def in_period(info: Mapping, period: Period) -> bool:
    """Whether a run may have done something in `period`, by its `run.json` alone: started
    before it closes, and not finished before it opens. A run that does not say is kept."""
    started, finished = when(info.get("started_at")), when(info.get("finished_at"))
    if started is not None and started >= period.closes:
        return False
    return not (finished is not None and finished < period.opens)


# --- the trends of a period ------------------------------------------------------------


def _round(v: float | None, n: int = 6) -> float | None:
    return round(v, n) if v is not None else None


def _median(walls: list[float]) -> float:
    """The median of `walls`, sorted (`statistics.median`, without sorting again)."""
    n = len(walls)
    if not n:
        return 0.0
    return walls[n // 2] if n % 2 else (walls[n // 2 - 1] + walls[n // 2]) / 2


def _add_model(models: dict[tuple[str, str], dict], m: Mapping) -> None:
    """Add one slot's spend on a model (`model_usage`) to `models`, in order of first use."""
    into = models.get((m["agent"], m["model"]))
    if into is None:
        models[(m["agent"], m["model"])] = dict(m)
        return
    for f, v in m.items():
        if f in ("agent", "model") or v is None:
            continue
        if f == "cost_usd":
            into[f] = round((into[f] or 0.0) + v, 6)
        elif f == "wall_s":
            into[f] = round(into[f] + v, 1)
        else:
            into[f] += v


class _Slots:
    """The day and the hour of each slot in a period, worked out once each."""

    def __init__(self, period: Period) -> None:
        self.period = period
        self.first = int(period.opens.timestamp()) // SLOT_S
        self.end = int(period.closes.timestamp()) // SLOT_S
        self._days: dict[int, int] = {}

    def holds(self, slot: int) -> bool:
        return self.first <= slot < self.end

    def day(self, slot: int) -> int:
        """The slot's day, as an index of the period's days."""
        d = self._days.get(slot)
        if d is None:
            local = datetime.fromtimestamp(slot * SLOT_S, self.period.zone).date()
            d = self._days[slot] = (local - self.period.start).days
        return d

    def hour(self, slot: int) -> int:
        """The slot's hour, counted from the period's first instant."""
        return (slot - self.first) * SLOT_S // 3600


def aggregate(digests: Iterable[dict], period: Period, groups: Mapping[str, str] | None = None) -> dict:
    """The trends of `period` over run `digests` (`digest`); `groups` maps a kind to the
    group it is counted in (the monitor's `groups`), each other kind being its own."""
    group_of = dict(groups or {})
    at = _Slots(period)
    days = [d.isoformat() for d in period.days]
    hours = (at.end - at.first) * SLOT_S // 3600
    daily = [{"day": d, "cost_usd": {}, "attempts": 0, "ok": 0} for d in days]
    kinds: dict[str, dict] = {}
    walls: dict[str, list[float]] = {}
    stops: dict[str, dict] = {}
    denied: dict[str, dict] = {}
    models: dict[tuple[str, str], dict] = {}
    peaks: dict[tuple[str, str], dict] = {}
    rests, deferred, runs = [], [], []
    starts = [[0] * 24 for _ in _WEEKDAYS]
    totals = {"runs": 0, "attempts": 0, "ok": 0, "cost_usd": None, "wall_s": 0.0, "tokens": dict.fromkeys(_TOKENS, 0)}
    for dg in digests:
        run = dg["run"]
        span = dg["span"]
        if span is not None and at.holds(span[0]) and at.holds(span[1]) and at.day(span[0]) == at.day(span[1]):
            mine = [(span[0], dg["total"])]  # the whole run on one day: its sums, not its slots
        else:
            mine = [(slot, s) for slot, s in dg["slots"] if at.holds(slot)]
        started = period.day_of(dg.get("started_at"))
        if not mine and started is None:
            continue
        if started is not None:
            t = when(dg["started_at"]).astimezone(period.zone)  # type: ignore[union-attr]
            starts[t.weekday()][t.hour] += 1
        cost: float | None = None
        n = ok = 0
        wall = 0.0
        last = ""
        for slot, s in mine:
            d = daily[at.day(slot)]
            last = max(last, s["last_ts"])
            for kind, k in s["kinds"].items():
                group = group_of.get(kind, kind)
                d["attempts"] += k["n"]
                d["ok"] += k["ok"]
                if k["cost"] is not None:
                    d["cost_usd"][group] = round(d["cost_usd"].get(group, 0.0) + k["cost"], 6)
                    cost = (cost or 0.0) + k["cost"]
                into = kinds.setdefault(
                    kind,
                    {"kind": kind, "group": group, "executor": dg["kinds"][kind]["executor"], "tasks": 0, "tasks_ok": 0,
                     "attempts": 0, "ok": 0, "wall_s": 0.0, "wall_s_median": 0.0, "cost_usd": None,
                     "tokens": dict.fromkeys(_TOKENS, 0)},
                )  # fmt: skip
                into["attempts"] += k["n"]
                into["ok"] += k["ok"]
                into["wall_s"] += k["wall"]
                if k["cost"] is not None:
                    into["cost_usd"] = (into["cost_usd"] or 0.0) + k["cost"]
                for i, name in enumerate(_TOKENS):
                    into["tokens"][name] += k["tokens"][i]
                    totals["tokens"][name] += k["tokens"][i]
                walls.setdefault(kind, []).extend(k["walls"])
                for stop, c in k["stops"].items():
                    st = stops.setdefault(stop, {"stop": stop, "attempts": 0, "kinds": {}})
                    st["attempts"] += c
                    st["kinds"][kind] = st["kinds"].get(kind, 0) + c
                n += k["n"]
                ok += k["ok"]
                wall += k["wall"]
            for m in s["models"]:
                _add_model(models, m)
        # A task is one key of one run: its last attempt in the period says how it ended.
        whole = dg["span"] is not None and at.holds(dg["span"][0]) and at.holds(dg["span"][1])
        for kind, keys in dg["tasks"].items():
            if whole:
                counted, passed = dg["kinds"][kind]["tasks"], dg["kinds"][kind]["tasks_ok"]
            else:
                counted = passed = 0
                first = dg["span"][0] if dg["span"] is not None else 0
                for pairs in keys:
                    last_ok = None
                    for i in range(0, len(pairs), 2):
                        if at.holds(first + pairs[i]):
                            last_ok = pairs[i + 1]
                    if last_ok is not None:
                        counted += 1
                        passed += last_ok
            if counted and kind in kinds:
                kinds[kind]["tasks"] += counted
                kinds[kind]["tasks_ok"] += passed
        if cost is not None:
            totals["cost_usd"] = (totals["cost_usd"] or 0.0) + cost
        totals["attempts"] += n
        totals["ok"] += ok
        totals["wall_s"] += wall
        for slot, credential, window, pct in dg["quota"]:
            if at.holds(slot):
                p = peaks.setdefault((credential, window), {"daily": {}, "hourly": {}})
                day, hour = at.day(slot), at.hour(slot)
                p["daily"][day] = max(p["daily"].get(day, 0.0), pct)
                p["hourly"][hour] = max(p["hourly"].get(hour, 0.0), pct)
        for slot, tool, kind, c in dg["denied"]:
            if at.holds(slot):
                t = denied.setdefault(tool, {"tool": tool, "count": 0, "kinds": {}})
                t["count"] += c
                if kind:
                    t["kinds"][kind] = t["kinds"].get(kind, 0) + c
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
                "last_ts": last,
                "attempts": n,
                "ok": ok,
                "cost_usd": _round(cost),
                "wall_s": round(wall, 1),
                "stub": dg["stub"],
            }
        )
    for kind, k in kinds.items():
        k["wall_s"] = round(k["wall_s"], 1)
        k["wall_s_median"] = round(_median(sorted(walls.get(kind, []))), 1)
        k["cost_usd"] = _round(k["cost_usd"])
    totals["cost_usd"] = _round(totals["cost_usd"])
    totals["wall_s"] = round(totals["wall_s"], 1)
    runs.sort(key=lambda r: r["started_at"] or r["last_ts"], reverse=True)
    rests.sort(key=lambda r: r.get("ts") or "")
    deferred.sort(key=lambda r: r.get("ts") or "")
    causes: dict[str, int] = {}
    for d in deferred:
        causes[d["cause"]] = causes.get(d["cause"], 0) + 1
    quota = [
        {
            "credential": credential,
            "window": window,
            "daily_peak": [p["daily"].get(i) for i in range(len(days))],
            "hourly_peak": [p["hourly"].get(h) for h in range(hours)],
        }
        for (credential, window), p in sorted(peaks.items())
    ]
    return {
        "period": period.as_dict(),
        "totals": totals,
        "daily": [{**d, "cost_usd": dict(sorted(d["cost_usd"].items()))} for d in daily],
        "kinds": sorted(kinds.values(), key=lambda k: (-(k["cost_usd"] or 0.0), k["kind"])),
        "models": list(models.values()),
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
            for r in view["runs"][:BODY_RUNS]
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
