"""The live processes of a run on this host, read from `/proc` (`procfs`; no `ps`).

A run is live when the pid recorded in its `run.json` is still the same
process (pid *and* start time, so a recycled pid is not mistaken for it).
Its agent launches are the descendants that carry the `CONTRAAGENT_*`
environment `AgentRunner.launch` sets — a fact about the process, not a guess
parsed from its command line — and the topmost process of each task is
reported as one launch. Work running inside the run's own process (a Python
task, an agent behind a library-call backend) is known from the in-flight
markers `Run` writes (`layout.INFLIGHT`).

A run's records are read through its `DirectorySource`; `ProcLiveness` serves this as
the `Liveness` of one host's runs directory.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from contraagent import envvars, procfs, telemetry
from contraagent.runs import layout
from contraagent.runs.liveness import empty_snapshot
from contraagent.runs.names import BadName
from contraagent.runs.source import DirectorySource
from contraagent.runs.times import parse_iso

_CLK = procfs.clock_ticks()


def is_alive(info: dict | None) -> bool:
    """True when the recorded pid is still the process that started the run."""
    if not info or not info.get("pid") or info.get("finished_at"):
        return False
    return procfs.pid_identity_ok(int(info["pid"]), info.get("start_ticks"))


def live_runs(source: DirectorySource) -> set[str]:
    """The runs of `source` whose driving process is alive."""
    out = set()
    for run in source.runs():
        try:
            info = source.info(run)
        except BadName:
            continue
        if is_alive(info):
            out.add(run)
    return out


def _scan() -> dict[int, dict]:
    btime, now = procfs.boot_time(), time.time()
    procs: dict[int, dict] = {}
    for pid in procfs.pids():
        st = procfs.read_proc_stat(pid)
        if st is None or st["state"] == "Z":
            continue
        cmd = procfs.read_cmdline(pid)
        if not cmd:
            continue
        procs[pid] = {"pid": pid, "ppid": st["ppid"], "cmd": cmd, "age_s": round(now - (btime + st["starttime"] / _CLK))}
    return procs


def _short(cmd: str, limit: int = 100) -> str:
    return " ".join(cmd.split()[:3])[:limit]


def _flag(cmd: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}[ =](\S+)", cmd)
    return m.group(1) if m else ""


def snapshot(source: DirectorySource, run: str) -> dict:
    """Live processes of one run: its agent launches, the full tree, and running Python tasks."""
    info = source.info(run)
    alive = is_alive(info)
    out = empty_snapshot(run, info, alive)
    if not alive or info is None:
        return out
    procs = _scan()
    by_ppid: dict[int, list[dict]] = {}
    for p in procs.values():
        by_ppid.setdefault(p["ppid"], []).append(p)

    def node(p: dict, depth: int, parent_key: str) -> dict:
        env = procfs.read_environ(p["pid"], prefix=envvars.PREFIX)
        key = env.get(envvars.TASK, "")
        n = {"pid": p["pid"], "age_s": p["age_s"], "cmd": _short(p["cmd"]), "full_cmd": p["cmd"]}
        if key and key != parent_key and env.get(envvars.RUN, run) == run:
            tele = telemetry.parse(p["cmd"])
            n.update(
                {
                    "key": key,
                    "kind": env.get(envvars.KIND, ""),
                    "unit": env.get(envvars.UNIT, ""),
                    "role": tele.role if tele else "",
                    "model": _flag(p["cmd"], "--model"),
                    "plugin": _flag(p["cmd"], "--plugin-dir"),
                }
            )
            out["launches"].append(n)
        n["children"] = (
            [node(c, depth + 1, key or parent_key) for c in sorted(by_ppid.get(p["pid"], []), key=lambda x: x["pid"])] if depth < 3 else []
        )
        return n

    root = procs.get(int(info["pid"]))
    if root is not None:
        out["tree"] = [
            {
                "pid": root["pid"],
                "age_s": root["age_s"],
                "cmd": f"run {run}",
                "full_cmd": root["cmd"],
                "children": [node(c, 1, "") for c in sorted(by_ppid.get(root["pid"], []), key=lambda x: x["pid"])],
            }
        ]
    # Work inside the run's own process: Python tasks, and agent tasks whose
    # backend is a library call (no child process to find; known only by marker).
    seen = {lc["key"] for lc in out["launches"]}
    for m in _inflight(source, run):
        if m.pop("executor") == "python":
            out["python_tasks"].append(m)
        elif m["key"] not in seen:
            out["launches"].append({**m, "cmd": "", "full_cmd": "", "children": [], "role": "", "model": "", "plugin": ""})
    return out


def _inflight(source: DirectorySource, run: str) -> list[dict]:
    """Tasks running inside the run's own process, from their in-flight markers.
    A marker whose process is gone is ignored."""
    out = []
    now = time.time()
    for text in source.folder(run, layout.INFLIGHT):
        try:
            m = json.loads(text)
        except ValueError:
            continue
        if not isinstance(m, dict):
            continue
        pid = int(m.get("pid") or 0)
        if not pid or procfs.read_proc_stat(pid) is None:
            continue
        started = parse_iso(m.get("started_at"))
        out.append(
            {
                "key": m.get("key", ""),
                "kind": m.get("kind", ""),
                "unit": m.get("unit", ""),
                "pid": pid,
                "executor": m.get("executor") or "agent",
                "age_s": round(now - started.timestamp()) if started else 0,
            }
        )
    return out


class ProcLiveness:
    """Live runs of one `runs/` directory on this host: the pid in `run.json`, checked in `/proc`."""

    def __init__(self, root: str | Path) -> None:
        self.source = DirectorySource(root)

    def live(self) -> set[str]:
        return live_runs(self.source)

    def snapshot(self, run: str) -> dict:
        return snapshot(self.source, run)

    def unresponsive(self) -> set[str]:
        return set()

    def hosts(self) -> list[dict]:
        return [{"host_id": layout.host_id(), "up": True, "last_seen": "", "interval_s": None}]
