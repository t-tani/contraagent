import Lean.Data.Json
import Contraagent.Hub.Core

/-!
# Scenarios of the relay's shipping of a run

A scenario is one run's logs and a list of steps: lines added to a log, a pass of the
relay at a time, a hub that loses lines of a log or everything, and a hub whose retention
removes the run. The hub of a scenario keeps every line once, in order (`hubTakes`), and
remembers a run it pruned (`PrunedRun.records`). `runScenario` plays it on the
specification and returns the requests of each pass, then the relay's progress and the
lines the hub holds. `tests/lean/relay_scenarios.py` plays the same scenario on `Relay`
and `Hub`.
-/

namespace Conformance.Relay

open Lean (FromJson ToJson Json)
open Contraagent

/-- One step. `op`: `grow` (with `log`, `lines`), `pass` (with `now`), `lose` (the hub
keeps `keep` lines of `log`), `forget` (the hub holds nothing of the run and remembers
nothing), `prune` (the hub's retention removes the run, when it holds it), `reset` (the
relay starts again without its progress) or `renew` (the run directory holds a new run: a
new run uid over the same logs). -/
structure Step where
  op : String
  now : Int
  log : String
  lines : List String
  keep : Nat
  deriving FromJson

/-- `logs`: the run's logs, in the order the source lists them. -/
structure Scenario where
  logs : List String
  batchLines : Nat
  resyncS : Int
  steps : List Step
  deriving FromJson

/-- The hub of a scenario: the lines it holds of each log it was sent, and the run it
pruned. -/
structure Hub where
  uid : Nat := 0
  logs : List (String × List String) := []
  pruned : Option PrunedRun := none

/-- The uid of the run a scenario's directory holds after `renewed` new runs. -/
def runUid (renewed : Nat) : String := s!"u{renewed}"

/-- The hub after it stores a request, and how many lines of each log the request names it
holds. -/
def stores (hub : Hub) (request : RelayRequest) : Hub × List (String × Nat) :=
  request.chunks.foldl
    (fun (acc : Hub × List (String × Nat)) chunk =>
      let lines := hubTakes ((acc.1.logs.lookup chunk.log).getD []) chunk
      ({ acc.1 with logs := (chunk.log, lines) :: acc.1.logs.filter (·.1 != chunk.log) },
        acc.2 ++ [(chunk.log, lines.length)]))
    (hub, [])

/-- The hub after a request of the run `uid`, and its answer: for a run it pruned, the
answer alone, unless the run grew. A run of another uid takes the place of the one held. -/
def answer (uid : Nat) (hub : Hub) (request : RelayRequest) : Hub × List (String × Nat) :=
  match hub.pruned.bind fun pruned => pruned.records (runUid uid) request.chunks with
  | some held => (hub, held)
  | none => stores { uid := uid, logs := if hub.uid == uid then hub.logs else [], pruned := none } request

structure Played where
  files : List (String × List String)
  uid : Nat := 0
  hub : Hub := {}
  progress : Option RunProgress := none
  /-- The run uid the relay's progress is of. -/
  progressUid : Nat := 0
  nextResync : Int := 0
  answers : Array Json := #[]

def request (r : RelayRequest) : Json :=
  Json.mkObj [("documents", r.documents),
    ("chunks", Json.arr (r.chunks.map fun c => Json.arr #[c.log, c.offset, c.lines.length]).toArray)]

def step (sc : Scenario) (p : Played) (st : Step) : Played :=
  match st.op with
  | "grow" =>
    { p with
      files := p.files.map fun (log, lines) => if log == st.log then (log, lines ++ st.lines) else (log, lines)
      answers := p.answers.push Json.null }
  | "lose" =>
    { p with
      hub := { p.hub with
        logs := p.hub.logs.map fun (log, lines) => if log == st.log then (log, lines.take st.keep) else (log, lines) }
      answers := p.answers.push Json.null }
  | "forget" => { p with hub := {}, answers := p.answers.push Json.null }
  | "prune" =>
    { p with
      hub := if p.hub.logs.isEmpty then p.hub
        else { uid := p.hub.uid, logs := [],
               pruned := some { runUid := runUid p.hub.uid, logs := p.hub.logs.map fun (log, lines) => (log, lines.length) } }
      answers := p.answers.push Json.null }
  | "reset" => { p with progress := none, nextResync := 0, answers := p.answers.push Json.null }
  | "renew" => { p with uid := p.uid + 1, answers := p.answers.push Json.null }
  | _ =>
    let resync := decide (st.now ≥ p.nextResync)
    -- Progress of another run uid is none: the directory holds a new run.
    let known := if p.progressUid == p.uid then p.progress else none
    -- A run the relay never shipped has nothing to ask about.
    let walk : ShipWalk := { probe := resync && known.isSome }
    let fuel := 2 * (p.files.map fun entry => entry.2.length).sum + 4 * p.files.length + 8
    let (hub, progress, sent) :=
      ship sc.batchLines { logs := p.files, documents := true } (answer p.uid) fuel walk p.hub (known.getD {}) []
    { p with
      hub := hub
      -- The relay holds a run's progress once the hub took a request of it.
      progress := if sent.isEmpty then p.progress else some progress
      progressUid := if sent.isEmpty then p.progressUid else p.uid
      nextResync := if resync then st.now + sc.resyncS else p.nextResync
      answers := p.answers.push (Json.arr (sent.map request).toArray) }

/-- Play a scenario from its JSON: the requests of each pass, then the relay's progress
and how many lines of each log the hub holds. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let p := sc.steps.foldl (step sc) { files := sc.logs.map fun log => (log, []) }
    let lengths := fun (table : List (String × Nat)) =>
      Json.mkObj (sc.logs.filterMap fun log => (table.lookup log).map fun n => (log, (n : Json)))
    Json.mkObj [("answers", Json.arr p.answers),
      ("progress", lengths ((p.progress.map (·.logs)).getD [])),
      ("hub", lengths (p.hub.logs.map fun (log, lines) => (log, lines.length)))]

end Conformance.Relay
