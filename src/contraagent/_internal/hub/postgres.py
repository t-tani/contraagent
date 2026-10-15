"""A `HubStore` in Postgres: `PostgresHubStore`, for a hub of many processes.

The schema is created on first use, under an advisory lock so that several hub processes
starting at once create it once; `schema_version` holds its version, the place for later
migrations. Every name column is `COLLATE "C"`, so the database orders names as Python
does.

    schema_version  version
    runs            id, name, run_uid, host_id, run_id, received_at
    logs            id, run -> runs.id, log, lines (how many lines it holds)
    log_lines       log -> logs.id, line_no, line          one row per line
    documents       run -> runs.id, name, text
    files           run -> runs.id, path, sha256, size, mtime
    heartbeats      host_id, heartbeat (the JSON), received_at

A batch is stored in one transaction that first locks its run's row, so two hub processes
ingesting the same run apply its batches one after the other. A new `run_uid` under a held
name keeps the row (and its lock) and removes the old run's logs, documents and files.

After each committed batch that changed what the hub holds of the run (the rule in
`store`, which also decides `received_at`) the store sends `NOTIFY contraagent_hub` with the
run's name as the payload, and after each heartbeat with `host:<host_id>` (`NOTIFY_CHANNEL`).

`delete_run` deletes the run's row, and with it (`ON DELETE CASCADE`) its logs, lines,
documents and files, in one transaction.
"""

from __future__ import annotations

import threading
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from typing import LiteralString

import psycopg
from psycopg.types.json import Jsonb

from contraagent._internal.hub.protocol import Accepted, FileRef, Heartbeat, RecordBatch, RunRef
from contraagent._internal.runs.source import Pager

#: The channel a `PostgresHubStore` notifies after each batch that changed a run, and each heartbeat.
NOTIFY_CHANNEL = "contraagent_hub"

POSTGRES_SCHEMA_VERSION = 1

# An arbitrary 64-bit key for the advisory lock held while the schema is created.
_SCHEMA_LOCK = 0x636F6E7472616167

_SCHEMA: list[LiteralString] = [
    "CREATE TABLE IF NOT EXISTS schema_version (version integer PRIMARY KEY)",
    """CREATE TABLE IF NOT EXISTS runs (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name text COLLATE "C" NOT NULL UNIQUE,
        run_uid text NOT NULL,
        host_id text NOT NULL,
        run_id text NOT NULL,
        received_at text NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS logs (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        run bigint NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
        log text COLLATE "C" NOT NULL,
        lines bigint NOT NULL DEFAULT 0,
        UNIQUE (run, log)
    )""",
    """CREATE TABLE IF NOT EXISTS log_lines (
        log bigint NOT NULL REFERENCES logs (id) ON DELETE CASCADE,
        line_no bigint NOT NULL,
        line text NOT NULL,
        PRIMARY KEY (log, line_no)
    )""",
    """CREATE TABLE IF NOT EXISTS documents (
        run bigint NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
        name text COLLATE "C" NOT NULL,
        text text NOT NULL,
        PRIMARY KEY (run, name)
    )""",
    """CREATE TABLE IF NOT EXISTS files (
        run bigint NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
        path text COLLATE "C" NOT NULL,
        sha256 text,
        size bigint NOT NULL,
        mtime text NOT NULL,
        PRIMARY KEY (run, path)
    )""",
    """CREATE TABLE IF NOT EXISTS heartbeats (
        host_id text COLLATE "C" PRIMARY KEY,
        heartbeat jsonb NOT NULL,
        received_at text NOT NULL
    )""",
]


