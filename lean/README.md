# The Lean specification

This Lake package describes modules of contraagent's Python package in Lean 4. A
description is a set of definitions that run. Theorems state what holds of the
definitions, and Lean checks every proof each time the package is built.

A proof is about the description, not about the Python code. Tests of the Python
package keep the two in step. They need no Lean: they read the Lean files, and
files that this package writes and the repository keeps.

## What it describes

The modules are those of `src/contraagent/_internal/`.

| Lean file | Describes | Holds |
|---|---|---|
| `Contraagent/Runs/Files.lean` | `runs/files.py` | a run's log: the bytes an append writes, what a write that was cut leaves, and the lines a reader reads |
| `Contraagent/Dispatch/Records.lean` | `dispatch/records.py` | the cause of a deferral, a line of `services.jsonl`, a quota reading and why a credential rests |
| `Contraagent/Dispatch/Task.lean` | `dispatch/task.py` | a task, its result, a time box, a deferral and the stop values |
| `Contraagent/Dispatch/Queue.lean` | `dispatch/queue.py` | the work queue: what it accepts, what a pass starts and in which order, what it defers, retries and cancels, and how each task finishes |
| `Contraagent/Dispatch/Flow.lean` | `dispatch/flow.py` | the flow driver's record: the numbers of each flow call, which task it gives the queue and when, the order in which it gives results to the flow code, how a flow call ends, which task it cancels, and when it closes the flow calls that nothing will answer |
| `Contraagent/Backends/Launch.lean` | `backends/launch.py` | the stops a launch of a coding agent ends with |
| `Contraagent/Routing/Router.lean` | `routing/router.py` | the failover breaker: the route the next task runs on, what a 429 moves, the probe of the primary and what closes the breaker |
| `Contraagent/Routing/Capacity.lean` | `routing/capacity.py` | a claim capacity sized by the host: how many tasks may hold a name, given the memory and cores one needs, what the running tasks hold and what the host reads |
| `Contraagent/Routing/Pool.lean` | `routing/pool.py` | a credential pool: the member the next launch uses, in order or in a round robin, and how long a member rests after a 429 |
| `Contraagent/Routing/Quota.lean` | `routing/quota.py` | the credential rests: which reading of a credential counts, when a cap or the quota rule rests it and until when, the grace window of the finishing kinds, when a pool rests, and a credential refused for the rest of the run |
| `Contraagent/Execution/Runner.lean` | `execution/runner.py` | one attempt of an agent task on its kind's failover chain: the hops it launches on, the hops it passes over because their credential rests, when it is deferred, which launch's result is its own; and whether a fresh attempt follows |
| `Contraagent/Execution/Services.lean` | `execution/services.py` | the services of a run: when the service a claim name stands for starts, which tasks a start that raised fails and for how long, and what the run's end stops, in which order |
| `Contraagent/Execution/Journal.lean` | `execution/journal.py` | the journal a resume reads: the rows of its log, each key's last row, and the tasks an attempt of which the run's end cut |
| `Contraagent/Execution/Run.lean` | `execution/run.py` | what a resume skips, given each key's last journal row, and why it runs a finished task again |
| `Contraagent/Pipeline/Graph.lean` | `pipeline/graph.py` | what the graph decides of a task call: its key, its output file and the tasks it waits for, or why the call is refused |
| `Contraagent/Hub/Segments.lean` | `hub/segments.py` | the hub's copies of a log: which lines it holds and which are durable, when an open segment is sealed, the order of a seal's steps, what a start recovers from the files, the objects and the index, and what `sweep` and `drop` delete |
| `Contraagent/Hub/Relay.lean` | `hub/relay.py` | the relay's shipping of a run's logs: the lines of each request, what it takes from the hub's answer as its progress, and when it sends the run again or stops |
| `Contraagent/Hub/Core.lean` | `hub/core.py` | the hub's retention: which runs, transcripts, heartbeats and blobs a prune removes and what it reports; the blobs and the file refs, and what the hub holds under one name, while a prune runs beside the relays; and what the hub answers a request for a run its retention removed |

A description holds the fields that its module decides by. What only travels with
a task or a result is left out, and the first comment of each file says what.

## What is proved

