# Security model

This topic states what a task's coding agent can see and do, what contraagent
enforces and on which coding agent, what a run records, and who can read the
records. It also states the limits of each of these. The other topics describe each
part in full, and this one links to them.

## What a task's session receives

Each task runs in a new session of its coding agent. The session receives the task's
role, its plugin (skills, hooks, MCP servers, permissions), its call file (the
parameters and the output contract), the working directory, one credential and the
coding agent's built-in tools. The user's and the project's settings, instruction
files (`CLAUDE.md`, `AGENTS.md`), the user's skills, hooks and MCP servers, and the
sessions of other tasks are kept out. The table in
[What a task agent sees](plugins.md#what-a-task-agent-sees) lists what each coding
agent keeps out and keeps.

Claude Code runs with `--setting-sources ""` and `--strict-mcp-config`, and its
`CLAUDE.md` files and auto-memory are disabled. Codex runs with `--ignore-rules`, its
plugins are disabled, and it reads no `AGENTS.md`.

Three exceptions remain:

- opencode reads the user's `~/.config/opencode`. A light launch (a task with no
  tools) does not.
- Codex reads the user's `config.toml` when it runs on `ambient`, the host's own
  login. On any other credential it runs with an empty `CODEX_HOME`.
- On omp, contraagent verifies that a launch uses only its own credential for the
  providers `anthropic`, `openai-codex` and `litellm`. It does not verify other omp
  providers, so a task that requires traits is refused on them.

A pipeline can give a session more than its plugin holds:

