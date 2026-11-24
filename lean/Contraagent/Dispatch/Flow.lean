import Contraagent.Dispatch.Task

/-!
# The flow driver's record

What `FlowDriver` of `src/contraagent/_internal/dispatch/flow.py` decides by its own
record: the id of each flow call, which task it gives the queue and when, the order in
which it gives results to the flow code, how a flow call ends, which task it cancels, and
when it closes the flow calls that nothing will answer.

Flow code runs as asyncio Tasks on the driver's own event loop, and what the Tasks do
reaches the driver as calls. A function here is one such call: a Task is created (`start`,
`create`), flow code creates a task (`add`) or begins to wait for one (`wait`), the queue
finishes a task (`followUp`), the driver gives the flow code a result (`give`), a Task is
cancelled (`cancelled`) or ends (`ended`), and the driver's own steps (`attach`,
`closeStuck`, `endStuck`, `cancelRest`, `closeRest`). Which call comes when is the business of asyncio
and of the flow code, and is not described.

Left out: a flow call's frontier and what reached it, which follow the callbacks of the
event loop; whether a flow call is on record; the unawaited tasks; time boxes; the errors
a flow call ends with; and the value a wait gives (`answer`).
-/

namespace Contraagent

/-- A flow call's place: the number of its top flow call, then its number in each parent
down to it. Its id is these numbers joined by dots (`0.1.2`). -/
abbrev FlowCallPath := List Nat

/-- The id of a flow call (`FlowCall.id`). -/
def FlowCallPath.id (path : FlowCallPath) : FlowCallId :=
  ".".intercalate (path.map toString)

/-- Whether a flow call runs, or how it ended (`FlowState`). -/
inductive FlowCallState where
  | running
  | returned
  | raised
  | closed
  deriving DecidableEq, Repr

/-- One flow call (`FlowCall`), with what the driver decides by. `children`: how many Tasks
its code created. `closing`: the driver cancels it, so it ends `closed` whatever it ends
with. `cancellable`: the keys of the cancellable tasks it created or waited for. -/
structure FlowCall where
  path : FlowCallPath
  state : FlowCallState := .running
  children : Nat := 0
  closing : Bool := false
  cancellable : List Key := []
  deriving DecidableEq, Repr

/-- How a flow call's Task ended (`_task_done`): cancelled, with an exception, or with a
value. -/
inductive TaskEnd where
  | cancelled
  | raised
  | returned
  deriving DecidableEq, Repr

/-- A result as the driver keeps it: the task's key and how it ended. -/
structure FlowResult where
  key : Key
  stop : Stop
  deriving DecidableEq, Repr

/-- The driver's record (`FlowDriver`). `calls`: every flow call, in the order of their
creation. `tops`: how many top flow calls were started. `running`: how many flow calls
run. `done`: every result given to the flow code, by key. `queuedKeys`: every key the
driver queued. `open`: the keys queued whose result was not given. `creators`: the
cancellable tasks whose result was not given, each with the flow call that created it.
`waiters`: the waits that go on, each the key and the flow call that waits, in the order
they began. `results`: the results not yet given, in the order they came. `replayed`: the
results of skipped tasks not yet given, each with its key's place on a resume and the
order it came in. `attached`: the queue is attached. `outbox`, `toCancel`: the tasks and
the cancels that wait for the queue. `sent`, `cancels`, `given`: the tasks given to the
queue, the keys cancelled on it and the results given to the flow code, the latest
first. `stuck`: the flow calls the latest `closeStuck` cancelled. -/
structure FlowDriverState where
  calls : List FlowCall := []
  tops : Nat := 0
  running : Nat := 0
  done : List FlowResult := []
  queuedKeys : List Key := []
  «open» : List Key := []
  creators : List (Key × FlowCallPath) := []
  waiters : List (Key × FlowCallPath) := []
  results : List FlowResult := []
  replayed : List (Nat × Nat × FlowResult) := []
  arrived : Nat := 0
  attached : Bool := false
  outbox : List Key := []
  toCancel : List Key := []
  sent : List Key := []
  cancels : List Key := []
  given : List Key := []
  stuck : List FlowCallPath := []
  deriving Repr

