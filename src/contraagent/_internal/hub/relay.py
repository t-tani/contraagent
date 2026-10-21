"""`contraagent relay`: ship one host's runs to a hub, incrementally, at least once.

    contraagent relay --runs-dir runs --hub http://hub:8790 --token-file hub.token

Each pass (`Relay.pass_once`) reads every run under the runs directory through its run
source (`DirectorySource`; `contraagent._internal.runs.layout` names the records), and sends the hub
what it does not hold yet:

* **Logs** (`RunSource.logs`: `layout.LOGS`, the transcripts, the pipeline logs
  `pipeline/<name>.jsonl`): complete lines only (a trailing line without its newline waits
  for the next pass), from the line the hub holds on, read from a kept position
  (`RunSource.lines_at`) so a long transcript is not read again each pass. A request carries at
  most `batch_bytes` of lines (a longer line goes alone) and `batch_lines` lines.
* **Documents** (`RunSource.documents`: `run.json`, `cursor.json`, and the files in
  `contracts/`, `definitions/`, `calls/`, `inflight/`, `pipeline/`): a document whose
  content changed; `text: null` for one that is gone. One that does not parse as JSON is
  not sent: a document is replaced whole (`write_document`), never seen half written, so
  it is broken. The relay logs a warning once for that content and sends the document
  when it parses again.
* **Files a contract names** (`outputs[].path`, `inputs[].path`): when their content,
  size or modification time changed, their content as a blob (`has_blob`, `put_blob`) and a
  `FileRef`; `sha256: null` for a missing one. A relative path is under the run's `cwd`
  in `run.json` (`layout.file_path`).

Every `interval_s` seconds a heartbeat (`Relay.heartbeat_once`) reports the runs this
host's liveness (`ProcLiveness`) counts live, with their process snapshots.

Between passes, every `FAST_S` seconds, the relay ships the new lines of the active
transcripts only (`Relay.fast_once`), so a transcript being written reaches the hub well
within a second while everything else waits for the next pass. A transcript is active
while its run was live at the last heartbeat and its task is running (an in-flight marker
in the run, or a process of the task in the heartbeat's snapshot), or while its file was
written in the last `ACTIVE_S` seconds. Each run's fast request is bounded as a pass's
requests are; what does not fit goes in the next one. `Relay.serve` runs the heartbeat,
the passes and the fast path until it is stopped.

The relay's progress, where the hub is up to in each run (each log's line and byte
offset, each document's SHA-256, each file's size, modification time and SHA-256), is a
JSON file kept next to the runs directory (`<runs-dir>.relay.json`), never inside a run,
so a restarted relay continues where it stopped. The hub stays the authority:
`Accepted.logs` corrects the relay's offsets, and when the hub holds fewer lines than the
relay sent before (a hub that lost data, or a new hub) the relay sends the run again
from what the hub holds, documents and files included. On its first pass, after an
outage, and every `resync_s` seconds, the relay's first request for each run names each
log it sent before, with no lines, so the hub says what it holds.

When the hub does not take a request (`client.HubUnavailable`) the pass stops; the relay
logs it once per outage and waits longer each time (`Relay.delay`, up to
`MAX_BACKOFF_S`). A refused token (`client.HubRefused`, HTTP 401 or 403) is logged as an
error and retried only every `MAX_BACKOFF_S`. The run directories are the buffer: nothing is lost while the hub is
down. Logging is under `contraagent._internal.hub.relay`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contraagent._internal.commandline import UsageError, add_runs_dir, setup_logging
from contraagent._internal.hub.client import HttpClient, HubClient, HubRefused, HubUnavailable
from contraagent._internal.hub.protocol import Accepted, DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import parse_rows, read_document, write_document
from contraagent._internal.runs.liveness import Liveness
from contraagent._internal.runs.procs import ProcLiveness
from contraagent._internal.runs.source import DirectorySource, LogPosition
from contraagent._internal.runs.times import iso_of

_logger = logging.getLogger(__name__)

#: The environment variable that holds the ingest token when `--token-file` is not given.
TOKEN_ENV = "CONTRAAGENT_HUB_TOKEN"
#: The longest wait between passes while the hub is unavailable, in seconds.
MAX_BACKOFF_S = 60.0
#: Seconds between the requests that ask the hub what it holds of each run.
RESYNC_S = 60.0
#: At most this many bytes of log lines in one request (a longer line goes alone).
BATCH_BYTES = 1 << 20
#: At most this many log lines in one request.
BATCH_LINES = 5000
#: Seconds between two looks at the active transcripts (`Relay.fast_once`).
FAST_S = 0.25
#: A transcript written within this many seconds is active.
ACTIVE_S = 5.0
#: Seconds between two writes of the progress file during a long pass.
_SAVE_EVERY_S = 5.0


def default_progress_path(runs_dir: str | Path) -> Path:
    """`<runs-dir>.relay.json`, next to the runs directory."""
    runs = Path(runs_dir).resolve()
    return runs.with_name(runs.name + ".relay.json")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the relay's progress ----------------------------------------------------------------


@dataclass
class RunProgress:
    """Where the hub is up to in one run, as far as the relay knows."""

    run_uid: str
    #: log name -> [lines the hub holds, byte offset after them]
    logs: dict[str, list[int]] = field(default_factory=dict)
    #: document name -> SHA-256 of the text the hub holds
    documents: dict[str, str] = field(default_factory=dict)
    #: file path -> [size, modification time in ns, SHA-256], or None for a missing file
    files: dict[str, list | None] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"run_uid": self.run_uid, "logs": self.logs, "documents": self.documents, "files": self.files}

    @classmethod
    def from_json(cls, data: dict) -> RunProgress:
        return cls(
            run_uid=str(data["run_uid"]),
            logs={k: [int(v[0]), int(v[1])] for k, v in dict(data.get("logs", {})).items()},
            documents={k: str(v) for k, v in dict(data.get("documents", {})).items()},
            files=dict(data.get("files", {})),
        )


@dataclass
class _Pending:
    """One run's records for the next request."""

    documents: list[DocumentPut] = field(default_factory=list)
    doc_shas: dict[str, str | None] = field(default_factory=dict)
    files: list[FileRef] = field(default_factory=list)
    file_stats: dict[str, list | None] = field(default_factory=dict)
    chunks: list[LogChunk] = field(default_factory=list)
    ends: dict[str, int] = field(default_factory=dict)

    def empty(self) -> bool:
        return not (self.documents or self.files or self.chunks)


