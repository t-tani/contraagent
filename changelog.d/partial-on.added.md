An agent task keeps what a stopped launch wrote: with `agent_task(partial_on=["timeout",
"stalled"])` (or `partial_on` in `[tasks.<kind>]`), a launch the runner stopped for its
time whose output was written by the attempt and passes every check makes the task
partial, as a Python task's `Partial` does: ok, stop `partial`, its reason the launch's
stop, and a resume runs it again. Rows keep the rows written so far. The stub agent plays
such a launch with `writes(value, stop=Stop.TIMEOUT)`.
