"""The hub: runs of many hosts in one monitor.

Each host keeps writing its runs to its own `runs/` directory, as without a hub. A
`contraagent relay` on the host ships each run's records (`contraagent.rundir`) and a
heartbeat to a `contraagent hub`, which stores them and serves the monitor's views of
every host's runs through `HubSource` and `HeartbeatLiveness`.

* `protocol`  the wire between relay and hub (HTTP + JSON): record batches, heartbeats, blobs
* `store`     `HubStore` (the records the hub holds) and `BlobStore` (file contents by
              SHA-256), with in-memory and directory implementations
* `streams`   `StreamLogs`: task transcripts, apart from the other records
* `segments`  `SegmentedStreamLogs`: open segments on local disk, sealed ones in object storage
              (`segment_format`, `segment_objects`)
* `source`    `HubSource` and `HeartbeatLiveness`: the monitor's ports over a hub store
* `core`      `Hub`: what the hub does with each request, the monitor it serves, and
              its retention (`Hub.prune`)
* `client`    `HubClient`: how a relay reaches a hub; `DirectClient` calls a `Hub` in-process
* `relay`     `contraagent relay`: ship one host's runs
* `server`    `contraagent hub`: receive, store, and serve the monitor

It needs the `hub` extra (`pip install 'contraagent[hub]'`) for its server, its
Postgres store and its S3 blobs; the protocol, the in-memory store and the sources do not.
"""