`Contraagent/Dispatch/Queue/Keys.lean` proves that no two tasks of one key are queued
or running at once (`Reachable.keys_distinct`, `Reachable.running_keys_distinct`).
It holds in every state the queue reaches (`Reachable`): from the empty queue, by
any sequence of what the queue is told (`add`, `extend`, `cancel`), passes, ends of
tasks and `giveUp`, at any times and with any answers of the callbacks. The proofs
about the queue assume nothing of its runner. Of the task a runner gives as a task
starts, the queue takes only the fingerprint (`QueueEnv.started`), so the task that
starts has the id, the key, the dependencies and the claims the queue held it by
(`Queue/Reachable.lean`, which also holds the reachable states).

`Contraagent/Dispatch/Queue/After.lean` proves that no task starts before the tasks
it comes after have finished (`Reachable.starts_after`): wherever the queue's log
shows a task starting, each key the task names in `after` is of a task that the log
shows finished before, with any result.

`Contraagent/Dispatch/Queue/Capacity.lean` proves that a claim capacity is not
passed: while the capacity of a claim name is the number `n` at every pass, at most
`n` running tasks hold the name (`ReachableWithin.capacity`). Only a pass starts a
task, and it starts one only while every name the task claims has room.

`Contraagent/Dispatch/Queue/Ids.lean` proves that each task finishes once. In every
state the queue reaches, the log shows each task finished once at most
(`Reachable.finished_once`); and once nothing is queued, running or waiting to
finish, every task the queue accepted has finished (`Reachable.accepted_finished`).

`Contraagent/Dispatch/Queue/Idle.lean` proves that no slot idles. The queue's log
only grows, so a pass that reports nothing started and deferred nothing; when a slot
was free at such a pass, every queued task was held back (`Reachable.pass_quiet`):
it is not startable, because a task it comes after has not finished or it waits for
its retry, or what it needs is not free, or starting it would take what a task that
waits for room still needs.

`Contraagent/Dispatch/Queue/Ends.lean` proves that the queue ends. Every round of
the queue's loop, a pass and then another pass, a task's end, the end of a retry
wait or a give-up, takes at least one from a count of what the held tasks may still
do, but for seven for each task the queue is newly given (`Round.lowers`). So a run
in which the queue is given a bounded number of tasks has a bounded number of rounds
(`Rounds.bounded`): from an empty queue, at most seven for each task
(`Rounds.from_empty`), whatever the tasks' results are and whenever they end. A wait
that ends with no task ended is no round, so the theorem assumes nothing of how long
a task runs: it bounds what the queue does, not the time it takes.

`Contraagent/Dispatch/Flow/Keys.lean` proves, of the flow driver, that the queue is
given each key once, whatever flow code does with the key: creates its task twice,
waits for it in several flow calls, or names it again after its result was given
(`Reachable.sent_once`). A key the driver cancels on the queue is one it gave the
queue (`Reachable.cancels_sent`). And when the driver closes the flow calls that
nothing will answer, no flow call waits for a task, and every task the driver queued
has given its result (`Reachable.stuck_waits_for_no_task`): what it closes waits for
something that no task answers. These hold of every record the driver reaches
(`Flow/Reachable.lean`): from the empty record, by any calls in any order. A Task
is created under a flow call only when the driver holds that flow call, which the
driver checks as it numbers the Task.

`Contraagent/Dispatch/Flow/Calls.lean` proves that each flow call has numbers of its
own (`Reachable.calls_distinct`), and its id is those numbers joined by dots; that
the driver says a flow call still runs exactly when one does (`Reachable.alive_iff`);
and that once the run is over and the driver has closed the flow calls that still
ran, none runs (`Reachable.none_runs_after_close`).
`Contraagent/Dispatch/Flow/Order.lean` proves that the result the flow code gets
next is, of the kept results of skipped tasks, the one whose key has the least place
in the first run (`next_least`). So a resume gives the flow code those results in
the order of the first run, whatever order they come in.

`Contraagent/Dispatch/Flow/Settles.lean` proves that a run does not wait for what
nothing will answer. When the driver closes the flow calls that nothing will answer
and they have their turn, no flow call runs after the settle, whatever their code
does with the cancellation: one that goes on to wait again is ended by the driver
(`settle_ends`). The file then puts the driver beside a queue that holds the tasks
it was given until it finishes each and gives the driver each result (`Runs`): once
that queue holds no task and the driver keeps no result, no key is open
(`Runs.none_open`), so one settle ends every flow call, unless flow code creates a
task or a flow call in it (`Runs.settles`). With the queue's own bound
(`Rounds.bounded`), a run whose flow code creates a bounded number of tasks and of
flow calls ends: this last step is an argument over the two theorems, and the
queue's description and the driver's are not joined in one.

