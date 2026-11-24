import Lean.Data.Json
import Contraagent.Dispatch.Queue.After
import Contraagent.Dispatch.Queue.Ids

/-!
# The log of a queue that ran

A trace is what one `WorkQueue` reported while it ran with its real runner, threads and
clock: its events in order, its size and the capacities of its claim names. `runTrace`
checks the log against what the theorems about the queue's description conclude, and
returns what it breaks: a start before a task it comes after finished
(`Reachable.starts_after`), a task finished twice (`Reachable.finished_once`), and, for a
queue that ran to its end, a task accepted and not finished
(`Reachable.accepted_finished`). It also follows the tasks the log shows running, from
each start to its end, its deferral or its retry, and checks them against the queue's size, the capacity of each claim
name and the keys of the other running tasks, which the theorems state of the queue's
record (`ReachableWithin.capacity`, `Reachable.running_keys_distinct`).

`tests/lean/trace.py` records the traces.
-/

namespace Conformance.Trace

open Lean (FromJson ToJson Json)
open Contraagent

/-- One event. `event`: `queued` (with `key`, `after`, `claims`), `refused`, `start` (with
`attempt`, `running`, `slots`), `retry`, `throttle`, `deferred`, `result`, `end` and
`finished` (with `key`, `stop`). `id` is the task's. -/
structure Event where
  event : String
  id : String
  key : String := ""
  after : List String := []
  claims : List String := []
  attempt : Nat := 0
  running : Nat := 0
  slots : Nat := 0
  stop : String := ""
  deriving FromJson

/-- `capacity`: the claim names whose capacity is a number, with it; a name that has none
here and is not in `sized` has capacity 1. `sized`: the names whose capacity the host sizes,
which are not checked. `complete`: the queue ran to its end. -/
structure Trace where
  test : String
  maxConcurrent : Nat
  capacity : List (String × Nat)
  sized : List String
  complete : Bool
  events : List Event
  deriving FromJson

/-- The task of an event, as the queue accepted it, or with what the event itself says. -/
def taskOf (tasks : List Task) (event : Event) : Task :=
  (tasks.find? (·.id == event.id)).getD
    { kind := "", unit := event.key, id := event.id, key := event.key, after := event.after, claims := event.claims }

def resultOf (tasks : List Task) (event : Event) : TaskResult :=
  { task := taskOf tasks event, ok := event.stop == Stop.completed || event.stop == Stop.skipped, stop := event.stop }

/-- The log, the earliest event first, with the tasks accepted so far. -/
def logOf (events : List Event) : List QueueEvent :=
  (events.foldl (fun (acc : List Task × List QueueEvent) event =>
    let tasks := if event.event == "queued" then acc.1 ++ [taskOf [] event] else acc.1
    let entry : Option QueueEvent :=
      match event.event with
      | "queued" => some (.queued (taskOf tasks event))
      | "refused" => some (.duplicateKeyRefused (taskOf tasks event))
      | "start" => some (.start (taskOf tasks event) event.attempt event.running event.slots)
      | "retry" => some (.retry (taskOf tasks event) event.stop 0)
      | "throttle" => some (.throttle (taskOf tasks event) event.slots)
      | "deferred" => some (.deferred (taskOf tasks event) none)
      | "result" => some (.result (resultOf tasks event) event.attempt)
      | "end" => some (.ended (resultOf tasks event) event.attempt)
      | "finished" => some (.finished (resultOf tasks event))
      | _ => none
    (tasks, acc.2 ++ entry.toList)) ([], [])).2

/-- What the tasks the log shows running break, start by start: the queue's size, the
capacity of a claim name, and a key that another running task has. -/
def runningBreaks (trace : Trace) (log : List QueueEvent) : List String :=
  (log.foldl (fun (acc : List Task × List String) event =>
    match event with
    | .start task _ shown _ =>
      let running := acc.1 ++ [task]
      let twice := if acc.1.any (·.key == task.key) then [s!"{task.key} starts while a task of its key runs"] else []
      let size :=
        if running.length > trace.maxConcurrent then
          [s!"{task.key} starts as task {running.length} of {trace.maxConcurrent} at most"]
        else []
      let count :=
        if shown != running.length then
          [s!"{task.key} starts as running task {shown} by the queue, {running.length} by its log"]
        else []
      let names := task.claims.eraseDups.filter fun name => !trace.sized.contains name
      let held := names.filterMap fun name =>
        let capacity := (trace.capacity.lookup name).getD 1
        let holders := running.countP (·.claims.contains name)
        if holders > capacity then some s!"{task.key} starts as holder {holders} of {name}, whose capacity is {capacity}"
        else none
      (running, acc.2 ++ twice ++ size ++ count ++ held)
    | .ended result _ => (acc.1.filter (·.id != result.task.id), acc.2)
    | .deferred task _ => (acc.1.filter (·.id != task.id), acc.2)
    | .retry task _ _ => (acc.1.filter (·.id != task.id), acc.2)
    | _ => acc) ([], [])).2

/-- Check a trace from its JSON: the test that ran the queue, and what its log breaks. -/
def runTrace (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Trace) with
  | .error message => Json.mkObj [("error", message)]
  | .ok trace =>
    let earliestFirst := logOf trace.events
    let log := earliestFirst.reverse
    let ids := (trace.events.map (·.id)).eraseDups
    let order := if decide (StartsAfter log) then [] else ["a task starts before a task it comes after finished"]
    let twice := ids.filterMap fun id =>
      if finishedOf id log ≤ 1 then none else some s!"task {id} finished {finishedOf id log} times"
    let left := if trace.complete then
        ids.filterMap fun id =>
          if acceptedOf id log ≤ finishedOf id log then none else some s!"task {id} was accepted and did not finish"
      else []
    let breaks := order ++ twice ++ left ++ runningBreaks trace earliestFirst
    Json.mkObj [("test", trace.test), ("breaks", Json.arr (breaks.map fun (line : String) => (line : Json)).toArray)]

end Conformance.Trace