namespace FlowDriverState

def callOf (s : FlowDriverState) (path : FlowCallPath) : Option FlowCall :=
  s.calls.find? (·.path == path)

/-- The record with one flow call changed. -/
def setCall (s : FlowDriverState) (path : FlowCallPath) (change : FlowCall → FlowCall) : FlowDriverState :=
  { s with calls := s.calls.map fun call => if call.path == path then change call else call }

/-- Whether a result of `key` was given to the flow code. -/
def isDone (s : FlowDriverState) (key : Key) : Bool :=
  s.done.any (·.key == key)

/-- A Task is created (`_make_task`): a new flow call, running. With `parent`, the flow
call whose code creates it, it is the next of the parent's; without, the next top flow
call. With its path. -/
def create (s : FlowDriverState) (parent : Option FlowCallPath) : FlowDriverState × FlowCallPath :=
  match parent with
  | none =>
    ({ s with calls := s.calls ++ [{ path := [s.tops] }], tops := s.tops + 1, running := s.running + 1 }, [s.tops])
  | some up =>
    let number := ((s.callOf up).map (·.children)).getD 0 + 1
    ({ (s.setCall up fun call => { call with children := number }) with
        calls := (s.setCall up fun call => { call with children := number }).calls ++ [{ path := up ++ [number] }]
        running := s.running + 1 },
      up ++ [number])

/-- Give a task to the queue, once (`_enqueue`): a key that was queued, or whose result was
given, is not queued again. Before the queue is attached, the task waits for it. -/
def enqueue (s : FlowDriverState) (key : Key) : FlowDriverState :=
  if s.queuedKeys.contains key || s.isDone key then s
  else
    let s := { s with queuedKeys := s.queuedKeys ++ [key], «open» := s.«open» ++ [key] }
    if s.attached then { s with sent := key :: s.sent } else { s with outbox := s.outbox ++ [key] }

/-- The flow call `call` counts the task of `key` among its own, to cancel it when the flow
call is closed (`FlowCall._cancellable`). -/
def own (s : FlowDriverState) (call : FlowCallPath) (key : Key) : FlowDriverState :=
  s.setCall call fun c => { c with cancellable := if c.cancellable.contains key then c.cancellable else key :: c.cancellable }

/-- The record once flow code created a task in the flow call `call`, before the task is
queued (`add`): a cancellable task whose result was not given and that has no creator yet
gets the flow call as its creator. -/
def created (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) (cancellable : Bool) : FlowDriverState :=
  match call with
  | some path =>
    if cancellable && !s.isDone key && !s.creators.any (·.1 == key) then
      { (s.own path key) with creators := s.creators ++ [(key, path)] }
    else s
  | none => s

/-- Flow code creates a task (`add`), in the flow call `call`: the task has its creator
(`created`), and is given to the queue (`enqueue`). -/
def add (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) (cancellable : Bool) : FlowDriverState :=
  (s.created call key cancellable).enqueue key

/-- A flow call that waits for a cancellable task with a creator counts it among its own
(`_waiting`). -/
def ownWaited (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) : FlowDriverState :=
  match call with
  | some path => if s.creators.any (·.1 == key) then s.own path key else s
  | none => s

/-- The record once the flow call `call` waits for the task of `key`, before the task is
queued (`_waiting`). -/
def waiting (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) : FlowDriverState :=
  match call with
  | some path => { s with waiters := s.waiters ++ [(key, path)] }
  | none => s

/-- Flow code begins to wait for a task (`_waiting`), in the flow call `call`: with whether
its result was given before, so that the wait ends at once. Else the wait goes on, and the
task is given to the queue when it was not. -/
def wait (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) : FlowDriverState × Bool :=
  if (s.ownWaited call key).isDone key then (s.ownWaited call key, true)
  else (((s.ownWaited call key).waiting call key).enqueue key, false)