`Contraagent/Routing/Router/Breaker.lean` proves, of the breaker, that a 429 changes
nothing when it comes from a launch on the primary that is no probe
(`rateLimited_no_probe`) or from a hop that is neither the primary nor the hop in
force (`rateLimited_other_hop`); that after the task picked as the probe, every
task is picked the hop in force until the cool-off has passed again
(`pick_after_probe`); and that an exhausted chain stays exhausted.

`Contraagent/Routing/Capacity/Room.lean` proves that while no running task holds
memory, a name that no task holds admits at least one task, whatever the host reads
(`allowed_one`): a queue with nothing running always finds room for a task whose
capacities the host sizes.

`Contraagent/Routing/Pool/Rest.lean` proves, of a credential pool, that the member
a pick gives does not cool down on the model and is not excluded (`pick_rested`),
and that a member that answered 429 on a model is not picked for that model until
its wait has passed (`pick_after_rateLimited`).

`Contraagent/Routing/Quota/Rests.lean` proves, of the credential rests, that a
credential refused on a coding agent and a model rests there in every state the run
reaches after, for a task of any kind (`Steps.refused_rests`); that a rest the quota
rule gave an end holds to that end, whatever the readings and the rule say meanwhile
(`judge_ruled`); and that a credential with no reading, no rest of the rule in force
and no refused launch does not rest (`memberRest_unread`).

`Contraagent/Execution/Runner/Ends.lean` proves that an attempt ends: on a chain
with no two hops of one identity, its walk gives a result within twice the chain's
hops and one more round, whatever its launches give, whichever credentials rest and
whatever other tasks do to the breaker (`runWithFailover_ends`). Each round launches
once at most, so that bounds the launches of an attempt. The chain of every router
has no two hops of one identity (`chainOf_distinct`).
`Contraagent/Execution/Runner/Deferred.lean` proves that an attempt ends deferred
only when it launched nothing, having passed over every hop it could take, one of
them resting on its quota (`runWithFailover_deferred`); and that `deferral`, which
the queue asks before it starts a task, says what the attempt's first round would
(`choose_deferral`). The first holds of launches that end with a stop of a launch
or as a partial result, and `Contraagent/Backends/Launch/Own.lean` proves that none
of those stops is one of a task that was not launched: `deferred`, `skipped`,
`cancelled` or `duplicate_key` (`launchStops_not_own`).
`Contraagent/Execution/Runner/Attempts.lean` proves that a task gets one attempt
and its kind's `retries` more at most, that it ends with a result, and that the
journal gets no deferred attempt.

`Contraagent/Execution/Services/Once.lean` proves, of a run's services, that in
every state the run reaches, `services.jsonl` shows at most one start that went well
for each claim name (`Reachable.started_once`); that a service whose start raised
fails each task that claims its name, and starts nothing, until the cool-off has
passed (`acquire_resting`); that a task starts no service once the run's end closed
them (`hold_closed`); and that the run's end leaves no service up
(`close_none_up`). `Contraagent/Execution/Services/Order.lean` proves that the run's
end stops the services in the reverse order of their starts: the stops it writes,
the latest first, are the starts that went well, the earliest first
(`Reachable.close_reverse`).

`Contraagent/Execution/Run/Skip.lean` proves, of a resume, that a task is skipped
only when its key's last row is ok and not `partial`, holds the fingerprint the task
is judged by, the task does not rerun on resume and its output reads
(`resumeSkip_sound`); and that the history of a file that tasks fill in is that
file's own: the rows of tasks that fill in another file change nothing in it
(`leftDigests_own_file`). The digest of a fingerprint is asked of the surroundings,
so the first says "the same fingerprint", and what that means for the task's work
rests on SHA-256.

