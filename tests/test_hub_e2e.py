"""The hub end to end, as real processes: `contraagent hub` over Postgres and RustFS (docker,
`hub_services`), one `contraagent relay` per host, and the monitor read over HTTP.

The tests share one hub and two hosts and run in file order: each leaves the hub as the
next one expects it. Run them with `uv run pytest -m e2e` (`-s` prints the latencies).
The hub seals open segments within a second (the hidden `--seal-*` flags)."""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("boto3")
pytest.importorskip("zstandard")
httpx2 = pytest.importorskip("httpx2")

from fastapi.testclient import TestClient  # noqa: E402

from contraagent._internal.monitor import server  # noqa: E402
from contraagent._internal.platform import processes  # noqa: E402
from contraagent.monitor import Monitor  # noqa: E402
from hub_services import (  # noqa: E402
    S3_ENV,
    hub_services,  # noqa: F401  # the fixture that gives a test the services' credentials
    postgres_dsn,
    s3_url,
)

# One worker under pytest-xdist: the tests share the module's hub and relays and build on what
# the earlier ones shipped, so each worker would otherwise start its own and find it empty.
pytestmark = [pytest.mark.e2e, pytest.mark.usefixtures("hub_services"), pytest.mark.xdist_group("hub-e2e")]

HOSTS = ("h1", "h2")
READ_TOKEN = "read-" + uuid.uuid4().hex
INGEST = {h: f"ingest-{h}-" + uuid.uuid4().hex for h in HOSTS}
TTL_S = 3.0
INTERVAL_S = 0.5
LIVE, LIVE_KEY, LONG_KEY = "live", "live-task", "long-task"

