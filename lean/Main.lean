import Lean.Data.Json
import Contraagent.Dispatch.Task
import Conformance.Queue
import Conformance.Router
import Conformance.Run

/-!
# `lake exe contraagent-lean`

What the tests of the Python package read of the specification.
-/

/-- The names the specification shares with the code, as `tests/lean/vocabulary.json` holds
them. -/
def vocabulary : Lean.Json :=
  Lean.Json.mkObj [("stops", Lean.toJson Contraagent.Stop.named)]

/-- Play each line of the standard input, a scenario, and print what the specification
answers, one line for each. -/
partial def playScenarios (play : String → Lean.Json) (input : IO.FS.Stream) : IO Unit := do
  let line ← input.getLine
  if line.isEmpty then return
  if !line.trimAscii.isEmpty then
    IO.println (play line).compress
  playScenarios play input

def main (args : List String) : IO UInt32 := do
  match args with
  | ["vocabulary"] =>
    IO.println vocabulary.pretty
    return 0
  | ["queue"] =>
    playScenarios Conformance.runScenario (← IO.getStdin)
    return 0
  | ["router"] =>
    playScenarios Conformance.Router.runScenario (← IO.getStdin)
    return 0
  | ["resume"] =>
    playScenarios Conformance.Run.runScenario (← IO.getStdin)
    return 0
  | _ =>
    IO.eprintln "usage: lake exe contraagent-lean vocabulary | (queue | router | resume) < scenarios.jsonl"
    return 2
