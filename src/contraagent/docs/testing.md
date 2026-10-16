# Checking and testing

Two tools find a flow's mistakes before a coding agent spends tokens on them.
Neither says whether a plugin's roles make an LLM write good outputs; that
takes a run on a real coding agent.

## Check: nothing launches

```
contraagent check tasks.py:<flow> --config pipeline.toml --kwargs '{"units": ["a", "b"]}'
```

It builds the task graph a run would, launches nothing, writes no run
directory, and reports every problem at once: an exception in the flow at the
line that raised it, parameters that do not fit their model, an output model
the agent's own check cannot import, a validator's program missing from `PATH`,
what `plugin lint` finds, and what the routing plan refuses. Each problem names
the documentation topic that explains it: a message that ends with a pointer such as
`(contraagent docs tasks, Services)` names the topic and its section, and the last
line, `read:`, lists the pointers of all the errors. A declaration that is wrong where it
is written (a role the plugin does not define, an unknown budget key in
`agent_task`) stops the import of the module that declares it, so it is the one
error reported until it is fixed. `Pipeline.check(flow, ...)`
does the same in Python; its docstring (`help(contraagent.Pipeline.check)`) lists
every check, and `contraagent check --help` every option.

A generator flow creates its tasks as it runs, so `check` runs it to its first
wait: every flow call it starts runs up to the first `yield` that waits for a
task, and the tasks created by then are checked like a flow's that does not
yield. The kinds it creates later are found in its code: the task declarations
the flow refers to, directly or through the functions, modules, closures and
containers it refers to (the glossary's **reachable kind**, in [Concepts](concepts.md), says
exactly what is followed). Their declarations and routing are checked too, and
the report lists them as later kinds. Two declarations of one kind that differ
and are both reachable are a warning, not an error: the flow may create tasks of
only one of them (a default argument its caller replaces), and the kind is
checked as the first one found. A task declared inside the flow's body is not
found until it is created. What the flow does with results is tested on the
stub agent.

Run it after every change to tasks, plugins or the config.

## Stub run: the whole flow on examples, nothing called

```
contraagent run tasks.py:<flow> --config pipeline.toml --stub --kwargs '{"units": ["a", "b"]}' [--execute fetch]
```

With `--config`, its `[route]` lines name the routes a real run takes; without it,
each kind's declared defaults.

A stub run goes past the first wait. The stub agent plays every task: an agent
task's output, and a Python task's return value, is its output's **example**. No
model is called, no Python task's function runs, and the flow goes on to its end on
those outputs, so the run lists every task the flow creates on that path
(`kind · unit`, how it ended, and the flow path that created it). `--execute <kind>`
runs that Python task kind's function instead (a read-only step whose real output
the flow needs); give it once per kind, or give an `fnmatch` pattern of kinds
(`--execute 'fetch_*'`). `--execute '*'` runs the function of every Python task, so
the stub agent plays the agent tasks only: the pipeline's own code runs for real, and
no model is called. Quote a pattern, so that the shell does not expand it. A kind name
holds no `*`, `?` or `[`, so a pattern never reads as a kind. The run id is
`<flow>-stub`, and the monitor marks the run "stub agent".

The example follows one rule, at every part of the output's JSON Schema: the first
entry of that part's `examples`, else the smallest value that part accepts (required
fields only, the shortest lists and strings, numbers nearest zero, an enum's first
value). So a model's own example is the whole value, a field's example is that
field's value, and a part with none is the smallest:

::code{file="examples/demo/tasks.py" from="class Summary(BaseModel):" to="class Score(BaseModel):"}

