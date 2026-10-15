**Tasks and flows.** A task is a typed function whose body is a coding agent
(`agent_task`) or Python (`@python_task`); its parameters and its output are pydantic
models, or text. A flow is plain Python that calls tasks: passing a task's `Pending` (or
the output it received) to another task is the dependency. A generator flow `yield`s a
task, a list of tasks or another flow and receives the checked output there, so loops,
branches, fan-outs sized by a result and joins across units are ordinary code; a task
that did not succeed raises `TaskFailed` (`TaskDeferred` when it was deferred) at the
`yield`. `Pipeline.run` returns a `RunReport` (`ok`, `failed`, `deferred`, `partial`,
`flow_errors`, the flow's `value`).

- An agent task takes its implementation from a plugin, or from `instructions=`; a light
  launch (`tools=()`) is one turn with no tools, for a judgement; `output_from="message"`
  takes the output from the agent's final message.
- `changes=` names the files a task may change beside its output (recorded per attempt);
  `preserve=` the parts of a JSON output it must keep; `output_of=` lets a task fill in
  another kind's output; `skills_from=` shares skill plugins between tasks.
- One step with several implementations (`agent_task(..., implementations={...})`),
  chosen per unit.
- A Python task's arguments are checked against its annotations; it may retry on named
  exceptions (`retries=`, `retry_on=`) and return a `Partial` result when a service it
  needs is unavailable.
- `TaskScope`s, `ResultEnricher`s and a pipeline's own journal columns (`row_extras`)
  wrap each attempt of both kinds of task.
