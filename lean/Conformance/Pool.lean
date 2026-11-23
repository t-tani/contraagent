import Lean.Data.Json
import Contraagent.Routing.Pool

/-!
# Scenarios of a credential pool

A scenario is a pool's members, its strategy and its cool-down, and a list of steps, each a
call of a `CredentialPool` at a time the scenario gives. `runScenario` plays it on the
specification and returns what each call answers. `tests/lean/pool_scenarios.py` plays the
same scenario on `CredentialPool`.
-/

namespace Conformance.Pool

open Lean (FromJson ToJson Json)
open Contraagent

/-- One call. `op`: `pick` (with `model` and `exclude`) or `rate_limited` (with `member`,
`model` and `retryAfterS`). -/
structure Step where
  now : Int
  op : String
  model : String
  exclude : List String
  member : String
  retryAfterS : Option Int
  deriving FromJson

structure Scenario where
  members : List String
  roundRobin : Bool
  cooldownS : Int
  steps : List Step
  deriving FromJson

/-- Play a scenario from its JSON: what each step answers. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let cfg : PoolConfig := { members := sc.members, roundRobin := sc.roundRobin, cooldownS := sc.cooldownS }
    let (_, answers) := sc.steps.foldl
      (fun (acc : PoolState × Array Json) step =>
        match step.op with
        | "pick" =>
          let (s, member) := cfg.pick step.now acc.1 step.model step.exclude
          (s, acc.2.push (match member with | some name => (name : Json) | none => Json.null))
        | _ => (cfg.rateLimited step.now acc.1 step.member step.model step.retryAfterS, acc.2.push Json.null))
      ({}, #[])
    Json.arr answers

end Conformance.Pool
