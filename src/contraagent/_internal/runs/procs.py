"""The live processes of a run on this host, read from the OS (`processes`; no `ps`).

A run is live when the pid recorded in its `run.json` is still the same
process (pid *and* start time, so a recycled pid is not mistaken for it).
Its agent launches are the descendants that carry the `CONTRAAGENT_*`
environment `AgentRunner.launch` sets — a fact about the process, not a guess
parsed from its command line; where the OS shows no other process's environment
(macOS), the telemetry line of its command line — and the topmost process of each
task is reported as one launch. Work running inside the run's own process (a Python
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

from contraagent._internal.platform import envvars, processes, telemetry
from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import empty_snapshot
from contraagent._internal.runs.names import BadName
from contraagent._internal.runs.source import DirectorySource
from contraagent._internal.runs.times import parse_iso


def is_alive(info: dict | None) -> bool:
    """True when the recorded pid is still the process that started the run."""
    if not info or not info.get("pid") or info.get("finished_at"):
        return False
    return processes.identity_ok(int(info["pid"]), info.get("start_ticks"))


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
    now = time.time()
    return {p.pid: {"pid": p.pid, "ppid": p.ppid, "cmd": p.cmd, "age_s": round(now - p.started)} for p in processes.scan().values()}


def _short(cmd: str, limit: int = 100) -> str:
    return " ".join(cmd.split()[:3])[:limit]


def _flag(cmd: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}[ =](\S+)", cmd)
    return m.group(1) if m else ""


def _env_of_telemetry(cmd: str) -> dict[str, str]:
    """The task variables a telemetry line in `cmd` names, for a process whose environment
    is not readable (on macOS, any process's but one's own); empty when it has none (its
    prompt came over stdin)."""
    tele = telemetry.parse(cmd)
    if tele is None:
        return {}
    values = {envvars.RUN: tele.run, envvars.KIND: tele.kind, envvars.UNIT: tele.unit, envvars.TASK: tele.key}
    return {k: "" if v == "-" else v for k, v in values.items()}


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
        env = processes.environ(p["pid"], prefix=envvars.PREFIX) or _env_of_telemetry(p["cmd"])
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
    for m in _inflight(source, run, info):
        if m.pop("executor") == "python":
            out["python_tasks"].append(m)
        elif m["key"] not in seen:
            out["launches"].append({**m, "cmd": "", "full_cmd": "", "children": [], "role": "", "model": "", "plugin": ""})
    return out


def _inflight(source: DirectorySource, run: str, info: dict) -> list[dict]:
    """Tasks running inside the run's own process, from their in-flight markers. A marker
    whose process is gone, or whose pid another process now has (its start differs from
    the one the marker holds), is ignored. A marker that holds no start, written before
    markers held one, is taken at the start `info` (`run.json`) holds for the same pid."""
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
        ticks = m.get("start_ticks", info.get("start_ticks") if pid == info.get("pid") else None)
        if not pid or not processes.identity_ok(pid, ticks):
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
    """Live runs of one `runs/` directory on this host: the pid in `run.json`, checked against the OS."""

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
