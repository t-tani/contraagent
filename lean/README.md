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
| `Contraagent/Dispatch/Records.lean` | `dispatch/records.py` | the cause of a deferral |
| `Contraagent/Dispatch/Task.lean` | `dispatch/task.py` | a task, its result, a time box, a deferral and the stop values |
| `Contraagent/Dispatch/Queue.lean` | `dispatch/queue.py` | the work queue: what it accepts, what a pass starts and in which order, what it defers, retries and cancels, and how each task finishes |
| `Contraagent/Routing/Router.lean` | `routing/router.py` | the failover breaker: the route the next task runs on, what a 429 moves, the probe of the primary and what closes the breaker |
| `Contraagent/Execution/Run.lean` | `execution/run.py` | what a resume skips, given each key's last journal row, and why it runs a finished task again |

A description holds the fields that its module decides by. What only travels with
a task or a result is left out, and the first comment of each file says what.

## What is proved

`Contraagent/Dispatch/Queue/Keys.lean` proves that no two tasks of one key are queued
or running at once (`Reachable.keys_distinct`, `Reachable.running_keys_distinct`).
It holds in every state the queue reaches (`Reachable`): from the empty queue, by
any sequence of what the queue is told (`add`, `extend`, `cancel`), passes, ends of
tasks and `giveUp`, at any times and with any answers of the callbacks. The proof
assumes one thing of the runner: the task it gives as a task starts has the key of
the task it was given (`QueueEnv.KeepsKey`).

The other properties of the queue (a task starts after the tasks it comes after, a
claim capacity is not passed, each task finishes once, no slot idles) are stated
in the code's documentation and are not proved yet. The tests below hold the code
to the description, on which they would be proved.

`Contraagent/Routing/Router/Breaker.lean` proves, of the breaker, that a 429 changes
nothing when it comes from a launch on the primary that is no probe
(`rateLimited_no_probe`) or from a hop that is neither the primary nor the hop in
force (`rateLimited_other_hop`); that after the task picked as the probe, every
task is picked the hop in force until the cool-off has passed again
(`pick_after_probe`); and that an exhausted chain stays exhausted.

`Contraagent/Execution/Run/Skip.lean` proves, of a resume, that a task is skipped
only when its key's last row is ok and not `partial`, holds the fingerprint the task
is judged by, the task does not rerun on resume and its output reads
(`resumeSkip_sound`); and that the history of a file that tasks fill in is that
file's own: the rows of tasks that fill in another file change nothing in it
(`leftDigests_own_file`). The digest of a fingerprint is asked of the surroundings,
so the first says "the same fingerprint", and what that means for the task's work
rests on SHA-256.

## How it is checked against the code

`tests/test_lean.py` and `tests/test_lean_scenarios.py` run with the other tests of
the Python package:

- Each Lean file is named after a module that exists, and the Lean imports follow
  the layers of `_internal`.
- The names that the specification shares with the code are the same on both
  sides. `lake exe contraagent-lean vocabulary` prints them,
  `tests/lean/vocabulary.json` holds them, and the test compares them with the
  code's: the stop values of `dispatch/task.py`.
- The work queue, the failover breaker and a resume answer what their
  specifications do. A scenario of the breaker is a chain of routes and a list of
  calls of a `Router`, each at a time the scenario gives (`Conformance/Router.lean`,
  `tests/lean/router_scenarios.py`, 100 scenarios in
  `tests/lean/router_scenarios.jsonl`). A scenario of a resume is each key's last
  journal row and the tasks the resume is asked about (`Conformance/Run.lean`,
  `tests/lean/resume_scenarios.py`, 80 scenarios in
  `tests/lean/resume_scenarios.jsonl`). A scenario of the queue scripts
  everything a queue does not decide: how each attempt ends and how long it takes,
  what a resume skips, what the runner defers, what a result's follow-up queues and
  what is cancelled, on a clock that only the scenario moves.
  `lake exe contraagent-lean queue` plays scenarios on the specification
  (`Conformance/Queue.lean`), and `tests/lean/queue_scenarios.py` plays the same
  ones on `WorkQueue`. `tests/lean/queue_scenarios.jsonl` holds 150 scenarios with
  what the specification reports for each, and `tests/test_lean_scenarios.py` plays
  them on the code: the two lists of events must be equal.

The `lean` job of `.github/workflows/ci.yml` builds the package, with every proof.
It fails when a committed file is not what the specification gives now. It also
plays 400 scenarios of each kind, made for that run, on both sides
(`uv run pytest -m lean`).

A scenario's tasks never wait for each other: where `after` has a cycle, the
queue's bottom level depends on the order in which the code meets the tasks, and
the specification's does not.
