# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The changes not released yet are the fragments in [`changelog.d/`](changelog.d/);
`towncrier build --draft` shows them as the next release's section.

<!-- towncrier release notes start -->

## [0.1.0] - 2026-10-16

### Added

- A task is a typed Python function whose body is a coding agent (`agent_task`) or Python
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
- An agent task's implementation is a plugin in the coding agent's own format: roles,
  skills, MCP servers and hooks. Its hooks are written once in `hooks.toml` and rendered
  for each coding agent, and `contraagent plugin new`, `lint` and `render` create, check
  and render a plugin. Each launch is given a call file with the task's parameters and its
  output contract.
- A flow can be checked and tested with nothing spent. `contraagent check` builds the task
  graph and reports every problem in the flow, the output models, the validators, the
  plugins and the routing at once, each with the documentation topic that explains it.
  `contraagent.testing.StubAgent` plays scripted replies in tests, and a stub run
  (`contraagent run --stub`) runs the whole flow on each output's example. A run records
  each attempt with `--record DIR`, and a later run replays the recordings with
  `--replay DIR`.
- Five coding agents run the same tasks, plugins and config: Claude Code (`claude -p`),
  Codex CLI (`codex exec`), opencode (`opencode run`), oh-my-pi (`omp -p`) and pi
  (`pi -p`). `register_backend` adds another one. Each launch starts in a clean context:
  the user's and the project's settings, instruction files, skills, hooks and MCP servers
  are kept out. contraagent supervises the time, the budget, stalls and denied tool calls,
  and records the tokens, the cost, the peak context and the account's 5-hour and weekly
  usage when the agent reports them. A coding agent does not outlive the pipeline that
  started it.
- One TOML file (`pipeline.toml`, with a JSON Schema) gives each kind its coding agent,
  model, effort, budget, time limits and credential, from `[defaults]` and
  `[tasks.<kind>]`.
  - Credentials are the host's own login (`ambient`), subscriptions, API keys, OAuth
    tokens, gateways, Bedrock, Vertex, workload identity and pools of them.
  - A kind's `fallbacks` move a task to its next route (another model, coding agent or
    credential) after a rate limit, a failed launch or a safeguard refusal.
  - Quota caps on a subscription's 5-hour and weekly usage rest a credential until its
    window resets, and a preflight probes every route before the first launch.
- The work queue starts the ready task with the longest remaining work first, within each
  kind's `max_concurrent`. Claims (`claims=["topic:{unit}"]`) keep tasks that share a name
  from running at the same time. A run's deadline, and time boxes over part of a flow,
  defer the tasks that cannot finish in time, and a deferred task is not a failure. A
  resumed run (`contraagent run --resume`) runs a task again only when its parameters, its
  definition or its inputs changed.
- Each run writes its records to `runs/<id>/`: the run, the journal of attempts with each
  one's tokens, cost, route and changed files, the plan, the launches, deferrals, quota
  rests, call files, outputs and transcripts. Each record has a JSON Schema, and `run.json`
  names its run format. A flow and its Python tasks keep the pipeline's own records there
  with `contraagent.log` and `contraagent.save`.
- `contraagent monitor` (the `monitor` extra) serves a live, read-only view of every run:
  its state, problems, outputs, cost, tokens and subscription usage, the pipeline graph,
  the timeline, and each task with its transcript, inputs, outputs and checks. A Trends
  page sums the runs of a period, and a pipeline adds views of its own
  (`contraagent.monitor.Panel`). The monitor speaks English and Japanese, with light, dark
  and high-contrast themes, and `openapi.json` describes its HTTP API.
  `contraagent monitor export` writes the views of the newest runs as static files that any
  web server serves.
- `contraagent hub` and `contraagent relay` (the `hub` extra) show the runs of many hosts in
  one monitor. A relay on each host sends its runs to the hub, which keeps them in Postgres
  and object storage, with a token per host, a read token for the monitor and retention.
  `contraagent docs hub-operations` describes a deployment.
- The monitor's page is built from three npm packages that work in any page or framework:
  - `@contraagent/api`: types generated from `openapi.json`, a client and the live feeds;
  - `@contraagent/elements`: generic web components, such as a data table, charts, a
    layered graph, a transcript and the themes;
  - `@contraagent/ui`: `<ca-monitor>` and an element for each of its views.
- The documentation is installed with the package and is written for the coding agent that
  writes a pipeline. `contraagent docs` prints the index, `contraagent docs <topic>` a
  topic, and `contraagent docs --pointer` a short block that points a project's coding agent
  at them, and its examples run in the tests. The same documentation, with each web
  element drawn live, is at https://t-tani.github.io/contraagent/.
- contraagent runs on Linux, macOS and Windows with Python 3.12, 3.13 and 3.14. The
  compatibility topic (`contraagent docs compatibility`) lists what is public: the public
  modules' names, the command line, the config file, the files a run writes and the
  monitor's HTTP API and the hub's protocol. Before 1.0, a minor release may change them, and
  the changelog names each change; a patch release does not.