#: The relay, with each records request it sends counted in `$E2E_SENT` (one JSON line each).
RELAY = """
import json, os, sys
from contraagent._internal.hub import client
send = client.HttpClient.send_records
def counted(self, batch):
    got = send(self, batch)
    with open(os.environ["E2E_SENT"], "a") as f:
        row = {"run": batch.run.run_id, "lines": {c.log: len(c.lines) for c in batch.logs if c.lines},
               "documents": len(batch.documents), "files": len(batch.files)}
        f.write(json.dumps(row) + "\\n")
    return got
client.HttpClient.send_records = counted
from contraagent._internal.cli import main
raise SystemExit(main(["relay", *sys.argv[1:]]))
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _until(check: Callable[[], object], what: str, timeout: float = 60.0, every: float = 0.1):
    deadline = time.monotonic() + timeout
    while True:
        got = check()
        if got:
            return got
        if time.monotonic() > deadline:
            raise AssertionError(f"{what}: not within {timeout}s")
        time.sleep(every)


class Proc:
    """A child process with its output in a log file."""

    def __init__(self, argv: list[str], log: Path, env: dict[str, str] | None = None) -> None:
        self.log = log
        self.out = open(log, "ab")  # closed in stop()
        self.p = subprocess.Popen(argv, stdout=self.out, stderr=subprocess.STDOUT, env={**os.environ, **(env or {})})

    def alive(self) -> bool:
        return self.p.poll() is None

    def stop(self, sig: int = signal.SIGTERM) -> int:
        if self.alive():
            self.p.send_signal(sig)
            try:
                self.p.wait(15)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(5)
        self.out.close()
        return self.p.returncode

    def tail(self) -> str:
        return self.log.read_text(errors="replace")[-4000:]


class Env:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.dsn = postgres_dsn()
        self.blobs = s3_url()
        self.segments = s3_url()
        self.hot = tmp / "hot"
        (tmp / "ingest").write_text("".join(f"{h} {t}\n" for h, t in INGEST.items()))
        (tmp / "read").write_text(READ_TOKEN + "\n")
        for h in HOSTS:
            (tmp / f"{h}.token").write_text(INGEST[h] + "\n")
        self.runs = {h: _demo(tmp / h) for h in HOSTS}
        # Picked once the slow demo runs are over, so little time passes before the hub binds it.
        # A restarted hub binds it again: its relays know the hub by this URL.
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.hub: Proc | None = None
        self.relays: dict[str, Proc] = {}
        self.http = httpx2.Client(base_url=self.url, headers={"Authorization": f"Bearer {READ_TOKEN}"}, timeout=30)

    # --- processes ---

    def start_hub(self) -> None:
        argv = [
            *(sys.executable, "-m", "contraagent", "hub", "--port", str(self.port)),
            *("--store", self.dsn, "--blobs", self.blobs, "--streams-dir", str(self.hot), "--segments", self.segments),
            *("--ingest-token-file", str(self.tmp / "ingest"), "--read-token-file", str(self.tmp / "read")),
            *("--seal-bytes", "65536", "--seal-idle", "1", "--seal-tick", "0.5"),
        ]
        self.hub = hub = Proc(argv, self.tmp / "hub.log", env=S3_ENV)  # started before `hub_services` runs

        def up() -> bool:
            assert hub.alive(), f"the hub exited:\n{hub.tail()}"
            try:
                return self.http.get("/api/info").status_code == 200
            except httpx2.TransportError:
                return False

        _until(up, "the hub answers", 30)

    def start_relay(self, host: str) -> None:
        argv = [
            *(sys.executable, "-c", RELAY, "--runs-dir", str(self.runs[host]), "--hub", self.url),
            *("--token-file", str(self.tmp / f"{host}.token"), "--host-id", host, "--interval", str(INTERVAL_S), "--ttl", str(TTL_S)),
            *("--progress-file", str(self.tmp / f"{host}.relay.json"), "--timeout", "5"),
        ]
        self.relays[host] = Proc(argv, self.tmp / f"relay-{host}.log", env={"E2E_SENT": str(self.sent_file(host))})

    def sent_file(self, host: str) -> Path:
        return self.tmp / f"sent-{host}.jsonl"

    def sent(self, host: str) -> list[dict]:
        try:
            return [json.loads(line) for line in self.sent_file(host).read_text().splitlines()]
        except FileNotFoundError:
            return []

    def close(self) -> None:
        for relay in self.relays.values():
            relay.stop()
        if self.hub is not None:
            self.hub.stop()
        self.http.close()

    # --- reading ---

    def local(self, host: str) -> TestClient:
        return TestClient(server.create_app(Monitor(self.runs[host])), base_url="http://127.0.0.1")

    def runs_list(self) -> list[dict]:
        return self.http.get("/api/runs").json()

    def summary(self, name: str) -> dict | None:
        return next((r for r in self.runs_list() if r["run"] == name), None)

    def stream_total(self, run: str, key: str) -> int:
        got = self.http.get(f"/api/runs/{run}/stream/{key}", params={"since": 0})
        return got.json()["total"] if got.status_code == 200 else -1


def _demo(where: Path) -> Path:
    from contraagent.docs.examples.demo import run as demo

    where.mkdir(parents=True)
    old = Path.cwd()
    os.chdir(where)
    try:
        demo.main(["--no-serve", "--fast"])
    finally:
        os.chdir(old)
    return where / "demo-runs"


@pytest.fixture(scope="module")
def env(tmp_path_factory) -> Iterator[Env]:
    began = time.monotonic()
    e = Env(tmp_path_factory.mktemp("e2e"))
    try:
        e.start_hub()
        for h in HOSTS:
            e.start_relay(h)
        yield e
    finally:
        e.close()
        print(f"\ne2e: {time.monotonic() - began:.1f}s; logs in {e.tmp}")


# --- views -------------------------------------------------------------------------------


def _views(get: Callable[[str], object], run: str, keys: list[str]) -> dict:
    paths = [f"/api/runs/{run}/{view}" for view in ("journal", "plan", "outputs", "definitions", "cursor")]
    for k in keys:
        paths += [f"/api/runs/{run}/task/{k}", f"/api/runs/{run}/stream/{k}?since=0", f"/api/runs/{run}/stream/{k}?since=3"]
    return {p.replace(f"/{run}/", "/<run>/"): get(p) for p in paths}


def _same_views(e: Env, host: str, run: str) -> tuple[dict, dict]:
    local = e.local(host)
    keys = [n["key"] for n in local.get(f"/api/runs/{run}/plan").json()["nodes"]]
    mine = _views(lambda p: local.get(p).json(), run, keys)
    theirs = _views(lambda p: e.http.get(p).json(), f"{run}@{host}", keys)
    return mine, theirs


def _converged(e: Env, host: str, run: str, timeout: float = 30) -> tuple[dict, dict]:
    """The local and the hub's views of a run, once they are equal or after `timeout`."""
    deadline = time.monotonic() + timeout
    while True:
        mine, theirs = _same_views(e, host, run)
        if mine == theirs or time.monotonic() > deadline:
            return mine, theirs
        time.sleep(0.5)


