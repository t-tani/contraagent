import Lean.Data.Json
import Contraagent.Dispatch.Task
import Contraagent.Backends.Launch
import Conformance.Queue
import Conformance.Router
import Conformance.Run
import Conformance.Graph
import Conformance.Capacity
import Conformance.Pool
import Conformance.Services
import Conformance.Runner
import Conformance.Quota
import Conformance.Segments
import Conformance.Relay
import Conformance.Flow

/-!
# `lake exe contraagent-lean`

What the tests of the Python package read of the specification.
-/

/-- The names the specification shares with the code, as `tests/lean/vocabulary.json` holds
them. -/
def vocabulary : Lean.Json :=
  Lean.Json.mkObj
    [("stops", Lean.toJson Contraagent.Stop.named), ("launchStops", Lean.toJson Contraagent.launchStops)]

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
  | ["graph"] =>
    playScenarios Conformance.Graph.runScenario (← IO.getStdin)
    return 0
  | ["capacity"] =>
    playScenarios Conformance.Capacity.runScenario (← IO.getStdin)
    return 0
  | ["pool"] =>
    playScenarios Conformance.Pool.runScenario (← IO.getStdin)
    return 0
  | ["services"] =>
    playScenarios Conformance.Services.runScenario (← IO.getStdin)
    return 0
  | ["attempt"] =>
    playScenarios Conformance.Runner.runScenario (← IO.getStdin)
    return 0
  | ["rests"] =>
    playScenarios Conformance.Quota.runScenario (← IO.getStdin)
    return 0
  | ["hub"] =>
    playScenarios Conformance.Segments.runScenario (← IO.getStdin)
    return 0
  | ["relay"] =>
    playScenarios Conformance.Relay.runScenario (← IO.getStdin)
    return 0
  | ["flow"] =>
    playScenarios Conformance.Flow.runScenario (← IO.getStdin)
    return 0
  | _ =>
    IO.eprintln "usage: lake exe contraagent-lean vocabulary | (queue | router | resume | graph | capacity | pool | services | attempt | rests | hub | relay | flow) < scenarios.jsonl"
    return 2
