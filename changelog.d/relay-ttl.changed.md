The relay sets how long the hub counts its host as up: `contraagent relay --ttl`,
four times `--interval` unless given, and more than `--interval`. Each heartbeat
carries it as `ttl_s`, and the hub counts the host as up for `ttl_s` seconds after it
receives the heartbeat, so a relay with a long `--interval` no longer shows its host as
down between heartbeats. `contraagent hub --ttl` and `contraagent hub prune --ttl` are
removed. `HeartbeatAck.ttl_s` is the TTL of the heartbeat it answers, and the hub reads
a heartbeat without `ttl_s` as four times its `interval_s`. Upgrade the hub first,
then the relays.
