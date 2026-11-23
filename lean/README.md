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

A description holds the fields that its module decides by. What only travels with
a task or a result is left out, and the first comment of each file says what.

## How it is checked against the code

`tests/test_lean.py` and `tests/test_lean_queue.py` run with the other tests of the
Python package:

- Each Lean file is named after a module that exists, and the Lean imports follow
  the layers of `_internal`.
- The names that the specification shares with the code are the same on both
  sides. `lake exe contraagent-lean vocabulary` prints them,
  `tests/lean/vocabulary.json` holds them, and the test compares them with the
  code's: the stop values of `dispatch/task.py`.
- The work queue reports what its specification does. A scenario scripts
  everything a queue does not decide: how each attempt ends and how long it takes,
  what a resume skips, what the runner defers, what a result's follow-up queues and
  what is cancelled, on a clock that only the scenario moves.
  `lake exe contraagent-lean queue` plays scenarios on the specification
  (`Conformance/Queue.lean`), and `tests/lean/queue_scenarios.py` plays the same
  ones on `WorkQueue`. `tests/lean/queue_scenarios.jsonl` holds 150 scenarios with
  what the specification reports for each, and the test plays them on the code:
  the two lists of events must be equal.

The `lean` job of `.github/workflows/ci.yml` builds the package, with every proof.
It fails when a committed file is not what the specification gives now. It also
plays 400 scenarios made for that run on both sides (`uv run pytest -m lean`).

A scenario's tasks never wait for each other: where `after` has a cycle, the
queue's bottom level depends on the order in which the code meets the tasks, and
the specification's does not.
