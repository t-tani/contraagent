"""Hub retention on the command line: `contraagent hub --retain-days N [--prune-every H]`
runs `Hub.prune` in a thread on a schedule, and `contraagent hub prune` runs it once."""

import argparse
import dataclasses
import hashlib
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from contraagent._internal.cli import main as cli_main
from contraagent._internal.commandline import UsageError
from contraagent._internal.hub import server
from contraagent._internal.hub.core import Hub, PruneReport
from contraagent._internal.hub.protocol import DocumentPut, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent._internal.hub.retention import Pruner, default_prune_every, report_line
from contraagent._internal.hub.store import DirectoryBlobs, MemoryBlobs, MemoryHubStore
from contraagent._internal.runs import layout

NOW = datetime.now(UTC)
OLD = NOW - timedelta(days=40)
RECENT = NOW - timedelta(days=1)


def iso(at: datetime) -> str:
    return at.isoformat(timespec="milliseconds")


def ship(store: MemoryHubStore, run_id: str, at: datetime, host: str = "h1") -> str:
    ref = RunRef(host_id=host, run_id=run_id, run_uid=f"uid-{run_id}")
    journal = LogChunk(log=layout.JOURNAL, offset=0, lines=['{"key": "summarize-a", "ok": true}'])
    docs = [DocumentPut(name=layout.RUN_INFO, text=f'{{"run_id": "{run_id}"}}')]
    store.put_batch(RecordBatch(run=ref, logs=[journal], documents=docs), iso(at))
    return ref.name


def heartbeat(store: MemoryHubStore, host: str, at: datetime, alive: list[str]) -> None:
    runs = [RunLiveness(run=RunRef(host_id=host, run_id=r, run_uid=f"uid-{r}"), alive=True, snapshot={}) for r in alive]
    store.put_heartbeat(Heartbeat(host_id=host, sent_at=iso(at), interval_s=3, runs=runs), iso(at))


# --- arguments -----------------------------------------------------------------------------


def _days(flag, environ):
    return server.retain_days(flag, environ)


def test_retain_days_come_from_the_flag_then_the_environment_and_default_to_keeping_everything():
    assert _days(server._UNSET, {}) is None
    assert _days(server._UNSET, {server.RETENTION_ENV: ""}) is None
    assert _days(server._UNSET, {server.RETENTION_ENV: "30"}) == 30
    assert _days(12.0, {server.RETENTION_ENV: "30"}) == 12
    assert _days(None, {server.RETENTION_ENV: "30"}) is None  # `--retain-days=` given empty: keep everything


def test_retain_days_that_are_not_a_positive_number_are_refused():
    with pytest.raises(UsageError, match=server.RETENTION_ENV):
        _days(server._UNSET, {server.RETENTION_ENV: "thirty"})
    for bad in ("0", "-1", "x"):
        with pytest.raises(argparse.ArgumentTypeError):
            server._days(bad)
    assert server._days("") is None and server._days("0.5") == 0.5


def test_the_cadence_is_daily_or_hourly_under_a_week():
    assert default_prune_every(30) == 24
    assert default_prune_every(7) == 24
    assert default_prune_every(6.9) == 1
    assert default_prune_every(1) == 1


def test_prune_every_needs_a_retention(tmp_path, monkeypatch):
    monkeypatch.delenv(server.RETENTION_ENV, raising=False)
    (tmp_path / "tokens").write_text("t\n")
    with pytest.raises(SystemExit) as exc:
        cli_main(["hub", "--ingest-token-file", str(tmp_path / "tokens"), "--prune-every", "2"])
    assert exc.value.code == 2


# --- the thread ----------------------------------------------------------------------------


class CountingHub(Hub):
    """A hub whose `prune` fails on the calls in `failing` and counts the rest."""

    def __init__(self, failing: set[int]) -> None:
        super().__init__(MemoryHubStore(), MemoryBlobs())
        self.failing = failing
        self.calls = 0
        self.called = threading.Event()

    def prune(self, **kwargs) -> PruneReport:
        self.calls += 1
        if self.calls >= 3:
            self.called.set()
        if self.calls in self.failing:
            raise ConnectionError("the store went away")
        return super().prune(**kwargs)


