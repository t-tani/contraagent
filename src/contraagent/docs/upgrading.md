# Upgrading from 0.7 to 0.8

This topic lists what a pipeline written for contraagent 0.7 changes, or must know, to
run on 0.8. It is the one topic that names the forms of an earlier release. The other
topics state only the forms of this release, and `CHANGELOG.md` lists every change of
0.8.0, also those that need nothing from a pipeline.

Most flows of 0.7 run on 0.8 with no change to their code. A config or a declaration
with `timeout_s = 0` stops the run before it starts, a custom claim capacity needs
three new methods, and a hub's TTL is set on the relays now. The run format stays 1:
0.8 reads the run directories of 0.7, and the monitor shows them.

## Before you upgrade

Do these steps in this order for a pipeline that runs in production.

1. Give each `timeout_s` a number of seconds above 0 (see
   [Launch time limits](#launch-time-limits-above-0)).
2. Decide the `max_corrections` of each kind again, since it now counts the stop
   hook's objections too (see [Corrections](#corrections-one-budget-for-objections-and-correction-rounds)).
3. Add `started`, `ended` and `refresh` to each `ClaimCapacity` class of the
   pipeline's own (see [Claim capacities](#claim-capacities-a-task-holds-its-memory-until-it-ends)).
4. When the runs go to a hub, upgrade the hub first and the relays after it, and move
   a `--ttl` from the hub's command to the relays' (see
   [The relay sets the TTL](#the-relay-sets-the-ttl)).
5. Finish on 0.7 the runs that give an output file to another task as an input file,
   or accept that the first resume on 0.8 runs those tasks again, once (see
   [Output files given as input files](#output-files-given-as-input-files-the-root-out)).
6. Check the pipeline (see [Check the upgrade](#check-the-upgrade)).

## Launch time limits: above 0

`timeout_s` takes a finite number of seconds above 0 only: in `Limits(timeout_s=)`, in
`[tasks.<kind>]` and in `agent_task(timeout_s=)`. 0, a negative number, infinity and
NaN are an error where they are given: `ConfigError` from the config file and from
`agent_task`, `ValueError` from `Limits`. `contraagent check` reports a value of the
config file. On 0.7, `timeout_s = 0` meant an immediate timeout on most coding
agents, 600 seconds on `omp-rpc` and no time limit on the omp command line. Give the
seconds the launch may take.

## Corrections: one budget for objections and correction rounds

A correction is each time the output's errors go back to the agent session: an
objection of the plugin's stop hook within a round, or a correction round, in which
the runner resumes the session. `max_corrections` counts both, in all. On 0.7 it
counted only the correction rounds, and the stop hook could also object once in each
round, so the default of 3 allowed up to 3 correction rounds and 4 objections.

| 0.7 | 0.8 |
|---|---|
| `max_corrections = N`: N correction rounds, and up to N + 1 objections | `max_corrections = N`: N corrections in all |
| the default 3, which allowed up to 7 corrections on Claude Code, Codex and omp | `max_corrections = 7` to keep that ceiling (20 at most) |

On opencode and pi, which have no stop hook that continues a session, nothing
changes. Each round's environment holds the corrections it has left
(`CONTRAAGENT_CORRECTIONS_LEFT`). A `stop` script of the plugin's own exits 0 when
that value is `0`, as `run = "validate"` does
([Hooks](plugins.md#hooks)). The journal's `max_corrections`, the run summary's
`corrections` and the monitor's counts of corrections include the objections, and
`StubAgent` applies the same limit to its stop hooks, so a test that counts a stub
task's objections may count fewer.
[Checked twice, by the same rules](contracts.md#checked-twice-by-the-same-rules) states
the rules.

## Claim capacities: a task holds its memory until it ends

A `PerTask(memory_mb=...)` claim capacity holds each running task's `memory_mb` until
the task ends, or what its processes take when that is more. On 0.7 it subtracted
`memory_mb` from the free memory for the task's first 30 seconds only. A host may
therefore start fewer tasks at once than on 0.7 when a task's `memory_mb` is more than
it takes. Give as `memory_mb` the most memory one task takes
([Claims](tasks.md#claims-one-task-at-a-time-on-a-name)).

A claim capacity of the pipeline's own, given to `WorkQueue(claim_capacity=)`,
implements the protocol `ClaimCapacity` of `contraagent.engine`, which has three more
methods. The queue calls them, so a class
without them fails when a task that claims the name starts.

| Method | The queue calls it when |
|---|---|
| `allowed(held)` | it asks how many running tasks may hold the name, as on 0.7 |
| `refresh()` | it begins to try to start tasks: what the capacity reads of the host, it reads again |
| `started(key)` | the task with `key`, which claims the name, has started |
| `ended(key)` | that task has ended, one call for each `started` |

A capacity that reads nothing of the host and holds nothing for a task gives each of
the three methods an empty body.

## The relay sets the TTL

A hub counts a host as up for its TTL after it receives the host's heartbeat. The relay
sets the TTL now, and carries it in each heartbeat (`ttl_s`).

| 0.7 | 0.8 |
|---|---|
| `contraagent hub --ttl 30` | `contraagent relay --ttl 30` on each host |
| `contraagent hub prune --ttl 30` | `contraagent hub prune` |
| the hub's default TTL | four times the relay's `--interval` |

The hub refuses `--ttl`, so remove it from the hub's service or compose file. The relay
refuses a `--ttl` that is not more than its `--interval`. Upgrade the hub first, then
the relays: the hub of 0.8 counts a heartbeat of a relay of 0.7, which has no `ttl_s`,
as up for four times its `interval_s`. [Operating a hub](hub-operations.md#upgrade) has
the steps.

## Output files given as input files: the root `out`

An output file of the run given to a task as an input file is a file of the input root
`out`, the run's `out/` directory. `pending.input_file()` returns
`InputFile("<path under out/>", root="out")`, and the params, `plan.jsonl` and the
fingerprint hold `{"root": "out", "path": ..., "sha256": ...}`.

| 0.7 | 0.8 |
|---|---|
| `pending.input_file().path` is `out/review/a.json`, from the working directory | `review/a.json`, with `root` `out` |
| `InputFile("out/review/a.json")` | the same file, held as a file of `out` |

So the fingerprint of a task given an output file as an input file changed. The first
resume on 0.8 of a run that 0.7 started runs each such task again, once, and spends
what it spent. A replay still plays a recording of 0.7 for such a task, and the task's
reason says that the fingerprint differs; record again to make them match. Code that
reads the `path` of such an `InputFile`, or the params JSON that an `outside_state`
function is given, reads the path under `out/`. A Python task is given an absolute
`path`, as on 0.7.

## New in 0.8, and optional

These need nothing from a pipeline of 0.7.

- A task call's option `cwd` gives an agent task a working directory of its own, such
  as a git worktree for each unit: `implement.options(cwd=tree)(unit, change)`
  ([A working directory of its own](tasks.md#a-working-directory-of-its-own-git-worktrees)).
- Input roots give a task a file outside its working directory without its directory
  in the fingerprint: `Pipeline(input_roots={"data": "/srv/corpus"})` or
  `contraagent run --input-root data=/srv/corpus`, and
  `InputFile("2026/x.csv", root="data")`
  ([Input roots](tasks.md#files-outside-the-working-directory-input-roots)).
- `record_exclude` leaves paths out of a recording run's comparison of the working
  directory: `Pipeline(record_exclude=[".venv"])` or `contraagent run --record-exclude
  .venv` ([Undeclared changes](testing.md#undeclared-changes)).

## Check the upgrade

These steps launch no coding agent and spend nothing.

1. Type check the pipeline with mypy or pyright. They find a `ClaimCapacity` class
   that lacks one of the new methods where it is given to `WorkQueue(claim_capacity=)`.
2. Run `contraagent check <file.py>:<flow> --config pipeline.toml --kwargs '{...}'`
   until it prints ✓. It reports a `timeout_s` that is not above 0 and a
   `max_corrections` out of range ([Check](testing.md#check-nothing-launches)).
3. Run the tests of the flow on `contraagent.testing.StubAgent`, and correct a test
   that counts the stop hook's objections.
4. Remove `--ttl` from the hub's command, and start it; it refuses an option it does
   not know.
