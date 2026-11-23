import Lean.Data.Json
import Contraagent.Dispatch.Queue

/-!
# Scenarios of the work queue

A scenario is a queue's configuration, its tasks, and a script for everything the queue
does not decide: which tasks a resume skips, which the runner defers, how each attempt
ends and how long it takes, what a result's follow-up queues, and what is cancelled.
`runScenario` plays it on the specification and returns what the queue reports.
`tests/lean/queue_scenario.py` plays the same scenario on `WorkQueue`; the two must report
the same.

Time is virtual. The clock starts at `startAt`. A task that starts at `t` ends at `t` plus
its duration. When tasks run, the one that ends first ends next, the one that started first
when two end together, and the clock moves to that time; when nothing runs and a task
waits for its retry, the clock moves to the end of that wait.
-/

namespace Conformance

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioBox where
  deadlineAt : Int
  deadlineS : Int
  graceS : Int
  slackS : Int
  finishingKinds : List String
  flowCall : Option String
  deriving FromJson

structure ScenarioTask where
  id : String
  key : String
  kind : String
  after : List String
  claims : List String
  estimateS : Option Int
  tailS : Option Int
  priority : Int
  fingerprintAtStart : Bool
  timeBoxes : List ScenarioBox
  deriving FromJson

structure ScenarioOutcome where
  stop : String
  ok : Bool
  retryable : Bool
  cause : Option String
  deriving FromJson

/-- `deadlineS`: the run's own deadline, counted from the start; `none`: no deadline.
`claimCapacity`, `kindCaps`, `estimates` (by kind), `followUps` (by the id of the task
whose result it follows), `outcomes` (by id, one for each attempt; `completed` beyond
them), `durations` (by id; 1 when not given) and `cancels` (by the id of the task whose
finish it follows: the keys to cancel before the next pass) are lists of pairs. -/
structure Scenario where
  maxConcurrent : Nat
  deadlineS : Option Int
  graceS : Int
  slackS : Int
  finishingKinds : List String
  retryOn : List String
  throttleOn : List String
  throttleS : Int
  overdueS : Int
  retryWaitS : Int
  claimCapacity : List (String × Nat)
  kindCaps : List (String × Nat)
  estimates : List (String × Int)
  skip : List String
  rests : List String
  tasks : List ScenarioTask
  initial : List String
  followUps : List (String × List String)
  outcomes : List (String × List ScenarioOutcome)
  durations : List (String × Int)
  cancels : List (String × List String)
  deriving FromJson

/-- Where the clock starts, as the tests' clock does. -/
def startAt : Int := 1000

def toBox (b : ScenarioBox) : TimeBox :=
  { deadlineAt := b.deadlineAt, deadlineS := b.deadlineS, graceS := b.graceS, slackS := b.slackS,
    finishingKinds := b.finishingKinds, flowCall := b.flowCall }

def toTask (t : ScenarioTask) : Task :=
  { kind := t.kind, unit := t.key, after := t.after, claims := t.claims,
    timeBoxes := t.timeBoxes.map toBox, estimateS := t.estimateS, tailS := t.tailS,
    priority := t.priority, id := t.id, key := t.key, fingerprintAtStart := t.fingerprintAtStart }

def Scenario.config (sc : Scenario) : QueueConfig :=
  { maxConcurrent := max 1 sc.maxConcurrent,
    timeBox := sc.deadlineS.map fun d =>
      { deadlineAt := startAt + d, deadlineS := d, graceS := sc.graceS, slackS := sc.slackS,
        finishingKinds := sc.finishingKinds },
    retryOn := sc.retryOn, throttleOn := sc.throttleOn, throttleS := sc.throttleS,
    overdueS := sc.overdueS }

def Scenario.task? (sc : Scenario) (id : String) : Option Task :=
  (sc.tasks.find? (·.id == id)).map toTask

def Scenario.env (sc : Scenario) : QueueEnv :=
  { kindCap := fun task => sc.kindCaps.lookup task.kind,
    capacity := fun name => .number ((sc.claimCapacity.lookup name).getD 1),
    skip := fun task => sc.skip.contains task.key,
    starting := fun task => task,
    deferral := fun task =>
      if sc.rests.contains task.key then some { cause := { cause := "rest" } } else none,
    estimate := fun task => sc.estimates.lookup task.kind,
    finishChance := fun _ _ _ => none,
    followUp := fun result => ((sc.followUps.lookup result.task.id).getD []).filterMap sc.task?,
    fuel := 100000 }

