**The hub.** `contraagent hub` and `contraagent relay` (the `hub` extra) show the runs of
many hosts in one monitor: a relay on each host sends its runs' records, files and
transcripts to a hub, which keeps them in Postgres and object storage. Per-host tokens for
ingest, a read token for the monitor, retention (`--retain-days`, `contraagent hub
prune`), `GET /healthz`, and a compose example (`contraagent docs hub-operations`).
