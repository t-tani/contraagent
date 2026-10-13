# Operating a hub

How to run a hub for real: set it up, connect hosts, keep it within its storage, back
it up, upgrade it, and find what is wrong. What a hub and a relay are is in
[Many hosts: the hub](hub.md); every option is in `contraagent hub --help` and
`contraagent relay --help`.

The files below are in `examples/hub/` of the installed package (`contraagent docs
--path`); copy that directory to the host that runs the hub.

## Set up with compose

`examples/hub/compose.yaml` runs the hub with Postgres and MinIO; the hub's image is
built from this source tree (`examples/hub/Dockerfile`) or named by
`CONTRAAGENT_HUB_IMAGE`.

```
./make-tokens build-01 build-02     # one ingest token per host, the read token, .env with passwords
$EDITOR .env                        # CONTRAAGENT_HUB_HOSTNAME: the name hosts and browsers use
docker compose up -d
curl -s http://localhost:8790/healthz
```

`make-tokens` writes `secrets/ingest-tokens` (`<host_id> <token>`, each token good for
that host only), `secrets/read-token`, `secrets/relay-<host>.env` for each host's relay,
and `.env` from `.env.example` with a new password for each `change-me`. It refuses to
replace tokens that exist. Compose gives the hub its tokens as secrets and its Postgres
and MinIO passwords as environment variables, so none is on its command line.

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

## Tokens

| To | Do |
|---|---|
| add a host | append `<host_id> <token>` to `secrets/ingest-tokens` (a token from `openssl rand -hex 32`), give the host a `relay.env`, `docker compose up -d --force-recreate hub` |
| revoke a host | remove its line, recreate the hub; its relay then gets 401 |
| rotate the read token | replace `secrets/read-token`, recreate the hub; open `/login?token=<new>` again |

A relay that gets 401 (unknown token) or 403 (a token bound to another host id) logs it
once and retries every minute: the token or `--host-id` is wrong.

## Retention

`contraagent hub --retain-days N` (in compose, `CONTRAAGENT_RETENTION_DAYS` in `.env`)
removes runs whose last activity is older than N days, with everything the hub holds of
them: records, transcripts (open segments, sealed segments, their index) and file
references. It never removes a run that is live, a run whose host stopped reporting
while it ran (the record of what happened), or a run with no activity time. File
contents (blobs) no run references are removed a day after they were stored. Hosts not
seen for N days lose their heartbeat. Without `--retain-days` the hub keeps everything.

The hub prunes on a schedule of its own (`--prune-every`). To see what a prune would
remove, or to prune by hand while no hub prunes the same storage:

```
docker compose run --rm hub prune --retain-days 30 --dry-run
```

## Back up and restore

| What | How | Needed |
|---|---|---|
| records and the segment index | `docker compose exec postgres pg_dump -U contraagent contraagent > hub.sql` | yes |
| blobs and sealed segments | `mc mirror minio/contraagent <backup>` (or the bucket's own replication) | yes |
| open segments (`hub-data` volume) | a copy of the volume | no: relays send again what the hub no longer holds |

Back up Postgres before the bucket: an object no index row names is removed by the
hub's sweep, but an index row naming a missing object is a page the monitor cannot read.
To restore, load the dump into an empty database, restore the bucket, and start the
hub; the relays fill in what came after the backup from their hosts.

## Upgrade

Build or pull the new image and recreate the hub (`docker compose up -d --build hub`).
The hub creates or extends its tables on start; it refuses a database written by a
newer version. Relays and hubs speak the protocol in `contraagent/hub/openapi.json`:
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
