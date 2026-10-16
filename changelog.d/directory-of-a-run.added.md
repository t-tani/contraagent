Each run writes its records to `runs/<id>/`: the run, the journal of attempts with each
one's tokens, cost, route and changed files, the plan, the launches, deferrals, quota
rests, call files, outputs and transcripts. Each record has a JSON Schema, and `run.json`
names its run format. A flow and its Python tasks keep the pipeline's own records there
with `contraagent.log` and `contraagent.save`.
