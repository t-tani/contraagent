import Lean.Data.Json
import Contraagent.Routing.Capacity

/-!
# Scenarios of the host's room

A scenario is a host's cores, some `PerTask` needs and a list of steps, each a call of a
`HostCapacity` or of one of its capacities, with what the host reads then. `runScenario`
plays it on the specification and returns, after each step, what the call answered, the
baseline and the running tasks. `tests/lean/capacity_scenarios.py` plays the same scenario
on `HostCapacity`.
-/

namespace Conformance.Capacity

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioNeed where
  memoryMb : Option Nat
  cores : Option Nat
  deriving FromJson

/-- One call. `op`: `refresh`, `allowed` (with `held`), `started` or `ended` (with `key`).
`need`: the place of the capacity's need. `freeMb` and `usageMb`: what the host reads. -/
structure Step where
  op : String
  need : Nat
  held : Nat
  key : String
  freeMb : Option Nat
  usageMb : List (String × Nat)
  deriving FromJson

structure Scenario where
  cores : Nat
  needs : List ScenarioNeed
  steps : List Step
  deriving FromJson

def optNat : Option Nat → Json
  | some n => ToJson.toJson n
  | none => Json.null

/-- Play a scenario from its JSON: after each step, the answer, the baseline and the tasks. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let (_, answers) := sc.steps.foldl
      (fun (acc : HostState × Array Json) step =>
        let (state, answers) := acc
        let need : PerTask := match sc.needs[step.need]? with
          | some n => { memoryMb := n.memoryMb, cores := n.cores }
          | none => {}
        let host : HostReading := { freeMb := step.freeMb, usageMb := step.usageMb }
        let (state, answer) := match step.op with
          | "refresh" => (state.refresh, Json.null)
          | "allowed" => let (s, n) := state.allowed host need step.held; (s, optNat n)
          | "started" => (state.started host step.key need, Json.null)
          | "ended" => (state.ended step.key need, Json.null)
          | _ => (state, "unknown step")
        let tasks := state.tasks.map fun task =>
          Json.arr #[task.1, ToJson.toJson task.2.1, ToJson.toJson task.2.2]
        (state, answers.push (Json.mkObj [("answer", answer), ("baseline", optNat state.baselineMb),
          ("tasks", Json.arr tasks.toArray)])))
      ({ cores := sc.cores }, #[])
    Json.arr answers

end Conformance.Capacity
