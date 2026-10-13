"""`contraagent relay`: ship one host's runs to a hub, incrementally, at least once.

    contraagent relay --runs-dir runs --hub http://hub:8790 --token-file hub.token

Each pass (`Relay.pass_once`) reads every run under the runs directory, in the layout
`contraagent.rundir` names, and sends the hub what it does not hold yet:

* **Logs** (`rundir.LOGS`, `streams/<key>.stream.jsonl`): complete lines only (a trailing
  line without its newline waits for the next pass), from the line the hub holds on, read
  by byte offset so a long transcript is not read again each pass. A request carries at
  most `batch_bytes` of lines (a longer line goes alone) and `batch_lines` lines.
* **Documents** (`run.json`, `cursor.json`, and the files in `contracts/`,
  `definitions/`, `calls/`, `inflight/`): a document whose content changed; `text: null`
  for one that is gone. One that does not parse as JSON is half written and waits.
* **Files a contract names** (`outputs[].path`, `inputs[].path`): when their size or
  modification time changed, their content as a blob (`has_blob`, `put_blob`) and a
  `FileRef`; `sha256: null` for a missing one. A relative path is taken from the run's
  `cwd` in `run.json`.

Every `interval_s` seconds a heartbeat (`Relay.heartbeat_once`) reports the runs this
host's liveness (`ProcLiveness`) counts live, with their process snapshots.

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
down. Logging is under `contraagent.hub.relay`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contraagent import rundir
from contraagent.hub.client import HttpClient, HubClient, HubRefused, HubUnavailable
from contraagent.hub.protocol import Accepted, DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent.monitor import paths
from contraagent.monitor.source import DirectorySource, Liveness, ProcLiveness

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
#: Seconds between two writes of the progress file during a long pass.
_SAVE_EVERY_S = 5.0
_READ_BLOCK = 1 << 20

#: The folders whose `*.json` files are documents.
_FOLDERS = (rundir.CONTRACTS, rundir.DEFINITIONS, rundir.CALLS, rundir.INFLIGHT)


def default_progress_path(runs_dir: str | Path) -> Path:
    """`<runs-dir>.relay.json`, next to the runs directory."""
    runs = Path(runs_dir).resolve()
    return runs.with_name(runs.name + ".relay.json")


def _iso(ts: float, timespec: str = "seconds") -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec=timespec)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plain(name: str) -> bool:
    try:
        paths.check_name(name)
    except paths.BadName:
        return False
    return True


# --- reading logs by byte offset ---------------------------------------------------------


def read_lines(path: Path, start: int, max_bytes: int = BATCH_BYTES, max_lines: int = BATCH_LINES) -> tuple[list[str], int]:
    """The complete lines of `path` from byte `start` (at a line's start), without their
    newline: at most `max_lines`, and at most `max_bytes` unless the first line alone is
    longer. Returns them and the byte offset after the last one; ([], start) when no
    complete line follows `start`."""
    with open(path, "rb") as f:
        f.seek(start)
        buf = f.read(max_bytes)
        cut = buf.rfind(b"\n")
        while cut < 0:
            more = f.read(_READ_BLOCK)
            if not more:
                return [], start
            found = more.find(b"\n")
            if found >= 0:
                cut = len(buf) + found
            buf += more
        raw = buf[: cut + 1].split(b"\n")[:-1][:max_lines]
    end = start + sum(len(line) + 1 for line in raw)
    # A newline byte is never inside a UTF-8 sequence, so each line decodes on its own.
    return [line.decode("utf-8", errors="replace") for line in raw], end


def seek_line(path: Path, n: int) -> tuple[int, int]:
    """Line `n` of `path`: `(n, byte offset where it starts)`; when the file has fewer
    complete lines, `(their count, byte offset after the last)`."""
    count = pos = after = 0
    if n <= 0:
        return 0, 0
    with open(path, "rb") as f:
        while block := f.read(_READ_BLOCK):
            here = block.count(b"\n")
            if count + here < n:
                count += here
                if here:
                    after = pos + block.rfind(b"\n") + 1
                pos += len(block)
                continue
            at = -1
            for _ in range(n - count):
                at = block.find(b"\n", at + 1)
            return n, pos + at + 1
    return count, after


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
    names this host on the hub (default `rundir.host_id()`); `hub` is written into the
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
        self.host_id = host_id or rundir.host_id()
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
        self._reported: set[tuple[str, str]] = set()
        self.runs: dict[str, RunProgress] = self._load()

    # --- progress file ---

    def _load(self) -> dict[str, RunProgress]:
        try:
            data = json.loads(self.progress_path.read_text())
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
        tmp = self.progress_path.with_name(self.progress_path.name + ".tmp")
        try:
            self.progress_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, separators=(",", ":")))
            tmp.replace(self.progress_path)
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
        times = []
        for name in ("", rundir.RUN_INFO, *rundir.LOGS):
            try:
                times.append(self.source.path(run, name).stat().st_mtime)
            except OSError:
                continue
        return bool(times) and max(times) >= self.clock() - self.since_days * 86400

    def _ship(self, run: str, resync: bool) -> None:
        info_bytes = self._read(run, rundir.RUN_INFO)
        try:
            info = json.loads(info_bytes) if info_bytes is not None else None
        except ValueError:
            return  # half written: the next pass
        if not isinstance(info, dict):
            return
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
                self._files(run, info, prog, pending)
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

    def _read(self, run: str, name: str) -> bytes | None:
        try:
            return self.source.path(run, name).read_bytes()
        except OSError:
            return None

    def _documents(self, run: str, prog: RunProgress, pending: _Pending) -> None:
        names = [rundir.RUN_INFO, rundir.CURSOR]
        for folder in _FOLDERS:
            d = self.source.path(run, folder)
            try:
                names += sorted(rundir.entry(folder, f.stem) for f in d.glob("*.json") if f.is_file() and _plain(f.name))
            except OSError:
                continue
        present = set()
        for name in names:
            data = self._read(run, name)
            if data is None:
                continue
            present.add(name)
            sha = _sha(data)
            if prog.documents.get(name) == sha:
                continue
            text = data.decode("utf-8", errors="replace")
            try:
                json.loads(text)
            except ValueError:
                continue  # half written: the next pass
            pending.documents.append(DocumentPut(name=name, text=text))
            pending.doc_shas[name] = sha
        for name in sorted(set(prog.documents) - present):
            pending.documents.append(DocumentPut(name=name, text=None))
            pending.doc_shas[name] = None

    def _contract_paths(self, run: str) -> list[str]:
        out: dict[str, None] = {}
        for text in self.source.folder(run, rundir.CONTRACTS):
            try:
                rec = json.loads(text)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            for spec in [*rec.get("outputs", []), *rec.get("inputs", [])]:
                if isinstance(spec, dict) and isinstance(spec.get("path"), str) and spec["path"]:
                    out[spec["path"]] = None
        return list(out)

    def _files(self, run: str, info: dict, prog: RunProgress, pending: _Pending) -> None:
        cwd = Path(str(info.get("cwd") or "."))
        for path in self._contract_paths(run):
            where = cwd / path
            try:
                st = where.stat()
            except OSError:
                if path in prog.files and prog.files[path] is None:
                    continue
                pending.files.append(FileRef(path=path, sha256=None))
                pending.file_stats[path] = None
                continue
            stat = [st.st_size, st.st_mtime_ns]
            held = prog.files.get(path)
            if held is not None and held[:2] == stat:
                continue
            try:
                data = where.read_bytes()
            except OSError:
                continue
            sha = _sha(data)
            if not self._call(self.client.has_blob, sha):
                self._call(self.client.put_blob, sha, data)
            pending.files.append(FileRef(path=path, sha256=sha, size=len(data), mtime=_iso(st.st_mtime)))
            pending.file_stats[path] = [*stat, sha]

    def _log_names(self, run: str) -> list[str]:
        names = [log for log in rundir.LOGS if self.source.path(run, log).is_file()]
        streams = self.source.path(run, rundir.STREAMS)
        suffix = ".stream.jsonl"
        try:
            keys = sorted(f.name[: -len(suffix)] for f in streams.iterdir() if f.name.endswith(suffix) and f.is_file())
        except OSError:
            keys = []
        return names + [rundir.stream(k) for k in keys if _plain(k)]

    def _logs(self, run: str, prog: RunProgress, pending: _Pending, probe: bool) -> None:
        budget_bytes, budget_lines = self.batch_bytes, self.batch_lines
        for log in self._log_names(run):
            path = self.source.path(run, log)
            held = prog.logs.get(log)
            lines_at, byte_at = held if held is not None else (0, 0)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size < byte_at:
                _logger.warning("run %s: %s is shorter than the part already sent; sending it from its start", run, log)
                lines_at, byte_at = 0, 0
            lines: list[str] = []
            end = byte_at
            if size > byte_at and budget_lines > 0 and (budget_bytes > 0 or not pending.chunks):
                try:
                    lines, end = read_lines(path, byte_at, max(budget_bytes, 1), budget_lines)
                except OSError:
                    continue
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
            try:
                prog.logs[chunk.log] = list(seek_line(self.source.path(run, chunk.log), held))
            except OSError:
                prog.logs.pop(chunk.log, None)
        return lost

    # --- heartbeat ---

    def heartbeat_once(self) -> bool:
        """Send a heartbeat with the live runs and their snapshots; True when the hub took it.
        Never raises."""
        try:
            reports = []
            for run in sorted(self.liveness.live()):
                info = self.source.info(run)
                if not isinstance(info, dict):
                    continue
                ref = RunRef(host_id=self.host_id, run_id=run, run_uid=str(info.get("run_uid") or run))
                reports.append(RunLiveness(run=ref, alive=True, snapshot=self.liveness.snapshot(run)))
            beat = Heartbeat(host_id=self.host_id, sent_at=_iso(self.clock(), "milliseconds"), interval_s=self.interval_s, runs=reports)
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


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="contraagent relay",
        description="Ship every run under a runs directory to a contraagent hub, incrementally, and send a heartbeat "
        "with the live runs. The ingest token comes from --token-file, else the environment variable "
        f"{TOKEN_ENV}; it is never a command line argument.",
    )
    ap.add_argument("--runs-dir", default="runs", help="the runs directory to ship (default: runs)")
    ap.add_argument("--hub", required=True, help="the hub's address, for example http://hub:8790")
    ap.add_argument("--token-file", help=f"a file holding the hub's ingest token (default: the environment variable {TOKEN_ENV})")
    ap.add_argument("--host-id", help=f"this host's name on the hub (default: {rundir.HOST_ID_ENV}, else the host name)")
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
    return ap


def _token(args: argparse.Namespace, ap: argparse.ArgumentParser) -> str:
    if args.token_file:
        try:
            return Path(args.token_file).read_text().strip()
        except OSError as exc:
            ap.error(f"cannot read --token-file: {exc}")
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        ap.error(f"no ingest token: give --token-file or set {TOKEN_ENV}")
    return token


def main(argv: list[str] | None = None) -> int:
    ap = _parser()
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.interval <= 0:
        ap.error("--interval must be more than 0")
    token = _token(args, ap)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
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

        def beat() -> None:
            while not stop.is_set():
                relay.heartbeat_once()
                stop.wait(relay.heartbeat_delay())

        threading.Thread(target=beat, name="relay-heartbeat", daemon=True).start()
        _logger.info("shipping %s to %s as host %s", relay.runs_dir, client.base_url, relay.host_id)
        while not stop.is_set():
            relay.pass_once()
            stop.wait(relay.delay())
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        relay.save()
        client.close()
