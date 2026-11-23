import Lean.Data.Json
import Contraagent.Hub.Core

/-!
# Scenarios of a prune

A scenario is what a hub holds (runs, transcripts, heartbeats, blobs and the runs it
remembers it pruned), a time, how old a run and a blob must be, and whether the prune is a
dry run. `runScenario` plays `Holdings.prune` on it and returns the report and what the hub
holds after. `tests/lean/prune_scenarios.py` fills a `Hub` in memory with the same and
calls `Hub.prune`.
-/

namespace Conformance.Core

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioRun where
  name : String
  runUid : String
  recordsAt : Option Int
  finished : Bool
  files : List String
  logs : List (String × Nat)
  deriving FromJson

structure ScenarioTranscripts where
  name : String
  runUid : String
  activity : Option Int
  logs : List (String × Nat)
  deriving FromJson

structure ScenarioHeartbeat where
  host : String
  receivedAt : Int
  ttl : Int
  alive : List String
  deriving FromJson

structure ScenarioBlob where
  sha : String
  modified : Int
  size : Nat
  deriving FromJson

structure ScenarioPruned where
  runUid : String
  logs : List (String × Nat)
  deriving FromJson

/-- Each list is in the order its store lists it. `pruned`: the runs the hub remembers it
pruned, by name. -/
structure Scenario where
  now : Int
  olderThan : Int
  blobGrace : Int
  dryRun : Bool
  runs : List ScenarioRun
  transcripts : List ScenarioTranscripts
  heartbeats : List ScenarioHeartbeat
  blobs : List ScenarioBlob
  pruned : List (String × ScenarioPruned)
  deriving FromJson

def Scenario.holdings (sc : Scenario) : Holdings :=
  { runs := sc.runs.map fun r =>
      { name := r.name, runUid := r.runUid, recordsAt := r.recordsAt, finished := r.finished, files := r.files,
        logs := r.logs },
    transcripts := sc.transcripts.map fun t =>
      { name := t.name, runUid := t.runUid, activity := t.activity, logs := t.logs },
    heartbeats := sc.heartbeats.map fun h => { host := h.host, receivedAt := h.receivedAt, ttl := h.ttl, alive := h.alive },
    blobs := sc.blobs.map fun b => { sha := b.sha, modified := b.modified, size := b.size },
    pruned := sc.pruned.map fun entry => (entry.1, { runUid := entry.2.runUid, logs := entry.2.logs }) }

def names (items : List String) : Json :=
  Json.arr (items.map fun (name : String) => (name : Json)).toArray

def pairs (items : List (String × String)) : Json :=
  Json.arr (items.map fun pair => Json.arr #[(pair.1 : Json), (pair.2 : Json)]).toArray

def counts (items : List (String × Nat)) : Json :=
  Json.arr ((items.mergeSort fun a b => decide (a.1 ≤ b.1)).map fun pair => Json.arr #[(pair.1 : Json), (pair.2 : Json)]).toArray

/-- Play a scenario from its JSON: the report, and what the hub holds after the prune. The
runs it remembers it pruned are given by name, each log's lines by the log's name. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let (after, report) := sc.holdings.prune sc.now sc.olderThan sc.blobGrace sc.dryRun
    let remembered := after.pruned.mergeSort fun a b => decide (a.1 ≤ b.1)
    Json.mkObj
      [("runs", names report.runs), ("transcripts", pairs report.transcripts), ("blobs", names report.blobs),
        ("blobBytes", report.blobBytes), ("heartbeats", names report.heartbeats), ("keptRuns", pairs report.keptRuns),
        ("keptHeartbeats", pairs report.keptHeartbeats),
        ("heldRuns", pairs (after.runs.map fun run => (run.name, run.runUid))),
        ("heldTranscripts", pairs (after.transcripts.map fun held => (held.name, held.runUid))),
        ("heldHeartbeats", names (after.heartbeats.map (·.host))), ("heldBlobs", names (after.blobs.map (·.sha))),
        ("pruned", Json.arr (remembered.map fun entry =>
          Json.arr #[(entry.1 : Json), (entry.2.runUid : Json), counts entry.2.logs]).toArray)]

/-! ## The blobs, while a prune runs beside the relays -/

/-- One step. `op`: `has` and `put` (a relay asks for the blob `blob`, or stores it, at
`now`), `ref` (a file ref of `blob` arrives), `reset` (the run's file refs go), or `prune`
(at `now`; `during`: the steps of relays after the prune read the file refs and before it
removes a blob). -/
structure BlobStep where
  op : String
  now : Int
  blob : String
  deriving FromJson

structure BlobPrune where
  op : String
  now : Int
  blob : String
  during : List BlobStep
  deriving FromJson

structure BlobScenario where
  grace : Int
  steps : List BlobPrune
  deriving FromJson

/-- Play a step of a relay: the state after it, and what it answers. -/
def relayStep (s : BlobsState) (step : BlobStep) : BlobsState × Json :=
  match step.op with
  | "has" =>
    let (s, held) := s.hasBlob step.now step.blob
    (s, held)
  | "put" => (s.putBlob step.now step.blob, Json.null)
  | "ref" => (s.fileRef step.blob, Json.null)
  | "reset" => (s.refs.foldl BlobsState.forget s, Json.null)
  | _ => (s, "unknown step")

def relaySteps (s : BlobsState) (steps : List BlobStep) (answers : Array Json) : BlobsState × Array Json :=
  steps.foldl (fun (acc : BlobsState × Array Json) step =>
    let (s, answer) := relayStep acc.1 step
    (s, acc.2.push answer)) (s, answers)

/-- Play a prune: it marks, the relays' steps come, and it removes each blob it marked that
is still old, in the order of their names. With the blobs it removed. -/
def pruneStep (grace : Int) (s : BlobsState) (step : BlobPrune) (answers : Array Json) : BlobsState × Array Json :=
  let old := step.now - grace
  let s := s.mark old
  let marked := s.marked.mergeSort fun a b => decide (a ≤ b)
  let (s, answers) := relaySteps s step.during answers
  let (s, removed) := marked.foldl (fun (acc : BlobsState × List String) sha =>
    let (s, gone) := acc.1.expire old sha
    (s, if gone then acc.2 ++ [sha] else acc.2)) (s, [])
  (s, answers.push (names removed))

/-- Play a scenario from its JSON: what each step answers (a prune after the steps during
it), then the blobs held with their dates and the blobs that file refs name, each once, each
list in the order of the names. -/
def runBlobs (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String BlobScenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let (s, answers) := sc.steps.foldl (fun (acc : BlobsState × Array Json) step =>
      if step.op == "prune" then pruneStep sc.grace acc.1 step acc.2
      else
        let (s, answer) := relayStep acc.1 { op := step.op, now := step.now, blob := step.blob }
        (s, acc.2.push answer)) ({}, #[])
    let held := s.blobs.mergeSort fun a b => decide (a.1 ≤ b.1)
    Json.mkObj
      [("answers", Json.arr answers),
        ("blobs", Json.arr (held.map fun blob => Json.arr #[(blob.1 : Json), (blob.2 : Json)]).toArray),
        ("refs", names (s.refs.eraseDups.mergeSort fun a b => decide (a ≤ b)))]

end Conformance.Core
