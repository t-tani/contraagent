# contraagent

**Run coding agents as typed, checked, supervised tasks.** contraagent turns
Claude Code, Codex CLI, opencode, oh-my-pi and pi into the steps of a Python
pipeline: each task is a typed function whose body is a coding agent, its result
is a file checked against a pydantic model, and the runner handles scheduling,
failover, quotas, deadlines, resume and a live monitor.

![Python 3.12 | 3.13 | 3.14](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-3776ab)
![Typed](https://img.shields.io/badge/typing-typed-2a6db2)
![Linux](https://img.shields.io/badge/platform-Linux-555)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

![The monitor's overview of a run: its state, problems with their causes, outputs, and the pipeline graph with a review loop](docs/assets/readme/overview.png)

<sub>The monitor over the shipped demo pipeline, run on its demo agent: one task failed, one was partly done, one was done after retrying, and a review loop ran a second pass for one unit.</sub>

## A task is a function whose body is a coding agent

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

<sub>From the tutorial's pipeline, [`examples/tutorial/tasks.py`](src/contraagent/docs/examples/tutorial/tasks.py); a test keeps this block identical to it.</sub>

The procedure for a triage lives in the plugin `plugins/triage`, as a role the
coding agent loads itself. The flow is plain Python: a `yield` waits for the
checked output, so loops, branches and fan-outs are ordinary code. Then, in
order: every problem with nothing launched, the whole flow on a stub agent, the
run on the coding agent and model `pipeline.toml` names, and the monitor:

```
contraagent check tasks.py:triage_all --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent run tasks.py:triage_all --stub --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent run tasks.py:triage_all --config pipeline.toml --kwargs '{"reports": ["login-timeout", "csv-export"]}'
contraagent monitor --runs-dir runs      # http://127.0.0.1:8787
```

The [tutorial](src/contraagent/docs/tutorial.md) builds this pipeline from an empty directory.

## Why contraagent

contraagent is built for work you would give a coding agent many times over:
review every module, triage every report, migrate every service. It does not
contain an agent loop of its own; it runs the coding agents you already use, and
adds what a pipeline of them needs.

- **The coding agents themselves.** Each task runs `claude -p`, `codex exec`,
  `opencode run`, `omp -p` or `pi -p`. The same task, plugin and config run on
  each of them; `pipeline.toml` chooses the coding agent and model per kind of
  task, and `--agent` moves a whole run to another one.
- **The agent's own extensions.** A task's implementation is a plugin in the
  coding agent's own format: roles (subagents), skills, MCP servers, hooks and
  permissions, beside the agent's built-in tools (shell, editing, web search
  where the agent has it). There is no tool API of contraagent's to learn. Hooks
  are written once in `hooks.toml` and rendered into each agent's own hook
  system. Agents load a plugin in different ways (Claude Code and omp natively,
  opencode and pi through the flags and config contraagent gives them, Codex with its plugins turned
  off and the plugin's skills, hooks and MCP servers passed in):
  [Coding agents](src/contraagent/docs/agents.md) has a row for each difference.
- **A clean context per task.** A task's agent sees its role, its plugin, its
  skills and its call file. The user's and the project's settings, instruction
  files (`CLAUDE.md`, `AGENTS.md`), skills, hooks and MCP servers are kept out,
  and so is every other task's conversation (the exceptions per agent are
  [listed](#for-security-engineers)). A narrow context that holds only the task's
  purpose leaves fewer chances for unrelated text to steer the agent, or to make
  a model's safeguards misread legitimate work, such as security research.
- **Outputs are contracts.** Each output file is checked against its pydantic
  model and its validators. An output that fails goes back to the same agent
  session with the errors, for a number of correction rounds. A
  `CommandValidator` also runs in the agent's own stop hook, so the agent fixes
  the file before its turn ends. A task whose input is missing does not start,
  and the cause names the earlier task.
- **Failover and quotas.** A kind's `fallbacks` move a task to another model,
  coding agent or credential after a rate limit or a failed launch. A safeguard
  refusal moves only that task to its next hop. Caps on a subscription's 5-hour
  and weekly usage rest a credential until its window resets, and a preflight
  checks every route before the first launch.
- **Deadlines and scheduling.** A run's deadline and a flow call's own time box
  defer the work that cannot finish, with the cause recorded; a deferred task is
  not a failure. Claims keep tasks that share a resource apart, and each kind
  has its own limit of tasks running at once.
- **Resume.** `contraagent run --resume` runs a task again only when its
  fingerprint changed: its parameters, its definition, or the outputs it received.
- **Written by a coding agent, too.** The package installs its documentation
  (`contraagent docs`, `contraagent docs <topic>`), and `contraagent docs
  --pointer` prints a block that points a project's coding agent at it. The public
  API is typed and documented in its docstrings, and `contraagent check` reports
  every problem at once, each with the topic that explains it.
- **A typed, stable surface.** The public modules ship `py.typed` and are kept
  against an API snapshot in the tests. Every file a run writes, and the config
  file, has a JSON Schema; the monitor's HTTP API has an OpenAPI document.
  [Compatibility](src/contraagent/docs/compatibility.md) says what is public.

## An audit trail and live telemetry

Every agent session leaves a record in the run directory, and the monitor
(`contraagent monitor`, read-only) shows it live, for all five coding agents, and
after the run:

- **Processes**: a live process tree of the agent sessions and Python tasks,
  read from `/proc`.
- **Per-session events**, in time order: each tool call with its arguments and
  result, web searches with their results, pages fetched, the agent's messages
  and reasoning, API requests sent again.
- **Per-task facts**: the files changed under the task's declared patterns
  (created, modified, deleted), model switches and why, failed checks and the
  correction rounds that followed, deferrals with their causes, tokens, cost and
  the subscription usage at the start of each session.

The events are what each coding agent reports in its own output, plus the
process tree contraagent reads; it is not a kernel-level capture of every file
or network access. When a task goes wrong, the run can be reproduced:
`contraagent run --record DIR` keeps each attempt, `--replay DIR` plays the
recordings back in place of the coding agent with nothing spent, and a stub run
or `contraagent.testing.StubAgent` in pytest replays scripted replies.

| | |
|---|---|
| ![Task detail: the first agent session's output failed two checks; a correction passed](docs/assets/readme/task-detail.png) | ![Task detail in the dark theme: rate limited on the primary model, done after a model switch](docs/assets/readme/model-switch-dark.png) |
| **Task detail.** The transcript of each agent session, followed live for all five coding agents, with the task's input, output and definition. Here the first output failed its checks, and the correction in the same session passed. | **Model switch.** Rate limited on its first model, the task moved to its fallback; each agent session keeps its own transcript, tokens and cost. |
| ![History: every attempt with its outcome, coding agent, model, identity, tokens, cost and time](docs/assets/readme/history.png) | ![The pipeline graph of a nested flow: functions drawn open, a loop inside a loop](docs/assets/readme/pipeline-graph.png) |
| **History.** Every attempt with its outcome, coding agent, model, identity, tokens, cost, time and reason, with counts of corrections and retries. | **Pipeline graph.** The flow by function and loop, a mark per unit, the passes of each loop; tasks that have not started are in it too. |

Besides these: the problems of a run with their causes (a failed task names the
later tasks it stopped), and the [Trends](docs/assets/readme/trends.png) page,
which adds up the cost, tasks and models of the runs of a period.

Many hosts: `contraagent relay` on each host sends its runs to a
`contraagent hub`, which serves one monitor over all of them
([the hub](src/contraagent/docs/hub.md)).

## For security engineers

What a task's coding agent can see and do, and what a run records, as the code
does it; [Coding agents](src/contraagent/docs/agents.md) and
[Plugins](src/contraagent/docs/plugins.md#what-a-task-agent-sees) have the details.

- **Context.** Each launch keeps out the project's and the user's settings,
  instruction files, skills, hooks and MCP servers, and every other task's
  session. Claude Code runs with `--setting-sources ""`, `--strict-mcp-config`
  and its `CLAUDE.md` files and auto-memory turned off; Codex with
  `--ignore-rules`, its plugins turned off and no `AGENTS.md`. Exceptions:
  opencode still reads the user's `~/.config/opencode` (not on a light launch);
  Codex reads the user's `config.toml` when it runs on the host's own login
  (`ambient`); omp's credential isolation is verified for the `anthropic`,
  `openai-codex` and `litellm` providers only.
- **Safeguard refusals.** A safety refusal is a stop of its own (`refused`), on
  its hop in the journal, with the provider's text as the reason. It is not
  retried on the same route: the task moves to its next hop, and the other tasks
  stay on their first one.
- **Credentials.** The config names credentials (subscriptions, API keys, OAuth
  tokens, gateways, Bedrock, Vertex, pools); a secret in it is a reference,
  `env:NAME` or `file:PATH`, and an inline value is refused. The journal records
  the credential's name, never its value. A launch on any credential but
  `ambient` (the host's own login) starts without the host's credential
  variables (`ANTHROPIC_API_KEY`, any `*_API_KEY`, `*_AUTH_TOKEN`, ...). A gateway's `headers` are plain config values.
- **Tools and limits.** `disallowed_tools` denies tools per kind; a route whose
  coding agent cannot enforce the rule is refused before anything launches. Each
  launch has its time, turn and budget limits, stall detection, and runs in a
  process group of its own, ended when the pipeline ends or is interrupted.
- **Sandbox and scratch.** Codex runs in its `workspace-write` sandbox (network
  on), with a temporary directory of its own per launch. Scratch directories are
  under `<temp dir>/contraagent-<uid>/`, owner-only; a symbolic link or another
  user's directory there is refused.
- **Audit trail.** Per run: `journal.jsonl` (one row per attempt: coding agent,
  model, credential name, hops, tokens, cost, web searches, and the files the task
  changed among those it declared with `changes=`), `launches.jsonl` (each launch's
  command line with its prompt cut short, its refused tool calls), the call file
  each agent was given, and each task's transcript.
- **Monitor and hub.** The monitor is read-only (GET only), binds to 127.0.0.1 by
  default and answers only local host names and those named by `--allow-host`. `contraagent monitor
  export` leaves out transcripts and processes and redacts paths and host names
  by default. A hub takes an ingest token per host (a token bound to one host
  cannot send another host's runs) and a read token for its monitor; it reads them
  from files and compares them in constant time.

## When to use something else

- **Your own agent loop over a model API** (your tools, your prompts, typed
  output in your process): an agent SDK such as Pydantic AI, the OpenAI Agents
  SDK or LangGraph.
- **Claude Code's agent inside an application**, or one agent run per pull
  request or issue: the Claude Agent SDK, or claude-code-action.
- **Workflows that are mostly not coding-agent work** (ETL, scheduled batch jobs,
  long-lived business processes): Temporal, Prefect or Airflow, which can call a
  contraagent pipeline as one step.
- **One agent call on one file:** `claude -p` alone is enough. Typed outputs,
  correction rounds, failover and the monitor pay off over many tasks, or when
  runs must be repeatable.

## Coding agents

| Agent (`agent`) | CLI | A launch runs |
|---|---|---|
| `claude` | Claude Code | `claude -p --output-format stream-json` |
| `codex` | Codex CLI | `codex exec --json` |
| `opencode` | opencode | `opencode run --format json` |
| `omp` | oh-my-pi | `omp -p`, or `omp --mode rpc` (`omp-rpc`) |
| `pi` | pi (pi.dev) | `pi --mode json -p` |

They differ in what their CLIs enforce (stop hooks, budgets, quota readings, tool
denial): [Coding agents](src/contraagent/docs/agents.md). A coding agent of your
own is a `Backend` subclass.

## Install

Linux, Python 3.12 or later, and a coding agent on `PATH` for real runs:

```
uv add 'contraagent[monitor]'       # or: pip install 'contraagent[monitor]'
```

`python -m contraagent.docs.examples.demo.run` runs the demo pipeline on a demo
agent (no coding agent, nothing spent) and serves the monitor on
http://127.0.0.1:8787.

## Documentation

This repository holds four packages, each with its documentation:

| Package | What it is | Documentation |
|---|---|---|
| `contraagent` (Python) | pipelines of coding-agent tasks, their runner, the monitor, the hub | [src/contraagent/docs/](src/contraagent/docs/README.md) |
| `@contraagent/ui` (npm) | the monitor and its views as web components | [web/packages/ui/](web/packages/ui/README.md) |
| `@contraagent/elements` (npm) | generic web components (`cae-*`), themes and design tokens, with no contraagent data | [web/packages/elements/](web/packages/elements/README.md) |
| `@contraagent/api` (npm) | the typed client for the monitor's API | [web/packages/api/](web/packages/api/README.md) |

The documentation site renders all four: `pnpm docs` in `web/`. The npm
packages are not in the npm registry: `pnpm tarballs` in `web/` packs them for
installing from this checkout. The screenshots above are made by
`pnpm --dir web screenshots`.

Working on contraagent itself: [AGENTS.md](AGENTS.md). Changes:
[CHANGELOG.md](CHANGELOG.md). MIT licensed.
