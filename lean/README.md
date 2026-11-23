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

A description holds the fields that its module decides by. What only travels with
a task or a result is left out, and the first comment of each file says what.

## How it is checked against the code

`tests/test_lean.py` runs with the other tests of the Python package:

- Each Lean file is named after a module that exists, and the Lean imports follow
  the layers of `_internal`.
- The names that the specification shares with the code are the same on both
  sides. `lake exe contraagent-lean vocabulary` prints them,
  `tests/lean/vocabulary.json` holds them, and the test compares them with the
  code's: the stop values of `dispatch/task.py`.

The `lean` job of `.github/workflows/ci.yml` builds the package, with every proof,
and fails when `tests/lean/vocabulary.json` is not what the specification prints.
