# Many hosts: the hub

A pipeline writes its runs to its own `runs/` directory, and the monitor shows that
directory. When pipelines run on several hosts, a **hub** holds every host's runs and
serves one monitor over all of them; a **relay** on each host ships that host's runs to
it. Neither changes how a pipeline runs: the run directory stays the record, and a host
whose hub is unreachable keeps running and catches up later.

Every option is in `contraagent hub --help` and `contraagent relay --help`; the wire
between them is the OpenAPI document `contraagent hub --openapi PATH` writes. Install the `hub` extra
(`pip install 'contraagent[hub]'`) on the hub's host, or run it in compose from an image of the installed
version. How to run one for real (compose, tokens, retention, backups) is in [Operating a hub](hub-operations.md).

## Start a hub

```
contraagent hub --host 0.0.0.0 --allow-host hub.lan \
  --store postgres://hub@db/contraagent \
  --blobs s3://contraagent/blobs?endpoint=http://rustfs:9000 \
  --streams-dir /var/lib/contraagent/streams \
  --segments s3://contraagent/segments?endpoint=http://rustfs:9000 \
  --ingest-token-file /etc/contraagent/ingest-tokens \
  --read-token-file /etc/contraagent/read-token
```

| What | Where | Option |
|---|---|---|
| runs' records (run info, journal, plan, flow calls, contracts, definitions, call files) | Postgres | `--store` |
| contents of the files contracts name | object storage, by SHA-256 | `--blobs` |
| transcripts being written | the hub's local disk | `--streams-dir` |
| sealed transcript segments | object storage, or a directory (default: `<streams-dir>/segments`) | `--segments` |

`--store memory`, `--blobs memory` and no `--streams-dir` keep everything in memory:
for a try-out, lost when the hub stops.

The ingest token file holds one token per line, or `<host_id> <token>` to bind a token
to one host. The read token opens the monitor: open `/login?token=<token>` once in a
browser, or send it as `Authorization: Bearer`. With no read token the monitor is open
to anyone who reaches the port.

A hub [behind a reverse proxy](monitor.md#behind-a-reverse-proxy), under a path of a
site, takes `--base-path` as one monitor does, and its `/login` then redirects to that
path.

## Start a relay on each host

```
CONTRAAGENT_HUB_TOKEN=... contraagent relay --runs-dir runs --hub http://hub.lan:8790
```

It ships each run's records as they are written (the pipeline's own logs and documents
among them), the contents of the files its contracts name, and a heartbeat with the run's live processes every few seconds. Where
it is up to is kept in a progress file next to the runs directory
(`<runs-dir>.relay.json`), so a restarted relay continues; the hub's answers correct it
when the hub holds less (a new hub, lost data). A run is named on the hub
`<run_id>@<host_id>`; the host id is `--host-id`, else `CONTRAAGENT_HOST_ID`, else the
host name.

## What the monitor shows

The same views as on one host, for every host's runs. A run is live while its host's
heartbeats keep arriving (`contraagent hub --ttl`) and report it alive.

On a hub the monitor shows the host behind each run. The run picker groups the runs by
host, each group headed by the host's state (up, or no report since its last heartbeat),
and filters them by host; the run's header names its host. A run whose host stopped
reporting while the run was alive is neither running nor finished: it reads "no report
from host" in the picker, the header and the run panel, with the host's last report. The
hosts page (`?page=hosts`, the first entry of the run picker) lists each host with its
state, its last report, the seconds between its reports and its runs, then each
account's subscription usage over every run of every host (`/api/hosts`).

A task's transcript reaches the monitor within about a quarter of a second while the
task runs: the relay ships the transcripts of running tasks between its full passes,
and the monitor's transcript feed wakes when the hub receives lines. A viewer that
reconnects resumes where it stopped (the feed's event id is the line number). Earlier
pages are read from sealed segments: a page is at most 1,500 lines and 4 MiB.

## Transcripts on the hub

A transcript is an append-only log that grows while its task runs and never changes
after. The hub appends it to a file in `--streams-dir` (its open segment) and, when the
task ends, when the file reaches 64 MiB, or after an hour or ten idle minutes, seals it:
the lines go to one object in `--segments` as zstd frames of about 256 KiB with an index
of their first lines, and the index is recorded in the `--store` database (with
`--store memory`, it is rebuilt from the sealed objects when the hub starts). A page of an
earlier part of a transcript is one ranged read of one object. The hub answers each
batch with how many lines it holds and how many are sealed (`logs` and `durable` of
its response, `Accepted` in the OpenAPI document `contraagent hub --openapi` writes).

A restarted hub resumes its open segments from `--streams-dir`. The open segments live
on one host's disk, so a hub is one process.
