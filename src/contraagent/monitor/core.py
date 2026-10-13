"""What the monitor reads: runs, journal rows, the plan, task details, agent transcripts.

`Monitor` is the framework-neutral core (no web dependency): the HTTP
layer in `server.py` is a thin shell over its methods, so a CLI, a TUI or
a test can use the same views.

A domain extends it two ways, neither touching the framework:

* `panels` — named callables `fn(run) -> dict`. Each shows up as its own
  tab in the web UI (rendered as a JSON tree) and is pushed over the live
  feed whenever its value changes. A security-scan pipeline would register
  "findings" or "targets"; a data pipeline would register "datasets".
* `task_detail` — `fn(run, key, rows) -> dict` (`TaskDetailFn`), merged into the
  per-task view (a task's declared inputs/outputs, the state it wrote).

It reads runs only through a `RunSource` and a `Liveness` (`source.py`): by default
one host's `runs/` directory and `/proc`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from contraagent import rundir
from contraagent.backends.streams import normalize_stream_event, resolve_format
from contraagent.execution.cursor import parse_cursor
from contraagent.monitor import paths
from contraagent.monitor.source import PAGE_BYTES, DirectorySource, Liveness, ProcLiveness, RunSource, StaticLiveness

PanelFn = Callable[[str], dict]


@dataclass
class Panel:
    """A named view a domain adds to the monitor: `fn(run) -> dict`.

    `title` and `description` label its tab and say what it shows; `icon` is a
    short glyph. A bare callable works too (the dict key becomes the title).
    """

    fn: PanelFn
    title: str = ""
    description: str = ""
    icon: str = "▤"

    def __call__(self, run: str) -> dict:
        return self.fn(run)


#: The `task_detail` callback: `fn(run, key, rows) -> dict`, merged into `Monitor.task_detail`.
TaskDetailFn = Callable[[str, str, list], dict]


def _running_keys(snap: dict) -> set:
    """Keys of every task running now: agent launches and Python tasks."""
    return {lc.get("key") for lc in snap.get("launches", [])} | {pt.get("key") for pt in snap.get("python_tasks", [])}


def _first_last(readings: list[dict]) -> dict:
    """Per credential (account), the run's first and last utilization reading, by when
    they were received; the account with the highest weekly utilization first."""
    by: dict[str, list[dict]] = {}
    for q in sorted((q for q in readings if q.get("observed_at")), key=lambda q: q["observed_at"]):
        by.setdefault(q.get("credential") or "", []).append(q)
    accounts = [{"credential": c, "first": qs[0], "last": qs[-1]} for c, qs in by.items()]
    accounts.sort(key=lambda a: -(a["last"].get("seven_day_pct") or 0))
    return {"quota": accounts}


def _shown(file: str, cwd: Path | None) -> str:
    """A flow code file as the monitor serves it: relative to the run's working
    directory when under it, else as recorded."""
    path = Path(file)
    if cwd is not None and path.is_absolute() and path.is_relative_to(cwd):
        return str(path.relative_to(cwd))
    return file


def _shown_flow(flow: list, cwd: Path | None) -> list:
    """A flow path with each frame's file as `_shown` gives it."""
    return [{**f, "file": _shown(f.get("file", ""), cwd)} for f in flow if isinstance(f, dict)]


def _parses(line: str) -> bool:
    try:
        json.loads(line)
    except ValueError:
        return False
    return True