/-- A wait of the flow call `call` got a result that ended in `stop` (`_waiting`). `past`:
the run is past its grace window. A deferred result past it cancels the flow call, which
ends `closed`; whether it does. Else the flow code gets what `answer` makes of the
result. -/
def waited (s : FlowDriverState) (call : Option FlowCallPath) (stop : Stop) (past : Bool) : FlowDriverState × Bool :=
  match call with
  | some path =>
    if stop == Stop.deferred && past then (s.setCall path fun c => { c with closing := true }, true) else (s, false)
  | none => (s, false)

/-- The queue finished a task (`follow_up`): the result is kept for the flow code. That of
a skipped task whose key has a place on a resume (`replay`) is kept by that place. -/
def followUp (replay : List (Key × Nat)) (s : FlowDriverState) (result : FlowResult) : FlowDriverState :=
  match (if result.stop == Stop.skipped then replay.lookup result.key else none) with
  | some place => { s with replayed := s.replayed ++ [(place, s.arrived, result)], arrived := s.arrived + 1 }
  | none => { s with results := s.results ++ [result] }

/-- Of two kept results of skipped tasks, each with its key's place on a resume and the
order it came in, the one given first: the one with the lower place, and of two with one
place the one that came first. -/
def earlier (best entry : Nat × Nat × FlowResult) : Nat × Nat × FlowResult :=
  if entry.1 < best.1 || (entry.1 == best.1 && entry.2.1 < best.2.1) then entry else best

/-- The result the flow code is given next (`_run_flows`): that of a skipped task with the
least place on a resume, the first that came of two with one place; with none of those,
the result that came first. -/
def next (s : FlowDriverState) : Option FlowResult :=
  match s.replayed with
  | first :: rest => some (rest.foldl earlier first).2.2
  | [] => s.results.head?

/-- Take the next result out of those kept: that one, once. -/
def takeNext (s : FlowDriverState) : FlowDriverState :=
  match s.replayed with
  | first :: rest => { s with replayed := s.replayed.erase (rest.foldl earlier first) }
  | [] => { s with results := s.results.drop 1 }

/-- The flow code gets `result` (`_give`): the waits for its key end. But for the result of
a refused duplicate, whose key's own result is still to come, the key is done, no longer
open, and has no creator. -/
def got (s : FlowDriverState) (result : FlowResult) : FlowDriverState :=
  if result.stop == Stop.duplicateKey then
    { s with given := result.key :: s.given, waiters := s.waiters.filter (·.1 != result.key) }
  else
    { s with
      given := result.key :: s.given
      waiters := s.waiters.filter (·.1 != result.key)
      done := s.done.filter (·.key != result.key) ++ [result]
      «open» := s.«open».filter (· != result.key)
      creators := s.creators.filter (·.1 != result.key) }

/-- Give the flow code the next result (`_run_flows`, `_give`). With the key given, when a
result was kept. -/
def give (s : FlowDriverState) : FlowDriverState × Option Key :=
  match s.next with
  | none => (s, none)
  | some result => (s.takeNext.got result, some result.key)

/-- The Task of a flow call was cancelled (`Task.cancel`): the wait it was in ends, with
no result. -/
def cancelled (s : FlowDriverState) (call : FlowCallPath) : FlowDriverState :=
  { s with waiters := s.waiters.filter (·.2 != call) }

/-- Cancel the cancellable task of `key` when the flow call that created it is closed, no
result of it was given and no flow call waits for it (`_cancel_unwaited`). Before the
queue is attached, the cancel waits for it. -/
def cancelUnwaited (s : FlowDriverState) (key : Key) : FlowDriverState :=
  match s.creators.lookup key with
  | none => s
  | some creator =>
    if ((s.callOf creator).map (·.state)) != some .closed || s.isDone key then s
    else if s.waiters.any (·.1 == key) then s
    else
      let s := { s with creators := s.creators.filter (·.1 != key) }
      if s.attached then { s with cancels := key :: s.cancels } else { s with toCancel := s.toCancel ++ [key] }

