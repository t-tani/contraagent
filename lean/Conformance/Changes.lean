import Lean.Data.Json
import Contraagent.Execution.Changes

/-!
# Scenarios of the changes patterns

A scenario is two tasks' `changes` patterns and the real path of each task's working
directory. `runScenario` plays it on the specification and returns the pair of patterns that
may cover one file when both are read from one directory (`mayOverlap`), and when each is
read from its own (`overlap`). `tests/lean/changes_scenarios.py` plays the same scenario on
`may_overlap` and `overlap`.
-/

namespace Conformance.Changes

open Lean (FromJson ToJson Json)
open Contraagent

structure Scenario where
  a : List String
  b : List String
  dirA : String
  dirB : String
  deriving FromJson

def pairJson : Option (String × String) → Json
  | some (pa, pb) => Json.arr #[pa, pb]
  | none => Json.null

/-- Play a scenario from its JSON: what `mayOverlap` and `overlap` answer. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    Json.mkObj
      [("mayOverlap", pairJson (mayOverlap sc.a sc.b)),
       ("overlap", pairJson (overlap sc.dirA sc.a sc.dirB sc.b))]

end Conformance.Changes
