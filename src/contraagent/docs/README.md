# contraagent

Run coding agents as typed, checked, supervised tasks. contraagent turns Claude
Code (`claude -p`), Codex CLI (`codex exec`), opencode (`opencode run`), oh-my-pi
(`omp -p`) and pi (`pi -p`) into the steps of a Python pipeline: a task is a typed
function whose body is a coding agent, and its result is a file checked against a
pydantic model. Scheduling, failover, quotas, deadlines, resume and a live
monitor are the runner's job.

- **The coding agents themselves**: the same task, plugin and config run on each
  of the five; one TOML file chooses the coding agent, model, budget and
  credential of each kind of task.
- **The agent's own extensions**: an agent task's implementation is a plugin in
  the coding agent's own format (roles, skills, MCP servers, hooks), beside its
  built-in tools; hooks are written once and rendered for each agent.
- **A clean context per task**: a task's agent sees its role, plugin, skills and
  call file, not the user's or the project's settings, instruction files, skills,
  hooks or MCP servers, nor another task's conversation ([Plugins](plugins.md)
  lists the exceptions per agent).
- **Outputs are contracts**: an output that does not pass its schema or its
  validators goes back to the same session with the errors.
- **Failover and quotas**: another model, coding agent or credential after a rate
  limit, a failed launch or a safeguard refusal; caps on a subscription's 5-hour
  and weekly usage.
- **Deadlines and resume**: a run's deadline and time boxes defer what cannot
  finish; a resumed run repeats only the tasks whose inputs or definition changed.
- **Checked before it spends**: `contraagent check` reports every problem with
  nothing launched; a stub agent, stub runs and recorded replays test a flow with
  nothing spent.
- **A live monitor** of every run, read-only: the pipeline graph, each task's
  transcript, inputs, outputs and checks, the history of attempts, and trends
  over a period; a hub serves the runs of many hosts.
- **Written by a coding agent, too**: this documentation is installed with the
  package (`contraagent docs`), and `contraagent docs --pointer` points a
  project's coding agent at it.

## Install

Linux, Python 3.12 or later, and a coding agent on `PATH` for real runs:
`claude` (Claude Code), `omp` (oh-my-pi), `opencode`, `pi` (pi.dev), `codex` (Codex CLI), or several of them.

```
uv add contraagent                  # or: pip install contraagent
uv add 'contraagent[monitor]'       # with the web monitor
```

From a wheel or a checkout of the repository, name it in place of the package:
`uv add ./contraagent-<version>-py3-none-any.whl --extra monitor`, or
`uv add --editable <checkout> --extra monitor`. `contraagent --version` prints the
version installed.

## The main path

1. `tasks.py`: the pydantic models, the agent tasks (`agent_task`), the Python
   tasks (`@python_task`) and the flow, a plain function that calls them.
2. `contraagent plugin new plugins/<name>`: the plugin that holds how the coding
   agent does each agent task, a role per kind.
3. `contraagent check tasks.py:<flow> --kwargs '{...}'`: every problem, before
   anything launches; then `contraagent run ... --stub`, the whole flow on a stub agent.
4. `contraagent run tasks.py:<flow> --config pipeline.toml --kwargs '{...}'`: the run,
   on the coding agent and model `pipeline.toml` names for each kind
   (`--agent <name>` runs every kind on another one).
5. `contraagent monitor --runs-dir runs`: the run, live, in a browser.

The [tutorial](tutorial.md) takes these steps from an empty directory.

## Documentation

The documentation is installed with the package and matches its version:
`contraagent docs` prints this index, `contraagent docs <topic>` a topic, and
`contraagent docs --path` where they are. `contraagent docs --pointer` prints a
block that points a coding agent at them, for the instruction file it reads
(`contraagent docs --pointer >> AGENTS.md`; Claude Code reads `CLAUDE.md`).
A `::code` line in these files quotes a file of the package; `contraagent docs`
and the documentation site print the quoted lines in place.

- [Tutorial: your first pipeline](tutorial.md): a pipeline from an empty directory, step by step: models, an agent task and its plugin, a flow, a stub run, a run on a coding agent, a test. Start here.
- [Guide](guide.md): building a pipeline: the steps, the decisions, the pitfalls.
- [Concepts](concepts.md): the words contraagent uses, each with one meaning.
- [Tasks and flows](tasks.md): agent tasks and a map of their options, Python tasks, the flow, flows that depend on results, time boxes, claims, files a task changes, scopes and enrichers around each attempt, a pipeline's own records, and the engine underneath.
- [Plugins](plugins.md): an agent task's implementation: roles, skills, hooks.
- [Contracts and validators](contracts.md): how outputs are checked and sent back.
- [Routing and credentials](routing.md): the config file: coding agent, model, budget, failover, identity, quota caps.
- [Coding agents](agents.md): what each of the five coding agents does and does not do, and how to add another.
- [Checking and testing](testing.md): `contraagent check`, a stub run of the whole flow, and flows tested on a stub agent.
- [The monitor](monitor.md): the live view of runs, and an export of it that needs no server.
- [Many hosts: the hub](hub.md): every host's runs in one monitor: `contraagent hub` and `contraagent relay`.
- [Operating a hub](hub-operations.md): set up with compose, connect hosts, tokens, retention, backups, upgrades, troubleshooting.
- [Compatibility](compatibility.md): what is public, what a release may change, deprecation, every file of a run directory and which are public, and the formats and JSON Schemas of the files a run writes and of the config file.

`examples/tutorial/` is the tutorial's pipeline, finished. `examples/demo/` is a whole pipeline (its tasks, plugin, config, a test, and a
script that runs it); `examples/review/flow.py` and `examples/analysis/flow.py`
are generator flows (a review loop per unit; a three-layer nested flow);
`examples/changes/flow.py` is a task that changes files beside its output;
`examples/implementations/flow.py` declares a step with two implementations and chooses one per unit;
`examples/runner/run.py` runs a flow from a program, with what `contraagent run` cannot pass;
`examples/reference/pipeline.toml` is every config table and key, annotated. The
other directories of `examples/` (`before/`, `claims/`, `hub/`, `light/`, `panels/`,
`partial/`, `preserve/`, `retries/`, `scopes/`, `skills/`, `time_box/`) are each quoted
by the topic that explains them. The test suite runs them all.