class Relay:
    """Ships the runs under `runs_dir` to a hub through `client`.

    `progress_path` is the relay's progress file (`default_progress_path`); `host_id`
    names this host on the hub (default `layout.host_id()`); `hub` is written into the
    progress file, and progress kept for another hub or host is not used. `interval_s` is
    the heartbeat's interval and the wait between passes; `since_days`, when set, leaves
    out the runs the relay has not shipped yet whose records last changed longer ago than
    that. `liveness` says which runs are live (default `ProcLiveness(runs_dir)`), `clock`
    is the time in seconds since the epoch.
    """

    def __init__(
        self,
        client: HubClient,
        runs_dir: str | Path,
        progress_path: str | Path | None = None,
        *,
        host_id: str | None = None,
        hub: str = "",
        interval_s: float = 3.0,
        since_days: float | None = None,
        liveness: Liveness | None = None,
        clock: Callable[[], float] = time.time,
        resync_s: float = RESYNC_S,
        batch_bytes: int = BATCH_BYTES,
        batch_lines: int = BATCH_LINES,
    ) -> None:
        self.client = client
        self.runs_dir = Path(runs_dir).resolve()
        self.source = DirectorySource(self.runs_dir)
        self.progress_path = Path(progress_path) if progress_path is not None else default_progress_path(self.runs_dir)
        self.host_id = host_id or layout.host_id()
        self.hub = hub
        self.interval_s = interval_s
        self.since_days = since_days
        self.liveness: Liveness = liveness if liveness is not None else ProcLiveness(self.runs_dir)
        self.clock = clock
        self.resync_s = resync_s
        self.batch_bytes = batch_bytes
        self.batch_lines = batch_lines
        self.failures = 0
        self._down = False
        self._refused = False
        self._lock = threading.Lock()
        self._next_resync = 0.0
        self._unreadable: set[tuple[str, str, str]] = set()  # (run, document, SHA-256) warned about
        self._reported: set[tuple[str, str]] = set()
        #: run -> the keys of its running tasks, for each run live at the last heartbeat
        self._running: dict[str, set[str]] = {}
        self.runs: dict[str, RunProgress] = self._load()

    # --- progress file ---

    def _load(self) -> dict[str, RunProgress]:
        try:
            data = json.loads(read_document(self.progress_path))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            _logger.warning("progress file %s is unreadable (%s); starting from what the hub holds", self.progress_path, exc)
            return {}
        if not isinstance(data, dict) or data.get("hub", "") != self.hub or data.get("host_id") != self.host_id:
            _logger.info("progress file %s is for another hub or host; starting from what the hub holds", self.progress_path)
            return {}
        out = {}
        for run, item in dict(data.get("runs", {})).items():
            try:
                out[run] = RunProgress.from_json(item)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        return out

    def save(self) -> None:
        """Write the progress file atomically."""
        data = {"hub": self.hub, "host_id": self.host_id, "runs": {r: p.to_json() for r, p in sorted(self.runs.items())}}
        try:
            self.progress_path.parent.mkdir(parents=True, exist_ok=True)
            write_document(self.progress_path, json.dumps(data, separators=(",", ":")))
        except OSError as exc:
            _logger.warning("cannot write the progress file %s: %s", self.progress_path, exc)

    # --- hub calls and outages ---

    def _call(self, fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return fn(*args)
        except HubUnavailable:
            raise
        except Exception as exc:
            raise HubUnavailable(f"{type(exc).__name__}: {exc}") from exc

    def _failed(self, exc: Exception) -> None:
        with self._lock:
            refused = isinstance(exc, HubRefused)
            if isinstance(exc, HubRefused) and not self._refused:
                what = "the ingest token" if exc.status == 401 else "the ingest token's host and --host-id"
                _logger.error("hub refused the relay, retrying every %.0fs; check %s: %s", MAX_BACKOFF_S, what, exc)
            elif not refused and not self._down:
                _logger.warning("hub unavailable, retrying with backoff: %s", exc)
            self._down = True
            self._refused = refused

    def _reached(self) -> None:
        with self._lock:
            if self._down:
                _logger.info("hub reachable again")
                self._next_resync = 0.0
            self._down = False
            self._refused = False

    def delay(self) -> float:
        """Seconds to wait before the next pass: `interval_s`, doubled for each pass in a
        row the hub did not take, up to `MAX_BACKOFF_S`; `MAX_BACKOFF_S` at once while the
        hub refuses the relay's token (`HubRefused`)."""
        if not self.failures:
            return self.interval_s
        if self._refused:
            return max(MAX_BACKOFF_S, self.interval_s)
        return min(self.interval_s * 2 ** min(self.failures, 16), max(MAX_BACKOFF_S, self.interval_s))

    def heartbeat_delay(self) -> float:
        """Seconds to wait before the next heartbeat: `interval_s`; `MAX_BACKOFF_S` while
        the hub refuses the relay's token."""
        return max(MAX_BACKOFF_S, self.interval_s) if self._refused else self.interval_s

    # --- one pass ---

    def pass_once(self) -> bool:
        """Send every run's changes; True when the hub took every request. Never raises."""
        resync = self.clock() >= self._next_resync
        ok = True
        last_save = time.monotonic()
        try:
            runs = self.source.runs()
            for run in runs:
                try:
                    self._ship(run, resync)
                except HubUnavailable as exc:
                    self._failed(exc)
                    ok = False
                    break
                except Exception as exc:
                    key = (run, repr(exc))
                    if key not in self._reported:
                        self._reported.add(key)
                        _logger.exception("run %s: not shipped this pass", run)
                if time.monotonic() - last_save >= _SAVE_EVERY_S:
                    self.save()
                    last_save = time.monotonic()
            if ok and self.runs_dir.is_dir():
                for gone in set(self.runs) - set(runs):
                    del self.runs[gone]
        except Exception:
            _logger.exception("pass failed")
            ok = False
        self.save()
        if ok:
            self.failures = 0
            self._reached()
            if resync:
                self._next_resync = self.clock() + self.resync_s
        else:
            self.failures += 1
        return ok

    def _eligible(self, run: str) -> bool:
        if self.since_days is None:
            return True
        times = [st.mtime_ns / 1e9 for name in ("", layout.RUN_INFO, *layout.LOGS) if (st := self.source.stat(run, name)) is not None]
        return bool(times) and max(times) >= self.clock() - self.since_days * 86400

    def _ship(self, run: str, resync: bool) -> None:
        info = self.source.info(run)
        if info is None:
            return  # none yet, or half written: the next pass
        uid = str(info.get("run_uid") or run)
        prog = self.runs.get(run)
        if prog is not None and prog.run_uid != uid:
            _logger.info("run %s: a new run_uid %s, shipped again", run, uid)
            prog = None
        if prog is None:
            if not self._eligible(run):
                return
            prog = RunProgress(run_uid=uid)
            resync = False  # nothing sent before: nothing to ask about
        ref = RunRef(host_id=self.host_id, run_id=run, run_uid=uid)
        whole = True
        probe = resync
        resent = False
        while True:
            pending = _Pending()
            if whole:
                self._documents(run, prog, pending)
                self._files(run, prog, pending)
            self._logs(run, prog, pending, probe)
            if pending.empty():
                break
            batch = RecordBatch(run=ref, logs=pending.chunks, documents=pending.documents, files=pending.files)
            accepted: Accepted = self._call(self.client.send_records, batch)
            if run not in self.runs:
                _logger.info("run %s: shipping to the hub as %s", run, ref.name)
            self.runs[run] = prog
            for name, sha in pending.doc_shas.items():
                if sha is None:
                    prog.documents.pop(name, None)
                else:
                    prog.documents[name] = sha
            prog.files.update(pending.file_stats)
            before = {k: tuple(v) for k, v in prog.logs.items()}
            lost = self._accept(run, prog, pending, accepted) and not resent
            if lost:
                _logger.info("run %s: the hub holds less than it took before; sending the run again", run)
                prog.documents.clear()
                prog.files.clear()
                resent = True
            elif not (pending.documents or pending.files) and before == {k: tuple(v) for k, v in prog.logs.items()}:
                break  # the hub took no line of this request: the next pass tries again
            whole = lost
            probe = False

    def _documents(self, run: str, prog: RunProgress, pending: _Pending) -> None:
        present = set()
        for name in self.source.documents(run):
            text = self.source.document(run, name)
            if text is None:
                continue
            present.add(name)
            sha = _sha(text.encode())
            if prog.documents.get(name) == sha:
                continue
            try:
                json.loads(text)
            except ValueError as exc:
                if (run, name, sha) not in self._unreadable:
                    self._unreadable.add((run, name, sha))
                    _logger.warning("run %s: %s is not JSON (%s); not sent until it is", run, name, exc)
                continue
            pending.documents.append(DocumentPut(name=name, text=text))
            pending.doc_shas[name] = sha
        for name in sorted(set(prog.documents) - present):
            pending.documents.append(DocumentPut(name=name, text=None))
            pending.doc_shas[name] = None

    def _files(self, run: str, prog: RunProgress, pending: _Pending) -> None:
        for path in layout.contract_paths(self.source.folder(run, layout.CONTRACTS)):
            st = self.source.file_stat(run, path)
            if st is None:
                if path in prog.files and prog.files[path] is None:
                    continue
                pending.files.append(FileRef(path=path, sha256=None))
                pending.file_stats[path] = None
                continue
            stat = [st.size, st.mtime_ns]
            got = self.source.file(run, path)
            if got is None:
                continue
            sha = _sha(got.data)
            if prog.files.get(path) == [*stat, sha]:
                continue
            if not self._call(self.client.has_blob, sha):
                self._call(self.client.put_blob, sha, got.data)
            pending.files.append(FileRef(path=path, sha256=sha, size=got.size, mtime=st.mtime))
            pending.file_stats[path] = [*stat, sha]

    def _logs(self, run: str, prog: RunProgress, pending: _Pending, probe: bool, names: list[str] | None = None) -> None:
        budget_bytes, budget_lines = self.batch_bytes, self.batch_lines
        for log in self.source.logs(run) if names is None else names:
            held = prog.logs.get(log)
            lines_at, byte_at = held if held is not None else (0, 0)
            st = self.source.stat(run, log)
            if st is None:
                continue
            if st.size < byte_at:
                _logger.warning("run %s: %s is shorter than the part already sent; sending it from its start", run, log)
                lines_at, byte_at = 0, 0
            lines: list[str] = []
            end = byte_at
            if st.size > byte_at and budget_lines > 0 and (budget_bytes > 0 or not pending.chunks):
                lines, after = self.source.lines_at(run, log, LogPosition(lines_at, byte_at), budget_lines, max(budget_bytes, 1))
                end = after.offset
                budget_bytes -= end - byte_at
                budget_lines -= len(lines)
            if lines or held is None or probe:
                # A log new to the hub is named even while empty, so the hub has it too.
                pending.chunks.append(LogChunk(log=log, offset=lines_at, lines=lines))
                pending.ends[log] = end

    def _accept(self, run: str, prog: RunProgress, pending: _Pending, accepted: Accepted) -> bool:
        """Take the hub's line counts as the logs' offsets; True when the hub holds fewer
        lines of a log than before this request (it lost data)."""
        lost = False
        for chunk in pending.chunks:
            held = accepted.logs.get(chunk.log)
            if held is None:
                continue
            sent_to = chunk.offset + len(chunk.lines)
            if held == sent_to:
                prog.logs[chunk.log] = [sent_to, pending.ends[chunk.log]]
                continue
            if held < chunk.offset:
                lost = True
            prog.logs[chunk.log] = list(self.source.position(run, chunk.log, held))
        return lost

    # --- the fast path: active transcripts ---

    def _active(self, run: str, running: set[str]) -> list[str]:
        """The run's active transcripts (see the module's docstring), by layout name."""
        keys = set(running)
        for marker in parse_rows(self.source.folder(run, layout.INFLIGHT)):
            if isinstance(marker.get("key"), str):
                keys.add(marker["key"])
        names = {layout.file_name(k) for k in keys}
        recent = self.clock() - ACTIVE_S
        out = []
        for log in self.source.logs(run):
            name = layout.stream_name(log)
            if name is None:
                continue
            if name in names or ((st := self.source.stat(run, log)) is not None and st.mtime_ns / 1e9 >= recent):
                out.append(log)
        return out

    def fast_once(self) -> bool:
        """Send the new lines of every active transcript of the runs the hub already holds,
        one bounded request per run; True when the hub took every request. A run the
        relay has not shipped, or whose `run_uid` changed, waits for the next pass. Never
        raises."""
        with self._lock:
            running = {run: set(keys) for run, keys in self._running.items()}
        for run, keys in sorted(running.items()):
            prog = self.runs.get(run)
            if prog is None:
                continue
            try:
                info = self.source.info(run)
                if not isinstance(info, dict) or str(info.get("run_uid") or run) != prog.run_uid:
                    continue
                names = self._active(run, keys)
                if not names:
                    continue
                pending = _Pending()
                self._logs(run, prog, pending, False, names)
                if pending.empty():
                    continue
                ref = RunRef(host_id=self.host_id, run_id=run, run_uid=prog.run_uid)
                accepted: Accepted = self._call(self.client.send_records, RecordBatch(run=ref, logs=pending.chunks))
                if self._accept(run, prog, pending, accepted):
                    # The hub lost data: the next pass sends the run's documents and files again.
                    prog.documents.clear()
                    prog.files.clear()
            except HubUnavailable as exc:
                self._failed(exc)
                return False
            except Exception as exc:
                key = (run, repr(exc))
                if key not in self._reported:
                    self._reported.add(key)
                    _logger.exception("run %s: active transcripts not shipped", run)
        return True

    def serve(self, stop: threading.Event) -> None:
        """Send heartbeats (in a thread of their own), passes and the fast path until `stop`
        is set: a pass every `delay()` seconds, the fast path every `FAST_S` seconds in
        between while the hub takes requests."""

        def beat() -> None:
            while not stop.is_set():
                self.heartbeat_once()
                stop.wait(self.heartbeat_delay())

        beats = threading.Thread(target=beat, name="relay-heartbeat", daemon=True)
        beats.start()
        next_pass = 0.0
        while not stop.is_set():
            if time.monotonic() >= next_pass:
                self.pass_once()
                next_pass = time.monotonic() + self.delay()
            elif not self.failures:
                self.fast_once()
            stop.wait(max(0.0, min(FAST_S, next_pass - time.monotonic())))
        beats.join(timeout=1.0)

    # --- heartbeat ---

    def heartbeat_once(self) -> bool:
        """Send a heartbeat with the live runs and their snapshots; True when the hub took it.
        Never raises."""
        try:
            reports = []
            running: dict[str, set[str]] = {}
            for run in sorted(self.liveness.live()):
                info = self.source.info(run)
                if not isinstance(info, dict):
                    continue
                ref = RunRef(host_id=self.host_id, run_id=run, run_uid=str(info.get("run_uid") or run))
                snapshot = self.liveness.snapshot(run)
                tasks = [*snapshot.get("launches", []), *snapshot.get("python_tasks", [])]
                running[run] = {str(t["key"]) for t in tasks if t.get("key")}
                reports.append(RunLiveness(run=ref, alive=True, snapshot=snapshot))
            with self._lock:
                self._running = running
            beat = Heartbeat(host_id=self.host_id, sent_at=iso_of(self.clock(), "milliseconds"), interval_s=self.interval_s, runs=reports)
        except Exception:
            _logger.exception("heartbeat not built")
            return False
        try:
            self._call(self.client.send_heartbeat, beat)
        except HubUnavailable as exc:
            self._failed(exc)
            return False
        self._reached()
        return True


# --- command line ------------------------------------------------------------------------


def add_arguments(ap: argparse.ArgumentParser) -> None:
    """`contraagent relay`."""
    ap.description = (
        "Ship every run under a runs directory to a contraagent hub, incrementally, and send a heartbeat "
        "with the live runs. The ingest token comes from --token-file, else the environment variable "
        f"{TOKEN_ENV}; it is never a command line argument."
    )
    add_runs_dir(ap, "the runs directory to ship (default: runs)")
    ap.add_argument("--hub", required=True, help="the hub's address, for example http://hub:8790")
    ap.add_argument("--token-file", help=f"a file holding the hub's ingest token (default: the environment variable {TOKEN_ENV})")
    ap.add_argument("--host-id", help=f"this host's name on the hub (default: {layout.HOST_ID_ENV}, else the host name)")
    ap.add_argument("--interval", type=float, default=3.0, help="seconds between heartbeats and between passes (default: 3)")
    ap.add_argument(
        "--since",
        type=float,
        metavar="DAYS",
        help="of the runs not shipped yet, ship only those whose records changed in the last DAYS days (default: every run)",
    )
    ap.add_argument("--once", action="store_true", help="make one full pass, then exit: 0 when the hub took everything, else 1")
    ap.add_argument(
        "--progress-file",
        help="where the relay keeps how far the hub is in each run (default: <runs-dir>.relay.json, next to the runs directory)",
    )
    ap.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for each request to the hub (default: 30)")


def _token(args: argparse.Namespace) -> str:
    if args.token_file:
        try:
            return Path(args.token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise UsageError(f"cannot read --token-file: {exc}") from None
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise UsageError(f"no ingest token: give --token-file or set {TOKEN_ENV}")
    return token


def run(args: argparse.Namespace) -> int:
    """`contraagent relay`: ship until stopped, or make one pass (`--once`)."""
    if args.interval <= 0:
        raise UsageError("--interval must be more than 0")
    token = _token(args)
    setup_logging("%(asctime)s %(name)s %(levelname)s %(message)s")
    client = HttpClient(args.hub, token, args.timeout)
    relay = Relay(
        client,
        args.runs_dir,
        args.progress_file,
        host_id=args.host_id,
        hub=client.base_url,
        interval_s=args.interval,
        since_days=args.since,
    )
    try:
        if args.once:
            return 0 if relay.pass_once() else 1
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        _logger.info("shipping %s to %s as host %s", relay.runs_dir, client.base_url, relay.host_id)
        relay.serve(stop)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        relay.save()
        client.close()
