<h1>
  <img src="docs/assets/brand/contraagent-logo-any.svg" width="330" alt="contraagent">
</h1>

contraagent runs coding agents as typed, checked and supervised tasks. Claude Code,
Codex CLI, opencode, oh-my-pi and pi become the steps of a Python pipeline. Each
task is a typed function whose body is a coding agent, and its result is a file that
contraagent checks against a pydantic model. The runner schedules the tasks and
handles failover, quotas, deadlines and resume, and a live monitor shows every run.

![Python 3.12 | 3.13 | 3.14](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-3776ab)
![Typed](https://img.shields.io/badge/typing-typed-2a6db2)
![Linux](https://img.shields.io/badge/platform-Linux-555)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

<img src="docs/assets/readme/overview.png" width="880" alt="The monitor's header with the run docs: 44 of 44 tasks done. Below it, part of the pipeline graph: summarize, then a loop of score, review and revise, up to 2 passes, then write_note, each with a mark per unit, all done. Below that, the totals: 44 tasks, 44 attempts, the cost and the tokens">

<sub>The monitor after the demo pipeline ran on its demo agent: its header with the
run's line, part of the pipeline graph, and the first totals. Every task is done and
every output passed its checks, after two corrections in their own sessions, one
model switch after a rate limit, and a second pass of the review loop for one unit
(an item that the pipeline works on). The pipeline graph draws the flow as it is
written, by function and loop, with a mark for each unit.</sub>

## Example

<!-- ::code{file="src/contraagent/docs/examples/tutorial/tasks.py" from="from typing import" to="class Triage"} -->
<!-- ::code{file="src/contraagent/docs/examples/tutorial/tasks.py" from="class Triage" to="class FixPlan"} -->
<!-- ::code{file="src/contraagent/docs/examples/tutorial/tasks.py" from="triage = agent_task(" to="plan_fix = agent_task"} -->
<!-- ::code{file="src/contraagent/docs/examples/tutorial/tasks.py" from="def triage_one" to="def triage_and_plan"} -->
```python
from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Triage(BaseModel):
    severity: Literal["low", "medium", "high"] = Field(description="high: users lose data or cannot work")
    area: str = Field(description="the part of the product the report is about, in one or two words")
    summary: str = Field(description="what goes wrong, in one sentence")


triage = agent_task(
    "triage",
    plugin="plugins/triage",
    role="triager",
    output=Triage,
    validators=[short_summary],
    max_turns=10,
    timeout_s=300,
)


def triage_one(name: str):
    """One report: its triage, and a fix plan when it is high severity."""
    found = yield triage(name, report=report_path(name))
    if found.severity == "high":
        yield plan_fix(name, report=report_path(name), triage=found)
    return found
```

<sub>This block is quoted from the tutorial's
[`examples/tutorial/tasks.py`](src/contraagent/docs/examples/tutorial/tasks.py), and
a test checks that the two are identical.</sub>

The instructions for a triage are in the plugin `plugins/triage`, as a role that the
coding agent loads itself. The flow around the tasks is plain Python. Each `yield`
waits for a checked output, so loops, branches and parallel tasks are ordinary code.

`contraagent check` reports every problem in the pipeline and launches nothing. With
`--stub`, `contraagent run` runs the whole flow on a stub agent, which plays scripted
replies and spends nothing. With `--config pipeline.toml`, it runs on the coding
agent and model that the config names. `contraagent monitor` then shows the runs in a
browser.

```
contraagent check tasks.py:triage_all --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent run tasks.py:triage_all --stub --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent run tasks.py:triage_all --config pipeline.toml --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent monitor --runs-dir runs      # http://127.0.0.1:8787
```

The [tutorial](src/contraagent/docs/tutorial.md) builds this pipeline from an empty
directory.

## Why contraagent

contraagent is for work that you give a coding agent many times, once for each item,
such as a review of every module or a triage of every report. It has no agent loop of
its own. It runs the coding agents that you already use, and adds what a pipeline of
them needs.

- The same task, plugin and config run on `claude -p`, `codex exec`, `opencode run`,
  `omp -p` and `pi -p`. `pipeline.toml` chooses the coding agent and model for each
  kind, the class of work that a task does (`triage`). With `--agent`, every task of
  a run uses another coding agent.
- A task's implementation is a plugin in the coding agent's own format, with roles
  (subagents), skills, MCP servers, hooks and permissions. The agent keeps its
  built-in tools, such as the shell, file editing and web search where the agent has
  it, and contraagent adds no tool API of its own. You write hooks once in
  `hooks.toml`, and contraagent renders them into the hook system of each agent.
  Claude Code and omp load a plugin natively. opencode and pi load it through the
  flags and config that contraagent gives them. Codex runs with its own plugins
  disabled and receives the plugin's skills, hooks and MCP servers from contraagent.
  The page [Coding agents](src/contraagent/docs/agents.md) has a row for each of
  these differences.
- Each task starts in a clean context. Its agent sees its role, its plugin, its
  skills and its call file, which holds the task's parameters and output contract.
  The user's and the project's settings, instruction files (`CLAUDE.md`,
  `AGENTS.md`), skills, hooks and MCP servers are excluded, and so are the
  conversations of other tasks. Some coding agents have
  [exceptions](#for-security-engineers). With only the task's purpose in its context,
  the agent is less likely to follow unrelated text, and a model's safeguards are
  less likely to misread legitimate work such as security research.
- Every output file is checked against its pydantic model and its validators. When
  an output fails, the errors go to the same agent session, for a set number of
  correction rounds. A `CommandValidator` also runs in the agent's own stop hook, so
  the agent fixes the file before its turn ends. A task whose input is missing does
  not start, and its recorded cause names the earlier task.
- After a rate limit or a failed launch, a task moves along its kind's `fallbacks`.
  This chain holds routes, and each route names a model, a coding agent and a
  credential (the account that the agent's API calls are billed to). Each launch on
  a route is a hop. A safeguard refusal moves only the refused task to its next hop.
  Caps on a subscription's 5-hour and weekly usage pause a credential until its usage
  window resets, and a preflight checks every route before the first launch.
- A run can have a deadline, and a function that the flow calls can have its own
  (`time_box`). Work that cannot finish in time is deferred with its cause recorded,
  and a deferred task is not a failure. Tasks that share a resource can claim its
  name (`claims`) so that they run one at a time. Each kind also has its own limit of
  tasks that run at once.
- `contraagent run --resume` runs a task again only when its `fingerprint` changed.
  The fingerprint is a digest of the task's parameters, its definition and the
  outputs it received.
- A coding agent can write these pipelines too. The package installs its
  documentation (`contraagent docs`, `contraagent docs <topic>`), and
  `contraagent docs --pointer` prints a block that points a project's coding agent to
  it. The public API is typed and documented in docstrings. `contraagent check`
  reports every problem at once, each with the topic that explains it.
- The public modules ship `py.typed`, and a test compares the public API with a saved
  snapshot. Every file that a run writes has a JSON Schema, and so does the config
  file. The monitor's HTTP API has an OpenAPI document.
  [Compatibility](src/contraagent/docs/compatibility.md) states what is public.

## An audit trail and live telemetry

Every agent session leaves a record in the run directory. The monitor
(`contraagent monitor`) is read-only and shows these records for all five coding
agents, while a run is live and after it ends. It shows a live process tree of the
agent sessions and Python tasks, read from `/proc`. For each session, it shows the
events in time order, with each tool call and its arguments and result, web searches
and their results, fetched pages, the agent's messages and reasoning, and API
requests sent again. For each task, it shows the files changed under the task's
declared patterns (created, modified, deleted), model switches and their causes,
failed checks and the correction rounds after them, deferrals and their causes,
tokens, cost, and the subscription usage at the start of each session.

The events are what each coding agent reports in its own output, plus the process
tree that contraagent reads. They are not a kernel-level capture of every file or
network access.

A failed task can be reproduced. `contraagent run --record DIR` keeps each attempt,
and `--replay DIR` replays those recordings in place of the coding agent, with
nothing spent. A stub run (`--stub`, a run that launches no coding agent) plays
scripted replies, and so does `contraagent.testing.StubAgent` in pytest.

<img src="docs/assets/readme/task-detail.png" width="880" alt="Task detail of write_note · alpha, done after 1 correction: the first agent session's transcript, and the two checks its output failed">

<sub>The task detail holds the transcript of each agent session, with the task's
input, output and definition. The first version of this note failed two checks, the
errors went to the same session, and the corrected version passed.</sub>

<img src="docs/assets/readme/history.png" width="826" alt="Two rows of the history of the summarize tasks, both done: beta on fallback-model after a model switch, delta on primary-model with 1 correction">

<sub>The history has one row per attempt, with its outcome, coding agent, model,
identity (the credential used), tokens, cost and time. Every summary is done. One
needed a correction, and one switched from a rate-limited model to its fallback,
which the later summary tasks used from their first attempt.</sub>

<img src="docs/assets/readme/model-switch-dark.png" width="880" alt="Task detail of summarize · beta in the dark theme: done after a model switch from primary-model (rate limited) to fallback-model, and its two agent sessions">

<sub>The same model switch in the dark theme. Each agent session keeps its own
transcript, tokens and cost.</sub>

<img src="docs/assets/readme/trends.png" width="880" alt="Trends over 7 days: 2 runs, 81 attempts, all passed, and the cost by day and kind">

<sub>Trends show the totals of the runs in a period, such as cost by day and kind,
tasks and models.</sub>

With several hosts, `contraagent relay` on each host sends its runs to a
[hub](src/contraagent/docs/hub.md) (`contraagent hub`), which serves one monitor for
all of them.

## For security engineers

This section describes what a task's coding agent can see and do, and what a run
records, as the code implements it. The pages
[Coding agents](src/contraagent/docs/agents.md) and
[What a task agent sees](src/contraagent/docs/plugins.md#what-a-task-agent-sees)
give the details.

- Each launch excludes the project's and the user's settings, instruction files,
  skills, hooks and MCP servers, and the sessions of all other tasks. Claude Code
  runs with `--setting-sources ""` and `--strict-mcp-config`, with its `CLAUDE.md`
  files and auto-memory disabled. Codex runs with `--ignore-rules`, with its plugins
  disabled and with no `AGENTS.md`. Three exceptions remain. opencode still reads the
  user's `~/.config/opencode`, except on a light launch (a launch of a task with no
  tools). Codex reads the user's `config.toml` when it runs on the host's own login
  (`ambient`). On omp, a launch is verified to use only the credential that
  contraagent gives it with the providers `anthropic`, `openai-codex` and `litellm`,
  and other omp providers are not verified.
- A safety refusal is a stop of its own, `refused`. The journal records it on its
  hop, with the provider's text as the reason. The task is not retried on the same
  route but moves to its next hop, and the other tasks stay on their first route.
- The config names the credentials, which can be subscriptions, API keys, OAuth
  tokens, gateways, Bedrock, Vertex or pools. A secret in the config is a reference
  (`env:NAME` or `file:PATH`), and contraagent refuses an inline value. The journal
  records a credential's name, never its value. A launch on any credential except
  `ambient`, the host's own login, starts without the host's credential variables
  (`ANTHROPIC_API_KEY`, any `*_API_KEY`, `*_AUTH_TOKEN`, ...). A gateway's `headers`
  are plain config values.
- `disallowed_tools` denies tools for a kind. If the coding agent of a route cannot
  enforce that rule, the route is refused before anything launches. Every launch has
  time, turn and budget limits and stall detection. It runs in a process group of its
  own, which contraagent ends when the pipeline ends or is interrupted.
- Codex runs in its `workspace-write` sandbox with the network on, and with a
  temporary directory of its own for each launch. Scratch directories are under
  `<temp dir>/contraagent-<uid>/`, and only their owner can use them. contraagent
  refuses a symbolic link or another user's directory there.
- `journal.jsonl` has one row per attempt, with the coding agent, model, credential
  name, hops, tokens, cost, web searches, and the files that the task changed among
  those it declared with `changes=`. `launches.jsonl` has the command line of each
  launch, with the prompt truncated to 200 characters, and its refused tool calls.
  The run directory also keeps the call file that each agent was given, and the
  transcript of each task.
- The monitor is read-only (GET only) and binds to 127.0.0.1 by default. It answers
  only local host names and the names given with `--allow-host`.
  `contraagent monitor export` never includes transcripts or processes, and by
  default it redacts paths and host names. A hub requires an ingest token for each
  host, and a token bound to one host cannot send the runs of another host. The
  hub's monitor requires a read token. The hub reads its tokens from files and
  compares them in constant time.

## When to use something else

For your own agent loop over a model API, with your own tools and prompts and typed
output in your process, use an agent SDK such as Pydantic AI, the OpenAI Agents SDK
or LangGraph.

To run Claude Code's agent inside an application, or to run one agent for each pull
request or issue, use the Claude Agent SDK or claude-code-action.

For workflows that are mostly not coding-agent work, use Temporal, Prefect or
Airflow. Examples are jobs that extract, transform and load data, scheduled batch
jobs, and business processes that run for a long time. Such a workflow can call a
contraagent pipeline as one step.

One agent call on one file needs only `claude -p`. Typed outputs, correction rounds,
failover and the monitor are useful over many tasks, or when runs must be
repeatable.

## Coding agents

| Agent (`agent`) | CLI | A launch runs |
|---|---|---|
| `claude` | Claude Code | `claude -p --output-format stream-json` |
| `codex` | Codex CLI | `codex exec --json` |
| `opencode` | opencode | `opencode run --format json` |
| `omp` | oh-my-pi | `omp -p`, or `omp --mode rpc` (`omp-rpc`) |
| `pi` | pi (pi.dev) | `pi --mode json -p` |

Their CLIs enforce different things, such as stop hooks, budgets, quota readings and
tool denial. The page [Coding agents](src/contraagent/docs/agents.md) lists each
difference. A coding agent of your own is a subclass of `Backend`.

## Install

Real runs need Linux, Python 3.12 or later, and a coding agent on `PATH`.

```
uv add 'contraagent[monitor]'       # or: pip install 'contraagent[monitor]'
```

`python -m contraagent.docs.examples.demo.run` runs the demo pipeline on a demo
agent, which launches no coding agent and spends nothing. It serves the monitor on
http://127.0.0.1:8787.

## Documentation

This repository holds four packages, and each has its own documentation.

| Package | What it is | Documentation |
|---|---|---|
| `contraagent` (Python) | pipelines of coding-agent tasks, their runner, the monitor, the hub | [src/contraagent/docs/](src/contraagent/docs/README.md) |
| `@contraagent/ui` (npm) | the monitor and its views as web components | [web/packages/ui/](web/packages/ui/README.md) |
| `@contraagent/elements` (npm) | generic web components (`cae-*`), themes and design tokens, with no contraagent data | [web/packages/elements/](web/packages/elements/README.md) |
| `@contraagent/api` (npm) | the typed client for the monitor's API | [web/packages/api/](web/packages/api/README.md) |

`pnpm docs` in `web/` serves the documentation site, which renders all four. The npm
packages are not published to the npm registry. `pnpm tarballs` in `web/` packs them
so that you can install them from this checkout, and `pnpm --dir web screenshots`
makes the screenshots in this README.

[AGENTS.md](AGENTS.md) is for work on contraagent itself, and
[CHANGELOG.md](CHANGELOG.md) lists the changes. contraagent is MIT licensed.
