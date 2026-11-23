import Lean.Data.Json
import Contraagent.Pipeline.Graph

/-!
# Scenarios of the task graph

A scenario is some declarations and a list of task calls, each by a flow call. `runScenario`
plays it on the specification and returns, for each call, the task's key, the keys it waits
for and its output file, or why the call is refused. `tests/lean/graph_scenarios.py` plays
the same scenario on `Graph`.
-/

namespace Conformance.Graph

open Lean (FromJson ToJson Json)
open Contraagent

/-- `outputName`: the template of the kind's output file; `none`: no output. `outputOf`:
the place, among the scenario's kinds, of the kind whose file it fills in. -/
structure ScenarioKind where
  kind : String
  python : Bool
  outputName : Option String
  outputOf : Option Nat
  deriving FromJson

/-- `after`: the places of earlier calls, whose tasks this one names in `after`. -/
structure ScenarioCall where
  kind : Nat
  unit : String
  key : Option String
  after : List Nat
  flowCall : String
  deriving FromJson

structure Scenario where
  kinds : List ScenarioKind
  calls : List ScenarioCall
  deriving FromJson

def Scenario.declaration (sc : Scenario) (place : Nat) : Option Declaration :=
  (sc.kinds[place]?).map fun k =>
    { kind := k.kind, python := k.python, outputName := k.outputName,
      outputOf := k.outputOf.bind fun other =>
        (sc.kinds[other]?).bind fun o => o.outputName.map fun template => (o.kind, template) }

def refusalName : GraphRefusal → String
  | .twoFlowCalls _ => "two_flow_calls"
  | .keyUsedTwice => "key_used_twice"
  | .sameLayout _ => "same_layout"
  | .outside => "outside"
  | .oneWriter _ => "one_writer"
  | .filledBefore _ => "filled_before"

def optJson : Option String → Json
  | some text => text
  | none => Json.null

/-- Play a scenario from its JSON: an answer for each call. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let (_, _, answers) := sc.calls.foldl
      (fun (acc : GraphState × Array (Option Key) × Array Json) call =>
        let (state, keys, answers) := acc
        match sc.declaration call.kind with
        | none => (state, keys.push none, answers.push (Json.mkObj [("refused", "no such kind")]))
        | some decl =>
          let after := call.after.filterMap fun place => (keys[place]?).join
          match addTask state decl call.unit call.key after call.flowCall with
          | (state, .ok node) =>
            (state, keys.push (some node.key),
              answers.push (Json.mkObj [("key", node.key), ("after", ToJson.toJson node.after),
                ("output", optJson node.outputPath)]))
          | (state, .error why) =>
            (state, keys.push none, answers.push (Json.mkObj [("refused", refusalName why)])))
      ({}, #[], #[])
    Json.arr answers

end Conformance.Graph
