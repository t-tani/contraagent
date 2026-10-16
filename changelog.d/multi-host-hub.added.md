`contraagent hub` and `contraagent relay` (the `hub` extra) show the runs of many hosts in
one monitor. A relay on each host sends its runs to the hub, which keeps them in Postgres
and object storage, with a token per host, a read token for the monitor and retention.
`contraagent docs hub-operations` describes a deployment.