def _parse(lines: list[str]) -> list[dict]:
    """The JSON values of log lines or documents; one that does not parse (a torn last write) is skipped."""
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


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
        panels: dict[str, Panel | PanelFn] | None = None,
        task_detail: TaskDetailFn | None = None,
        static_dir: str | Path | None = None,
        stream_formats: dict[str, str] | None = None,
        groups: list[dict] | None = None,
    ):
        """`groups` are the plan's columns (`[{"id", "label", "kinds": [...]}]`);
        without them each kind is a group of its own.
        `static_dir` replaces the bundled web UI with the caller's own.
        `stream_formats` maps a custom coding agent's name to a built-in stream
        format (`claude`, `omp`) when the monitor runs in another process than
        the one that called `register_normalizer`.
        `source` and `liveness` replace where runs are read from (default: `runs_dir`
        and this host's `/proc`); a `source` given without `liveness` has no live run.
        `many_hosts`: the runs come from many hosts (a hub), so the UI offers its hosts."""
        self.many_hosts = many_hosts
        self.runs_dir = Path(runs_dir).resolve()
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
        self.static_dir = Path(static_dir) if static_dir else None
        self.stream_formats = dict(stream_formats or {})
        self.group_defs = list(groups or [])

    def check_run(self, run: str) -> str:
        """`run` itself; `paths.BadName` (a ValueError) when it is not a plain name."""
        return paths.check_name(run, "run id")

    # --- runs --------------------------------------------------------------

    def runs(self) -> list[dict]:
        """One row per run directory, newest activity first."""
        out: list[dict] = []
        live = self.liveness.live()
        unresponsive = self.liveness.unresponsive()
        for run in self.source.runs():
            info = self.source.info(run) or {}
            n = ok = not_run = 0
            cost: float | None = None
            tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "calls": 0}
            readings: list[dict] = []
            wall = 0.0
            last = ""
            run_group = info.get("run_group", "")
            kinds: dict[str, int] = {}
            for e in self._read_journal(run):
                n += 1
                ok += bool(e.get("ok"))
                not_run += e.get("stop") in ("invalid_input", "skipped")
                if e.get("cost_usd") is not None:
                    cost = (cost or 0.0) + float(e["cost_usd"])
                readings += [q for q in e.get("quota") or [] if isinstance(q, dict)]
                for k, v in (e.get("usage") or {}).items():
                    if k in tokens:
                        tokens[k] += int(v or 0)
                wall += float(e.get("wall_s") or 0)
                last = e.get("ts", last)
                kinds[e.get("kind", "?")] = kinds.get(e.get("kind", "?"), 0) + 1
                run_group = e.get("run_group") or run_group
            if not last:
                # A run on its first task has no journal row yet (rows land when
                # a task finishes); still list it once it has live evidence.
                if not info and not self.source.exists(run, rundir.STREAMS):
                    continue
                last = self.source.activity(run) or ""
                if not last:
                    continue
            out.append(
                {
                    "run": run,
                    "run_group": run_group or run,
                    "attempts": n,
                    "ok": ok,
                    "not_run": not_run,
                    "tasks": self._task_counts(run, live=run in live),
                    "cost_usd": round(cost, 6) if cost is not None else None,
                    "tokens": tokens,
                    **_first_last(readings),
                    "wall_s": round(wall),
                    "last_ts": last,
                    "kinds": kinds,
                    "running": run in live,
                    "unresponsive": run in unresponsive,
                    "host_id": info.get("host_id", ""),
                    "run_uid": info.get("run_uid", ""),
                    "started_at": info.get("started_at", ""),
                }
            )
        out.sort(key=lambda r: r["last_ts"], reverse=True)
        return out

    def hosts(self) -> dict:
        """The hosts that drive the runs, with their runs counted, and each account's first
        and last utilization reading over every run. A host that drives runs but does not
        report (it has no heartbeat) is listed as not up."""
        rows = self.runs()
        by_host: dict[str, list[dict]] = {}
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
        return {"hosts": hosts, **_first_last(readings)}

    def _task_counts(self, run: str, live: bool = False) -> dict:
        """Tasks (not attempts) by how they ended, from the plan's states: the
        same numbers the run's own page shows. Running tasks are looked up only
        for a run that is `live`."""
        counts = {"total": 0, "done": 0, "failed": 0, "not_started": 0, "running": 0, "waiting": 0, "skipped": 0}
        name = {"done": "done", "failed": "failed", "blocked": "not_started", "skipped": "skipped"}
        running = _running_keys(self.liveness.snapshot(run)) if live else set()
        for n in self.plan(run, live={})["nodes"]:
            counts["total"] += 1
            state = name.get(n["state"], "waiting")
            counts["running" if state == "waiting" and n.get("key") in running else state] += 1
        return counts

    # --- journal -----------------------------------------------------------

    def _read_journal(self, run: str) -> list[dict]:
        return _parse(self.source.lines(run, rundir.JOURNAL)[0])

    def journal(self, run: str, since: int = 0) -> tuple[list[dict], int]:
        """Rows after line offset `since`, and the new total."""
        if self.source.size(run, rundir.JOURNAL) < 0:
            return [], since
        lines, total = self.source.lines(run, rundir.JOURNAL, since)
        return _parse(lines), total

    # --- plan (the pipeline, including work that has not started) ---------

    def _read_plan(self, run: str) -> list[dict]:
        out, seen = [], set()
        for row in _parse(self.source.lines(run, rundir.PLAN)[0]):
            # A key queued again (a retry, a re-dispatch) is the same node.
            if row.get("key") not in seen:
                seen.add(row.get("key"))
                out.append(row)
        return out

    def plan(self, run: str, live: dict | None = None) -> dict:
        """The pipeline as a graph: every task ever queued, its dependencies and
        state, plus the groups. `failed` is a task that ran and failed;
        `blocked` is one that did not start because an input was missing or
        off-contract (refused, `invalid_input`), or that waits for such a task
        or a failed one: it shows where a failure stopped the work.

        A run with no `plan.jsonl` (an older run, or one not made through
        `Run.queue`) falls back to the journal: finished tasks only, no edges.
        """
        journal = self._read_journal(run)
        last: dict[str, dict] = {}
        for e in journal:
            last[e.get("key", "")] = e
        rows = self._read_plan(run)
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
        snap = live if live is not None else self.liveness.snapshot(run)
        running = _running_keys(snap)
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
            else:
                state = "done" if j.get("ok") else "failed"
            node = {**r, "state": state}
            if j:
                node.update(
                    {
                        "wall_s": j.get("wall_s", 0),
                        "stop": j.get("stop", ""),
                        "route": j.get("route", ""),
                        "attempts": j.get("attempt", 0) + 1,
                    }
                )
            nodes.append(node)
        by_key = {n["key"]: n for n in nodes}
        changed = True
        while changed:  # a pending task behind a failed or blocked one is blocked too
            changed = False
            for n in nodes:
                if n["state"] == "pending" and any(by_key.get(d, {}).get("state") in ("failed", "blocked") for d in n["after"]):
                    n["state"], changed = "blocked", True
        depth: dict[str, int] = {}

        def level(key: str, trail: tuple = ()) -> int:
            if key in depth:
                return depth[key]
            after = by_key.get(key, {}).get("after", [])
            deps = [d for d in after if d in by_key and d not in trail]
            # A dependency not (yet) queued is upstream of this task all the same.
            floor = 0 if any(d not in by_key for d in after) else -1
            depth[key] = 1 + max((level(d, trail + (key,)) for d in deps), default=floor)
            return depth[key]

        cwd = self._cwd(run)
        for n in nodes:
            n["level"] = level(n["key"])
            n["group"] = self._group_name(n)
            if n.get("flow"):
                n["flow"] = _shown_flow(n["flow"], cwd)
        return {"nodes": nodes, "groups": self._groups(nodes), "flow_calls": self._flow_calls(run, cwd)}

    def _cwd(self, run: str) -> Path | None:
        """The run's working directory, as `run.json` records it."""
        cwd = (self.source.info(run) or {}).get("cwd")
        return Path(cwd) if isinstance(cwd, str) and cwd else None

    def _flow_calls(self, run: str, cwd: Path | None) -> list[dict]:
        """Each flow call of `flow_calls.jsonl` in start order, folded with its end. A
        resumed run starts its flow calls again: the latest start of an id counts."""
        calls: dict[str, dict] = {}
        for row in _parse(self.source.lines(run, rundir.FLOW_CALLS)[0]):
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
                }
            elif row.get("event") == "end" and cid in calls:
                calls[cid].update(state=row.get("state") or "closed", error=row.get("error"))
        return list(calls.values())

    def _group_name(self, n: dict) -> str:
        """A node's group: the first of `groups` that lists its kind, else its `Task.kind`."""
        for d in self.group_defs:
            if n["kind"] in d.get("kinds", ()):
                return d["id"]
        return n["kind"]

    def _groups(self, nodes: list[dict]) -> list[dict]:
        def tally(sid: str, label: str, members: list[dict]) -> dict:
            c = {s: sum(1 for n in members if n["state"] == s) for s in ("done", "failed", "running", "pending", "skipped", "blocked")}
            return {"id": sid, "label": label, "total": len(members), **c}

        if self.group_defs:
            out = []
            for d in self.group_defs:
                members = [n for n in nodes if n["kind"] in d.get("kinds", ())]
                out.append(tally(d["id"], d.get("label", d["id"]), members))
            return out
        groups: dict[str, list[dict]] = {}
        for n in nodes:
            groups.setdefault(n["group"], []).append(n)
        order = sorted(groups, key=lambda g: (min(n["level"] for n in groups[g]), nodes.index(groups[g][0])))
        return [tally(g, g, groups[g]) for g in order]

    def procs(self, run: str) -> dict:
        return self.liveness.snapshot(run)

    def task_detail(self, run: str, key: str) -> dict:
        """Journal rows, live launches and the stream file for one task, by its key."""
        paths.check_name(key, "task key")
        rows = [e for e in self._read_journal(run) if e.get("key") == key]
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
            "io": self.task_io(run, key),
            "stream": key if self.source.size(run, rundir.stream(key)) >= 0 else None,
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
        for e in reversed(self._read_journal(run)):
            if e.get("key") == key and e.get("agent"):
                return e["agent"]
        for c in self.liveness.snapshot(run).get("launches", []):
            if c.get("key") == key and c.get("full_cmd"):
                return c["full_cmd"].split()[0].rsplit("/", 1)[-1]
        return "omp"

    def stream_size(self, run: str, key: str) -> int:
        """A number that changes whenever task `key`'s transcript grows; -1 while it has
        none. `paths.BadName` for a run id or task key that is not a plain name."""
        return self.source.size(run, rundir.stream(paths.check_name(key, "task key")))

    async def wait_stream(self, run: str, key: str, beyond: int, timeout: float) -> int:
        """Wait until task `key`'s transcript has grown past `beyond` (a value `stream_size`
        returned), or `timeout` seconds; return its `stream_size` then."""
        return await self.source.wait(run, rundir.stream(paths.check_name(key, "task key")), beyond, timeout)

    def stream(self, run: str, key: str, since: int, limit: int = 1500) -> tuple[dict, int]:
        """A page of task `key`'s normalized transcript events.

        `since` is a line offset; the first call (`since=0`) returns the TAIL
        page so a huge stream never crosses the wire whole, and the client
        pages backward on demand. Always `{events, total, behind}`, including
        when the file is absent.
        """
        page, _ = self.stream_from(run, key, since if since > 0 else None, limit)
        return page, page["total"]

    def stream_from(self, run: str, key: str, since: int | None, limit: int = 1500) -> tuple[dict, int]:
        """A page of task `key`'s normalized transcript events from line `since` (None:
        the tail page, the last `limit` lines), as `stream` gives it, and the line offset
        after the last line the page read: where the next page starts. The page stops at
        `limit` events or `PAGE_BYTES`, so that offset can be less than `total`. A last
        line that starts as a JSON object but does not parse is still being written: the
        page does not read it."""
        log = rundir.stream(paths.check_name(key, "task key"))
        start = since or 0
        if self.source.size(run, log) < 0:
            return {"events": [], "total": start, "behind": 0}, start
        behind = 0
        if since is None:
            total = self.source.lines(run, log, 0, 0)[1]
            behind = start = max(0, total - limit)
        lines, total = self.source.lines(run, log, start, limit * 4, max_bytes=PAGE_BYTES)
        if lines and start + len(lines) == total and lines[-1].lstrip().startswith("{") and not _parses(lines[-1]):
            lines = lines[:-1]
        fmt = resolve_format(self.task_agent(run, key), self.stream_formats)
        out: list[dict] = []
        tools: dict[str, str] = {}  # call id -> tool name: some formats name the tool only on its start
        end = start
        for line in lines:
            end += 1
            ev = normalize_stream_event(fmt, line)
            if ev is not None:
                if ev.get("type") == "tool_execution_start" and ev.get("call"):
                    tools[ev["call"]] = ev.get("tool") or ""
                elif ev.get("type") == "tool_execution_end" and not ev.get("tool"):
                    ev["tool"] = tools.get(ev.get("call") or "", "")
                out.append(ev)
                if len(out) >= limit:
                    break
        return {"events": out, "total": total, "behind": behind}, end

    # --- contracts: the files tasks must leave behind ----------------------

    def outputs(self, run: str) -> dict:
        """Every declared `OutputContract` / `InputContract` of the run: its file,
        the model it must satisfy, and where it stands.

        Status comes from the journal, which records what `run_until_valid`
        concluded: `pending` before the task finishes, `valid` (with the number
        of rounds it took when it needed a resume), `invalid` when the file
        was still off-contract after every resume, `refused` when an input was off-contract so
        the task never started, `failed` when the task ended for another reason before
        the check could pass.
        """
        last: dict[str, dict] = {}
        for e in self._read_journal(run):
            last[e.get("key", "")] = e
        running = _running_keys(self.liveness.snapshot(run))
        records = []
        for rec in _parse(self.source.folder(run, rundir.CONTRACTS)):
            row = last.get(rec.get("key", ""))
            for spec in rec.get("outputs", []) + rec.get("inputs", []):
                spec["file"] = self._file_view(run, spec["path"])
                props = (spec.get("schema") or {}).get("properties", {})
                req = set((spec.get("schema") or {}).get("required", []))
                spec["fields"] = [{"name": n, "type": self._type_of(p), "required": n in req} for n, p in props.items()]
                spec.pop("schema", None)
            for spec in rec.get("outputs", []):
                spec["status"], spec["rounds"], spec["errors"] = self._contract_status(row, spec["file"], rec.get("key") in running)
            records.append(rec)
        outs = [o for r in records for o in r["outputs"]]
        tally = {s: sum(1 for o in outs if o["status"] == s) for s in ("valid", "invalid", "refused", "pending", "failed", "running")}
        return {"contracts": records, "tally": tally}

    @staticmethod
    def _type_of(prop: dict) -> str:
        if "$ref" in prop:
            return prop["$ref"].rsplit("/", 1)[-1]
        t = prop.get("type", "any")
        if t == "array":
            return f"list[{Monitor._type_of(prop.get('items', {}))}]"
        return "|".join(x.get("type", "any") for x in prop["anyOf"]) if "anyOf" in prop else str(t)

    def _file_view(self, run: str, path: str, limit: int = 20_000) -> dict:
        got = self.source.file(run, path)
        if got is None:
            return {"exists": False}
        text, size, mtime = got
        out: dict = {"exists": True, "size": size, "mtime": mtime}
        if text is None:
            out["content"] = None
            return out
        out["truncated"] = len(text) > limit
        try:
            out["content"] = json.loads(text) if len(text) <= limit else text[:limit]
        except ValueError:  # a text output, or JSON that does not parse: the text itself
            out["content"] = text
        return out

    @staticmethod
    def _contract_status(row: dict | None, file: dict, running: bool) -> tuple[str, int | None, list[str]]:
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

    def definitions(self, run: str) -> list[dict]:
        """What defined each kind of task in this run (`definitions/<kind>.json`)."""
        return _parse(self.source.folder(run, rundir.DEFINITIONS))

    def task_io(self, run: str, key: str) -> dict:
        """One task's input and output: its params, the files it read, the files
        it left behind with the contract verdict, and how data flows around it.

        `upstream` are the output files of the tasks this one waits for (`after=`): for a task
        that declares no `InputContract`, they are what it actually reads. `downstream` are the
        tasks that wait for this one.
        """
        outs = self.outputs(run)
        by_key = {c.get("key"): c for c in outs["contracts"]}
        rec = by_key.get(key) or {}
        plan = {n["key"]: n for n in self._read_plan(run)}
        node = plan.get(key, {})
        upstream = []
        for dep in node.get("after", []):
            d = by_key.get(dep)
            upstream.append(
                {
                    "key": dep,
                    "kind": (plan.get(dep) or {}).get("kind", ""),
                    "unit": (plan.get(dep) or {}).get("unit", ""),
                    "executor": (plan.get(dep) or {}).get("executor", "agent"),
                    "outputs": (d or {}).get("outputs", []),
                }
            )
        downstream = [
            {"key": k, "kind": n.get("kind", ""), "unit": n.get("unit", ""), "executor": n.get("executor", "agent")}
            for k, n in plan.items()
            if key in n.get("after", [])
        ]
        return {
            "params": self._call_params(run, key, rec.get("params", {})),
            "inputs": rec.get("inputs", []),
            "outputs": rec.get("outputs", []),
            "executor": rec.get("executor", node.get("executor", "agent")),
            "upstream": upstream,
            "downstream": downstream,
        }

    def _call_params(self, run: str, key: str, fallback: dict) -> dict:
        """What the task was given: the call file's params (every value, a value
        from an earlier task included), else the contract record's scalar ones."""
        try:
            params = json.loads(self.source.document(run, rundir.entry(rundir.CALLS, key)) or "").get("params")
        except (ValueError, AttributeError):
            return fallback
        return params if isinstance(params, dict) else fallback

    # --- resume cursor -------------------------------------------------------

    def cursor(self, run: str) -> dict | None:
        """The run's `CursorStore` (runs/<run>/cursor.json), or None when it keeps none:
        the stage it is in, the stages behind it, and each unit's step."""
        text = self.source.document(run, rundir.CURSOR)
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

    def panel(self, name: str, run: str) -> dict:
        panel = self.panels.get(name)
        if panel is None:
            raise KeyError(name)
        return panel(run)

    def panel_info(self) -> list[dict]:
        return [{"name": n, "title": p.title or n, "description": p.description, "icon": p.icon} for n, p in sorted(self.panels.items())]
