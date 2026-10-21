# contraagent

contraagent runs coding agents as typed, checked and supervised tasks. Claude Code
(`claude -p`), Codex CLI (`codex exec`), opencode (`opencode run`), oh-my-pi
(`omp -p`) and pi (`pi -p`) become the steps of a Python pipeline. A task is a typed
function whose body is a coding agent, and its result is a file that contraagent
checks against a pydantic model. The runner handles scheduling, failover, quotas,
deadlines and resume, and a live monitor shows every run.

## How a task runs

An agent task's implementation is a [plugin](plugins.md) in the coding agent's own
format, with roles, skills, MCP servers and hooks, and the agent keeps its built-in
tools. contraagent launches the agent in a clean context with its role, plugin,
skills and call file. The user's and the project's settings, instruction files,
skills, hooks and MCP servers are excluded, and so are the conversations of other
tasks.

The agent writes the output file, and contraagent checks it against the pydantic
model and the validators. When a check fails, the errors go to the same session for
a correction round. The flow receives the output as a typed object only after it
passes.

Around each launch, a task moves to another model, coding agent or credential (the
account that the agent's API calls are billed to) after a rate limit, a failed launch
or a safeguard refusal. Caps on a subscription's 5-hour and weekly usage pause a
credential. Near the run's deadline, or the deadline of a
[time box](tasks.md#a-deadline-over-part-of-a-flow-time-boxes) over part of the
flow, work unlikely to finish in time gives its slot to other work and is deferred. A resumed run repeats only the tasks whose inputs or
definition changed.

One TOML file chooses the coding agent, model, budget and credential for each kind
of task, and the same task, plugin and config run on all five coding agents.
`contraagent check` reports every problem and launches nothing. A stub agent, stub
runs (runs that launch no coding agent) and recorded replays test a flow without
spending anything. The read-only [monitor](monitor.md) shows each run, and a
[hub](hub.md) serves the runs of many hosts in one monitor.

A person asks a coding agent for a pipeline, and the agent writes it from this
documentation. The documentation is written for that agent. It, the docstrings of
the public API and the messages of `contraagent check` hold every fact that a
pipeline needs, so the agent needs no source code of contraagent.

## Install

Real runs need Linux, macOS or Windows, Python 3.12 or later, and one or more coding
agents on `PATH`, such as `claude` (Claude Code), `omp` (oh-my-pi), `opencode`, `pi`
(pi.dev) or `codex` (Codex CLI). [Operating systems](guide.md#operating-systems) lists
what differs between them.

```
uv add contraagent                  # or: pip install contraagent
uv add 'contraagent[monitor]'       # with the web monitor
```

From a wheel or a checkout of the repository, name it in place of the package:
`uv add ./contraagent-<version>-py3-none-any.whl --extra monitor`, or
`uv add --editable <checkout> --extra monitor`. `contraagent --version` prints the
version installed.

## Start

Point your project's coding agent to this documentation, and ask it for the
pipeline. `contraagent docs --pointer` prints a short block for the instruction file
that the agent reads. Add the block to that file yourself, for example with
`contraagent docs --pointer >> AGENTS.md` (Claude Code reads `CLAUDE.md`).
contraagent does not write into your project. Then ask for the pipeline in plain
words, with any of the five coding agents:

```text
Use contraagent to write a pipeline that reviews each module in src/ and writes a
JSON report per module with its findings. Check it with `contraagent check` and test
it with a stub run.
```

The agent checks its work, and that spends nothing. You run the pipeline on the
coding agents and watch it in the monitor.

## For the coding agent that writes the pipeline

contraagent's API is newer than your training data. Read the topic before you write
the code, in this order:

1. [Guide](guide.md): the parts of a pipeline, the steps, the decisions and the
   pitfalls.
2. [Tutorial](tutorial.md): one pipeline built step by step. Its finished code is in
   `examples/tutorial/` (`contraagent docs --path` prints where).
3. [Tasks and flows](tasks.md), when you declare the tasks and write the flow.
4. [Contracts and validators](contracts.md), when you write the output models and
   their checks.
5. [Plugins](plugins.md), when you write each agent task's role
   (`contraagent plugin new plugins/<name>`, then `contraagent plugin lint`).
6. [Routing and credentials](routing.md), when you write `pipeline.toml`.
7. [Checking and testing](testing.md), when you check and test the pipeline.

[Concepts](concepts.md) defines each word that these topics use. Check your work with
these steps, which launch no coding agent and spend nothing:

1. `contraagent check tasks.py:<flow> --config pipeline.toml --kwargs '{...}'`, until
   it prints ✓. Each problem names the topic that explains it.
2. `contraagent run tasks.py:<flow> --config pipeline.toml --stub --kwargs '{...}'`, a stub run of the whole
   flow, in which each task's output is its output model's example. It lists the
   tasks that the flow created. Give each output model an example that passes its
   validators; the run's last line names a validator that rejects one.
3. Tests of the flow on `contraagent.testing.StubAgent` in pytest, which run the
   real checks, correction rounds, failures and failover with scripted replies.

A run on the coding agents (`contraagent run tasks.py:<flow> --config pipeline.toml
--kwargs '{...}'`) spends tokens. The person who asked for the pipeline starts it,
unless they ask you to, and watches it with `contraagent monitor --runs-dir runs`.

## Documentation

The documentation is installed with the package and matches its version:
`contraagent docs` prints this index, `contraagent docs <topic>` a topic, and
`contraagent docs --path` where they are. `contraagent docs --pointer` prints a
block for the instruction file that a coding agent reads, and the person who uses
the agent adds it there (`contraagent docs --pointer >> AGENTS.md`; Claude Code
reads `CLAUDE.md`).
A `::code` line in these files quotes a file of the package; `contraagent docs`
and the [documentation site](https://t-tani.github.io/contraagent/) print the quoted lines in place.

- [Tutorial: your first pipeline](tutorial.md): a pipeline from an empty directory, step by step: models, an agent task and its plugin, a flow, a stub run, a run on a coding agent, a test.
- [Guide](guide.md): building a pipeline: the steps, the decisions, the pitfalls.
- [Concepts](concepts.md): the words contraagent uses, each with one meaning.
- [Tasks and flows](tasks.md): agent tasks and a map of their options, Python tasks and partial results, the flow and call options, flows that depend on results, loops and their passes, time boxes, claims, services, files a task changes (those of a failed attempt kept, paths left out), scopes and enrichers around each attempt, a pipeline's own records, and the engine underneath.
- [Plugins](plugins.md): an agent task's implementation: roles, skills, hooks, and the MCP servers a pipeline builds for each task.
- [Contracts and validators](contracts.md): how outputs are checked and sent back: models, text and rows (JSON Lines), a launch stopped for its time, correction rounds and their number, validators, the parts to keep.
- [Routing and credentials](routing.md): the config file: coding agent, model, budget, failover, identity and a task call's own credential, quota caps.
- [Coding agents](agents.md): what each of the five coding agents does and does not do (stop hooks, budgets, tool denial, MCP servers), and how to add another.
- [Security model](security.md): what a task's session receives and what a pipeline adds to it, refusals and failover, credentials, what each coding agent enforces, what a run records and who can read it.
- [Checking and testing](testing.md): `contraagent check`, a stub run of the whole flow on the outputs' examples (with some or all Python tasks executed), record and replay, and flows tested on a stub agent.
- [The monitor](monitor.md): the live view of runs, the monitor behind a reverse proxy, and an export of it that needs no server.
- [Many hosts: the hub](hub.md): every host's runs in one monitor: `contraagent hub` and `contraagent relay`.
- [Operating a hub](hub-operations.md): set up with compose, connect hosts, tokens, retention, backups, upgrades, troubleshooting.
- [Compatibility](compatibility.md): what is public, what a release may change, deprecation, every file of a run directory and which are public, and the formats and JSON Schemas of the files a run writes and of the config file.
- [Upgrading from 0.6 to 0.7](upgrading.md): each change a pipeline written for 0.6 makes, as the 0.6 form and the 0.7 form, the steps for a pipeline in production, and how to check the upgrade.

`examples/tutorial/` is the tutorial's pipeline, finished. `examples/demo/` is a whole pipeline (its tasks, plugin, config, a test, and a
script that runs it); `examples/review/flow.py` and `examples/analysis/flow.py`
are async flows (a review loop per unit; a three-layer nested flow);
`examples/changes/flow.py` is a task that changes files beside its output;
`examples/mcp/flow.py` builds an MCP server for each task from its params;
`examples/services/flow.py` is a local server that the tasks which claim its name share;
`examples/implementations/flow.py` declares a step with two implementations and chooses one per unit;
`examples/runner/run.py` runs a flow from a program, with what `contraagent run` cannot pass;
`examples/reference/pipeline.toml` is every config table and key, annotated. The
other directories of `examples/` (`before/`, `claims/`, `converge/`, `credentials/`, `hub/`, `light/`, `panels/`,
`partial/`, `preserve/`, `proxy/`, `retries/`, `rows/`, `scopes/`, `security/`, `skills/`, `time_box/`) are each quoted
by the topic that explains them. The test suite runs them all.
