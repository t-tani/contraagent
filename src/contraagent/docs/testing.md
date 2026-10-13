# Checking and testing

Two tools find a flow's mistakes before a coding agent spends tokens on them.
Neither says whether a plugin's roles make an LLM write good outputs; that
takes a run on a real coding agent.

## Check: nothing launches

```
contraagent check tasks.py:<flow> --config pipeline.toml --kwargs '{"units": ["a", "b"]}'
```

It builds the task graph a run would, launches nothing, writes no run
directory, and reports every problem at once: an exception in the flow at the
line that raised it, parameters that do not fit their model, an output model
the agent's own check cannot import, a validator's program missing from `PATH`,
what `plugin lint` finds, and what the routing plan refuses. Each problem names
the documentation topic that explains it. A declaration that is wrong where it
is written (a role the plugin does not define, an unknown budget key in
`agent_task`) stops the import of the module that declares it, so it is the one
error reported until it is fixed. `Pipeline.check(flow, ...)`
does the same in Python; its docstring (`contraagent/pipeline/check.py`) lists
every check, and `contraagent check --help` every option.

A generator flow creates its tasks as it runs, so `check` runs it to its first
wait: every flow call it starts runs up to the first `yield` that waits for a
task, and the tasks created by then are checked like a flow's that does not
yield. The kinds it creates later are found in its code: the task declarations
the flow refers to, directly or through the functions, modules, closures and
containers it refers to (the docstring of `contraagent/pipeline/reach.py` says
exactly what is followed). Their declarations and routing are checked too, and
the report lists them as later kinds. Two declarations of one kind that differ
and are both reachable are a warning, not an error: the flow may create tasks of
only one of them (a default argument its caller replaces), and the kind is
checked as the first one found. A task declared inside the flow's body is not
found until it is created. What the flow does with results is tested on the
stub agent.

Run it after every change to tasks, plugins or the config.

## Test: the stub agent

`contraagent.testing.StubAgent` is a coding agent for tests. It reads its call
file like a real one and plays the reply scripted for each task: an output to
write, nothing, a failure, or a rate limit. Only the coding agent is replaced;
output checks, fix-up rounds, failover, retries and the journal run for real.
`stub.backends()` puts it under every coding agent's name, so the pipeline's
own config routes to it, and under each name it acts as that agent does: as
Claude Code it runs the plugin's Stop hooks before it ends its turn and replies
again when one sends the output back (`launch.in_turn`); as omp it stops. A
429 in a test moves the kind's later tasks to the hop too (see `routing`). Tests import the flow's module like any other code: one
outside the project's package needs the project root on `sys.path` (pytest's
`pythonpath` setting). The module docstring (`contraagent/testing.py`) lists
every kind of reply.

::code{file="examples/demo/test_demo.py" from="def summary(launch):" to="@pytest.fixture"}

Every launch is recorded (`stub.launches`, `stub.launches_of(key)`): which
model it ran on, whether it was a fix-up round, the prompt it was sent, its
call file and the launch itself (its budget, environment and plugin).

::code{file="examples/demo/test_demo.py" from="def test_the_flow_checks_clean" to="def test_the_report_covers"}

What a flow returns is `RunReport.value`: a generator flow's return value, or
the output of the task a flow that does not yield returns (its `Pending`):

::code{file="examples/demo/test_demo.py" from="def test_the_report_covers"}
