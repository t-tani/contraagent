"""Live process-tree introspection, read straight from /proc (no `ps`).

A run is live when the pid recorded in its `run.json` is still the same
process (pid *and* start time, so a recycled pid is not mistaken for it).
Its agent launches are the descendants that carry the `CONTRAAGENT_*`
environment `AgentRunner.launch` sets — a fact about the process, not a guess
parsed from its command line — and the topmost process of each task is
reported as one launch. Work running inside the run's own process (a Python
task, an agent behind a library-call backend) is known from the in-flight
markers `Run` writes.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from contraagent import envvars, procfs
from contraagent.monitor.paths import BadName, under


def _clock_ticks() -> int:
    """Clock ticks per second, the unit of /proc/<pid>/stat's start time."""
    try:
        return os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError):
        return 100


_CLK = _clock_ticks()
_TELEMETRY = re.compile(r"TELEMETRY run=(\S+) kind=(\S+) unit=(\S+) key=(\S+)(?: role=(\S+))?")


def read_run_info(runs_dir: Path, run: str) -> dict | None:
    """`runs/<run>/run.json`; `BadName` when `run` is not a plain name."""
    path = under(runs_dir, run, "run.json", what="run id")
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def is_alive(info: dict | None) -> bool:
    """True when the recorded pid is still the process that started the run."""
    if not info or not info.get("pid") or info.get("finished_at"):
        return False
    return procfs.pid_identity_ok(int(info["pid"]), info.get("start_ticks"))


def live_runs(runs_dir: Path) -> set[str]:
    out = set()
    try:
        dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    except OSError:
        return out
    for d in dirs:
        try:
            info = read_run_info(runs_dir, d.name)
        except BadName:
            continue
        if is_alive(info):
            out.add(d.name)
    return out


def _boot_time() -> int:
    try:
        with open("/proc/stat") as f:
            return int(next(line.split()[1] for line in f if line.startswith("btime")))
    except (OSError, StopIteration, ValueError):
        return 0


def _environ(pid: int) -> dict[str, str]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    out = {}
    for item in raw.split(b"\0"):
        k, _, v = item.partition(b"=")
        if k.startswith(b"CONTRAAGENT_"):
            out[k.decode()] = v.decode(errors="replace")
    return out


def _scan() -> dict[int, dict]:
    btime, now = _boot_time(), time.time()
    procs: dict[int, dict] = {}
    for name in filter(str.isdigit, os.listdir("/proc")):
        pid = int(name)
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


def empty_snapshot(run: str, info: dict | None, alive: bool) -> dict:
    """A snapshot with no processes: what `run.json` says about the run, and whether it is live."""
    return {
        "run": run,
        "alive": alive,
        "pid": (info or {}).get("pid"),
        "argv": (info or {}).get("argv", []),
        "started_at": (info or {}).get("started_at", ""),
        "max_workers": (info or {}).get("max_workers"),
        "run_group": (info or {}).get("run_group", run),
        "launches": [],
        "tree": [],
        "python_tasks": [],
    }


def snapshot(runs_dir: Path, run: str) -> dict:
    """Live processes of one run: its agent launches, the full tree, and running Python tasks."""
    info = read_run_info(runs_dir, run)
    alive = is_alive(info)
    out = empty_snapshot(run, info, alive)
    if not alive or info is None:
        return out
    procs = _scan()
    by_ppid: dict[int, list[dict]] = {}
    for p in procs.values():
        by_ppid.setdefault(p["ppid"], []).append(p)

    def node(p: dict, depth: int, parent_key: str) -> dict:
        env = _environ(p["pid"])
        key = env.get(envvars.TASK, "")
        n = {"pid": p["pid"], "age_s": p["age_s"], "cmd": _short(p["cmd"]), "full_cmd": p["cmd"]}
        if key and key != parent_key and env.get(envvars.RUN, run) == run:
            tele = _TELEMETRY.search(p["cmd"])
            n.update(
                {
                    "key": key,
                    "kind": env.get(envvars.KIND, ""),
                    "unit": env.get(envvars.UNIT, ""),
                    "role": tele.group(5) or "" if tele else "",
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
    for m in _inflight(runs_dir, run):
        if m.pop("executor") == "python":
            out["python_tasks"].append(m)
        elif m["key"] not in seen:
            out["launches"].append({**m, "cmd": "", "full_cmd": "", "children": [], "role": "", "model": "", "plugin": ""})
    return out


def _inflight(runs_dir: Path, run: str) -> list[dict]:
    """Tasks running inside the run's own process, from their in-flight markers.
    A marker whose process is gone is ignored."""
    out = []
    d = under(runs_dir, run, "inflight", what="run id")
    if not d.is_dir():
        return out
    now = time.time()
    for marker in sorted(d.glob("*.json")):
        try:
            m = json.loads(marker.read_text())
        except (OSError, ValueError):
            continue
        pid = int(m.get("pid") or 0)
        if not pid or procfs.read_proc_stat(pid) is None:
            continue
        try:
            from datetime import datetime

            started = datetime.fromisoformat(m.get("started_at", "")).timestamp()
        except ValueError:
            started = 0.0
        out.append(
            {
                "key": m.get("key", ""),
                "kind": m.get("kind", ""),
                "unit": m.get("unit", ""),
                "pid": pid,
                "executor": m.get("executor") or "agent",
                "age_s": round(now - started) if started else 0,
            }
        )
    return out