- [MCP servers built for each task](plugins.md#mcp-servers-built-for-each-task):
  `Pipeline(mcp_servers=)` returns the servers of each task, which replace its
  plugin's. The coding agent starts them as it starts a plugin's, and they see what
  the function gives them from the task's params. contraagent writes them to a file in an owner-only
  temporary directory, not to the run directory, because a server's arguments or
  environment may hold a secret, and removes the file when the process ends: at its
  normal end, after an exception or Ctrl-C, and on SIGTERM. A process killed outright
  (SIGKILL) removes nothing.
- [Services](tasks.md#services-a-server-that-the-tasks-of-a-claim-share): a task
  that claims a service's name gets its address in `CONTRAAGENT_SERVICE_<NAME>`, and
  a task that claims no service gets no such variable. The pipeline's own process
  starts a service, with its rights, outside any sandbox of a coding agent.
  `services.jsonl` and the monitor show its address, so an address holds no secret.
- [Files a task changes](tasks.md#files-a-task-changes): a kind declared with
  `keep_failed_changes` leaves the files a failed attempt created in the working
  directory, and the next attempt, and any later task, sees them. Nothing marks them
  as the output of a failed attempt but the journal row's `changes.kept`.

## A refused task and its failover chain

A launch that a model's safeguards refuse ends with the stop `refused`. The task
then moves to the next hop of its kind's failover chain, and a hop can name another
coding agent, model and credential. The chain below runs the kind `audit` on Claude
Code, then on Codex CLI, then on opencode:

::code{file="examples/security/pipeline.toml" from="[tasks.audit]"}

In a run where the task `audit · upload` is refused on hop 1 and the task
`audit · auth` is not, the runner does this:

1. It launches `audit · upload` on hop 1 (Claude Code). The launch ends `refused`.
2. It launches `audit · upload` on hop 2 (Codex CLI), with the same call file. It
   does not launch the task on hop 1 again.
3. The output file passes its checks, and the journal row of the attempt lists hops
   1 and 2.
4. It launches `audit · auth` on hop 1, because a refusal moves only the refused
   task. The output passes, and the row lists hop 1.

These rules hold for every refusal:

- contraagent reads the refusal from the coding agent's output. The attempt's reason
  holds the provider's text, for example `safeguard refusal on hop 1/3
  claude/claude-opus-5-5@anthropic-key (<the provider's text>); failing over to hop
  2/3 codex/gpt-6.1-sol@openai-key; ran on hop 2/3 codex/gpt-6.1-sol@openai-key`.
- The hops follow the order of the `[[tasks.<kind>.fallbacks]]` blocks. A kind's own
  blocks replace `[[defaults.fallbacks]]`.
- A rate limit (a 429) is different: it moves every task of the kind until the first
  hop answers again ([Failover](routing.md#failover)).
- When every hop refuses, the task fails with the stop `refused`. It is not retried,
  and a task that needs its output does not start.
- The journal row lists each hop with its coding agent, model, credential and stop.
  The monitor shows it as a model switch.
- Before the first launch, contraagent checks every hop as it checks the first one.

## Credentials

[Credentials](routing.md#credentials) gives each type and what each coding agent
accepts. The facts that concern security:

- A secret in the config is a reference, `env:NAME` or `file:PATH`. contraagent
  refuses an inline value. It reads the value in the launching process and writes
  it nowhere.
- The journal records a credential's name, never its value.
- A launch on any credential but `ambient` starts without the host's credential
  variables (`ANTHROPIC_API_KEY`, any `*_API_KEY`, `*_AUTH_TOKEN`, ...), then gets
  the one credential that its hop names. A tool that needs a key of its own gets it
  through `Pipeline(env=...)`.
- A launch on `ambient` keeps the host's environment as it is.
- A task call may name the credential of that one task
  ([A task call's credential](routing.md#a-task-calls-credential)). It runs as that
  credential on every hop of its kind, so a refusal or a 429 never moves it to
  another identity. A credential that lacks a trait the task `requires` is refused
  before the task launches, as for a kind's own. `plan.jsonl` records the call's
  credential, and the journal the one each launch ran as.
- A launch whose coding agent reports a credential source that does not match its
  credential ends with the stop `credential_mismatch`. It does not move to another
  hop.
- A gateway's `headers` are plain config values, not secrets. On Codex, a gateway's
  `base_url` and `headers` are arguments of the command line (`-c
  model_providers...`), so `launches.jsonl` records them. Its token is in the
  environment, not on the command line.

## What each coding agent enforces

The coding agents' CLIs do not enforce the same things. The table in
[What each one does](agents.md#what-each-one-does) has a row for each:

- `disallowed_tools`: Claude Code, opencode and omp deny tools and some patterns, pi
  whole tools only; Codex cannot, so a route on it is refused before anything launches,
  as is a route whose agent cannot deny a pattern the task names.
- `max_turns`: pi does not enforce it, and on omp and Codex it counts tool calls.
- On omp, `disallowed_tools` is enforced by an extension of contraagent's own inside
  the agent's process, which sees each tool call before it runs. omp has no
  permission checks of its own (`--approval-mode yolo`), so the extension is the only
  thing that denies a call. As on Claude Code, a pattern does not hold what another
  tool does: a `Read(secrets/**)` pattern does not stop `bash` from printing the file.
  Deny the whole tool (`Bash`) when that matters.
- `max_budget_usd`: Codex reports no cost, so the cap does not hold there.
- `context_budget`: only Claude Code and opencode launches are stopped by it.

`timeout_s` and `max_turns` are required for every kind. `max_budget_usd`,
`stall_s` and `context_budget` apply only when the config or the task sets them.

## Processes and files

- Each launch runs in a process group of its own (on Windows, also in a Job Object).
  contraagent ends the group when the pipeline ends or is interrupted (SIGTERM,
  Ctrl-C).
- When the pipeline's process is killed outright (SIGKILL, the out-of-memory
  killer), a watchdog process stops the agent groups that are still running; on
  Windows the OS ends each launch's job. The watchdog compares the start time of
  each group's first process with the one it recorded, so it does not signal an
  unrelated process that the OS later gave the same process id.
- Codex runs in its `workspace-write` sandbox (the OS's own: bubblewrap on Linux,
  Seatbelt on macOS, Codex's Windows sandbox), with the network on, and with a
  temporary directory of its own for each launch. Claude Code takes its permissions
  from the plugin's `settings.json`, and opencode from the role's `tools:`. omp
  (`--approval-mode yolo`) and pi run with no permission checks.
- Scratch directories are under `<temp dir>/contraagent-<uid>/` (`<temp dir>` is
  `$TMPDIR`, else `/tmp`), and only their owner can use them. contraagent refuses a
  symbolic link or another user's directory there. On Windows they are under
  `%TEMP%\contraagent\`, in the user's own temporary directory.
- pi's agent directory and Codex's `CODEX_HOME` are under `~/.cache/contraagent/`
  ([Directories outside the run](agents.md#directories-outside-the-run)).

## What a run records

| What | Where it is enforced or recorded |
|---|---|
| Tools a kind may not use | `disallowed_tools` in the config. A route whose coding agent cannot deny the tools is refused before anything launches. |
| Limits of a launch | `timeout_s` and `max_turns` for every kind; `max_budget_usd`, `stall_s` and `context_budget` when they are set. |
| The processes of a launch | A process group of its own, and the watchdog after a SIGKILL; on Windows a Job Object the OS ends with the pipeline. |
| Codex's sandbox | `workspace-write`, with the network on. |
| Scratch directories | `<temp dir>/contraagent-<uid>/`, owner-only. |
| Each attempt | `journal.jsonl`: the coding agent, model, credential name, hops, tokens, cost, web searches, and the changed files among those the task declares with `changes=`. |
| Each service | `services.jsonl`: each start, with the task that started it and its address, and each stop. |
| Each launch | `launches.jsonl`: the command line, with the prompt cut to 200 characters, and the refused tool calls. |
| What each agent was given, and what it did | The run directory: the call file of each task (`calls/`) and the transcript of each task (`streams/`). |

The journal and the transcripts hold what each coding agent reports in its own
output. The monitor adds a live process tree from the OS. Neither is a kernel-level
capture of every file or network access.
[Compatibility](compatibility.md) lists every file of a run directory.

## Who can read the records

- The [monitor](monitor.md) answers GET requests only and binds to `127.0.0.1` by
  default. It answers only local host names and the names given with
  `--allow-host`.
- The monitor has no login of its own. Behind a
  [reverse proxy](monitor.md#behind-a-reverse-proxy) (`--base-path`), it answers
  everyone the proxy passes, so the proxy checks who may read it, or it serves a hub
  with a read token. The `Host` check still applies: a proxy that passes the
  browser's host name needs that name given with `--allow-host`, and `*` turns the
  check off.
- `contraagent monitor export` never includes transcripts or processes. By default
  it redacts paths and the host's name
  ([Without a server: an export](monitor.md#without-a-server-an-export)).
- A [hub](hub.md) requires `--ingest-token-file`. A token in it is bound to one host
  (`<host_id> <token>`) or good for any host (a line with the token alone). A token
  bound to one host cannot send the runs of another host.
- The hub's monitor requires the read token when the hub has one
  (`--read-token-file`). With no read token, the monitor is open to anyone who
  reaches the port, and a hub bound to an address other than loopback logs a
  warning. Under a base path, its `/login` sets the cookie for that path only.
- The hub reads its tokens from files and compares them in constant time.
  [Operating a hub](hub-operations.md#tokens) shows how to add and rotate them.
