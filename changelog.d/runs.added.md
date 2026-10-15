**Runs and the command line.** `contraagent run flow.py:flow` runs a flow and exits 1 when
a task failed. Each run writes a run directory under `runs/<id>/`: `run.json`, the journal
of attempts (`journal.jsonl`, with each attempt's tokens, cost, hops, credential and
changed files), the plan, deferrals, quota rests, flow calls, launches, call files,
contracts, task definitions and transcripts. Each file has a JSON Schema (`schemas/`), and
`run.json` names its run format (`format`). Flow code and Python tasks keep a pipeline's
own records in the run (`contraagent.log`, `contraagent.save`). Progress goes to the
`contraagent.*` loggers, and every error the library raises is a `ContraagentError`.
