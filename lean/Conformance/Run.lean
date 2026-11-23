import Lean.Data.Json
import Contraagent.Execution.Run
import Contraagent.Execution.Journal

/-!
# Scenarios of a resume

A scenario is the rows of a journal, the tasks a resume is asked about, in order, and
the keys whose output no longer reads. `runScenario` plays it on the specification and
returns whether each task is skipped, and why each task that an earlier attempt finished
runs again, in the words of the code. `tests/lean/resume_scenarios.py` plays the same
scenario on `resume_skip`.
-/

namespace Conformance.Run

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioRow where
  key : String
  ok : Bool
  stop : String
  fingerprint : String
  fingerprintParts : List (String × String)
  outside : String
  outputOfAfter : String
  outputOfFile : String
  deriving FromJson

/-- `spliced`: the fingerprint of the task with the row's digest of the file it fills in,
in place of its own (`fingerprint_of`, which the code works out); `none` when there is no
such digest. `hasOrigin`: whether a flow created it. -/
structure ScenarioTask where
  key : String
  kind : String
  unit : String
  fingerprint : String
  fingerprintParts : List (String × String)
  outside : String
  rerunOnResume : Bool
  fingerprintAtStart : Bool
  hasOrigin : Bool
  givenFrom : List String
  createdFrom : List String
  spliced : Option String
  deriving FromJson

structure Scenario where
  rows : List ScenarioRow
  tasks : List ScenarioTask
  unread : List String
  deriving FromJson

def toRow (r : ScenarioRow) : JournalRow :=
  { key := r.key, ok := r.ok, stop := r.stop, fingerprint := r.fingerprint,
    fingerprintParts := r.fingerprintParts, outside := r.outside, outputOfAfter := r.outputOfAfter,
    outputOfFile := r.outputOfFile }

def toTask (t : ScenarioTask) : Task :=
  { kind := t.kind, unit := t.unit, id := t.key, key := t.key, fingerprint := t.fingerprint,
    fingerprintParts := t.fingerprintParts, outside := t.outside, rerunOnResume := t.rerunOnResume,
    fingerprintAtStart := t.fingerprintAtStart,
    origin := if t.hasOrigin then some { givenFrom := t.givenFrom, createdFrom := t.createdFrom } else none }

/-- A part of a fingerprint as a reason names it (`_part_name`). -/
def partName : String → String
  | "definition" => "its definition"
  | "params" => "its params"
  | "input_files" => "its input files"
  | "outside" => "its outside state"
  | "output_of" => "the file it fills in (output_of)"
  | other => other

/-- A reason in the words of the code. -/
def reasonText : RerunReason → String
  | .unread => "its output no longer reads under its output schema"
  | .refill => "the file it fills in (output_of) is not as the earlier attempts left it"
  | .rerunOnResume => "its kind is declared rerun_on_resume"
  | .lastPartial => "its last result was partial"
  | .outsideChanged => "its outside state changed"
  | .outsideUnknown => "its outside state could not be worked out"
  | .changedUnnamed => "its fingerprint changed: its params or its definition"
  | .kindOrUnit => "its fingerprint changed: its kind or its unit"
  | .divergence parts =>
    "divergence: the flow gave it other params for the same outputs, every task it was given "
      ++ "or created from skipped (a clock, randomness, outside state or changed flow code); changed: "
      ++ ", ".intercalate (parts.map partName)
  | .changed parts => "its fingerprint changed: " ++ ", ".intercalate (parts.map partName)

/-- Play a scenario from its JSON: whether each task is skipped, and the reasons by key. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let env : ResumeEnv :=
      { fingerprintOf := fun _ _ key _ =>
          (((sc.tasks.find? (·.key == key)).bind (·.spliced))).getD "",
        reads := fun task => ! sc.unread.contains task.key }
    let rows := lastRows (sc.rows.map toRow)
    let (state, skips) := sc.tasks.foldl
      (fun (acc : ResumeState × Array Json) t =>
        let (s, skip) := resumeSkip env rows acc.1 (toTask t)
        (s, acc.2.push skip))
      ({}, #[])
    let reruns := (state.reruns.mergeSort fun a b => a.1 ≤ b.1).map fun pair =>
      Json.arr #[pair.1, reasonText pair.2]
    Json.mkObj [("skips", Json.arr skips), ("reruns", Json.arr reruns.toArray)]

end Conformance.Run