def _strip(rows: list[dict]) -> list[dict]:
    return sorted(({k: v for k, v in r.items() if k not in ("run", "last_ts", "host_id")} for r in rows), key=json.dumps)


def test_every_host_s_runs_have_the_views_of_their_directory(env):
    demo = {h: [r["run"] for r in env.local(h).get("/api/runs").json()] for h in HOSTS}
    assert all(demo.values())
    expected = sorted(f"{r}@{h}" for h in HOSTS for r in demo[h])
    _until(lambda: sorted(r["run"] for r in env.runs_list()) == expected, "every run on the hub")
    for h in HOSTS:
        for run in demo[h]:
            mine, theirs = _converged(env, h, run)
            assert theirs == mine, f"{run}@{h}"
    rows = env.runs_list()
    for h in HOSTS:
        assert _strip([r for r in rows if r["run"].endswith(f"@{h}")]) == _strip(env.local(h).get("/api/runs").json())


def test_the_read_token_opens_the_monitor_by_header_or_login(env):
    bare = httpx2.Client(base_url=env.url, timeout=10)
    try:
        assert bare.get("/api/runs").status_code == 401
        assert bare.get("/login", params={"token": "wrong"}).status_code == 401
        login = bare.get("/login", params={"token": READ_TOKEN})
        assert login.status_code == 303 and login.headers["location"] == "/"
        assert bare.get("/api/runs").status_code == 200  # the cookie /login set
    finally:
        bare.close()
    other = httpx2.post(
        f"{env.url}/ingest/heartbeat",
        json={"host_id": "h2", "sent_at": "x", "interval_s": 1},
        headers={"Authorization": f"Bearer {INGEST['h1']}"},
    )
    assert other.status_code == 403


# --- live ----------------------------------------------------------------------------------


class Feed:
    """An SSE connection, read by a thread into a queue of (id, event, data)."""

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self.client = httpx2.Client(timeout=httpx2.Timeout(10, read=None))
        self.messages: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self.response = self.client.send(self.client.build_request("GET", url, headers=headers), stream=True)
        assert self.response.status_code == 200, self.response.read()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        fields: dict[str, str] = {}
        try:
            for line in self.response.iter_lines():
                if not line:
                    if "data" in fields:
                        self.messages.put((fields.get("id", ""), fields.get("event", ""), fields["data"]))
                    fields = {}
                elif not line.startswith(":"):
                    k, _, v = line.partition(":")
                    v = v[1:] if v.startswith(" ") else v
                    fields[k] = fields[k] + "\n" + v if k in fields else v
        except Exception:
            pass

    def next(self, timeout: float) -> tuple[str, str, str]:
        return self.messages.get(timeout=timeout)

    def close(self) -> None:
        self.response.close()
        self.client.close()


def _delta(text: str) -> str:
    return json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": text + "\n"}})


def _append(path: Path, *lines: str) -> None:
    with open(path, "a") as f:
        f.write("".join(line + "\n" for line in lines))


def _mark(i: int) -> str:
    return f"MARK-{i:06d}"


def _make_live_run(runs: Path, sleeper: subprocess.Popen) -> Path:
    """A copy of the demo's `analyse` run whose `run.json` names a live process, with a
    task in flight whose transcript holds its launch line."""
    src, dst = runs / "analyse", runs / LIVE
    shutil.copytree(src, dst)
    info = json.loads((src / "run.json").read_text())
    info.pop("finished_at", None)
    info.update(run_id=LIVE, run_uid=uuid.uuid4().hex, pid=sleeper.pid, start_ticks=processes.start_ticks(sleeper.pid))
    launch = (src / "streams" / "classify-east-0.stream.jsonl").read_text().splitlines()[0]
    (dst / "streams" / f"{LIVE_KEY}.stream.jsonl").write_text(launch + "\n")
    (dst / "inflight").mkdir(exist_ok=True)
    marker = {
        "key": LIVE_KEY,
        "kind": "classify",
        "unit": "live",
        "executor": "agent",
        "started_at": info["started_at"],
        "pid": sleeper.pid,
    }
    (dst / "inflight" / f"{LIVE_KEY}.json").write_text(json.dumps(marker))
    (dst / "run.json").write_text(json.dumps(info))
    return dst


