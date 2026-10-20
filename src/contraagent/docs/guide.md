# Guide

This page is for the one who writes a pipeline: usually a coding agent that a
person asked for it. contraagent's API is newer than any model's training data, so
read the topic before writing the code, and check what you wrote with
`contraagent check`. The [tutorial](tutorial.md) builds a pipeline step by step.
This page is the short form, with the decisions and the pitfalls.

A pipeline has three parts: the **interface** of each task, in Python; the
**implementation** of each agent task, a plugin the coding agent loads itself;
and the **flow**, a plain function that calls the tasks. The demo is all three:

```
examples/demo/
  tasks.py        the interface (agent tasks, Python tasks) and the flows
  checks.py       a check run as a command (a CommandValidator's program)
  plugins/docs/   the implementation, loaded by the coding agent itself
  pipeline.toml   routing: which coding agent and model each kind runs on
  test_demo.py    the flows checked and tested without spending tokens
  run.py          runs the flow and serves the monitor
```

`python -m contraagent.docs.examples.demo.run` runs it on a demo agent (no
coding agent needed) and serves the monitor on http://127.0.0.1:8787 (`--port`
for another port).

## Steps

1. **Models.** The pydantic models a task takes and leaves behind, at the top
   level of an importable module. → [Contracts](contracts.md)
2. **Agent tasks.** `agent_task(...)`: the interface, naming its plugin and
   role, its output, its validators and its budget. → [Tasks](tasks.md)
3. **Plugin.** `contraagent plugin new plugins/<name>`, then the procedure in
   `agents/<role>.md`, then `contraagent plugin lint`. → [Plugins](plugins.md)
4. **Python tasks.** `@python_task` for anything code does deterministically. → [Tasks](tasks.md)
5. **Flow.** A function that calls the tasks; passing a task's result to another
   is the dependency. A flow that waits is an `async def` function: it receives
   outputs at each `await` and decides what runs next from them. → [Tasks](tasks.md)
6. **Config.** Where each kind runs, in TOML. → [Routing](routing.md)
7. **Check.** `contraagent check tasks.py:<flow> --config pipeline.toml --kwargs '{...}'`
   until it prints ✓. → [Checking and testing](testing.md)
8. **Test.** The flow on `contraagent.testing.StubAgent`, in pytest. → [Checking and testing](testing.md)
9. **Run.** A run on the coding agents spends tokens, so the person who asked for
   the pipeline starts it, unless they ask the agent to. `contraagent run` takes the
   arguments `check` took (`--run-id`, `--resume`
   to continue one), or `Pipeline(config).run(flow, ...)` from a program for what a
   command line cannot pass: a journal column (`row_extras`), a `quota_rule`, scopes,
   enrichers, its own backends, `env`, `services`, `mcp_servers`
   (`examples/runner/run.py` lists them). A check of such a pipeline is
   `Pipeline(config, ...).check(...)` from a program too. The person
   watches it in the monitor. → [Tasks](tasks.md), [The monitor](monitor.md)

## Decisions

