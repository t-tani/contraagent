"""A hub for the monitor's end-to-end tests: the demo's runs shipped from two hosts.

`h1` is up and drives `docs@h1`; `h2` stopped reporting ten minutes ago while it drove
`docs@h2`, so that run has no report from its host. Every agent attempt carries a
subscription reading, so the hosts view has each account's utilization over every run.

    uv run python web/e2e/hub.py --port 18794 [--runs DIR]

Without `--runs` (a `demo-runs` directory), the demo pipeline is run into a temporary
directory first, removed once its runs are shipped. The hub keeps everything in memory
and has no read token.
"""

import argparse
import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn

from contraagent import rundir
from contraagent.hub.core import Hub
from contraagent.hub.protocol import DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent.hub.server import create_hub_app
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.hub.streams import is_stream
from contraagent.monitor.source import DirectorySource

QUIET_S = 600  # how long ago h2 last reported
LIVE = "docs"  # the run each host reports alive


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds")


def demo_runs(where: Path) -> Path:
    """The demo pipeline's runs, written under `where`."""
    from contraagent.docs.examples.demo import run as demo

    old = Path.cwd()
    os.chdir(where)
    try:
        demo.main(["--no-serve", "--fast"])
    finally:
        os.chdir(old)
    return where / "demo-runs"


def with_quota(text: str, credentials: list[str], start: datetime, pct: float) -> str:
    """The journal with a subscription reading on each agent attempt, rising as the run goes."""
    out = []
    for i, line in enumerate(text.splitlines()):
        row = json.loads(line)
        if row.get("executor") != "python" and row.get("stop") not in (None, "skipped", "invalid_input"):
            cred = credentials[i % len(credentials)]
            hot = 30.0 if cred == "ambient" else 0.0
            row["quota"] = [
                {
                    "observed_at": iso(start + timedelta(seconds=i)),
                    "credential": cred,
                    "five_hour_pct": min(99.0, 8 + hot + i * 1.6),
                    "seven_day_pct": min(99.0, pct + hot + i * 0.4),
                    "five_hour_resets_at": iso(start + timedelta(hours=3)),
                    "seven_day_resets_at": iso(start + timedelta(days=4)),
                }
            ]
        out.append(json.dumps(row))
    return "\n".join(out)


def ship(hub: Hub, root: Path, host: str, received: datetime, credentials: list[str], pct: float) -> list[RunRef]:
    """Every record of every run under `root`, as `host`'s relay would send them, received at `received`."""
    source = DirectorySource(root)
    refs = []
    for run in source.runs():
        info = source.info(run) or {}
        ref = RunRef(host_id=host, run_id=run, run_uid=f"{info.get('run_uid') or run}-{host}")
        logs, documents, files = [], [], []
        for path in sorted((root / run).rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(root / run).as_posix()
            text = path.read_text(errors="replace")
            if name == rundir.JOURNAL:
                text = with_quota(text, credentials, received - timedelta(minutes=20), pct)
            if name == rundir.RUN_INFO and run == LIVE:
                text = json.dumps({k: v for k, v in json.loads(text).items() if k != "finished_at"})
            if name.endswith(".jsonl"):
                logs.append(LogChunk(log=name, offset=0, lines=text.splitlines()))
            else:
                documents.append(DocumentPut(name=name, text=text))
        for text in source.folder(run, rundir.CONTRACTS):
            rec = json.loads(text)
            for spec in rec.get("outputs", []) + rec.get("inputs", []):
                p = Path(spec["path"])
                if not p.is_file():
                    files.append(FileRef(path=spec["path"], sha256=None))
                    continue
                data = p.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                hub.put_blob(sha, data)
                files.append(FileRef(path=spec["path"], sha256=sha, size=len(data), mtime=""))
        at = iso(received)
        hub.store.put_batch(RecordBatch(run=ref, logs=[c for c in logs if not is_stream(c.log)], documents=documents, files=files), at)
        for chunk in (c for c in logs if is_stream(c.log)):
            hub.streams.append(ref.name, ref.run_uid, chunk.log, 0, chunk.lines, at)
            hub.streams.close(ref.name, ref.run_uid, chunk.log)
        refs.append(ref)
    return refs


def snapshot(ref: RunRef, started: datetime) -> dict:
    return {
        "pid": 4242,
        "argv": ["python", "pipeline.py"],
        "started_at": iso(started),
        "max_workers": 4,
        "run_group": ref.run_id,
        "launches": [],
        "tree": [],
        "python_tasks": [],
    }


def beat(hub: Hub, host: str, refs: list[RunRef], at: datetime) -> None:
    runs = [RunLiveness(run=r, alive=True, snapshot=snapshot(r, at - timedelta(minutes=20))) for r in refs if r.run_id == LIVE]
    hub.store.put_heartbeat(Heartbeat(host_id=host, sent_at=iso(at), interval_s=3, runs=runs), iso(at))


def main() -> None:
    ap = argparse.ArgumentParser(description="A hub over the demo's runs, shipped from two hosts.")
    ap.add_argument("--port", type=int, default=18794)
    ap.add_argument("--runs", type=Path, help="a demo-runs directory (default: run the demo pipeline)")
    args = ap.parse_args()

    hub = Hub(MemoryHubStore(), MemoryBlobs())
    now = datetime.now(UTC)
    quiet = now - timedelta(seconds=QUIET_S)

    def ship_both(root: Path) -> list[RunRef]:
        h1 = ship(hub, root, "h1", now, ["team-max"], 20.0)
        beat(hub, "h2", ship(hub, root, "h2", quiet, ["team-max", "ambient"], 24.0), quiet)
        return h1

    if args.runs:
        h1 = ship_both(args.runs)
    else:
        with tempfile.TemporaryDirectory(prefix="hub-demo-") as tmp:
            h1 = ship_both(demo_runs(Path(tmp)))

    def keep_h1_up() -> None:
        while True:
            beat(hub, "h1", h1, datetime.now(UTC))
            time.sleep(3)

    threading.Thread(target=keep_h1_up, daemon=True).start()
    app = create_hub_app(hub, ingest_tokens=(), read_token=None, title="contraagent hub")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
