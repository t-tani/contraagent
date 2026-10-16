# Tutorial: your first pipeline

This tutorial builds a small pipeline from an empty directory, one part at a
time, and runs it at each stage. Its reader writes the pipeline: usually a coding
agent that a person asked for one, or a person who wants to understand each part.
When you finish, you can design a pipeline of your own: you know which part goes
where, how to check it without spending tokens, and how to read what a run did.

You need Linux, macOS or Windows, Python 3.12 or later and [uv](https://docs.astral.sh/uv/). Steps
1 to 7 call no model and cost nothing. Step 8 runs a coding agent: any of the five
contraagent runs (Claude Code, omp, opencode, pi, Codex), on your `PATH` and logged
in. Step 8's config uses Claude Code: install it as its
[setup page](https://docs.claude.com/en/docs/claude-code/setup) says, then run
`claude` once and log in (`/login`) with a Claude subscription or an Anthropic API
key. `--agent <name>` runs the same pipeline on another coding agent
([Coding agents](agents.md)).

The finished pipeline is installed with the package:
`$(contraagent docs --path)/examples/tutorial/`. The code on this page is quoted
from it.

## What you build

A team gets bug reports as Markdown files in `issues/`. The pipeline triages
each one with a coding agent (how severe, which area, what goes wrong), plans
a fix for each high-severity report with a stronger model, and joins the
triages into one table, the most severe first:

```
 input                agent tasks                                  Python task
 issues/*.md          (a coding agent does them)                   (your code does it)

 login-timeout.md ──► triage · login-timeout ──► high ──► plan_fix · login-timeout
 csv-export.md    ──► triage · csv-export    ──► medium
 dark-mode.md     ──► triage · dark-mode     ──► low
                          │ all three triages
                          └──────────────────────────────────► write_table ──► one table
```

Each box is a **task**: one kind of work (`triage`) applied to one **unit**
(`login-timeout`). The three triages run at the same time. Each one leaves a
checked JSON file behind, for example:

```json
{"severity": "high", "area": "login", "summary": "Login fails after 30 seconds on slow networks."}
```

## What you learn

| Step | You learn | With |
|---|---|---|
| 1 | set up a project | `uv`, `contraagent docs --path` |
| 2 | describe a task's output so that it can be checked | a pydantic model, a validator |
| 3 | declare an agent task: what it is given, what it leaves, what it may spend | `agent_task` |
| 4 | write how the agent does the task, outside your Python code | a plugin, a role |
| 5 | leave to code what code can do | `@python_task` |
| 6 | connect the tasks | a flow, `Pending` |
| 7 | find mistakes before you spend anything | `contraagent check`, a stub run, the monitor |
| 8 | choose the coding agent and model, run, resume | `pipeline.toml`, `contraagent run` |
| 9 | decide what runs next from a result | a generator flow, `yield` |
| 10 | test the pipeline without a model | `StubAgent`, pytest |

## The architecture

You write four parts. Each answers one question, in its own place:

| Part | Answers | Where | Step |
|---|---|---|---|
| **Interface** | what a task is given, what file it must leave behind, how much it may spend | `tasks.py`: `agent_task(...)`, pydantic models | 2, 3 |
| **Implementation** | how a coding agent does the task: its procedure, its permissions, its hooks | `plugins/triage/`: `agents/<role>.md` and more | 4 |
| **Flow** | which tasks run, and what each one is given | `tasks.py`: a plain Python function | 6, 9 |
| **Config** | which coding agent and model run each kind, with which budget | `pipeline.toml` | 8 |

The code says *what* a task is; the config says *where* it runs. No prompt
holds task knowledge: the role holds the procedure, and the task's data
reaches the agent in a file.

contraagent does everything between those parts. This is one agent task in a
run:

```
 tasks.py (flow) ──── task calls ───► plan: the tasks, and what each waits for
                                          │ a task whose inputs are ready
 pipeline.toml ────── routing ──────────► │ coding agent, model, budget
                                          ▼
                                      call file: params, output path, schema
                                          │
 plugins/triage ──── loaded by ─────────► ▼
                                      the coding agent (claude -p, ...), as the role
                                          │ reads params.report, writes the output file
                                          │ stop hook (Claude Code, Codex): checks the file before the agent stops
                                          ▼
                                      runner: checks the file (schema, then validators)
                                          │ fails ──► the same session, with the errors
                                          ▼ passes
                                      out/<kind>/<unit>.json, journal.jsonl
                                          │
                                          ├──► the flow: the tasks that wait for it
                                          └──► the monitor
```

A Python task takes the same path, but your function runs in place of the
coding agent. Around this path contraagent runs the ready tasks in parallel,
retries a session that made no progress, moves to another model on a rate
limit, and records each step in the run directory, which the monitor reads.

By the end your project looks like this:

```
triage/
  tasks.py              interface and flows: models, tasks
  plugins/triage/       implementation: one role per kind of agent task
  pipeline.toml         config: which coding agent and model run each kind
  test_tasks.py         the flow tested on a stub agent
  issues/*.md           the bug reports (the input)
  runs/                 written by each run, read by the monitor
```

## 1. Set up the project

```
uv init triage && cd triage
uv add 'contraagent[monitor]'
cp -r "$(uv run contraagent docs --path)/examples/tutorial/issues" .
```

`issues/` now holds three bug reports, such as `issues/login-timeout.md`:

::code{file="examples/tutorial/issues/login-timeout.md"}

## 2. Describe the output

An agent task's result is a file the agent writes, and its contract is a
pydantic model. Start `tasks.py` with the imports the whole file needs:

::code{file="examples/tutorial/tasks.py" from="from __future__ import" to="class Triage("}

Then write the model, at the top level of the module: the check of the agent's
file imports this model, so it must be importable.

::code{file="examples/tutorial/tasks.py" from="class Triage(" to="class FixPlan("}

Each `description` reaches the agent in the JSON Schema of its output, so
write it for the agent: it is part of the instructions.

A schema cannot say everything. A rule it cannot express is a **validator**: a
function that takes the file's path and its value and returns a list of errors
(None or an empty list when the file passes).

::code{file="examples/tutorial/tasks.py" from="def short_summary(" to="triage = agent_task("}

## 3. Declare the agent task

`agent_task` declares the interface: the kind's name, the plugin and role that
implement it, the output model, the validators, and a default budget. Every
kind needs `max_turns` and `timeout_s`, here or in the config, so that no
agent runs without a limit.

::code{file="examples/tutorial/tasks.py" from="triage = agent_task(" to="plan_fix = agent_task("}

Note what is not here: no prompt. What the agent should do is in the plugin
(step 4). What it should do it *with* is in the task's params, which you give
when the flow calls the task (step 6).

`plugin="plugins/triage"` is relative to `tasks.py`. The import fails until
the plugin exists and defines the role `triager`.

## 4. Write the implementation: a plugin

```
uv run contraagent plugin new plugins/triage
```

This writes a plugin that works: a settings file with safe permissions, a stop
hook that checks the output inside the session, a skill on how to write an
output file, and one role, `agents/worker.md`. Rename that role to
`agents/triager.md` (and its `name:` to `triager`), then write its procedure:

::code{file="examples/tutorial/plugins/triage/agents/triager.md"}

The prompt the agent gets only names a **call file**. The runner writes one
per task: its params (here `report`, the path of the bug report), the path of
the output file, and the output's JSON Schema. The role says how to do the
work; the call file says what to do it with. So nothing in a plugin names a
run, a report or a path, and one role serves every report.

Check that the plugin's parts agree:

```
uv run contraagent plugin lint plugins/triage
```

## 5. Add a Python task

Not every step needs a model. Work that code does the same way each time, such
as preparing an input or joining results, is a **Python task**: a function with
`@python_task`. Its return annotation is its output contract, and it runs in
your process.

::code{file="examples/tutorial/tasks.py" from="@python_task" to="def report_path("}

## 6. Write the flow

A flow is a plain function that calls the tasks. The first argument of a task
call is the **unit**, what the kind is applied to: here the report's name. One
kind on one unit is one **task** (`triage · login-timeout`). The keyword
arguments are its params.

::code{file="examples/tutorial/tasks.py" from="def report_path(" to="def triage_one("}

Calling a task in a flow does not run it. It returns a `Pending`, a reference
to the task's future output. Passing a `Pending` to another task is the
dependency: `write_table` waits for every triage and receives their checked
outputs. The three triages depend on nothing, so they run at the same time.

## 7. Check it, and run it without a model

`contraagent check` finds what is wrong before anything launches: a flow that
raises, params that do not fit, an output model the agent cannot import, a
plugin that does not lint, a kind with no budget.

```
uv run contraagent check tasks.py:triage_all --kwargs '{"reports": ["login-timeout", "csv-export", "dark-mode"]}'
```

```
✓ 4 tasks, 2 kinds: triage 3, write_table 1
  triage: claude/(the agent default model) effort=medium max_turns=10 timeout_s=300
```

A **stub run** goes further: it runs the whole flow with a stub agent in place
of every task. Each output is its model's example, or for a model with none (as
here) the smallest value its schema accepts (`contraagent docs testing`), so no
model is called and nothing is spent.

```
uv run contraagent run tasks.py:triage_all --stub --kwargs '{"reports": ["login-timeout", "csv-export", "dark-mode"]}'
```

```
4 tasks created:
  triage · login-timeout | completed | triage_all (line 62)
  triage · csv-export | completed | triage_all (line 62)
  triage · dark-mode | completed | triage_all (line 62)
  write_table | completed | triage_all (line 63)
✓ 4/4 tasks done in 1.3s; run in runs/triage_all-stub
```

Each line names a task, how it ended, and the flow function and line that created
it: the lines of the finished `tasks.py`, so yours may differ. Before these lines,
the log on stderr gives each kind's route (`[route]`) and each task's start and end
(`[start]`, `[end]`).

The run id is the flow's name, with `-stub` for a stub run, and a run id that
already holds a run is refused. Run the stub again with `--resume`, which continues
that run, or give it a new id with `--run-id` (both in step 8).

Open the run in the monitor:

```
uv run contraagent monitor --runs-dir runs      # http://127.0.0.1:8787
```

`--port` serves it on another port. The run directory is what the monitor reads,
and you can read it too. Among its files:

```
runs/triage_all-stub/
  calls/triage-login-timeout.json   the call file the agent was given
  out/triage/login-timeout.json     its output, checked
  out/write_table/write_table.json  the table: in a stub run "", the smallest string
  plan.jsonl                        every task the flow created
  journal.jsonl                     every finished attempt
  streams/                          the agents' transcripts
```

In a stub run no Python task's function runs: the stub plays `write_table` too, so
its file holds the smallest string. `--execute write_table` runs the real function.
[Compatibility](compatibility.md#the-run-directory) lists every file of a run directory.

## 8. Run it on a coding agent

This step spends tokens. When a coding agent follows this tutorial for a person, it
writes the config and checks it, and the person starts the run and watches it in the
monitor.

The config says where each kind runs. Write `pipeline.toml`:

::code{file="examples/tutorial/pipeline.toml" to="[tasks.plan_fix]"}

A `[tasks.<kind>]` table changes one kind: its model, its budget, its failover
chain (step 9 adds one). Check again with the config, then run:

```
uv run contraagent check tasks.py:triage_all --config pipeline.toml --kwargs '{"reports": ["login-timeout", "csv-export", "dark-mode"]}'
uv run contraagent run tasks.py:triage_all --config pipeline.toml --kwargs '{"reports": ["login-timeout", "csv-export", "dark-mode"]}'
```

`--kwargs '{"reports": ["login-timeout"]}'` runs one report, and so spends a
third. `--agent codex --model <model>` runs every kind on Codex instead (or on
`omp`, `opencode`, `pi`), with a model of that coding agent: each one names its
models its own way.

For each triage, contraagent writes the call file, starts `claude -p` with the
plugin loaded and the role selected, and waits. Before the agent stops, the
plugin's stop hook checks its output file against the schema; when it fails,
the agent reads the errors and fixes the file in the same turn. Claude Code and
Codex run this stop hook; omp, opencode and pi have none that continues a session
([Coding agents](agents.md)), so for them the runner's check below does this work.
After the session, the runner checks the file again, with the validators too. An
output that still fails goes back to the same session with the errors, a
**correction round** ([Contracts](contracts.md) has the details). A session that
ends without progress is tried again in a fresh session, a new **attempt**
(`retries`).

Watch it in the monitor while it runs: each task's status, its transcript as
the agent writes it, its cost and tokens, its corrections, and its output field
by field. The table is in `runs/triage_all/out/write_table/write_table.json`, as a
JSON string: `jq -r . runs/triage_all/out/write_table/write_table.json` prints it.

The run id is the flow's name. Running the same flow again under that id needs
`--resume`, which skips every task that finished with the same params and
definition, and runs again what changed: edit `triager.md`, resume, and the
triages run again, then the table that reads them. Or give a new run id with
`--run-id`.

## 9. Decide on results

`triage_all` creates every task at the start. A flow that decides what to do
from an output is a **generator**: it `yield`s a task call and receives the
task's checked output there. Plain Python then decides what runs next.

Add a model and a task for the fix plan, and a role `agents/planner.md` in the
same plugin:

::code{file="examples/tutorial/tasks.py" from="class FixPlan(" to="def short_summary("}

::code{file="examples/tutorial/tasks.py" from="plan_fix = agent_task(" to="@python_task"}

::code{file="examples/tutorial/plugins/triage/agents/planner.md"}

Then the flow:

::code{file="examples/tutorial/tasks.py" from="def triage_one("}

`triage_one` waits for one triage and plans a fix only when it is high.
`triage_and_plan` yields a list of `triage_one` calls: each runs as its own
**flow call**, at the same time as the others, and the list receives what each
one returned. A report that is not high severity does not wait for another
report's plan.

Planning a fix is harder than triage, so give `plan_fix` a stronger model in
`pipeline.toml`:

::code{file="examples/tutorial/pipeline.toml" from="[tasks.plan_fix]"}

A kind table can also hold a failover chain: on a rate limit, the task moves to
the next hop, which may be another model, another coding agent or another
credential (see [Routing and credentials](routing.md)).

Check and run it as before, with `tasks.py:triage_and_plan`. `check` lists
`plan_fix` as a later kind: the flow creates it only after a result, but its
declaration and its routing are checked now. A stub run never creates a plan:
its triages are the smallest values, `low`, so the flow never takes that
branch. The test in the next step does.

In the monitor, the overview draws the flow as a graph: a node for
`triage_one` holds its own tasks, and each report is one mark in it.

## 10. Test it

A test runs the real pipeline (its checks, correction rounds, retries and journal)
with `StubAgent` in place of the coding agent. You script what each task
replies, and assert on what happened. Here the triage of `login-timeout` is
high severity, and its first summary is too long:

Start `test_tasks.py` with its imports. The example imports the flows from the
package, `contraagent.docs.examples.tutorial.tasks`; your test imports them from
your own module, `from tasks import triage_all, triage_and_plan`:

::code{file="examples/tutorial/test_tutorial.py" from="from __future__ import" to="def triage(launch):"}

Then the replies and the tests:

::code{file="examples/tutorial/test_tutorial.py" from="def triage(launch):" to="def test_the_flows_check_clean"}

::code{file="examples/tutorial/test_tutorial.py" from="def test_only_a_high" to="def test_the_table_lists"}

`agent.backends()` registers the stub under every coding agent's name, so the
pipeline's own config routes to it: the first test also shows that `plan_fix`
ran on the model `pipeline.toml` gave it. With the tests in `test_tasks.py`:

```
uv add --dev pytest
uv run pytest
```

## Where to go next

- [Guide](guide.md): the steps again, in short, with the decisions and the pitfalls.
- [Tasks and flows](tasks.md): loops, keys, resume, claims, files a task changes.
- [Contracts and validators](contracts.md): command validators the agent runs itself, rules over the output and the input together.
- [Plugins](plugins.md): skills, hooks, tools and web search.
- [Routing and credentials](routing.md): failover, credentials, quota caps.
- [The monitor](monitor.md): every view of a run.
- `examples/demo/`: a larger pipeline with a review loop, failover and failures, for the monitor.
