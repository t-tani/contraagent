import Lean.Data.Json
import Contraagent.Dispatch.Flow

/-!
# Scenarios of the flow driver

A scenario is the calls a run of flows made on its driver, in order: Tasks created, tasks
created and waited for, results of the queue, results given, Tasks cancelled and ended, and
the driver's own steps. `runScenario` plays them on the specification and returns what
each call answers, then the tasks given to the queue, the keys cancelled on it and the
state of each flow call. `tests/lean/flow_scenarios.py` runs the flows on `FlowDriver`,
which makes those calls, and compares.
-/

namespace Conformance.Flow

open Lean (FromJson ToJson Json)
open Contraagent

/-- One call. `op`: `create` (with `parent`), `add` and `wait` (with `call`, `key`,
`cancellable`), `waited` (a wait of `call` got a result that ended in `stop`; `flag`: the
run is past its grace window), `result` (with `key`, `stop`), `give`,
`cancelled` and `ended` (with `call`, and `how`), `closeStuck` and `endStuck` (with `flag`:
a callback is ready), `cancelRest`, `closeRest` or `attach`. A flow call is named by its id. -/
structure Op where
  op : String
  parent : Option String
  call : Option String
  key : String
  cancellable : Bool
  stop : String
  how : String
  flag : Bool
  deriving FromJson

structure Scenario where
  replay : List (String × Nat)
  ops : List Op
  deriving FromJson

/-- The path of a flow call's id. -/
def path (id : String) : FlowCallPath :=
  (id.splitOn ".").map String.toNat!

def state : FlowCallState → String
  | .running => "running"
  | .returned => "returned"
  | .raised => "raised"
  | .closed => "closed"

def how : String → TaskEnd
  | "cancelled" => .cancelled
  | "raised" => .raised
  | _ => .returned

/-- Play one call: the record after it, and what it answers. -/
def step (sc : Scenario) (s : FlowDriverState) (op : Op) : FlowDriverState × Json :=
  let call := op.call.map path
  match op.op with
  | "create" =>
    let (s, made) := s.create (op.parent.map path)
    (s, made.id)
  | "add" => (s.add call op.key op.cancellable, Json.null)
  | "wait" =>
    let (s, atOnce) := s.wait call op.key
    (s, atOnce)
  | "waited" =>
    let (s, cancels) := s.waited call op.stop op.flag
    (s, cancels)
  | "result" => (FlowDriverState.followUp sc.replay s { key := op.key, stop := op.stop }, Json.null)
  | "give" =>
    let (s, key) := s.give
    (s, match key with | some k => (k : Json) | none => Json.null)
  | "cancelled" => (s.cancelled (call.getD []), Json.null)
  | "ended" =>
    let (s, ended) := s.ended (call.getD []) (how op.how)
    (s, match ended with | some st => (state st : Json) | none => Json.null)
  | "closeStuck" =>
    let (s, closed) := s.closeStuck op.flag
    (s, closed)
  | "endStuck" => (s.endStuck op.flag, Json.null)
  | "cancelRest" => (s.cancelRest, Json.null)
  | "closeRest" => (s.closeRest, Json.null)
  | "attach" => (s.attach, Json.null)
  | _ => (s, "unknown call")

/-- Play a scenario from its JSON: what each call answers, then the tasks given to the
queue and the keys cancelled on it, the first first, the state of each flow call and how
many run. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let (s, answers) := sc.ops.foldl
      (fun (acc : FlowDriverState × Array Json) op =>
        let (s, answer) := step sc acc.1 op
        (s, acc.2.push answer))
      ({}, #[])
    let names := fun (keys : List String) => Json.arr (keys.map fun (key : String) => (key : Json)).toArray
    Json.mkObj [("answers", Json.arr answers), ("sent", names s.sent.reverse), ("cancels", names s.cancels.reverse),
      ("states", Json.arr (s.calls.map fun call => Json.arr #[call.path.id, state call.state]).toArray),
      ("running", s.running)]

end Conformance.Flow
