import Lean.Data.Json
import Contraagent.Runs.Files

/-!
# Scenarios of a run's log

A scenario is a list of appends to one log, each with its rows and, when its write is cut,
how many of its bytes reach the file, and how a reader then finds the log: as it is, gone,
or a file it cannot read. `runScenario` plays them on the specification and returns the
complete lines of the log and the line with no end, and what a reader that rests on the
log reads of it as found: its rows, the numbers of its lines that are no row, and whether
its last line has no end, or nothing when it cannot be read.
`tests/lean/logs_scenarios.py` plays the same appends on a file with `append_lines`, where
a cut write fails as on a full disk, and reads the file with `read_lines` and `read_log`.
-/

namespace Conformance.Files

open Lean (FromJson ToJson Json)
open Contraagent

/-- One append. `written`: how many bytes of it reach the file; `none`: all of them. -/
structure Step where
  rows : List String
  written : Option Nat
  deriving FromJson

/-- `found`: how a reader finds the log after the appends: `present`, `absent` or
`unreadable`. -/
structure Scenario where
  steps : List Step
  found : String
  deriving FromJson

def text (line : Line) : String :=
  String.ofList (line.map fun byte => Char.ofNat byte.toNat)

/-- Whether a line is a row: a JSON object (`read_log`). -/
def isRow (line : String) : Bool :=
  match Json.parse line with
  | .ok (.obj _) => true
  | _ => false

/-- What `read_log` gives of the log as found: its rows, the numbers from 1 of its lines
that are no row and not blank, and whether its last line has no end; null when it cannot
be read. -/
def readLog (found : Found) : Json :=
  match found.read with
  | none => Json.null
  | some lines =>
    let texts := lines.map text
    let numbered := texts.zipIdx.map fun (line, i) => (line, i + 1)
    let tail := match found with
      | .present log => !log.tail.isEmpty
      | _ => false
    Json.mkObj
      [("rows", Json.arr ((texts.filter isRow).map Json.str).toArray),
       ("unread", Json.arr ((numbered.filter fun (line, _) => !isRow line && !line.all Char.isWhitespace).map
          fun (_, n) => (n : Json)).toArray),
       ("cutShort", tail)]

/-- Play a scenario from its JSON: the complete lines of the log, and the line with no end.
The rows are ASCII. -/
def runScenario (input : String) : Json :=
  match Json.parse input >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let log := sc.steps.foldl (fun (log : Log) step =>
      let rows := step.rows.map fun row => row.toUTF8.toList
      log.append rows (step.written.getD (log.data rows).length)) {}
    let found : Found := match sc.found with
      | "absent" => .absent
      | "unreadable" => .unreadable
      | _ => .present log
    Json.mkObj
      [("lines", Json.arr (log.read.map fun line => (text line : Json)).toArray), ("tail", text log.tail),
       ("read", readLog found)]

end Conformance.Files