@pytest.fixture(scope="module")
def live(env) -> Iterator[Path]:
    sleeper = subprocess.Popen(["sleep", "900"])
    try:
        run = _make_live_run(env.runs["h1"], sleeper)
        _until(lambda: (env.summary(f"{LIVE}@h1") or {}).get("running"), "the live run is running on the hub", 30)
        _until(lambda: env.stream_total(f"{LIVE}@h1", LIVE_KEY) == 1, "the live transcript on the hub", 30)
        yield run
    finally:
        sleeper.kill()
        sleeper.wait()


def _feed(env: Env, last_id: str | None = None) -> Feed:
    headers = {"Authorization": f"Bearer {READ_TOKEN}"}
    if last_id is not None:
        headers["Last-Event-ID"] = last_id
    return Feed(f"{env.url}/events/stream?run={LIVE}@h1&key={LIVE_KEY}", headers)


def _collect(feed: Feed, want: list[str], got: list[tuple[str, str]], timeout: float = 15) -> None:
    """Read messages into `got` as (id, data) until every mark in `want` was seen."""
    deadline = time.monotonic() + timeout
    while not all(any(m in d for _, d in got) for m in want):
        left = deadline - time.monotonic()
        assert left > 0, f"marks not received: {[m for m in want if not any(m in d for _, d in got)]}"
        try:
            mid, _, data = feed.next(left)
        except queue.Empty:
            continue
        got.append((mid, data))


def test_a_live_transcript_arrives_in_order_and_resumes_without_gap_or_duplicate(env, live):
    path = live / "streams" / f"{LIVE_KEY}.stream.jsonl"
    feed = _feed(env)
    got: list[tuple[str, str]] = []
    first = feed.next(15)
    assert first[1] == "stream" and first[0] == "1"  # the tail page: the launch line
    got.append((first[0], first[2]))
    latencies = []
    for i in range(20):
        _append(path, _delta(_mark(i)))
        t0 = time.monotonic()
        _collect(feed, [_mark(i)], got)
        latencies.append(time.monotonic() - t0)
        time.sleep(0.05)
    last_id = got[-1][0]
    feed.close()

    _append(path, *(_delta(_mark(i)) for i in range(20, 30)))  # while no viewer is connected
    again = _feed(env, last_id)
    _collect(again, [_mark(i) for i in range(20, 30)], got)
    _append(path, *(_delta(_mark(i)) for i in range(30, 35)))
    _collect(again, [_mark(i) for i in range(30, 35)], got)
    again.close()

    ids = [int(i) for i, _ in got]
    assert ids == sorted(set(ids)), ids  # increasing, across the reconnect too
    assert ids[-1] == 36
    every = "".join(d for _, d in got)
    assert [every.count(_mark(i)) for i in range(35)] == [1] * 35  # no gap, no duplicate
    assert [every.index(_mark(i)) for i in range(35)] == sorted(every.index(_mark(i)) for i in range(35))
    print(
        f"\nlive latency over {len(latencies)} lines: median {statistics.median(latencies) * 1000:.0f} ms, "
        f"max {max(latencies) * 1000:.0f} ms"
    )
    # Well within the 15 s each mark is waited for: a busy runner can be slow to schedule it.
    assert statistics.median(latencies) < 5.0


# --- segments ------------------------------------------------------------------------------


def _objects(url: str) -> list[str]:
    import boto3

    u = urlparse(url)
    endpoint = parse_qs(u.query)["endpoint"][0]
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1")
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=u.netloc, Prefix=u.path.lstrip("/"))
    return [o["Key"] for p in pages for o in p.get("Contents", [])]


def _hot_files(env: Env, key: str) -> list[Path]:
    return [p for p in env.hot.rglob("*.jsonl") if p.is_file() and f"{key}.stream.jsonl" in str(p)]


def test_an_early_page_of_a_long_transcript_is_read_from_sealed_segments(env, live):
    path = live / "streams" / f"{LONG_KEY}.stream.jsonl"
    filler = "x" * 120
    _append(path, *(_delta(f"{_mark(i)} {filler}") for i in range(4000)))
    _until(lambda: env.stream_total(f"{LIVE}@h1", LONG_KEY) == 4000, "the long transcript on the hub")
    sealed = _until(lambda: [k for k in _objects(env.segments) if f"{LONG_KEY}.stream.jsonl" in k], "sealed objects in RustFS", 30)
    assert len(sealed) > 1  # 65536-byte segments
    _until(lambda: not _hot_files(env, LONG_KEY), "the long transcript's open segment sealed", 30)
    local = env.local("h1")
    for since in (1, 1500, 3999):
        mine = local.get(f"/api/runs/{LIVE}/stream/{LONG_KEY}", params={"since": since}).json()
        theirs = env.http.get(f"/api/runs/{LIVE}@h1/stream/{LONG_KEY}", params={"since": since}).json()
        assert theirs == mine, since
        assert _mark(since) in json.dumps(theirs), since


