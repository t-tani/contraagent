import Lean.Data.Json
import Contraagent.Hub.Segments

/-!
# Scenarios of the hub's logs

A scenario is when a segment is sealed and a list of steps on some logs: appends, closes,
ticks, reads, `sweep`, `drop`, and starts of the hub on what the last process left. A step
may name a seal that fails or at which the process dies; after a step in which the process
dies, the hub starts again. `runScenario` plays it on the specification and returns what
each step answers, then what survives: the index rows, the objects and the files.
`tests/lean/hub_scenarios.py` plays the same scenario on `SegmentedStreamLogs`.
-/

namespace Conformance.Segments

open Lean (FromJson ToJson Json)
open Contraagent

/-- A seal that goes wrong: of the segment of the log `key` that starts at `first`, or of
each of its segments when `first` is none. `how`: `failPut`, `failAdd`, `crashAfterPut` or
`crashAfterAdd`. -/
structure FaultScript where
  key : List String
  first : Option Nat
  how : String
  deriving FromJson

/-- One step. `op`: `append` (with `key`, `offset`, `lines`), `close`, `tick`, `restart`
(with `loseIndex`: the index lost its rows), `read` (with `since`, `limit`), `held`,
`sweep` or `drop` (of the run of `key`). `key`: a run's name, its uid and a log. -/
structure Step where
  op : String
  now : Int
  key : List String
  offset : Nat
  lines : List String
  since : Nat
  limit : Option Nat
  loseIndex : Bool
  fault : Option FaultScript
  deriving FromJson

structure Scenario where
  segmentBytes : Nat
  idleS : Int
  ageS : Int
  steps : List Step
  deriving FromJson

def logKey (parts : List String) : LogKey :=
  match parts with
  | [name, uid, log] => (name, uid, log)
  | _ => ("", "", "")

def fault (script : Option FaultScript) : Option Fault :=
  script.bind fun f =>
    (match f.how with
    | "failPut" => some SealFault.failPut
    | "failAdd" => some SealFault.failAdd
    | "crashAfterPut" => some SealFault.crashAfterPut
    | "crashAfterAdd" => some SealFault.crashAfterAdd
    | _ => none).map fun how => { key := logKey f.key, first := f.first, how := how }

/-- A segment as the objects store names it, with how many lines it holds. -/
def named (key : LogKey) (first count : Nat) : String :=
  s!"{key.1}/{key.2.1}/{key.2.2}/{first}:{count}"

def sorted (names : List String) : Json :=
  Json.arr ((names.mergeSort fun a b => decide (a ≤ b)).map fun (name : String) => (name : Json)).toArray

/-- The objects a call deleted, as their keys. -/
def keys (deleted : List (LogKey × Nat)) : Json :=
  sorted (deleted.map fun (key, first) => s!"{key.1}/{key.2.1}/{key.2.2}/{first}.seg")

/-- What survives a crash: the index rows, the objects and the files, each with its lines. -/
def kept (k : Kept) : Json :=
  Json.mkObj [("rows", sorted (k.rows.map fun r => named r.key r.first r.count)),
    ("objects", sorted (k.objects.map fun o => named o.key o.first o.lines.length)),
    ("files", sorted (k.files.map fun f => named f.key f.first f.lines.length))]

/-- The hub after a step in which the process may have died: it starts again then. -/
def after (now : Int) (s : HubState) (crashed : Bool) : HubState :=
  if crashed then (HubState.recover now none s.kept).1 else s

/-- Play one step: the hub after it, and what the step answers. -/
def step (cfg : HubConfig) (s : HubState) (st : Step) : HubState × Json :=
  let key := logKey st.key
  match st.op with
  | "append" =>
    let (s, held, crashed) := cfg.append st.now (fault st.fault) s key st.offset st.lines
    -- A call in which the process died answers nothing.
    (after st.now s crashed,
      Json.mkObj [("held", if crashed then Json.null else Json.arr #[held.1, held.2]), ("crashed", crashed)])
  | "close" =>
    let (s, crashed) := HubConfig.close (fault st.fault) s key
    (after st.now s crashed, Json.mkObj [("crashed", crashed)])
  | "tick" =>
    let (s, crashed) := cfg.tick st.now (fault st.fault) s
    (after st.now s crashed, Json.mkObj [("crashed", crashed)])
  | "restart" =>
    let left : Kept := if st.loseIndex then { s.kept with rows := [] } else s.kept
    let (s, crashed) := HubState.recover st.now (fault st.fault) left
    (after st.now s crashed, Json.mkObj [("crashed", crashed)])
  | "read" =>
    let (s, lines, total) := s.read key st.since st.limit
    (s, Json.mkObj [("lines", Json.arr (lines.map fun (line : String) => (line : Json)).toArray), ("total", total)])
  | "held" =>
    let (s, held) := s.held key
    (s, Json.arr #[held.1, held.2])
  | "sweep" =>
    let (s, deleted) := s.sweep
    (s, keys deleted)
  | "drop" =>
    let (s, deleted) := s.drop key.1 key.2.1
    (s, keys deleted)
  | _ => (s, "unknown step")

/-- Play a scenario from its JSON: what each step answers, and what survives after the
last. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let cfg : HubConfig := { segmentBytes := sc.segmentBytes, idleS := sc.idleS, ageS := sc.ageS }
    let (s, answers) := sc.steps.foldl
      (fun (acc : HubState × Array Json) st =>
        let (s, answer) := step cfg acc.1 st
        (s, acc.2.push answer))
      ({}, #[])
    Json.mkObj [("answers", Json.arr answers), ("kept", kept s.kept)]

end Conformance.Segments
