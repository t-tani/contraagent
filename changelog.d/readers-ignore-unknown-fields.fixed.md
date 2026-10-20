Every reader of a run's records ignores a field it does not know, as
`compatibility.md` states: the monitor, the hub, a resume and the Stop hook
(`contraagent call validate`) read the records of a later release of the same
run format. Before, a new field in a call file, `flow_calls.jsonl`,
`deferred.jsonl`, `launches.jsonl`, the cursor, a flow path, a time box, a
deferral's cause or `run.json`'s `preflight` stopped the reader. The JSON
Schemas of the records no longer say `"additionalProperties": false`. The
config file, and a task's params against its params model, are checked as before.