| Question | Answer |
|---|---|
| Agent task or Python task? | Python when code can do it deterministically (preparing inputs, merging results); an agent task for reading, judging, writing. |
| Output: a model, `str` or rows? | A model for anything a task or a program reads next; `str` for a document; `Rows[Row]` for a list that grows as the agent works, one row per line. → [Contracts](contracts.md#rows) |
| A long task that may run out of time? | `partial_on=["timeout", "stalled"]` keeps what it wrote when that passes its checks, as a partial result. → [Contracts](contracts.md#a-launch-stopped-for-its-time) |
| A server that several tasks use? | A service that a claim name stands for (`Pipeline(services=)`); the runner starts and stops it. → [Tasks](tasks.md#services-a-server-that-the-tasks-of-a-claim-share) |
| A rule the schema cannot express? | A validator; a `CommandValidator` when the agent should also run it before it stops. → [Contracts](contracts.md) |
| A rule about the output and the input together? | A validator that takes `params` (or a `CommandValidator` given `{call}`). → [Contracts](contracts.md) |
| Order without passing data? | `.options(after=[...])` on the later task. |
| What runs depends on results? | An `async def` flow: `await` a task call and receive its output there; loops, branches and fan-outs are plain Python and asyncio (`asyncio.gather`). → [Tasks](tasks.md#flows-that-depend-on-results) |
| A one-off task with no plugin? | `agent_task(..., instructions=...)`; a plugin for anything kept. |
| Where may a task's data go? | `requires=` traits in code; credentials in the config. → [Routing](routing.md) |

## Pitfalls

- An output model in the script you run or inside a function: the agent's own
  check cannot import it.
- A Python validator runs in the runner only, so the agent hears of its errors in
  a correction round. A rule the agent should meet before it stops is a
  `CommandValidator` (given `{call}` when it needs the params).
- A kind with no `max_turns` or `timeout_s`, in code or in the config, is refused.
- A relative `plugin=` path is relative to the file that calls `agent_task`. A
  function in another directory that calls `agent_task` for its callers takes an
  absolute path from them: `Path(__file__).parent / "plugins/review"`.
- Task knowledge in a prompt or in Python: it belongs in the plugin's role.
  Per-task data belongs in params: the agent reads it from its call file.
  Nothing in a plugin names a run, a unit or a file path.
- The same kind on the same unit from two flow calls needs `.options(key=...)`; within one
  flow call the second is numbered (`<key>~2`).
- A coroutine never awaited never runs: `await sub(u)`, or
  `asyncio.gather(sub(u), ...)` for flow calls of their own, not `sub(u)`.
  `contraagent check` reports a coroutine never awaited as an error, the run logs
  a warning, and mypy and pyright report it too.
- Flow code must take the same path for the same outputs, or a resumed run
  creates different tasks: a random choice or the clock belongs in a Python task.
- Flow code between two `await`s runs on the thread of the event loop that
  schedules every task: heavy work there stalls the run, and belongs in a Python
  task. So do waiting and I/O: flow code runs on an event loop with no clock, no
  threads and no I/O, so `asyncio.sleep(5)`, `asyncio.timeout(5)`,
  `asyncio.to_thread` and an async client raise `TypeError` at their `await`.
- A flow awaits task calls and flow calls, with `await`, `asyncio.gather` and
  `asyncio.TaskGroup`; not `asyncio.wait`, `as_completed`, `shield`, `Queue` or
  `Event`. They are not refused, but a branch on what finished first takes another
  path on a resume. A flow call that waits for what nothing will answer is closed
  once no task is left to run, with an error that names the line where it waits.
- A failed task stops the rest of the flow call that awaits it, also work that does
  not need its output. One flow call per unit, gathered with
  `asyncio.gather(..., return_exceptions=True)`, keeps a failure to its unit; every
  other unit, and every task already queued or running, goes on. `asyncio.TaskGroup`
  is the choice when the work is all or nothing. An exception of flow code's own (a
  bug, `TooManyPasses`) caught this way still makes the run not ok.
- Flow code does not call `Pipeline.run` or `asyncio.run`: both raise inside a
  flow. Async code outside a flow runs a pipeline with
  `await Pipeline(config).run_async(flow, ...)`.
- Flow code does not branch on the order in which tasks finish
  (`asyncio.as_completed`, `FIRST_COMPLETED`): a resumed run finishes them in
  another order. `asyncio.gather(..., return_exceptions=True)`, inspected by
  position, tolerates failures in the same way in every run.
- A Python task runs once, as one task, and does not await tasks. Work that waits
  on tasks belongs in a flow, with its Python steps as separate Python tasks.
- A task is called inside a flow only; `pending.output` is read after the run (an
  async flow receives the output at the `await`).
- A failed task refuses every task that reads its output; a task that reads
  every unit's output (a report) is refused when any of them failed.
- The library reports through `logging` (`contraagent.*`): configure it at INFO
  to see routing, each task's start and end, correction rounds and model switches.
- Running a flow again under the same run id needs `resume=True` (`--resume`), or another run id.

## Limits

- On macOS and Windows some things differ from Linux
  ([Operating systems](#operating-systems)).
- The coding agents differ in what they enforce, and [Coding agents](agents.md)
  has a row for each difference. In short: Claude Code, Codex and omp run a stop
  hook that continues the session, so on opencode and pi the runner's check and a
  correction round alone hold the output to its contract; Codex runs no light
  launch and enforces no `max_budget_usd`; only Claude Code and opencode enforce
  `context_budget`; pi does not enforce `max_turns`.
- A credential rests on a quota only where its coding agent reports quota
  readings, or contraagent reads them: Claude Code, omp, Codex with a ChatGPT
  login, and opencode and pi for an `opencode-go` model, through the OpenCode Go
  usage ([Routing](routing.md#quota-caps)). A gateway, an API key or another
  opencode or pi model never rests on a quota.
- omp's credential isolation is verified for the `anthropic`, `openai-codex` and
  `litellm` providers only. A launch opencode runs sees the user's own opencode
  config (`~/.config/opencode`), except a light launch.
- `workload_identity`, `bedrock` and `vertex` follow Claude Code's
  documentation and are not yet checked against the real CLI.
- contraagent writes outside the run directory: its scratch directories under
  `<temp dir>/contraagent-<uid>/`, and pi's and Codex's directories under
  `~/.cache/contraagent/` ([Coding agents](agents.md#directories-outside-the-run)).

## Operating systems

contraagent runs on Linux, macOS and Windows. What differs:

| | Linux, macOS | Windows |
|---|---|---|
| An agent session's processes | a session of its own; stopped by SIGTERM, then SIGKILL | a process group of its own in a Job Object; stopped by CTRL_BREAK, then by ending the job |
| The pipeline's process killed outright | a watchdog process stops the sessions still running | the OS ends the job of each session still running |
| The run lock | `flock` | `msvcrt.locking` |
| A coding agent installed by npm (`claude.cmd`) | — | started as the program the batch file runs, so the arguments reach it unchanged; a batch file npm did not make is refused |
| A prompt goes over stdin | past 60,000 characters | past 16,000 characters (a command line holds at most 32,767) |
| A plugin's hook scripts | the `bash` on `PATH` | the bash of Git for Windows: `CONTRAAGENT_BASH`, else `CLAUDE_CODE_GIT_BASH_PATH`, else a `bash` on `PATH` outside `System32`, else the one in Program Files. Claude Code runs its own hooks with it too. Codex runs a hook's command under PowerShell, so a Codex launch has PowerShell start that bash; on a Windows without PowerShell, where Codex uses `cmd.exe`, the hook does not run. Without one, a hook script does not run, and a Codex launch is passed no plugin hooks. |
| A link in pi's agent directory or to a Codex skill | a symbolic link | a symbolic link where the user may make one, else a junction (a directory) or a hard link or copy (a file) |
| Scratch directories | `<temp dir>/contraagent-<uid>/` | `%TEMP%\contraagent\` (`%TEMP%` is the user's own) |
| Codex's sandbox | bubblewrap on Linux, Seatbelt on macOS | Codex's Windows sandbox (`windows.sandbox` in Codex's config) |
| `contraagent hub`, `contraagent relay` | stop gracefully on SIGTERM | Windows sends no SIGTERM |

On macOS the OS shows no process's environment to another process, so the monitor
knows an agent session by the telemetry line in its command line; a session whose
prompt came over stdin shows in the process tree without its task.

The test suite runs on all three. The tests that launch real coding agents and the
hub's end-to-end tests run on Linux.

## The API

The docstrings are the reference. A pipeline imports from the public modules only:
`contraagent` (`agent_task`, `python_task`, `Pipeline`, `Pipeline.check`,
validators, the task and result a callback is given, the errors), `contraagent.config`
(credentials, routes, budgets), `contraagent.backends` (the coding agents, the call file),
`contraagent.engine` (the runners, schedulers and contracts underneath a pipeline),
`contraagent.plugins`, `contraagent.monitor` and `contraagent.testing`
([Compatibility](compatibility.md) says what is public). `help(<name>)` prints a
name's docstring, and `contraagent docs --path` prints where the documentation is.