`Contraagent/Runs/Files/Whole.lean` proves, of a run's log, that a complete line stays
as it is (`append_keeps`); that an append that is not cut adds its rows as whole
lines, also after a write that was cut, whose line it ends first (`append_whole`), so
every row of such an append is read after any appends that follow (`whole_read`); and
that every line read is a row an append was given, or the first bytes of one whose
write was cut (`Reachable.read_given`). A write is cut by a full disk or by a host
that lost power. `Contraagent/Execution/Journal/Recorded.lean` puts this with the
resume: a resume skips a task only on a row the run recorded for the task's key, ok
and not `partial`, never on what a crash left in the file
(`resume_skips_recorded`); and a row appended whole is among the rows a resume reads,
whatever a cut write left before it (`recorded_read`). Both assume of a row's line
that it holds no newline and that its first bytes alone do not parse as a row, as a
JSON object does not. A task whose attempt the run's end cut is not skipped
(`unfinished_not_skipped`): the attempt left its in-flight marker and no row, so the
task's last row is of an earlier attempt, and its output file may hold what the cut
attempt wrote.

`Contraagent/Hub/Segments/Rows.lean` proves, of the hub's logs, that in every
state the hub reaches, each index row names an object that is in the store
(`Reachable.whole`): whichever seal failed, wherever a process died, and after an
index that lost its rows. A seal puts its object before it commits its row, and
`sweep` deletes only objects that no row names. The description gives a seal four
steps at which it may fail or the process may die, so every order of events a crash
leaves is one of its states.

`Contraagent/Hub/Relay/Prefix.lean` proves, of the relay, that every chunk of a
request holds lines of its log from the chunk's offset on (`chunks_of_file`), so a
hub that keeps every line once, in order, holds only first lines of the log
(`hubTakes_prefix`): never a line the log does not have in that place. The relay
takes as its progress what the hub says it holds (`acceptChunk_exact`), so its next
chunk starts where the hub's copy ends.

`Contraagent/Hub/Core/Pruned.lean` proves, of a run the hub pruned, that a request
that brings no line is answered and stores nothing (`answer_of_probe`), that every
answer names at least the lines of each chunk's offset (`answer_no_loss`), so the
relay finds no line lost and does not send the run again (`acceptChunk_kept`), and
that the hub stores the run again exactly when a chunk brings a line past those it
held (`answer_none_iff`).

`Contraagent/Hub/Core/Kept.lean` proves, of a prune, that it removes a run only when
the run's activity is older than the cutoff and the run is neither live nor
unresponsive (`removes_iff`), so each of those runs stays, as does one with no
activity time (`afterPrune_keeps_run`); that a blob stays when a file ref of a run
kept names it (`afterPrune_keeps_referenced`) or when it was stored within the grace
(`afterPrune_keeps_young`); that a heartbeat stays while it is not old, while its
host is up, and while it reports an unresponsive run the hub holds
(`afterPrune_keeps_heartbeat`); and that a dry run changes nothing and reports the
same (`prune_dry`). `Contraagent/Hub/Core/Settled.lean` proves that a prune is
complete: a second prune at the same time removes no run, no transcripts, no
heartbeat and no blob (`afterPrune_settled`), in a hub that holds one run under each
name. What a prune removes changes nothing in what it decided to keep.

`Contraagent/Hub/Core/Blobs.lean` proves that every file ref names a blob the hub
holds (`Reachable.refs_held`), after any steps of relays and prunes in any order and
however long a prune takes. A relay that asks for a blob renews it, as storing it
does, and a prune removes a blob only when it is still dated before the grace of the
time the prune began. The theorem assumes that each file ref arrives within the
grace of its relay's asking for the blob or storing it, and that the blob store
looks at a blob's date and removes the blob in one step, which the store in memory
does and the stores in a directory and in a bucket do in two calls.

`Contraagent/Hub/Core/Dated.lean` proves that a prune takes no line that arrives
while it runs. A request dates its run before it stores a line, and a prune removes
a run only while the run is dated as the prune read it. So whenever no request is
under way, the lines the relay was last told the hub holds are at most those the hub
holds, or held when it pruned the run (`Reachable.accounted`), after any steps of
requests and prunes in any order. The theorem assumes that a request stores its
lines within the retention of dating the run.

`Contraagent/Pipeline/Graph/Order.lean` proves, of every graph a flow builds
(`Built`), that no two tasks have one key (`Built.keys_distinct`) and that each task
waits for the latest earlier task of its output file, when there is one
(`Built.chained`). With the queue's `Reachable.starts_after`, the tasks of one file
run one after the other.

## How it is checked against the code

`tests/test_lean.py` and `tests/test_lean_scenarios.py` run with the other tests of
the Python package:

