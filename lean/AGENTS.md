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
```

`uv run pytest tests/test_lean.py` needs no Lean. It checks the names of the files,
their imports and the shared names.

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
- `Main.lean` is the executable `contraagent-lean`. No file imports it.
- `lakefile.toml` builds every file under `Contraagent/`, so no file needs to be
  listed anywhere.

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
- No proof is left open, and no axiom is added: no `sorry`, no `axiom`, no
  `native_decide`. What the specification assumes of its surroundings (a runner, a
  clock, a digest that does not collide) is a hypothesis of each theorem that needs
  it.
- The package depends on Lean's core library and `Std` only.

## Changing a described module

A pull request that changes what a described module decides changes its Lean file
too. After changing a name that both sides share, rewrite the committed file:

```
lake exe contraagent-lean vocabulary > ../tests/lean/vocabulary.json
```
