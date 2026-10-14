# Guide

contraagent's API is newer than any LLM's training data: read the topic before
writing the code, and check what you wrote with `contraagent check`. The
[tutorial](tutorial.md) builds a pipeline step by step; this page is the short
form, with the decisions and the pitfalls.

A pipeline has three parts: the **interface** of each task, in Python; the
**implementation** of each agent task, a plugin the coding agent loads itself;
and the **flow**, a plain function that calls the tasks. The demo is all three:

```
examples/demo/
  tasks.py        the interface (agent tasks, Python tasks) and the flows
  plugins/docs/   the implementation, loaded by the coding agent itself
  pipeline.toml   routing: which coding agent and model each kind runs on
  test_demo.py    the flows checked and tested without spending tokens
  run.py          runs the flow and serves the monitor
```

`python -m contraagent.docs.examples.demo.run` runs it on a demo agent (no
coding agent needed) and serves the monitor on http://127.0.0.1:8787.

## Steps

1. **Models.** The pydantic models a task takes and leaves behind, at the top
   level of an importable module. → [Contracts](contracts.md)
2. **Agent tasks.** `agent_task(...)`: the interface, naming its plugin and
   role, its output, its validators and its budget. → [Tasks](tasks.md)
3. **Plugin.** `contraagent plugin new plugins/<name>`, then the procedure in
   `agents/<role>.md`, then `contraagent plugin lint`. → [Plugins](plugins.md)
4. **Python tasks.** `@python_task` for anything code does deterministically. → [Tasks](tasks.md)
5. **Flow.** A function that calls the tasks; passing a task's result to another
   is the dependency. A generator flow receives outputs at each `yield` and
   decides what runs next from them. → [Tasks](tasks.md)
6. **Config.** Where each kind runs, in TOML. → [Routing](routing.md)
7. **Check.** `contraagent check tasks.py:<flow> --config pipeline.toml --kwargs '{...}'`
   until it prints ✓. → [Checking and testing](testing.md)
8. **Test.** The flow on `contraagent.testing.StubAgent`, in pytest. → [Checking and testing](testing.md)
9. **Run.** `contraagent run` with the arguments `check` took (`--run-id`, `--resume`
   to continue one), or `Pipeline(config).run(flow, ...)` from a program that
   needs more (its own backends, env, monitor panels). Watch it in the
   monitor. → [Tasks](tasks.md), [The monitor](monitor.md)

## Decisions

| Question | Answer |
|---|---|
| Agent task or Python task? | Python when code can do it deterministically (preparing inputs, merging results); an agent task for reading, judging, writing. |
| Output: a model or `str`? | A model for anything a task or a program reads next; `str` for a document. |
| A rule the schema cannot express? | A validator; a `CommandValidator` when the agent should also run it before it stops. → [Contracts](contracts.md) |
| A rule about the output and the input together? | A validator that takes `params` (or a `CommandValidator` given `{call}`). → [Contracts](contracts.md) |
| Order without passing data? | `after=` on the later task. |
| What runs depends on results? | A generator flow: `yield` a task call and receive its output there; loops, branches and fan-outs are plain Python. → [Tasks](tasks.md) |
| A one-off task with no plugin? | `agent_task(..., instructions=...)`; a plugin for anything kept. |
| Where may a task's data go? | `requires=` traits in code; credentials in the config. → [Routing](routing.md) |

## Pitfalls

- An output model in the script you run or inside a function: the agent's own
  check cannot import it.
- A Python validator runs in the runner only, so the agent hears of its errors in
  a fix-up round. A rule the agent should meet before it stops is a
  `CommandValidator` (given `{call}` when it needs the params).
- A kind with no `max_turns` or `timeout_s`, in code or in the config, is refused.
- A relative `plugin=` path is relative to the file that calls `agent_task`.
- Task knowledge in a prompt or in Python: it belongs in the plugin's role.
  Per-task data belongs in params: the agent reads it from its call file.
  Nothing in a plugin names a run, a unit or a file path.
- The same kind on the same unit from two flow calls needs `key=`; within one
  flow call the second is numbered (`<key>~2`).
- A generator called and not yielded never runs: `yield sub(u)` (its own flow
  call) or `yield from sub(u)`, not `sub(u)`.
- Flow code must take the same path for the same outputs, or a resumed run
  creates different tasks: a random choice or the clock belongs in a Python task.
- Flow code between two `yield`s runs on the thread that schedules every task:
  heavy work there stalls the run, and belongs in a Python task.
- A Python task runs once, as one task, and cannot yield tasks. Work that waits
  on tasks belongs in a flow, with its Python steps as separate Python tasks.
- A task is called inside a flow only; `pending.output` is read after the run (a
  generator flow receives the output at the `yield`).
- A failed task refuses every task that reads its output; a task that reads
  every unit's output (a report) is refused when any of them failed.
- The library reports through `logging` (`contraagent.*`): configure it at INFO
  to see routing, each task's start and end, fix-ups and model switches.
- Running a flow again under the same run id needs `resume=True` (`--resume`), or another run id.

## Limits

- Linux only: run locks and process tracking use `fcntl` and `/proc`.
- On omp no stop hook can keep a session going: the runner's check and its
  session resume enforce the output instead. omp's credential isolation is
  verified for the `anthropic` and `litellm` providers only.
- `workload_identity`, `bedrock` and `vertex` follow Claude Code's
  documentation and are not yet checked against the real CLI.

## The API

The docstrings are the reference: `contraagent/pipeline/` (`agent_task`,
`python_task`, `Pipeline`, `Pipeline.check`), `contraagent/plugins/`,
`contraagent/contracts.py`, `contraagent/validators.py`,
`contraagent/backends/credentials.py`, `contraagent/testing.py`, and the layer
list in `contraagent/__init__.py`. `contraagent docs --path` prints where they are.
