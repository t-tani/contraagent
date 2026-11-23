import Lean.Data.Json
import Contraagent.Dispatch.Task
import Conformance.Queue

/-!
# `lake exe contraagent-lean`

What the tests of the Python package read of the specification.
-/

/-- The names the specification shares with the code, as `tests/lean/vocabulary.json` holds
them. -/
def vocabulary : Lean.Json :=
  Lean.Json.mkObj [("stops", Lean.toJson Contraagent.Stop.named)]

/-- Play each line of the standard input, a scenario of the work queue, and print what the
queue reports, one line for each. -/
partial def playQueueScenarios (input : IO.FS.Stream) : IO Unit := do
  let line ← input.getLine
  if line.isEmpty then return
  if !line.trimAscii.isEmpty then
    IO.println (Conformance.runScenario line).compress
  playQueueScenarios input

def main (args : List String) : IO UInt32 := do
  match args with
  | ["vocabulary"] =>
    IO.println vocabulary.pretty
    return 0
  | ["queue"] =>
    playQueueScenarios (← IO.getStdin)
    return 0
  | _ =>
    IO.eprintln "usage: lake exe contraagent-lean vocabulary | queue < scenarios.jsonl"
    return 2
