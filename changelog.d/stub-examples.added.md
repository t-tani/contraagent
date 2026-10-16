**A stub run writes each output's example.** `contraagent run --stub` (`writes_example()`)
writes, at every part of an output's JSON Schema, the first of its `examples` (a model's own,
`model_config = ConfigDict(json_schema_extra={"examples": [...]})`, or a field's,
`Field(examples=[...])`), else the smallest value that part accepts. A text output takes its
example from `agent_task(output=Annotated[str, Field(examples=[...])])`. With an example
that passes its validators on each output, a stub run goes through the whole flow; the demo's
outputs have one. `contraagent check` reports an example that does not pass its own schema.
A task whose example its validators reject ends `invalid_output` after one round, with no
correction round and no retry (`LaunchResult.retryable`), and the stub run ends with one line
that counts those tasks, names the validators of each kind that rejected them, and asks for
an example that passes them. A failed task's line names an output in the run directory as
`out/<kind>/<unit>.json`.
