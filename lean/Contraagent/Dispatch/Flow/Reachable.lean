import Contraagent.Dispatch.Flow

/-!
# The records a driver reaches

`Reachable` holds of the driver's record after any calls, in any order, from the empty
record. A Task is created under a flow call only when the driver holds that flow call: the
driver numbers a Task under the flow call whose code runs when that is one of its own, and
as a top flow call otherwise (`_make_task`).
-/

namespace Contraagent

namespace FlowDriverState

/-- A record the driver reaches from the empty one. `replay`: the place of each key on a
resume. -/
inductive Reachable (replay : List (Key × Nat)) : FlowDriverState → Prop
  | start : Reachable replay {}
  | createTop {s} : Reachable replay s → Reachable replay (s.create none).1
  | create {s} (up : FlowCallPath) : Reachable replay s → (s.callOf up).isSome = true →
      Reachable replay (s.create (some up)).1
  | add {s} (call : Option FlowCallPath) (key : Key) (cancellable : Bool) : Reachable replay s →
      Reachable replay (s.add call key cancellable)
  | wait {s} (call : Option FlowCallPath) (key : Key) : Reachable replay s → Reachable replay (s.wait call key).1
  | waited {s} (call : Option FlowCallPath) (stop : Stop) (past : Bool) : Reachable replay s →
      Reachable replay (s.waited call stop past).1
  | followUp {s} (result : FlowResult) : Reachable replay s → Reachable replay (followUp replay s result)
  | give {s} : Reachable replay s → Reachable replay s.give.1
  | cancelled {s} (call : FlowCallPath) : Reachable replay s → Reachable replay (s.cancelled call)
  | ended {s} (call : FlowCallPath) (how : TaskEnd) : Reachable replay s → Reachable replay (s.ended call how).1
  | attach {s} : Reachable replay s → Reachable replay s.attach
  | closeStuck {s} (ready : Bool) : Reachable replay s → Reachable replay (s.closeStuck ready).1
  | endStuck {s} (ready : Bool) : Reachable replay s → Reachable replay (s.endStuck ready)
  | cancelRest {s} : Reachable replay s → Reachable replay s.cancelRest
  | closeRest {s} : Reachable replay s → Reachable replay s.closeRest

end FlowDriverState

end Contraagent
