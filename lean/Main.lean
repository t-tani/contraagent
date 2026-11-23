import Lean.Data.Json
import Contraagent.Dispatch.Task

/-!
# `lake exe contraagent-lean`

What the tests of the Python package read of the specification.
-/

/-- The names the specification shares with the code, as `tests/lean/vocabulary.json` holds
them. -/
def vocabulary : Lean.Json :=
  Lean.Json.mkObj [("stops", Lean.toJson Contraagent.Stop.named)]

def main (args : List String) : IO UInt32 := do
  match args with
  | ["vocabulary"] =>
    IO.println vocabulary.pretty
    return 0
  | _ =>
    IO.eprintln "usage: lake exe contraagent-lean vocabulary"
    return 2