def test_the_thread_prunes_on_schedule_survives_an_exception_and_stops(caplog):
    hub = CountingHub(failing={1})
    pruner = Pruner(hub, older_than=timedelta(days=30), every_s=0.02, first_after_s=0.0)
    with caplog.at_level(logging.INFO, logger="contraagent._internal.hub.retention"):
        pruner.start()
        assert hub.called.wait(10)
        pruner.stop()
    assert hub.calls >= 3
    assert any("prune failed" in r.message and r.exc_info for r in caplog.records)
    assert any(r.message.startswith("prune cutoff=") for r in caplog.records)
    calls = hub.calls
    time.sleep(0.1)
    assert hub.calls == calls  # stopped


def test_the_first_prune_waits_and_stop_ends_the_wait():
    hub = CountingHub(failing=set())
    pruner = Pruner(hub, older_than=timedelta(days=30), every_s=3600, first_after_s=3600)
    pruner.start()
    time.sleep(0.05)
    began = time.monotonic()
    pruner.stop()
    assert time.monotonic() - began < 1 and hub.calls == 0


def test_a_round_removes_old_runs_and_sweeps_the_transcript_store(tmp_path):
    pytest.importorskip("zstandard")
    streams = server.open_streams(str(tmp_path / "hot"), None, "memory", background=False)
    hub = Hub(MemoryHubStore(), MemoryBlobs(), streams=streams)
    try:
        assert isinstance(hub.store, MemoryHubStore)
        old, recent = ship(hub.store, "old", OLD), ship(hub.store, "recent", RECENT)
        report = Pruner(hub, older_than=timedelta(days=30), every_s=1, now=lambda: NOW).run_once()
    finally:
        streams.shutdown()  # type: ignore[attr-defined]
    assert report is not None and report.runs == [old]
    assert [e.name for e in hub.store.runs()] == [recent]


def test_the_log_line_counts_what_was_removed_and_kept():
    report = PruneReport(
        dry_run=False,
        cutoff="2026-09-14T00:00:00.000+00:00",
        runs=["a@h", "b@h"],
        segments=["k1", "k2", "k3"],
        blobs=["s1"],
        blob_bytes=2048,
        heartbeats=["h"],
        kept_runs={"c@h": "live", "d@h": "unresponsive", "e@h": "live"},
        kept_heartbeats={"h3": "unresponsive run"},
    )
    assert report_line(report, swept=4) == (
        "prune cutoff=2026-09-14T00:00:00.000+00:00"
        " | removed runs=2 transcripts=0 segments=3 blobs=1 blob_bytes=2048 heartbeats=1"
        " | kept runs: live=2 unresponsive=1 no-activity=0 | kept heartbeats=1 | swept segments=4"
    )
    assert report_line(dataclasses.replace(report, dry_run=True)).startswith("prune (dry run) cutoff=")


# --- `contraagent hub prune` ---------------------------------------------------------------


@pytest.fixture
def populated(tmp_path, monkeypatch):
    """A memory store with an old, a recent and an old but live run, and directory blobs
    with one old blob no run references; `open_store` returns that store."""
    store = MemoryHubStore()
    names = {
        "old": ship(store, "old", OLD),
        "recent": ship(store, "recent", RECENT),
        "live": ship(store, "live", OLD, host="h2"),
    }
    heartbeat(store, "h2", datetime.now(UTC), alive=["live"])
    blobs = DirectoryBlobs(tmp_path / "blobs")
    data = b"an orphan"
    sha = hashlib.sha256(data).hexdigest()
    blobs.put(sha, data)
    for path in (tmp_path / "blobs").rglob("*"):
        if path.is_file():
            os.utime(path, (OLD.timestamp(), OLD.timestamp()))
    monkeypatch.setattr(server, "open_store", lambda spec: store)
    monkeypatch.delenv(server.RETENTION_ENV, raising=False)
    return store, blobs, names, sha, ["--blobs", f"dir:{tmp_path / 'blobs'}"]


def test_hub_prune_dry_run_prints_the_report_and_changes_nothing(populated, capsys):
    store, blobs, names, sha, argv = populated
    assert cli_main(["hub", "prune", "--retain-days", "30", "--dry-run", *argv]) == 0
    out = capsys.readouterr()
    assert "dry run: nothing removed" in out.out
    assert "Would remove: runs" in out.out and names["old"] in out.out
    assert f"{names['live']} (live)" in out.out
    assert "one process prunes at a time" in out.err
    assert sorted(e.name for e in store.runs()) == sorted(names.values())
    assert blobs.has(sha)