A text output takes its example from `Annotated[str, Field(examples=[...])]` (the
demo's `Note`); a plain `str` output is `stub`. `contraagent check` reports an
example that does not pass its own model.

Give each output model an example that passes its validators, and a stub run goes
through the whole flow. In each string of an example the stub writes, `{unit}`,
`{key}`, `{kind}` and `{params.<name>}` are the task call's, as in a claim, when the
value is a string or a number; any other field stays as written. So one example
passes a validator that compares an output with a param set per unit:
`{"module": "{params.module}"}` is `"bank"` for the call `review("bank", module="bank")`.
A coding agent reads the example as written, in the output's schema. Examples that
agree with each other pass too: the demo's summary names the unit of the prepared
example, and its note names the summary's unit:

```
demo="$(contraagent docs --path)/examples/demo"
contraagent run "$demo/tasks.py:docs" --config "$demo/pipeline.toml" --stub --kwargs '{"units": ["alpha", "beta"]}'
```

```
11 tasks created:
  prepare · alpha | completed | docs > review_loop (line 151)
  summarize · alpha | completed | docs > review_loop (line 151)
  prepare · beta | completed | docs > review_loop (line 151)
  summarize · beta | completed | docs > review_loop (line 151)
  score · alpha | completed | docs > review_loop (line 155)
  review · alpha | completed | docs > review_loop (line 156)
  score · beta | completed | docs > review_loop (line 155)
  review · beta | completed | docs > review_loop (line 156)
  write_note · beta | completed | docs > review_loop (line 160)
  write_note · alpha | completed | docs > review_loop (line 160)
  report | completed | docs (line 167)
✓ 11/11 tasks done in 0.6s; run in runs/docs-stub
```

The flow takes the path its examples lead to: the demo's review approves, so no
summary is revised. A branch on a value no example holds is not taken, and a rule
the stub cannot build where there is no example (`pattern`) fails the task and
names the rule. A validator that rejects the example ends its task `invalid_output`
after one round, with no correction round and no retry (the stub would write the
same value again); the tasks that need its output do not run, `contraagent run`
exits 1, and its last line names the validators:

```
  summarize-alpha: invalid_output out/summarize/alpha.json: [three_points] points: exactly three expected, got 0
2 tasks failed checks on the examples the stub agent wrote (summarize: three_points), so the tasks that need their outputs did not run. Give each output model an example that passes its validators: `contraagent docs testing`
```

A stub run plays one reply per task, so the correction rounds, failures, retries
and failover of a flow are tested on the stub agent ([below](#test-the-stub-agent)).

Flow code itself runs as in any run: a side effect in the flow's own body happens
in a stub run too. Put side effects in Python tasks. In Python,
`Pipeline(stub=StubAgent(script, default=writes_example(), execute=[...]))`
scripts the replies of both kinds of task, as a test does (the
`contraagent.testing` module docstring lists the replies);
`StubAgent(default=writes_example(), execute=["*"])` is `--execute '*'`.

## Record once, replay in CI

```
contraagent run tasks.py:<flow> --config pipeline.toml --record recordings/ --kwargs '{"units": ["a", "b"]}'
contraagent run tasks.py:<flow> --config pipeline.toml --replay recordings/ --kwargs '{"units": ["a", "b"]}'
```

A run with `--record DIR` (`Pipeline(record=DIR)`) runs as any run does and keeps a
**recording** of each task attempt: `DIR/<kind>/<key>.json` with the facts of an agent
task's last launch (how it ended, its final message, turns, agent, model) and its task's
fingerprint, and beside it the final contents of its output files, the files its
`changes=` patterns saw created or modified (and the paths they saw deleted), and its
part of the transcript when transcripts are kept. A Python task attempt's recording holds
how its call ended (a `Partial` is played as `partial` again, its reason too) and its output
file, which is what the flow receives from it, and the rows and documents its call wrote with
`contraagent.log` and `contraagent.save` (a replay writes them into the run's `pipeline/` again,
so a panel reads the same; a file over the cap makes the attempt unplayable, as an output
does). An agent task has none: its coding agent runs in another process, with no current run. Nothing
else of the working directory is kept. A task's first attempt in a run replaces its
recording. Record on a real coding agent once, and commit the directory with the tests.

A recorded file larger than 4 MB (`--record-max-file-mb N`, `Pipeline(record_max_file_mb=N)`)
is kept by its SHA-256 and size only, so the directory stays small enough to commit; a
warning names each one (`[record] <key>: <path> (<size>) stored by hash only`), and the run
ends with one line on what it recorded:

```
[record] recordings/: 1,284 files, 212 MB | 3 files stored by hash | 2 tasks cannot be replayed: kinds extract, index
```

A task whose recording holds a file by hash only cannot be played: in a replay it ends
`error` at once, its reason naming the file and its size. Run its kind with `--execute`
(a Python task), record it again with a larger cap, or let `--record-missing` record it again.

A **replay** (`--replay DIR`, `Pipeline(replay=DIR)`) plays those recordings in place of
every agent task's launch and every Python task's function: attempt 1 the first
recording, attempt 2 the second, past the last the last again. Each writes the recorded
outputs and files into place, deletes the recorded deletions and adds the recorded
transcript; its output checks and the journal run as in any run, and it reports no cost
and no tokens. A Python task that calls a server (a local index server) needs nothing
running in CI, since its output is replayed. A [service](tasks.md#services-a-server-that-the-tasks-of-a-claim-share)
of `Pipeline(services=)` starts only for a task that really runs: a replay starts
none for a task it plays, and starts one for a Python task whose function it runs.
`--execute KIND` (`Pipeline(replay=DIR, execute=["KIND"])`) runs that
Python task kind's function instead, and `--execute '*'` (`Pipeline(replay=DIR,
execute=["*"])`) every Python task's, as in a stub run: the pipeline's own code under
test. So a replay in CI follows the flow down the path the real outputs led to, with
nothing spent.

A replay is a stub run (the monitor marks it "replay" and names its recordings), its run id is
`<flow>-replay`, and `run.json` names the recordings (`replay`). A task with no
recording, agent or Python (but a kind it executes), ends `error` with `no recording for <key>`
after one attempt; a key minted with `~n` that has
none of its own plays the first recording of its base key after it that no task has
played. A recording made by another definition of the task (another fingerprint) is
played all the same, and the task's reason says so: record again when the change
matters. A task's outside state (`outside_state=`) is worked out in the replay's own
working directory; a recording made with another one is played the same way. A replay walks no failover hop and is not combined with `--stub` or `--record`. A recording
directory holds:

```
recordings/<kind>/<key>.json         the task's recording: one entry per attempt, in order
recordings/<kind>/<key>/<id>/        the files of one attempt:
    output-<n>                       the final contents of its n-th output file
    output-<n>.message.txt           the whole final message beside an unwrapped output
    files/<path>                     what its `changes=` patterns saw created or modified
    stream.jsonl                     its part of the transcript, when transcripts are kept
    pipeline/<name>.jsonl            a Python task's rows of `contraagent.log(name, ...)`, in order
    pipeline/<name>.json             a Python task's last `contraagent.save(name, ...)`
recordings/undeclared.json           the undeclared changes of the last recording run (below)
```

### Undeclared changes

A replay writes only what a recording holds, and a recording holds only what a task
declares: its outputs and its `changes=` files. A file the recorded run wrote anywhere
else (a cache a Python task fills, a report the flow's own body writes, a file an agent
edited outside its patterns) is not there in a replay, and a later task that reads it
finds it missing, or finds what the CI checkout holds. So a recording run compares the
working directory at its start and its end (by each file's modification time and size;
`.git`, `__pycache__`, the recordings and the run's own files are left out, but its `out/`
is compared like any other folder). Each path created, modified or deleted that no task's
outputs or `changes=` cover is an **undeclared change**: the run warns once per path

```
[record] undeclared change: cache/index.json
```

and writes them to `DIR/undeclared.json` (`created`, `modified`, `deleted`). Tasks run at
once, so a change is the run's, not a task's. Declare it where it is made: a `changes=`
pattern on the agent task, the Python task's output, or a Python task in place of the
flow's own side effect.

### Fill in what is missing

```
contraagent run tasks.py:<flow> --config pipeline.toml --replay recordings/ --record-missing --kwargs '{"units": ["a", "b", "c"]}'
```

When the flow gains a task, or a unit, record only what is new: with `--record-missing`
(`Pipeline(replay=DIR, record_missing=True)`) a task with a recording plays it, and a task
with none launches (or runs its function) as in any run, on the config's routing with its
failover, and its recording is written into the same directory. The directory may start
empty. Such a run can spend tokens, so it is not a stub run (`run.json` `stub` is false);
each attempt that played a recording says so in its journal row (`replayed`). `--preflight`
and `backends=` apply to the launches it makes; `--stub` and `--record` are refused.

### Import a run that was not recorded

A run without `--record` still keeps most of what a recording holds: its journal, its
contract records, its launches, its transcripts and its output files. `contraagent
recording import RUN_DIR DIR` (`contraagent.import_recording(run_dir, directory)`) writes
a recording of each task that run finished into `DIR`, as if the run had been recorded,
so a replay plays the run's real outputs without running it again:

```
demo="$(contraagent docs --path)/examples/demo"
contraagent run "$demo/tasks.py:docs" --stub --kwargs '{"units": ["alpha"]}'
contraagent recording import runs/docs-stub recordings/
contraagent run "$demo/tasks.py:docs" --replay recordings/ --kwargs '{"units": ["alpha"]}'
```

```
✓ 6 tasks imported from runs/docs-stub into recordings
```

Each task whose last attempt finished ok, or `partial`, is imported as one attempt; a
replay plays it on the task's first attempt. An agent task brings its output files, the
whole final message beside an unwrapped output, the files its `changes=` patterns saw
created or modified, the paths they saw deleted, and the facts of its last launch. Its
transcript comes too when the journal holds a single attempt of the task; a replay does
not need one. A Python task brings its output file, which is the return value the flow
received (a task that returns None has none). The rows and documents its call wrote with
`contraagent.log` and `contraagent.save` are not imported, since the run's `pipeline/`
does not say which call wrote them; run its kind with `--execute` when a panel needs them.
The files are taken as they are now, so import a run that has ended and whose files
nobody has changed since. Recordings of other keys in `DIR` stay, and the import writes
no `undeclared.json`, since it did not see the working directory change.

The import reports each task it leaves out. A task whose last attempt did not finish ok
is listed as not finished: a replay of it, with no recording, ends `error` too, or
launches with `--record-missing`. A task that finished is listed as not imported, with
the reason, when its journal row holds no fingerprint, when one of its files is missing,
when a later task of the run wrote the same file again (the file then holds that task's
contents), or when a file is over the cap (`--record-max-file-mb N`, default 4). A run of a run format
this release does not read is refused (`RecordingError`). The command exits 1 when a task
that finished is not imported, or when it imports none.

An imported recording names the run it came from (its entry's `imported`: `run`,
`run_uid`, `imported_at`) and keeps the fingerprint the journal recorded. A replay plays it
only for a task of the same key and the same fingerprint. When the task's definition,
params or inputs have changed since that run, the task ends `error` with the reason `the
recording of <key> was imported from run <run> with another fingerprint`, or, with
`--record-missing`, launches and is recorded again. An imported recording is never
played for a `~n` key of its base. A recording that a recording run wrote is played for
another fingerprint, as above; an imported one is not, since nothing observed the
task as it ran then.

## Test: the stub agent

`contraagent.testing.StubAgent` is a coding agent for tests. It reads its call
file like a real one and plays the reply scripted for each task: an output to
write, nothing, a failure, or a rate limit. Only the coding agent is replaced;
output checks, correction rounds, failover, retries and the journal run for real.
`stub.backends()` puts it under every coding agent's name, so the pipeline's
own config routes to it, and under each name it acts as that agent does: under
the name of an agent whose stop hook continues the session (Claude Code, Codex,
omp) it runs the plugin's Stop hooks before it ends its turn and replies again when
one sends the output back (`launch.in_turn`); under the others (opencode, pi) it
stops. A
429 in a test moves the kind's later tasks to the hop too (see `routing`). A reply that
reports a quota reading (`writes(value, quota=QuotaReading(five_hour_pct=80))`)
rests a credential past its quota cap or its `quota_rule`, so a test can follow a task to
its next hop, or to `deferred`. A reply that writes and then stops
(`writes(value, stop=Stop.TIMEOUT)`, `Stop` from `contraagent.backends`) plays a
launch the runner stopped for its time, for a kind with
[`partial_on`](contracts.md#a-launch-stopped-for-its-time). A callable reply is given
the launch (`StubLaunch`): `launch.launch.cwd` is the working directory, where a reply
can write the files of a task's `changes`, and `launch.launch.mcp_config` the file of
its MCP servers (the plugin's `.mcp.json`, or those `Pipeline(mcp_servers=)` built for
the task, a file that exists while the launch runs). Tests import the flow's module like any other code: one
outside the project's package needs the project root on `sys.path` (pytest's
`pythonpath` setting). The `contraagent.testing` module docstring
(`help(contraagent.testing)`) lists every kind of reply.

::code{file="examples/demo/test_demo.py" from="def summary(launch):" to="@pytest.fixture"}

Every launch is recorded (`stub.launches`, `stub.launches_of(key)`): which
model it ran on, whether it was a correction round, the prompt it was sent, its
call file and the launch itself (its budget, environment and plugin).

::code{file="examples/demo/test_demo.py" from="def test_the_flow_checks_clean" to="def test_the_report_covers"}

What a flow returns is `RunReport.value`, as the flow returned it: a generator
flow's return value, or, for a flow that does not yield and returns a task call,
that task's `Pending` (its output is `report.value.output`):

::code{file="examples/demo/test_demo.py" from="def test_the_report_covers"}