- Each Lean file is named after a module that exists, and the Lean imports follow
  the layers of `_internal`.
- The names that the specification shares with the code are the same on both
  sides. `lake exe contraagent-lean vocabulary` prints them,
  `tests/lean/vocabulary.json` holds them, and the test compares them with the
  code's: the stop values of `dispatch/task.py`, and the stops of a launch, the
  members of `Stop` in `backends/launch.py`.
- A run's log, the work queue, the flow driver, the failover breaker, a resume, the
  task graph,
  the host's room, a credential pool, the credential rests, a run's services, the
  attempts of agent tasks, the hub's logs, the relay and the hub's retention answer
  what their specifications do. A scenario of the breaker is a chain of routes and a list of
  calls of a `Router`, each at a time the scenario gives (`Conformance/Router.lean`,
  `tests/lean/router_scenarios.py`, 100 scenarios in
  `tests/lean/router_scenarios.jsonl`). A scenario of a resume is the rows of a
  journal, some keys with rows of earlier attempts, and the tasks the resume is asked
  about; it is played on `resume_skip` over what `Journal` reads from a log of those
  rows (`Conformance/Run.lean`, `tests/lean/resume_scenarios.py`, 60 scenarios in
  `tests/lean/resume_scenarios.jsonl`). A scenario of a log is a list of appends,
  some cut after any of their bytes; it is played on `append_lines` over a file whose
  write fails as on a full disk, and the complete lines and the line with no end are
  compared (`Conformance/Files.lean`, `tests/lean/logs_scenarios.py`, 200 scenarios
  in `tests/lean/logs_scenarios.jsonl`). A scenario of the graph is some declarations
  and a list of task calls, each by a flow call (`Conformance/Graph.lean`,
  `tests/lean/graph_scenarios.py`, 150 scenarios in
  `tests/lean/graph_scenarios.jsonl`). A scenario of the host's room is some needs
  and a list of calls, each with what the host reads then, and the answer, the
  baseline and the running tasks are compared after every call
  (`Conformance/Capacity.lean`, `tests/lean/capacity_scenarios.py`, 80 scenarios in
  `tests/lean/capacity_scenarios.jsonl`). A scenario of a pool is its members, its
  strategy and its cool-down, and a list of picks and 429s, each at a time the
  scenario gives (`Conformance/Pool.lean`, `tests/lean/pool_scenarios.py`, 100
  scenarios in `tests/lean/pool_scenarios.jsonl`). A scenario of the rests is some
  credentials with their caps, a pool and the grace window, and a list of readings,
  refused launches and questions, each at a time of day and a reading of the clock
  that only moves forward, with what the quota rule and the accounts answer then;
  the answers and what `on_change` is told are compared (`Conformance/Quota.lean`,
  `tests/lean/rests_scenarios.py`, 40 scenarios in
  `tests/lean/rests_scenarios.jsonl`). A scenario of the services is
  the claim names that stand for one, the cool-off, and a list of tasks and ends of
  the run, each with the clock's reading and what the start or the stop of each
  service does then; the answers and the lines of `services.jsonl` are compared
  (`Conformance/Services.lean`, `tests/lean/services_scenarios.py`, 40 scenarios
  in `tests/lean/services_scenarios.jsonl`). A scenario of attempts is a failover
  chain and some tasks that run one after the other on its breaker, each with its
  attempts' rounds: what a launch on each route gives, which routes rest, whether
  the task is cancelled, and what other tasks do to the breaker meanwhile. It is
  played on `RetryingRunner` and `AgentRunner` with coding agents that answer from
  the script, and the results the journal gets, each task's result and the
  breaker's switches are compared (`Conformance/Runner.lean`,
  `tests/lean/attempt_scenarios.py`, 30 scenarios in
  `tests/lean/attempt_scenarios.jsonl`). A scenario of the hub's logs is a list of
  appends, closes, ticks, reads, sweeps, drops and starts on three logs of two runs,
  with seals that fail and processes that die at a step of a seal; the answers, and
  the index rows, the objects and the files after the last step, are compared
  (`Conformance/Segments.lean`, `tests/lean/hub_scenarios.py`, 40 scenarios in
  `tests/lean/hub_scenarios.jsonl`). A scenario of the relay is one run's logs
  that grow, passes of the relay, a hub that loses lines or prunes the run, a relay
  that starts again without its progress, and a new run in the same directory; it
  is played on `Relay` over a run directory and a `Hub` in memory, and the requests
  of each pass, the relay's progress and the hub's lines are compared
  (`Conformance/Relay.lean`, `tests/lean/relay_scenarios.py`, 60 scenarios in
  `tests/lean/relay_scenarios.jsonl`). A scenario of the flow driver is a flow made
  as data: waits, tasks, Tasks awaited or not, Tasks that are cancelled when one of
  them fails, flow code that fails or goes on when it is cancelled, how each task
  ends, the tasks the queue holds from its start, and the order in which the results
  come. The flow is run on `FlowDriver` with a board in the queue's place, and the
  calls that the run makes on the driver are kept with the scenario. The
  specification is played on those calls, and what the driver answers each call,
  the tasks it gives the queue, the keys it cancels and how each flow call ends are
  compared (`Conformance/Flow.lean`, `tests/lean/flow_scenarios.py`, 30 scenarios
  in `tests/lean/flow_scenarios.jsonl`). Which call comes when is decided by asyncio
  and by the flow code, and the specification does not describe it. A scenario of
  a prune is what a hub holds: runs with their activity and file refs, transcripts of
  those runs and of run uids the hub no longer holds, heartbeats, blobs, and runs
  pruned before, with times at the edge of the cutoff and of the grace. It is played
  on `Hub.prune` over a hub in memory, and the report and what the hub holds after
  are compared (`Conformance/Core.lean`, `tests/lean/prune_scenarios.py`, 70
  scenarios in `tests/lean/prune_scenarios.jsonl`). A scenario of the blobs is a list
  of steps at times the scenario gives: a relay asks for a blob, stores one or sends
  a file ref, and a prune runs, with steps of relays that come after it read the file
  refs and before it removes a blob; what each step answers, the blobs held with
  their dates and the blobs that file refs name are compared
  (`tests/lean/blobs_scenarios.py`, 150 scenarios in
  `tests/lean/blobs_scenarios.jsonl`). A scenario of
  the queue scripts everything a queue does not decide: how each attempt ends and
  how long it takes, what a resume skips, what the runner defers, the task the
  runner gives as a task starts (for some tasks another task, of which the queue
  takes the fingerprint only), what a result's follow-up queues and what is
  cancelled, on a clock that only the scenario moves.
  `lake exe contraagent-lean queue` plays scenarios on the specification
  (`Conformance/Queue.lean`), and `tests/lean/queue_scenarios.py` plays the same
  ones on `WorkQueue`. `tests/lean/queue_scenarios.jsonl` holds 150 scenarios with
  what the specification reports for each, and `tests/test_lean_scenarios.py` plays
  them on the code: the two lists of events must be equal.

