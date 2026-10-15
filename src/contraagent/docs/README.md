# contraagent

Run coding-agent CLIs (`claude -p`, `omp -p`, `opencode run`, `pi -p`, `codex exec`) as typed, supervised, observable
tasks. Think pydantic-ai for coding agents: a task is a typed function whose
body is a coding agent, and your contract with it is a file it must leave
behind. Scheduling, failover, validation, credentials, resume and live
monitoring are the framework's job.

- **Typed tasks**: parameters and outputs are pydantic models; an output that
  does not pass its schema or its validators goes back to the same session.
- **Agent-native implementations**: what an agent does lives in a plugin the
  coding agent loads itself (roles, skills, hooks), not in prompt strings.
- **Routing**: per-task coding agent, model, budget and credential from one
  TOML file, with failover on rate limits.
- **Checked before it spends**: a flow, its plugins and its routing are checked
  without launching anything, and a stub agent tests a flow's wiring.
- **A live monitor** of every run: plan, journal, transcripts, outputs.

## Install

Linux, Python 3.12 or later, and a coding agent on `PATH` for real runs:
`claude` (Claude Code), `omp` (oh-my-pi), `opencode`, `pi` (pi.dev), `codex` (Codex CLI), or several of them.

```
uv add contraagent                  # or: pip install contraagent
uv add 'contraagent[monitor]'       # with the web monitor
```

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
- [Tasks and flows](tasks.md): agent tasks, Python tasks, the flow, flows that depend on results, time boxes, files a task changes, a pipeline's own records, and the engine underneath.
- [Plugins](plugins.md): an agent task's implementation: roles, skills, hooks.
- [Contracts and validators](contracts.md): how outputs are checked and sent back.
- [Routing and credentials](routing.md): the config file: coding agent, model, budget, failover, identity, quota caps.
- [Checking and testing](testing.md): `contraagent check`, a stub run of the whole flow, and flows tested on a stub agent.
- [The monitor](monitor.md): the live view of runs, and an export of it that needs no server.
- [Many hosts: the hub](hub.md): every host's runs in one monitor: `contraagent hub` and `contraagent relay`.
- [Operating a hub](hub-operations.md): set up with compose, connect hosts, tokens, retention, backups, upgrades, troubleshooting.
- [Compatibility](compatibility.md): what is public, what a release may change, deprecation, and the formats and JSON Schemas of the files a run writes and of the config file.

`examples/tutorial/` is the tutorial's pipeline, finished. `examples/demo/` is a whole pipeline (its tasks, plugin, config, a test, and a
script that runs it); `examples/review/flow.py` and `examples/analysis/flow.py`
are generator flows (a review loop per unit; a three-layer nested flow);
`examples/changes/flow.py` is a task that changes files beside its output;
`examples/implementations/flow.py` declares a step with two implementations and chooses one per unit;
`examples/reference/pipeline.toml` is every config table and key, annotated. The
test suite runs them all.
