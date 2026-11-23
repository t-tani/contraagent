# contraagent lean

The Lean specification of contraagent, a Lake package: definitions that describe
what modules of the Python package do, and theorems about them. `README.md` lists
the modules it describes and how it is checked against them. The root `AGENTS.md`
applies here too.

## Commands

[elan](https://github.com/leanprover/elan) installs the Lean that `lean-toolchain`
names. Run these in `lean/`:

```
lake build --wfail                     # every file and every proof; a warning fails it, so a `sorry` does
lake exe contraagent-lean vocabulary   # the names shared with the code, as tests/lean/vocabulary.json holds them
lake exe contraagent-lean queue        # plays the scenarios of the work queue given on its input, one JSON line each
```

Run these at the repository's root:

```
uv run pytest tests/test_lean.py tests/test_lean_queue.py   # needs no Lean: the files' names, the shared names, the committed scenarios
uv run pytest -m lean -n0                                    # needs Lean: the committed files are current, and fresh scenarios agree
uv run python tests/lean/queue_scenarios.py                  # rewrites tests/lean/queue_scenarios.jsonl
```

## Files

- `Contraagent/<Layer>/<Module>.lean` describes
  `src/contraagent/_internal/<layer>/<module>.py`, under the module's name in Lean's
  case (`resume_from.py` is `ResumeFrom.lean`). It holds definitions, and its first
  comment names the module and says what it leaves out.
- The theorems about a description are in files below
  `Contraagent/<Layer>/<Module>/`.
- A file imports only files of its own layer and of the layers that `_internal` lets
  that layer import.
- Every declaration is in the namespace `Contraagent`.
- `Conformance/<Module>.lean` plays scenarios on the description of that module:
  it reads a scenario from JSON and prints what the description reports. Only this
  library and `Main.lean` import Lean's JSON; the specification imports neither.
- `Main.lean` is the executable `contraagent-lean`. No file imports it.
- `lakefile.toml` builds every file under `Contraagent/` and `Conformance/`, so no
  file needs to be listed anywhere.

A module is described when it decides which work runs, when, or whether it runs
again: the schedulers, the task graph, resume, failover, capacity, and the hub's
copies of a log. A module that reads an agent's output, checks a file against a
schema, counts tokens or draws the monitor is not described.

## Names

A name is the code's name in Lean's case: `TaskResult`, `deadlineAt` for
`deadline_at`, `Stop.deferred` for `STOP_DEFERRED`. A word of the glossary
(`src/contraagent/docs/concepts.md`) keeps its meaning here. "Contract" and "model"
are words of the glossary, so they name nothing of the specification itself.

## Definitions and proofs

- A structure holds the fields that the described module decides by, each under the
  type that matches the code's: a string for a string, a list for a tuple, `Option`
  for a value that may be `None`.
- A time or a length of time is an integer (`Time`, `Duration`). The unit is left
  open.
- A definition that says what the code computes is a function that runs. No
  definition is `noncomputable`.
- A function is one method of the code. What the method reads from outside is an
  argument: the clock's reading, and the answers of the callbacks as a record of
  functions. A loop of the code that has no bound takes the number of its rounds
  as an argument.
- What the code reports is part of the state the function returns, so a theorem can
  speak about everything that was reported.
- No proof is left open, and no axiom is added: no `sorry`, no `axiom`, no
  `native_decide`. What the specification assumes of its surroundings (a runner, a
  clock, a digest that does not collide) is a hypothesis of each theorem that needs
  it.
- The package depends on Lean's core library and `Std` only.

## Changing a described module

A pull request that changes what a described module decides changes its Lean file
too: the committed scenarios fail on the code until both agree. Decide which of the
two is right before changing either, and do not make the player of a scenario, on
either side, hide a difference.

After changing a name that both sides share, the description of the queue, or the
scenarios' generator, rewrite the committed files:

```
lake exe contraagent-lean vocabulary > ../tests/lean/vocabulary.json   # in lean/
uv run python tests/lean/queue_scenarios.py                            # at the root
```
