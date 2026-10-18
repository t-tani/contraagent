A launch refused for its credential (`auth_failed`: a 401 or 403) rests that credential on
its coding agent and model for the rest of the run. Later tasks pass the hop over without a
launch (`skipped_hops`), a pool goes on to its next member at once, and `rests.jsonl` and the
monitor record the rest (`Rest.stop`, `Rest.agent`, `Rest.model`). A task with every hop
refused fails `auth_failed` without a launch rather than being deferred. An attempt whose
chain ends on a refused hop after a hop that ran ends on the stop of the hop that ran.
