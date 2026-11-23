import Lean.Data.Json
import Contraagent.Hub.Relay

/-!
# Scenarios of the relay's shipping of a run

A scenario is one run's logs and a list of steps: lines added to a log, a pass of the
relay at a time, and a hub that loses lines of a log. The hub of a scenario keeps every
line once, in order (`hubTakes`). `runScenario` plays it on the specification and returns
the requests of each pass, then the relay's progress and the lines the hub holds.
`tests/lean/relay_scenarios.py` plays the same scenario on `Relay` with a hub of its own.
-/

namespace Conformance.Relay

open Lean (FromJson ToJson Json)
open Contraagent

/-- One step. `op`: `grow` (with `log`, `lines`), `pass` (with `now`), `lose` (the hub
keeps `keep` lines of `log`) or `forget` (the hub holds nothing of the run). -/
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

/-- The hub of a scenario: the lines it holds of each log it was sent. -/
abbrev Hub := List (String × List String)

/-- The hub after a request, and how many lines of each log the request names it holds. -/
def answer (hub : Hub) (request : RelayRequest) : Hub × List (String × Nat) :=
  request.chunks.foldl
    (fun (acc : Hub × List (String × Nat)) chunk =>
      let lines := hubTakes ((acc.1.lookup chunk.log).getD []) chunk
      ((chunk.log, lines) :: acc.1.filter (·.1 != chunk.log), acc.2 ++ [(chunk.log, lines.length)]))
    (hub, [])

structure Played where
  files : List (String × List String)
  hub : Hub := []
  progress : Option RunProgress := none
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
      hub := p.hub.map fun (log, lines) => if log == st.log then (log, lines.take st.keep) else (log, lines)
      answers := p.answers.push Json.null }
  | "forget" => { p with hub := [], answers := p.answers.push Json.null }
  | _ =>
    let resync := decide (st.now ≥ p.nextResync)
    -- A run the relay never shipped has nothing to ask about.
    let walk : ShipWalk := { probe := resync && p.progress.isSome }
    let fuel := 2 * (p.files.map fun entry => entry.2.length).sum + 4 * p.files.length + 8
    let (hub, progress, sent) :=
      ship sc.batchLines { logs := p.files, documents := true } answer fuel walk p.hub (p.progress.getD {}) []
    { p with
      hub := hub
      -- The relay holds a run's progress once the hub took a request of it.
      progress := if sent.isEmpty then p.progress else some progress
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
      ("hub", lengths (p.hub.map fun (log, lines) => (log, lines.length)))]

end Conformance.Relay