def Scenario.outcome (sc : Scenario) (id : String) (attempt : Nat) : Outcome :=
  match ((sc.outcomes.lookup id).getD [])[attempt - 1]? with
  | some o =>
    { ok := o.ok, stop := o.stop, retryable := o.retryable,
      cause := o.cause.map fun cause => { cause := cause } }
  | none => { ok := true, stop := Stop.completed }

/-- A play under way: the clock, the queue, when each running task ends (in the order they
started), and how many finished results the cancels were worked out for. -/
structure Play where
  now : Int
  state : QueueState
  endsAt : List (String × Int) := []
  cancelsSeen : Nat := 0

/-- The ids of the results finished, the earliest first. -/
def finishedIds (s : QueueState) : List String :=
  s.log.reverse.filterMap fun
    | .finished result => some result.task.id
    | _ => none

/-- The running task that ends first, the one that started first of those that end
together. -/
def firstToEnd : List (String × Int) → Option (String × Int)
  | [] => none
  | x :: rest =>
    match firstToEnd rest with
    | some y => if y.2 < x.2 then some y else some x
    | none => some x

/-- Play one turn of the loop: the cancels that are due, a pass, and what follows it. The
play after the turn, and whether the queue goes on. -/
def turn (sc : Scenario) (p : Play) : Play × Bool :=
  let cfg := sc.config
  let env := sc.env
  let finished := finishedIds p.state
  let due := (finished.drop p.cancelsSeen).flatMap fun id => (sc.cancels.lookup id).getD []
  let cancelled := due.foldl (fun s key => (cancel env s key).1) p.state
  let state := pass cfg env p.now cancelled
  let started := state.running.filter fun e => ! (p.endsAt.any (·.1 == e.task.id))
  let endsAt := p.endsAt ++ started.map fun e =>
    (e.task.id, p.now + (sc.durations.lookup e.task.id).getD 1)
  let p := { p with state := state, endsAt := endsAt, cancelsSeen := finished.length }
  match afterPass p.now cancelled state with
  | .again => (p, true)
  | .stop => (p, false)
  | .giveUp => ({ p with state := giveUp env state }, true)
  | .retryAt t => ({ p with now := t }, true)
  | .wait =>
    match firstToEnd endsAt with
    | none => (p, false)
    | some (id, t) =>
      let now := max p.now t
      let attempt := ((state.running.find? (·.task.id == id)).map (·.attempt)).getD 1
      ({ p with
          now := now
          state := done cfg env now state id (sc.outcome id attempt) sc.retryWaitS
          endsAt := endsAt.filter (·.1 != id) }, true)

def play (sc : Scenario) : Nat → Play → Except String QueueState
  | 0, _ => .error "the play did not end"
  | turns + 1, p =>
    match turn sc p with
    | (p, false) => .ok p.state
    | (p, true) => play sc turns p

def optJson {α : Type} [ToJson α] : Option α → Json
  | some a => ToJson.toJson a
  | none => Json.null

/-- One event as both sides write it. -/
def eventJson : QueueEvent → Json
  | .queued task => Json.arr #["queued", task.id]
  | .duplicateKeyRefused task => Json.arr #["duplicate_key_refused", task.id]
  | .start task attempt running slots =>
    Json.arr #["start", task.id, ToJson.toJson attempt, ToJson.toJson running, ToJson.toJson slots]
  | .retry task stop waitS => Json.arr #["retry", task.id, stop, ToJson.toJson waitS]
  | .throttle task slots => Json.arr #["throttle", task.id, ToJson.toJson slots]
  | .deferred task cause =>
    Json.arr #["deferred", task.id, optJson (cause.map (·.cause)), optJson (cause.bind (·.needS)),
      optJson (cause.bind (·.leftS)), optJson (cause.bind (·.flowCall))]
  | .result result attempt => Json.arr #["result", result.task.id, result.stop, ToJson.toJson attempt]
  | .ended result attempt =>
    Json.arr #["end", result.task.id, ToJson.toJson attempt, result.stop, ToJson.toJson result.ok]
  | .finished result => Json.arr #["finished", result.task.id, result.stop]

/-- Play a scenario from its JSON: the events the queue reports, the earliest first, or
why the scenario could not be played. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let added := (sc.initial.filterMap sc.task?).foldl (fun s task => (add sc.env s task).1) {}
    match play sc 100000 { now := startAt, state := added } with
    | .error message => Json.mkObj [("error", message)]
    | .ok state => Json.arr (state.log.reverse.map eventJson).toArray

end Conformance
