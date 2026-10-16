# Operating a hub

How to run a hub for real: set it up, connect hosts, keep it within its storage, back
it up, upgrade it, and find what is wrong. What a hub and a relay are is in
[Many hosts: the hub](hub.md); every option is in `contraagent hub --help` and
`contraagent relay --help`.

The files below are in `examples/hub/` of the installed package (`contraagent docs
--path`); copy that directory to the host that runs the hub. It is all the hub's host
needs besides Docker with compose.

## Set up with compose

`examples/hub/compose.yaml` runs the hub with Postgres and RustFS. The hub's image is
built from `examples/hub/Dockerfile`, which installs `contraagent[hub]` from PyPI at
`CONTRAAGENT_VERSION` in `.env`: the version the directory came with, which is what
`contraagent --version` prints where it is installed.

```
cp -r "$(contraagent docs --path)/examples/hub" contraagent-hub && cd contraagent-hub
./make-tokens build-01 build-02     # one ingest token per host, the read token, .env with passwords
$EDITOR .env                        # CONTRAAGENT_HUB_HOSTNAME: the name hosts and browsers use
docker compose up -d                # builds contraagent-hub:<version>, then starts the hub
curl -s http://localhost:8790/healthz
```

| To install the hub from | Set in `.env` |
|---|---|
| PyPI | `CONTRAAGENT_VERSION` (as shipped) |
| a wheel (`contraagent-<version>-py3-none-any.whl`) | copy it into the directory, set `CONTRAAGENT_WHEEL` to its file name and `CONTRAAGENT_VERSION` to its version |
| an image built elsewhere | `CONTRAAGENT_HUB_IMAGE`; `docker compose up -d --no-build` |

The build fails when the installed version is not `CONTRAAGENT_VERSION`. Only wheels
enter the build's context (`.dockerignore`), never `secrets/` or `.env`.

`make-tokens` writes `secrets/ingest-tokens` (`<host_id> <token>`, each token good for
that host only), `secrets/read-token`, `secrets/relay-<host>.env` for each host's relay,
and `.env` from `.env.example` with a new password for each `change-me`. It refuses to
replace tokens that exist. Compose gives the hub its tokens as secrets and its Postgres
and RustFS keys as environment variables, so none is on its command line.

The hub's command, with where each part of a run is kept:

::code{file="examples/hub/compose.yaml" from="    command:" to="    environment:"}

`/healthz` answers 200 when the record store, the blob store and the transcript store
each answer a read, and 503 naming the ones that do not. Compose marks the hub
unhealthy on it; the hub is restarted when its process exits (`restart:
unless-stopped`).

## Connect a host

On each host that runs pipelines, install the package and run the relay as a service:

::code{file="examples/hub/contraagent-relay.service" from="#   install" to="# The relay keeps"}

Set `User=`, `CONTRAAGENT_HUB_URL` and `CONTRAAGENT_RUNS_DIR` in the unit (or in
`/etc/contraagent/relay.env`). The relay keeps where it is up to in
`<runs-dir>.relay.json`; it retries an unreachable hub with backoff and catches up from
the runs directory, so a host never waits for the hub.

A relay checks the certificate of an `https://` hub against the trust store of the
host's operating system. A hub with a certificate from a private certificate authority
needs that authority in the host's trust store.

## Tokens

| To | Do |
|---|---|
| add a host | append `<host_id> <token>` to `secrets/ingest-tokens` (a token from `openssl rand -hex 32`), give the host a `relay.env`, `docker compose up -d --force-recreate hub` |
| revoke a host | remove its line, recreate the hub; its relay then gets 401 |
| rotate the read token | replace `secrets/read-token`, recreate the hub; open `/login?token=<new>` again |

A relay that gets 401 (unknown token) or 403 (a token bound to another host id) logs it
once and retries every minute: the token or `--host-id` is wrong.

## Retention

`contraagent hub --retain-days N` (default: `CONTRAAGENT_RETENTION_DAYS`; in compose,
that variable in `.env`, 30 when unset, every run kept when empty) removes runs whose
last activity is older than N days, with everything the hub holds of them: records,
transcripts (open segments, sealed segments, their index) and file references. It never
removes a run that is live, a run whose host stopped reporting while it ran (the record
of what happened), or a run with no activity time. File contents (blobs) no run
references are removed a day after they were stored. Hosts not seen for N days lose
their heartbeat. Without a retention the hub keeps everything.

The hub prunes five minutes after it starts and then every `--prune-every` hours (24, or
1 for a retention under 7 days), and logs one line per round:

```
prune cutoff=<time> | removed runs=N transcripts=N segments=N blobs=N blob_bytes=N heartbeats=N | kept runs: live=N unresponsive=N no-activity=N | kept heartbeats=N | swept segments=N
```

`contraagent hub prune` prunes once, with the same storage options as the hub.
`--dry-run` lists what it would remove and removes nothing, so it is safe beside a
running hub; without it, run it only while no hub with a retention uses the same
storage. In compose, give it the hub's storage options:

```
docker compose run --rm hub prune --retain-days 30 --dry-run \
  --store=postgresql://contraagent@postgres:5432/contraagent \
  --blobs='s3://contraagent/blobs?endpoint=http://rustfs:9000&region=us-east-1' \
  --streams-dir=/data/streams \
  --segments='s3://contraagent/segments?endpoint=http://rustfs:9000&region=us-east-1'
```

## Back up and restore

| What | How | Needed |
|---|---|---|
| records and the segment index | `docker compose exec postgres pg_dump -U contraagent contraagent > hub.sql` | yes |
| blobs and sealed segments | `docker compose run --rm -v "$PWD/backup:/backup" --entrypoint aws rustfs-init --endpoint-url http://rustfs:9000 s3 sync s3://contraagent /backup` (or the bucket's own replication) | yes |
| open segments (`hub-data` volume) | a copy of the volume | no: relays send again what the hub no longer holds |

Back up Postgres before the bucket: an object no index row names is removed by the
hub's sweep, but an index row naming a missing object is a page the monitor cannot read.
To restore, load the dump into an empty database, restore the bucket, and start the
hub; the relays fill in what came after the backup from their hosts.

## Upgrade

Set `CONTRAAGENT_VERSION` in `.env` to the new version, then build the new image and
recreate the hub (`docker compose up -d --build hub`). Compare the new version's
`examples/hub/` with your copy for changed settings.
The hub creates or extends its tables on start; it refuses a database written by a
newer version. Relays and hubs speak the protocol `contraagent hub --openapi PATH` writes:
upgrade the hub first, then the relays.

## When something is wrong

| What you see | Where it comes from | What to check |
|---|---|---|
| `/healthz` 503 `records` / `blobs` / `transcripts` | that store does not answer | `docker compose ps`, the store's logs, the hub's log (it logs each change of a store's state once) |
| a host shows "no report from host" | its relay's heartbeats stopped arriving | the relay's service (`journalctl -u contraagent-relay`), the network to the hub |
| a relay logs "hub unavailable" | the hub did not answer | `/healthz`; the relay catches up when the hub is back |
| a relay logs 401 or 403 | a wrong token or host id | the Tokens table above |
| `hub-data` grows | open segments of running tasks | segments are sealed when a task ends, at 64 MiB, after ten idle minutes or an hour |

A hub is one process: its open segments are on one host's disk.
