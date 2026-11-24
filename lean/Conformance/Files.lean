import Lean.Data.Json
import Contraagent.Runs.Files

/-!
# Scenarios of a run's log

A scenario is a list of appends to one log, each with its rows and, when its write is cut,
how many of its bytes reach the file. `runScenario` plays them on the specification and
returns the complete lines of the log and the line with no end.
`tests/lean/logs_scenarios.py` plays the same appends on a file with `append_lines`, where
a cut write fails as on a full disk, and reads the file.
-/

namespace Conformance.Files

open Lean (FromJson ToJson Json)
open Contraagent

/-- One append. `written`: how many bytes of it reach the file; `none`: all of them. -/
structure Step where
  rows : List String
  written : Option Nat
  deriving FromJson

structure Scenario where
  steps : List Step
  deriving FromJson

def text (line : Line) : String :=
  String.ofList (line.map fun byte => Char.ofNat byte.toNat)

/-- Play a scenario from its JSON: the complete lines of the log, and the line with no end.
The rows are ASCII. -/
def runScenario (input : String) : Json :=
  match Json.parse input >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let log := sc.steps.foldl (fun (log : Log) step =>
      let rows := step.rows.map fun row => row.toUTF8.toList
      log.append rows (step.written.getD (log.data rows).length)) {}
    Json.mkObj
      [("lines", Json.arr (log.read.map fun line => (text line : Json)).toArray), ("tail", text log.tail)]

end Conformance.Files