class PostgresHubStore:
    """A `HubStore` in the Postgres database at `dsn` (a libpq connection string or URL).

    Safe across threads: each call takes a connection of its own from a small pool.
    `close()` closes the pooled connections.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._idle: list[psycopg.Connection] = []
        self._lock = threading.Lock()
        self._create_schema()

    # --- connections -------------------------------------------------------------------

    @contextmanager
    def _conn(self) -> Iterator[psycopg.Connection]:
        with self._lock:
            conn = self._idle.pop() if self._idle else None
        if conn is None or conn.closed:
            conn = psycopg.connect(self.dsn, autocommit=True)
        try:
            yield conn
        except BaseException:
            conn.close()
            raise
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
            with self._lock:
                self._idle.append(conn)
        else:
            conn.close()

    def close(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, []
        for conn in idle:
            conn.close()

    def _create_schema(self) -> None:
        with self._conn() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK,))
            for statement in _SCHEMA:
                conn.execute(statement)
            row = conn.execute("SELECT max(version) FROM schema_version").fetchone()
            held = row[0] if row else None
            if held is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (POSTGRES_SCHEMA_VERSION,))
            elif held > POSTGRES_SCHEMA_VERSION:
                raise RuntimeError(f"the hub database has schema version {held}; this contraagent knows up to {POSTGRES_SCHEMA_VERSION}")

    # --- writes ------------------------------------------------------------------------

    def put_batch(self, batch: RecordBatch, received_at: str) -> Accepted:
        ref = batch.run
        held: dict[str, int] = {}
        with self._conn() as conn, conn.transaction():
            created = conn.execute(
                "INSERT INTO runs (name, run_uid, host_id, run_id) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING id",
                (ref.name, ref.run_uid, ref.host_id, ref.run_id),
            ).fetchone()
            changed = created is not None
            row = conn.execute("SELECT id, run_uid FROM runs WHERE name = %s FOR UPDATE", (ref.name,)).fetchone()
            assert row is not None
            run, run_uid = row
            if run_uid != ref.run_uid:
                changed = True
                conn.execute("DELETE FROM logs WHERE run = %s", (run,))
                conn.execute("DELETE FROM documents WHERE run = %s", (run,))
                conn.execute("DELETE FROM files WHERE run = %s", (run,))
                conn.execute(
                    "UPDATE runs SET run_uid = %s, host_id = %s, run_id = %s WHERE id = %s",
                    (ref.run_uid, ref.host_id, ref.run_id, run),
                )
            for chunk in batch.logs:
                row = conn.execute(
                    "INSERT INTO logs (run, log) VALUES (%s, %s) "
                    "ON CONFLICT (run, log) DO UPDATE SET lines = logs.lines RETURNING id, lines, xmax = 0",
                    (run, chunk.log),
                ).fetchone()
                assert row is not None
                log, count, inserted = row
                changed |= inserted
                if chunk.offset <= count:
                    new = chunk.lines[count - chunk.offset :]
                    if new:
                        with conn.cursor() as cur, cur.copy("COPY log_lines (log, line_no, line) FROM STDIN") as copy:
                            for i, line in enumerate(new, count):
                                copy.write_row((log, i, line))
                        count += len(new)
                        changed = True
                        conn.execute("UPDATE logs SET lines = %s WHERE id = %s", (count, log))
                held[chunk.log] = count
            for doc in batch.documents:
                if doc.text is None:
                    cur = conn.execute("DELETE FROM documents WHERE run = %s AND name = %s", (run, doc.name))
                else:
                    cur = conn.execute(
                        "INSERT INTO documents (run, name, text) VALUES (%s, %s, %s) "
                        "ON CONFLICT (run, name) DO UPDATE SET text = EXCLUDED.text WHERE documents.text <> EXCLUDED.text",
                        (run, doc.name, doc.text),
                    )
                changed |= cur.rowcount > 0
            if batch.files:
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO files (run, path, sha256, size, mtime) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (run, path) DO UPDATE SET sha256 = EXCLUDED.sha256, size = EXCLUDED.size, mtime = EXCLUDED.mtime "
                        "WHERE (files.sha256, files.size, files.mtime) IS DISTINCT FROM (EXCLUDED.sha256, EXCLUDED.size, EXCLUDED.mtime)",
                        [(run, f.path, f.sha256, f.size, f.mtime) for f in batch.files],
                    )
                    changed |= cur.rowcount > 0
            if changed:
                conn.execute("UPDATE runs SET received_at = %s WHERE id = %s", (received_at, run))
                conn.execute("SELECT pg_notify(%s, %s)", (NOTIFY_CHANNEL, ref.name))
        return Accepted(logs=held)

    def put_heartbeat(self, heartbeat: Heartbeat, received_at: str) -> None:
        with self._conn() as conn, conn.transaction():
            conn.execute(
                "INSERT INTO heartbeats (host_id, heartbeat, received_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (host_id) DO UPDATE SET heartbeat = EXCLUDED.heartbeat, received_at = EXCLUDED.received_at",
                (heartbeat.host_id, Jsonb(heartbeat.model_dump(mode="json")), received_at),
            )
            conn.execute("SELECT pg_notify(%s, %s)", (NOTIFY_CHANNEL, f"host:{heartbeat.host_id}"))

    # --- reads -------------------------------------------------------------------------

    def runs(self) -> list[RunRef]:
        with self._conn() as conn:
            rows = conn.execute("SELECT run_uid, host_id, run_id FROM runs ORDER BY name").fetchall()
        return [RunRef(run_uid=r[0], host_id=r[1], run_id=r[2]) for r in rows]

    def entry(self, name: str) -> RunRef | None:
        with self._conn() as conn:
            row = conn.execute("SELECT run_uid, host_id, run_id FROM runs WHERE name = %s", (name,)).fetchone()
        return RunRef(run_uid=row[0], host_id=row[1], run_id=row[2]) if row else None

    def lines(self, name: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT logs.id, logs.lines FROM logs JOIN runs ON runs.id = logs.run WHERE runs.name = %s AND logs.log = %s",
                (name, log),
            ).fetchone()
            if row is None:
                return [], 0
            log_id, total = row
            start, stop, _ = slice(since, None if limit is None else since + limit).indices(total)
            if stop <= start:
                return [], total
            pager = Pager(None, max_bytes)
            cur = conn.cursor()
            cur.execute(
                "SELECT line FROM log_lines WHERE log = %s AND line_no >= %s AND line_no < %s ORDER BY line_no", (log_id, start, stop)
            )
            while not pager.full and (rows := cur.fetchmany(500)):
                pager.take(r[0] for r in rows)
            cur.close()
        return pager.out, total

    def logs(self, name: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT logs.log FROM logs JOIN runs ON runs.id = logs.run WHERE runs.name = %s ORDER BY logs.log", (name,)
            ).fetchall()
        return [r[0] for r in rows]

    def documents(self, name: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT d.name FROM documents d JOIN runs ON runs.id = d.run WHERE runs.name = %s ORDER BY d.name", (name,)
            ).fetchall()
        return [r[0] for r in rows]

    def count(self, name: str, log: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT logs.lines FROM logs JOIN runs ON runs.id = logs.run WHERE runs.name = %s AND logs.log = %s",
                (name, log),
            ).fetchone()
        return row[0] if row else -1

    def document(self, name: str, doc: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT d.text FROM documents d JOIN runs ON runs.id = d.run WHERE runs.name = %s AND d.name = %s",
                (name, doc),
            ).fetchone()
        return row[0] if row else None

    def folder(self, name: str, folder: str) -> list[str]:
        prefix = folder + "/"
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT d.text FROM documents d JOIN runs ON runs.id = d.run "
                "WHERE runs.name = %s AND starts_with(d.name, %s) AND strpos(substr(d.name, %s), '/') = 0 "
                "ORDER BY d.name",
                (name, prefix, len(prefix) + 1),
            ).fetchall()
        return [r[0] for r in rows]

    def exists(self, name: str, entry: str) -> bool:
        prefix = entry + "/"
        with self._conn() as conn:
            row = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM logs JOIN runs ON runs.id = logs.run "
                "  WHERE runs.name = %(n)s AND (logs.log = %(e)s OR starts_with(logs.log, %(p)s))) "
                "OR EXISTS (SELECT 1 FROM documents d JOIN runs ON runs.id = d.run "
                "  WHERE runs.name = %(n)s AND (d.name = %(e)s OR starts_with(d.name, %(p)s)))",
                {"n": name, "e": entry, "p": prefix},
            ).fetchone()
        return bool(row and row[0])

    def file(self, name: str, path: str) -> FileRef | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT f.path, f.sha256, f.size, f.mtime FROM files f JOIN runs ON runs.id = f.run WHERE runs.name = %s AND f.path = %s",
                (name, path),
            ).fetchone()
        return FileRef(path=row[0], sha256=row[1], size=row[2], mtime=row[3]) if row else None

    def activity(self, name: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT received_at FROM runs WHERE name = %s", (name,)).fetchone()
        return (row[0] or None) if row else None

    def heartbeats(self) -> dict[str, tuple[Heartbeat, str]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT host_id, heartbeat, received_at FROM heartbeats").fetchall()
        return {host: (Heartbeat.model_validate(hb), at) for host, hb, at in rows}

    # --- retention ---------------------------------------------------------------------

    def delete_run(self, name: str, run_uid: str | None = None) -> bool:
        with self._conn() as conn:
            if run_uid is None:
                cur = conn.execute("DELETE FROM runs WHERE name = %s", (name,))
            else:
                cur = conn.execute("DELETE FROM runs WHERE name = %s AND run_uid = %s", (name, run_uid))
        return cur.rowcount > 0

    def delete_heartbeat(self, host_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM heartbeats WHERE host_id = %s", (host_id,))
        return cur.rowcount > 0

    def referenced_blobs(self, excluding: Collection[str] = ()) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT f.sha256 FROM files f JOIN runs ON runs.id = f.run WHERE f.sha256 IS NOT NULL AND runs.name <> ALL(%s)",
                (list(excluding),),
            ).fetchall()
        return {r[0] for r in rows}