A scenario plays a module one step at a time, on a clock that the scenario moves.
A run has threads, processes and the real clock. `tests/lean/trace.py` therefore
notes what a `WorkQueue` reports while it runs as it does in a run, and
`lake exe contraagent-lean trace` checks that log against the conclusions of the
theorems about the queue (`Conformance/Trace.lean`): no task starts before the
tasks it comes after finished, no task finishes twice, a queue that ran to its end
finished every task it accepted, and the tasks the log shows running stay within
the queue's size, the capacity of each claim name and one task for each key.
`tests/test_lean_traces.py` does so for queues that run random tasks on threads.
With `CONTRAAGENT_TRACE=<folder>`, a test session notes every queue of its process,
whichever tests it runs, and `uv run python tests/lean/trace.py <folder>` checks
them; a session of every test notes about 1500 queues.

A description leaves parts of its module out, and a fault in such a part is one
that these comparisons do not see. `tests/test_hub_laws.py` therefore checks the
laws of the hub's logs and of the relay on the code alone, on the same random
scenarios: each log reads as its relay sent it, the durable lines are not lost, and
the hub holds every line of a run that grew once the relay asked what it holds.

The `lean` job of `.github/workflows/ci.yml` builds the package, with every proof.
It fails when a committed file is not what the specification gives now. It also
plays 400 scenarios of each kind, made for that run, on both sides
(`uv run pytest -m lean`).

A scenario's tasks never wait for each other: where `after` has a cycle, the
queue's bottom level depends on the order in which the code meets the tasks, and
the specification's does not.
