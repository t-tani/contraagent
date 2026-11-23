import Lean.Data.Json
import Contraagent.Routing.Quota

/-!
# Scenarios of the credential rests

A scenario is some credentials with their caps, the pools, the finishing kinds and the
grace window, and a list of steps, each at a time of day and a reading of the clock that
only moves forward: a reading observed, a launch refused, or a question (`rests`,
`resting_members`) with what the quota rule and the accounts answer then. `runScenario`
plays it on the specification and returns what each step answers and what `on_change` was
told. `tests/lean/rests_scenarios.py` plays the same scenario on `CredentialRests`.
-/

namespace Conformance.Quota

open Lean (FromJson ToJson Json)
open Contraagent

structure WindowScript where
  name : String
  pct : Option Int
  resetsAt : Option Int
  deriving FromJson

structure ReadingScript where
  observedAt : Option Int
  credential : String
  account : String
  fiveHourPct : Option Int
  fiveHourResetsAt : Option Int
  sevenDayPct : Option Int
  sevenDayResetsAt : Option Int
  windows : List WindowScript
  deriving FromJson

/-- What the quota rule says of a credential in a step: a reason, and maybe an end. -/
structure RuleScript where
  credential : String
  said : String
  «end» : Option Int
  deriving FromJson

/-- One step. `op`: `observe` (with `reading`), `refuse` (with `name`, `agent`, `model`),
`rests` or `resting_members` (with `name`, `kind`, `agent`, `model`, and what the rule and
the accounts answer: `rule`, `accounts`). -/
structure Step where
  op : String
  now : Int
  clock : Int
  name : String
  kind : String
  agent : String
  model : String
  reading : Option ReadingScript
  rule : List RuleScript
  accounts : List (String × String)
  deriving FromJson

structure CapScript where
  credential : String
  window : String
  cap : Int
  deriving FromJson

structure Scenario where
  windows : List (String × Int)
  caps : List CapScript
  pools : List (String × List String)
  finishingKinds : List String
  graceS : Int
  hasRule : Bool
  steps : List Step
  deriving FromJson

def optional : Option Int → Json
  | some n => n
  | none => Json.null

def rest (r : Rest) : Json :=
  Json.mkObj [("credential", r.credential), ("window", r.window), ("pct", optional r.pct), ("cap", optional r.cap),
    ("rule", r.rule), ("until", optional r.until), ("account", r.account), ("stop", r.stop), ("agent", r.agent),
    ("model", r.model)]

def reading (r : ReadingScript) : QuotaReading :=
  { observedAt := r.observedAt, credential := r.credential, account := r.account,
    fiveHour := { pct := r.fiveHourPct, resetsAt := r.fiveHourResetsAt },
    sevenDay := { pct := r.sevenDayPct, resetsAt := r.sevenDayResetsAt },
    windows := r.windows.map fun w => (w.name, { pct := w.pct, resetsAt := w.resetsAt }) }

/-- Play a scenario from its JSON: what each step answers, and what `on_change` was told,
the first first. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let cfg : RestsConfig :=
      { windows := sc.windows
        caps := fun name window => (sc.caps.find? fun c => c.credential == name && c.window == window).map (·.cap)
        members := fun name => sc.pools.lookup name
        finishingKinds := sc.finishingKinds
        graceS := sc.graceS
        hasRule := sc.hasRule }
    let (s, answers) := sc.steps.foldl
      (fun (acc : RestsState × Array Json) step =>
        let env : RestsEnv :=
          { rule := fun name _ => (step.rule.find? (·.credential == name)).map fun r => (r.said, r.end)
            account := fun name => (step.accounts.lookup name).getD "" }
        match step.op with
        | "observe" =>
          (match step.reading with
          | some r => (acc.1.observe (reading r), acc.2.push Json.null)
          | none => (acc.1, acc.2.push Json.null))
        | "refuse" => (acc.1.refuse step.name step.agent step.model, acc.2.push Json.null)
        | "resting_members" =>
          let (s, members) := cfg.restingMembers env step.now step.clock acc.1 step.name step.kind step.agent step.model
          (s, acc.2.push (Json.arr (members.map fun (member : String) => (member : Json)).toArray))
        | _ =>
          let (s, why) := cfg.rests env step.now step.clock acc.1 step.name step.kind step.agent step.model
          (s, acc.2.push (Json.arr (why.map rest).toArray)))
      ({}, #[])
    Json.mkObj [("answers", Json.arr answers),
      ("events", Json.arr (s.log.reverse.map fun (event, r) => Json.arr #[event, rest r]).toArray)]

end Conformance.Quota