def test_hub_prune_removes_old_runs_and_prints_json(populated, capsys):
    store, blobs, names, sha, argv = populated
    assert cli_main(["hub", "prune", "--retain-days", "30", "--json", *argv]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is False and report["runs"] == [names["old"]]
    assert report["kept_runs"] == {names["live"]: "live"} and report["blobs"] == [sha]
    assert sorted(e.name for e in store.runs()) == sorted([names["recent"], names["live"]])
    assert not blobs.has(sha)


def test_hub_prune_takes_the_retention_from_the_environment_and_needs_one(populated, monkeypatch, capsys):
    store, _, names, _, argv = populated
    with pytest.raises(SystemExit) as exc:
        cli_main(["hub", "prune", *argv])
    assert exc.value.code == 2
    monkeypatch.setenv(server.RETENTION_ENV, "30")
    assert cli_main(["hub", "prune", *argv]) == 0
    assert names["old"] not in {e.name for e in store.runs()}
    assert "Removed: runs" in capsys.readouterr().out


def test_a_blob_within_its_grace_is_kept(populated, capsys):
    _, blobs, _, sha, argv = populated
    assert cli_main(["hub", "prune", "--retain-days", "30", "--blob-grace-hours", str(24 * 50), *argv]) == 0
    assert blobs.has(sha)


# --- the server ----------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="a graceful stop is SIGTERM, which Windows does not send")
def test_the_server_prunes_in_the_background_and_stops_on_sigterm(tmp_path):
    (tmp_path / "tokens").write_text("t\n")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    argv = [sys.executable, "-m", "contraagent", "hub", "--port", str(port), "--ingest-token-file", str(tmp_path / "tokens")]
    argv += ["--prune-every", str(0.1 / 3600), "--first-prune-after", "0.1"]
    env = {**os.environ, server.RETENTION_ENV: "30"}
    hub = subprocess.Popen(argv, stderr=subprocess.PIPE, text=True, env=env)
    try:
        lines = []
        deadline = time.monotonic() + 30
        assert hub.stderr is not None
        while sum(line.startswith("prune cutoff=") for line in lines) < 2:
            assert time.monotonic() < deadline, "".join(lines)
            line = hub.stderr.readline()
            assert line or hub.poll() is None, "".join(lines)
            lines.append(line)
        assert any("retention: runs with no activity for 30 days are removed" in line for line in lines)
        hub.send_signal(signal.SIGTERM)
        assert hub.wait(15) == 0
    finally:
        hub.kill()
        hub.wait()


def test_hub_prune_over_a_streams_dir_keeps_transcripts_on_a_dry_run_and_removes_them_after(populated, tmp_path, capsys):
    pytest.importorskip("zstandard")
    store, _, names, _, argv = populated
    hot = tmp_path / "hot"
    streams = server.open_streams(str(hot), None, "memory", background=False)
    for name in (names["old"], names["recent"]):
        uid = store.entry(name).run_uid  # type: ignore[union-attr]
        streams.append(name, uid, layout.stream("summarize-a"), 0, ["a", "b"], iso(OLD))
        streams.close(name, uid, layout.stream("summarize-a"))
        streams.append(name, uid, layout.stream("summarize-b"), 0, ["open"], iso(OLD))
    streams.shutdown()  # type: ignore[attr-defined]

    def files() -> list[str]:
        return sorted(str(p.relative_to(hot)) for p in hot.rglob("*") if p.is_file())

    before = files()
    assert any("old" in f for f in before) and any(f.startswith("segments") for f in before)
    assert cli_main(["hub", "prune", "--retain-days", "30", "--dry-run", "--streams-dir", str(hot), *argv]) == 0
    assert files() == before
    capsys.readouterr()
    assert cli_main(["hub", "prune", "--retain-days", "30", "--json", "--streams-dir", str(hot), *argv]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["runs"] == [names["old"]] and report["segments"]
    after = files()
    assert not any("old%40h1" in f or "old@h1" in f for f in after) and any("recent" in f for f in after)