/-- How a flow call ends, by how its Task ended (`_task_done`): `closed` when the Task was
cancelled or the driver was closing it. -/
def endState (closing : Bool) : TaskEnd → FlowCallState
  | .cancelled => .closed
  | .raised => if closing then .closed else .raised
  | .returned => if closing then .closed else .returned

/-- A flow call ends in `state` (`_end`): one flow call fewer runs, and when it is closed,
each cancellable task it created or waited for is cancelled if nothing waits for it
(`cancelUnwaited`), in the order of the keys. A flow call that had ended stays as it is. -/
def endCall (s : FlowDriverState) (call : FlowCallPath) (state : FlowCallState) : FlowDriverState :=
  match s.callOf call with
  | none => s
  | some found =>
    if found.state != .running then s
    else
      let s := { (s.setCall call fun c => { c with state := state }) with running := s.running - 1 }
      if state == .closed then
        (found.cancellable.mergeSort fun a b => decide (a ≤ b)).foldl cancelUnwaited s
      else s

/-- The Task of a flow call ended (`_task_done`). With the state the flow call ends in,
when it ran. -/
def ended (s : FlowDriverState) (call : FlowCallPath) (how : TaskEnd) : FlowDriverState × Option FlowCallState :=
  match s.callOf call with
  | none => (s, none)
  | some found =>
    if found.state != .running then (s, none)
    else (s.endCall call (endState found.closing how), some (endState found.closing how))

/-- The queue is attached (`attach`): the tasks and the cancels that waited go to it. -/
def attach (s : FlowDriverState) : FlowDriverState :=
  { s with attached := true, sent := s.outbox.reverse ++ s.sent, outbox := [],
           cancels := s.toCancel.reverse ++ s.cancels, toCancel := [] }

/-- Whether a flow call still runs (`alive`). -/
def alive (s : FlowDriverState) : Bool :=
  decide (s.running > 0)

/-- Whether something may still answer a flow call: a callback of the flow loop is ready
(`ready`), a result is kept, or a task the driver queued is still to give its result. -/
def answerable (s : FlowDriverState) (ready : Bool) : Bool :=
  ready || !s.results.isEmpty || !s.replayed.isEmpty || !s.«open».isEmpty

/-- When the flows are quiescent and nothing is still to give a result, close every flow
call that runs (`_close_stuck`): nothing will answer any of them. The flow calls closed
are cancelled, so their waits end; whether any was. -/
def closeStuck (s : FlowDriverState) (ready : Bool) : FlowDriverState × Bool :=
  if s.running == 0 || s.answerable ready then (s, false)
  else
    let stuck := (s.calls.filter (·.state == .running)).map (·.path)
    ({ s with
        calls := s.calls.map fun call => if call.state == .running then { call with closing := true } else call
        waiters := s.waiters.filter fun waiter => !stuck.contains waiter.2
        stuck := stuck },
      true)

/-- Once the flow calls that `closeStuck` cancelled had their turn (`_end_stuck`): those
that still run, while still nothing may answer them, end `closed`. Their code went on after
the cancellation and waits again; it does not keep the run from ending. -/
def endStuck (s : FlowDriverState) (ready : Bool) : FlowDriverState :=
  if s.answerable ready then { s with stuck := [] }
  else s.stuck.foldl (fun s path => s.endCall path .closed) { s with stuck := [] }

/-- The run is over (`_cancel_rest`): every flow call that runs is closing, and every Task
is cancelled. -/
def cancelRest (s : FlowDriverState) : FlowDriverState :=
  { s with
    calls := s.calls.map fun call => if call.state == .running then { call with closing := true } else call
    waiters := [] }

/-- Every flow call that still runs ends `closed` (`_close_rest`). -/
def closeRest (s : FlowDriverState) : FlowDriverState :=
  ((s.calls.filter (·.state == .running)).map (·.path)).foldl (fun s path => s.endCall path .closed) s

end FlowDriverState

end Contraagent
