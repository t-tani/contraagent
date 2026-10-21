"""What `PostgresHubStore` keeps beyond the hub's contract: several hub processes on one
database, a notification after each change, and a schema created once."""

import random
import threading

import psycopg
import pytest

from contraagent._internal.hub.postgres import NOTIFY_CHANNEL, PostgresHubStore
from contraagent._internal.hub.protocol import Heartbeat, LogChunk, RecordBatch, RunRef
from contraagent._internal.runs import layout
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that gives a test the services' credentials
    postgres_dsn,
)

pytestmark = pytest.mark.usefixtures("hub_services")

RUN = RunRef(host_id="h1", run_id="r1", run_uid="u1")


@pytest.fixture
def dsn() -> str:
    return postgres_dsn()


def test_two_hub_processes_ingesting_one_log_keep_each_line_once_in_order(dsn):
    every = [f"line {i}" for i in range(3000)]
    stores = [PostgresHubStore(dsn), PostgresHubStore(dsn)]
    errors: list[BaseException] = []

    def relay(store: PostgresHubStore, seed: int) -> None:
        rnd = random.Random(seed)
        held = 0
        try:
            while held < len(every):
                start = max(0, held - rnd.randint(0, 50))  # resend some held lines
                chunk = LogChunk(log=layout.JOURNAL, offset=start, lines=every[start : start + rnd.randint(1, 120)])
                held = store.put_batch(RecordBatch(run=RUN, logs=[chunk]), "t").logs[layout.JOURNAL]
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=relay, args=(s, i)) for i, s in enumerate(stores * 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    for store in stores:
        assert store.lines("r1@h1", layout.JOURNAL) == (every, len(every))
        assert store.lines("r1@h1", layout.JOURNAL, 1500, 3) == (every[1500:1503], len(every))
        store.close()


def test_each_batch_and_heartbeat_is_notified(dsn):
    store = PostgresHubStore(dsn)
    with psycopg.connect(dsn, autocommit=True) as listener:
        listener.execute(f"LISTEN {NOTIFY_CHANNEL}")
        store.put_batch(RecordBatch(run=RUN, logs=[LogChunk(log=layout.JOURNAL, offset=0, lines=["a"])]), "t")
        store.put_heartbeat(Heartbeat(host_id="h1", sent_at="s", interval_s=3, ttl_s=12), "t")
        got = [(n.channel, n.payload) for n in listener.notifies(timeout=5, stop_after=2)]
    assert got == [(NOTIFY_CHANNEL, "r1@h1"), (NOTIFY_CHANNEL, "host:h1")]
    store.close()


def test_the_schema_is_created_once_and_shared_by_every_store_on_the_database(dsn):
    stores: list[PostgresHubStore] = []
    threads = [threading.Thread(target=lambda: stores.append(PostgresHubStore(dsn))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(stores) == 4
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchall() == [(1,)]
    stores[0].put_batch(RecordBatch(run=RUN, logs=[LogChunk(log=layout.PLAN, offset=0, lines=["p"])]), "t")
    later = PostgresHubStore(dsn)
    assert later.lines("r1@h1", layout.PLAN) == (["p"], 1) and [e.name for e in later.runs()] == ["r1@h1"]
    for store in [*stores, later]:
        store.close()