# --- restarts ------------------------------------------------------------------------------


class Writer:
    """Appends a line to a transcript every few milliseconds, in a thread."""

    def __init__(self, path: Path, start: int) -> None:
        self.path, self.n, self.stop = path, start, threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop.is_set():
            _append(self.path, _delta(_mark(self.n)))
            self.n += 1
            self.stop.wait(0.01)

    def done(self) -> int:
        self.stop.set()
        self.thread.join()
        return self.n


def _local_lines(path: Path) -> int:
    return len(path.read_text().splitlines())


@pytest.mark.parametrize("name", ["SIGTERM", "SIGKILL"], ids=["sigterm", "sigkill"])
def test_a_hub_restarted_on_its_stores_loses_nothing_and_its_relays_catch_up(env, live, name):
    sig = getattr(signal, name)  # by name: Windows has no SIGKILL, and the module still imports there
    assert env.hub is not None
    path = live / "streams" / f"{LIVE_KEY}.stream.jsonl"
    writer = Writer(path, 100_000 + 10_000 * int(sig))
    time.sleep(1.0)
    code = env.hub.stop(sig)
    assert code == (0 if sig == signal.SIGTERM else -signal.SIGKILL), env.hub.tail()  # SIGTERM: a graceful stop
    time.sleep(1.5)  # the relay keeps writing and finds the hub gone
    env.start_hub()
    restarted = time.monotonic()
    time.sleep(1.0)
    writer.done()
    total = _local_lines(path)
    _until(lambda: env.stream_total(f"{LIVE}@h1", LIVE_KEY) == total, "the relay caught up", 90)
    print(f"\n{signal.Signals(sig).name}: {total} lines, caught up {time.monotonic() - restarted:.1f}s after the restart")
    local = env.local("h1")
    for since in range(1, total, 1000):
        mine = local.get(f"/api/runs/{LIVE}/stream/{LIVE_KEY}", params={"since": since}).json()
        theirs = env.http.get(f"/api/runs/{LIVE}@h1/stream/{LIVE_KEY}", params={"since": since}).json()
        assert theirs == mine, since
    for h in HOSTS:
        mine, theirs = _converged(env, h, "analyse")
        assert theirs == mine
    assert env.stream_total(f"{LIVE}@h1", LONG_KEY) == 4000


def test_a_restarted_relay_continues_from_its_progress_file(env):
    relay = env.relays["h2"]
    relay.stop(signal.SIGKILL)
    before = len(env.sent("h2"))
    launches = env.runs["h2"] / "analyse" / "launches.jsonl"
    _append(launches, launches.read_text().splitlines()[-1])
    env.start_relay("h2")
    mine, theirs = _converged(env, "h2", "analyse")
    assert theirs == mine
    time.sleep(3 * INTERVAL_S)  # a few more passes
    after = env.sent("h2")[before:]
    lines = {}
    for row in after:
        for log, n in row["lines"].items():
            lines[(row["run"], log)] = lines.get((row["run"], log), 0) + n
    assert lines == {("analyse", "launches.jsonl"): 1}
    assert sum(r["documents"] + r["files"] for r in after) == 0


# --- liveness ------------------------------------------------------------------------------


def test_a_run_stops_being_live_when_its_host_s_heartbeats_stop(env, live):
    name = f"{LIVE}@h1"
    assert env.summary(name)["running"] is True
    stopped = time.monotonic()  # before the stop, which can take a while to return
    env.relays["h1"].stop()
    _until(lambda: env.summary(name)["running"] is False, "the run no longer running", TTL_S + 10)
    took = time.monotonic() - stopped
    print(f"\nliveness: not running {took:.1f}s after the relay was stopped (relay --ttl {TTL_S:g})")
    # The TTL counts from the last heartbeat, which can be up to one interval before the stop.
    assert took >= TTL_S - INTERVAL_S - 0.5
    assert env.summary("analyse@h2")["running"] is False
    env.start_relay("h1")
    _until(lambda: env.summary(name)["running"] is True, "running again once heartbeats return", 15)
