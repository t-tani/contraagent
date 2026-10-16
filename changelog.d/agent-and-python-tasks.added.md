A task is a typed Python function whose body is a coding agent (`agent_task`) or Python
(`@python_task`), with pydantic models or text for its parameters and its output. A flow
is plain Python that calls tasks, and passing one task's result to another is the
dependency.
- A generator flow `yield`s a task, a list of tasks or another flow and receives the
  checked output there, so loops, branches, fan-outs and joins are ordinary code. A task
  that did not succeed raises `TaskFailed` (or `TaskDeferred`) at the `yield`.
- Each output is checked against its schema and its validators, Python functions or
  programs (`CommandValidator`). An output that fails goes back to the same agent session
  with the errors, for a correction round. A task whose input is missing or failed its
  checks does not start.
- `Pipeline.run` returns a `RunReport`, and `contraagent run flow.py:flow` runs a flow
  from the command line and exits 1 when a task failed.
