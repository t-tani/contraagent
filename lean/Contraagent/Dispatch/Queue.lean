import Contraagent.Dispatch.Task

/-!
# The work queue

What `WorkQueue` of `src/contraagent/_internal/dispatch/queue.py` decides: which tasks it
accepts, which start in a pass and in which order, which it defers, retries or cancels,
and how each task finishes once.

A function here is one method of the code, and takes what the method reads from outside
as arguments: the clock's reading (`now`) and the answers of the callbacks (`QueueEnv`).
The queue's own record is a `QueueState`; what it reports is added to `QueueState.log`.

Left out: the threads tasks run on (a task that ends is the step `done`), the waits of
the loop, the summary, the notes of a callback that raised, and a `ClaimCapacity` whose
answer changes as tasks start within one pass (`QueueEnv.capacity` answers for the step).
The bottom level is the code's on tasks whose `after` has no cycle, and on a task that
names its own key; on a longer cycle the code's value depends on the order it meets the
tasks, and no task of such a cycle ever starts.
-/

namespace Contraagent

/-- Used for a task with no estimate (`DEFAULT_ESTIMATE_S`). -/
def defaultEstimateS : Duration := 300

/-- Below this finish chance, in percent, a task is late (`FINISH_CHANCE`). -/
def finishChancePct : Nat := 35

/-- What a `WorkQueue` is built with. -/
structure QueueConfig where
  maxConcurrent : Nat := 8
  /-- The run's own time box, over every task; `none` without a deadline. -/
  timeBox : Option TimeBox := none
  retryOn : List Stop := []
  throttleOn : List Stop := []
  throttleS : Duration := 300
  overdueS : Duration := 600
  deriving Repr

/-- How many running tasks may hold a claimed name (an entry of `claim_capacity`): a number,
or what a `ClaimCapacity` answers when it is asked, given how many hold the name now. -/
inductive Capacity where
  | number (n : Nat)
  | asked (allowed : Nat → Nat)

def Capacity.allowed : Capacity → Nat → Nat
  | .number n, _ => n
  | .asked allowed, held => allowed held

/-- The answers of the queue's callbacks, as they are during one step.

`kindCap`: `runner.config(task).max_concurrent`. `capacity name`: the capacity of `name`
(`claim_capacity`; the number 1 when no entry names it). `skip`: whether a resume skips the
task. `starting`: the task as it starts, its fingerprint completed. `deferral`: why the
runner cannot launch the task now. `estimate`: the task's expected time, when it carries
none. `finishChance task left after`: the chance, in percent, that the task and the work
after it end within `left`. `followUp`: the tasks a result's follow-up queues. `fuel`: how
many results one drain finishes at most; the code's drain has no bound. -/
structure QueueEnv where
  kindCap : Task → Option Nat
  capacity : String → Capacity
  skip : Task → Bool
  starting : Task → Task
  deferral : Task → Option Deferral
  estimate : Task → Option Duration
  finishChance : Task → Duration → Duration → Option Nat
  followUp : TaskResult → List Task
  fuel : Nat

/-- A task in the queue or running, with what the queue keeps for it. `seq`: its place in
the order of arrival. `attempt`: the attempts started so far. `asked`: `skip` was asked
about it once its dependencies were done. `notBefore`: the end of its retry wait.
`readySince`: when a pass first found its dependencies done. `cancelled`: `cancel` was
called while it ran. -/
structure QueueEntry where
  task : Task
  seq : Nat
  attempt : Nat := 0
  asked : Bool := false
  notBefore : Option Time := none
  readySince : Option Time := none
  cancelled : Bool := false
  deriving Repr

/-- A result waiting to finish (`_settling`), with the attempts its task started. -/
structure Settling where
  result : TaskResult
  attempt : Nat
  deriving Repr

/-- What the queue reports. `queued` to `ended` are the events of `on_event` (`ended` is
its `end`); `result` is a call of `on_result`; `finished` is a call of `follow_up`, the one
place where a task finishes. -/
inductive QueueEvent where
  | queued (task : Task)
  | duplicateKeyRefused (task : Task)
  | start (task : Task) (attempt : Nat) (running : Nat) (slots : Nat)
  | retry (task : Task) (stop : Stop) (waitS : Duration)
  | throttle (task : Task) (slots : Nat)
  | deferred (task : Task) (cause : Option DeferralCause)
  | result (result : TaskResult) (attempt : Nat)
  | ended (result : TaskResult) (attempt : Nat)
  | finished (result : TaskResult)
  deriving Repr

/-- The queue's record. `queued`: in the order of arrival, a retry first. `known`: the ids
it was given. `inflight`: the keys of the tasks it accepted and has not finished
(`_inflight_keys`): queued, running, taken out of the queue to be deferred, or with a result
that waits to finish. `log`: what it reported, the latest first. -/
structure QueueState where
  queued : List QueueEntry := []
  running : List QueueEntry := []
  known : List String := []
  nextSeq : Nat := 0
  inflight : List Key := []
  doneKeys : List Key := []
  settling : List Settling := []
  throttledUntil : Option Time := none
  consecThrottled : Nat := 0
  log : List QueueEvent := []
  deriving Repr

/-- How a running task ended, as its runner returns it. -/
structure Outcome where
  ok : Bool
  stop : Stop
  cause : Option DeferralCause := none
  retryable : Bool := true
  deriving Repr

namespace QueueState

def report (s : QueueState) (event : QueueEvent) : QueueState :=
  { s with log := event :: s.log }

/-- Whether a task with this id is queued. -/
def isQueued (s : QueueState) (id : String) : Bool :=
  s.queued.any (·.task.id == id)

/-- How many results the queue has finished (`_finished`). -/
def finishedCount (s : QueueState) : Nat :=
  s.log.countP fun
    | .finished _ => true
    | _ => false

/-- Put a result among those waiting to finish (`_settle`, while a drain is under way). -/
def push (s : QueueState) (result : TaskResult) (attempt : Nat) : QueueState :=
  { s with settling := s.settling ++ [{ result := result, attempt := attempt }] }

/-- Take the task with this id out of the queue (`_dequeue`). -/
def dequeue (s : QueueState) (id : String) : QueueState :=
  { s with queued := s.queued.filter (·.task.id != id) }

/-- How many running tasks hold `name` (`_held`). -/
def held (s : QueueState) (name : String) : Nat :=
  s.running.countP (·.task.claims.contains name)

/-- How many running tasks are of `kind`. -/
def runningOf (s : QueueState) (kind : Kind) : Nat :=
  s.running.countP (·.task.kind == kind)

/-- The queued tasks that name `key` in `after` (`_successors`). -/
def successors (s : QueueState) (key : Key) : List QueueEntry :=
  s.queued.filter (·.task.after.contains key)

end QueueState

/-! ## Launch conditions -/

/-- Every time box a task is held to (`_boxes`): its flow calls' and the run's. -/
def boxes (cfg : QueueConfig) (task : Task) : List TimeBox :=
  task.timeBoxes ++ cfg.timeBox.toList

/-- Why a box no longer lets a task launch (`_closed`): past the box's grace window, or
past its deadline for a kind that is not one of its finishing kinds. -/
def closedBy (now : Time) (task : Task) : List TimeBox → Option Deferral
  | [] => none
  | box :: rest =>
    if now ≥ box.deadlineAt + box.graceS then
      some { cause := { cause := "grace_window", flowCall := box.flowCall } }
    else if now ≥ box.deadlineAt ∧ ¬ box.finishingKinds.contains task.kind then
      some { cause := { cause := "deadline", flowCall := box.flowCall } }
    else closedBy now task rest

def closed (cfg : QueueConfig) (now : Time) (task : Task) : Option Deferral :=
  closedBy now task (boxes cfg task)

/-- The box, of those in their endgame, with the earliest deadline (`_endgame_box`); the
first of them when two share it. -/
def endgameBox (cfg : QueueConfig) (now : Time) (task : Task) : Option TimeBox :=
  ((boxes cfg task).filter fun box => now ≥ box.deadlineAt - box.slackS).foldl
    (fun best box =>
      match best with
      | none => some box
      | some b => if box.deadlineAt < b.deadlineAt then some box else some b)
    none

/-- Whether the slots are halved now. -/
def throttled (now : Time) (s : QueueState) : Bool :=
  match s.throttledUntil with
  | some till => decide (now < till)
  | none => false

/-- The current concurrency cap (`slots`): halved while throttled. -/
def slots (cfg : QueueConfig) (now : Time) (s : QueueState) : Nat :=
  if throttled now s then max 1 (cfg.maxConcurrent / 2) else cfg.maxConcurrent

/-- Its dependencies are done and it is not waiting for a retry (`_startable`). -/
def startable (now : Time) (s : QueueState) (e : QueueEntry) : Bool :=
  e.task.after.all (s.doneKeys.contains ·)
    && match e.notBefore with
      | some t => decide (now ≥ t)
      | none => true

/-- What a task needs is free (`_free`): a place under its kind's cap, and every name it
claims. -/
def free (env : QueueEnv) (s : QueueState) (task : Task) : Bool :=
  (match env.kindCap task with
    | some cap => decide (s.runningOf task.kind < cap)
    | none => true)
    && task.claims.all fun name => decide (s.held name < (env.capacity name).allowed (s.held name))

/-- It could start with nothing else running (`_possible`): no cap of 0 and no capacity
that is the number 0 stands in its way. A capacity that is asked is none: what it answers
while other tasks run says nothing of then. -/
def possible (env : QueueEnv) (task : Task) : Bool :=
  (match env.kindCap task with
    | some cap => decide (cap > 0)
    | none => true)
    && task.claims.all fun name =>
      match env.capacity name with
      | .number n => decide (n > 0)
      | .asked _ => true

/-- Whether starting `task` takes what `head` still needs (`_takes`): the last place on a
name both claim, or the last place under their kind's cap. -/
def takes (env : QueueEnv) (s : QueueState) (task head : Task) : Bool :=
  (task.claims.any fun name =>
      head.claims.contains name
        && decide (s.held name + 1 ≥ (env.capacity name).allowed (s.held name)))
    || match env.kindCap head with
      | some cap => task.kind == head.kind && decide (s.runningOf head.kind + 1 ≥ cap)
      | none => false

/-! ## The order -/

/-- A task's expected time (`_known_est`): its own, else the callback's. -/
def knownEst (env : QueueEnv) (task : Task) : Option Duration :=
  match task.estimateS with
  | some est => some est
  | none => env.estimate task

def est (env : QueueEnv) (task : Task) : Duration :=
  (knownEst env task).getD defaultEstimateS

/-- The largest of `xs`, 0 when there is none. -/
def maxOf (xs : List Duration) : Duration :=
  xs.foldl max 0

/-- Bottom level (`_blevel`): a task's estimate plus the longer of the longest path through
the queued tasks after it and its `tailS`. A task whose key is already on the path (`path`)
adds nothing, so the value is defined when `after` has a cycle too. `depth` bounds the
path: the number of queued tasks is enough. -/
def blevelWithin (env : QueueEnv) (s : QueueState) : Nat → List Key → Task → Duration
  | 0, _, task => est env task + max 0 (task.tailS.getD 0)
  | depth + 1, path, task =>
    let after := (s.successors task.key).filter fun e => ! (task.key :: path).contains e.task.key
    est env task
      + max (maxOf (after.map fun e => blevelWithin env s depth (task.key :: path) e.task))
          (task.tailS.getD 0)

def blevel (env : QueueEnv) (s : QueueState) (task : Task) : Duration :=
  blevelWithin env s s.queued.length [] task

/-- It has waited since its dependencies were done for `overdueS` or longer (`_overdue`). -/
def overdue (cfg : QueueConfig) (now : Time) (e : QueueEntry) : Bool :=
  match e.readySince with
  | some since => decide (now - since ≥ cfg.overdueS)
  | none => false

/-- Whether the first list comes before the second, or is equal to it: the order of the
code's tuples. -/
def lexLe : List Int → List Int → Bool
  | [], _ => true
  | _ :: _, [] => false
  | a :: as, b :: bs => if a < b then true else if b < a then false else lexLe as bs

/-- What a queued task is ordered by (`_order`): first the tasks in a time box's endgame,
its finishing kinds first, then the smallest bottom level; then the overdue tasks, the
longest waiting first; then the highest bottom level. In each, the highest priority breaks
a tie, then arrival. -/
def orderKey (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState)
    (e : QueueEntry) : List Int :=
  let level := blevel env s e.task
  match endgameBox cfg now e.task with
  | some box =>
    [0, if box.finishingKinds.contains e.task.kind then 0 else 1, level, -e.task.priority, e.seq]
  | none =>
    if overdue cfg now e then [1, e.readySince.getD 0, -level, -e.task.priority, e.seq]
    else [2, 0, -level, -e.task.priority, e.seq]

/-- The chance, in percent, that a task and the work after it end within `left`
(`_finish_chance`): from the callback when the task carries no estimate, else 100 or 0
from its estimate; `none` when nothing knows the task. -/
def finishChance (env : QueueEnv) (s : QueueState) (task : Task) (left : Duration) : Option Nat :=
  let after := maxOf ((s.successors task.key).map fun e => blevel env s e.task)
  let asked := if task.estimateS.isNone then env.finishChance task left after else none
  match asked with
  | some chance => some chance
  | none =>
    match knownEst env task with
    | none => none
    | some known => some (if known + max after (task.tailS.getD 0) ≤ left then 100 else 0)

/-- Why a task is late under one of its boxes (`_late`): the first box, in whose endgame it
is before the deadline and of which it is no finishing kind, that its finish chance falls
short under. -/
def lateBy (env : QueueEnv) (now : Time) (s : QueueState) (task : Task) :
    List TimeBox → Option Deferral
  | [] => none
  | box :: rest =>
    let left := box.deadlineAt - now
    if left ≤ 0 ∨ now < box.deadlineAt - box.slackS ∨ box.finishingKinds.contains task.kind then
      lateBy env now s task rest
    else
      match finishChance env s task left with
      | some chance =>
        if chance < finishChancePct then
          some { cause := { cause := "cannot_finish", needS := some (blevel env s task),
                            leftS := some left, flowCall := box.flowCall } }
        else lateBy env now s task rest
      | none => lateBy env now s task rest

/-- The late tasks, by id, each with its deferral (`_late`). -/
def lateTasks (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) :
    List (String × Deferral) :=
  s.queued.filterMap fun e =>
    if startable now s e then
      (lateBy env now s e.task (boxes cfg e.task)).map fun why => (e.task.id, why)
    else none

/-! ## Finishing -/

/-- Ask `skip` about each of `tasks` that waits for its fingerprint until it starts, is
queued, was not asked, has started no attempt, and whose dependencies are done
(`_skip_startable`): one that `skip` accepts leaves the queue and waits to finish as
`skipped`. -/
def skipStartable (env : QueueEnv) (s : QueueState) : List String → QueueState
  | [] => s
  | id :: rest =>
    match s.queued.find? (·.task.id == id) with
    | none => skipStartable env s rest
    | some e =>
      if e.task.fingerprintAtStart ∧ ¬ e.asked ∧ e.attempt = 0
          ∧ e.task.after.all (s.doneKeys.contains ·) then
        let started := env.starting e.task
        if env.skip started then
          skipStartable env ((s.dequeue id).push (TaskResult.skipped started) 0) rest
        else
          skipStartable env
            { s with queued := s.queued.map fun q => if q.task.id == id then { q with asked := true } else q }
            rest
      else skipStartable env s rest

/-- Queue one task (`add`), while a drain is under way: whether it was accepted. A task
whose id is known is left; one whose key is in flight is refused; one that `skip` accepts
waits to finish as `skipped`. -/
def addCore (env : QueueEnv) (s : QueueState) (task : Task) : QueueState × Bool :=
  if s.known.contains task.id then (s, false)
  else
    let seq := s.nextSeq
    let s := { s with known := task.id :: s.known, nextSeq := seq + 1 }
    if s.inflight.contains task.key then (s.report (.duplicateKeyRefused task), false)
    else
      let s := { s with inflight := task.key :: s.inflight }.report (.queued task)
      if ¬ task.fingerprintAtStart ∧ env.skip task then
        (s.push (TaskResult.skipped task) 0, true)
      else
        let s := { s with queued := s.queued ++ [{ task := task, seq := seq }] }
        (skipStartable env s [task.id], true)

/-- Queue follow-up work (`extend`), while a drain is under way: a task refused for its key
waits to finish as `duplicate_key`. -/
def extendCore (env : QueueEnv) (s : QueueState) : List Task → QueueState
  | [] => s
  | task :: rest =>
    if s.known.contains task.id then extendCore env s rest
    else
      match addCore env s task with
      | (s, true) => extendCore env s rest
      | (s, false) => extendCore env (s.push (TaskResult.duplicateKey task) 0) rest

/-- Close one task (`_finish`): its key is done and no longer in flight, unless it is a
refused duplicate, whose key is the other task's; a task
that launched, or was skipped or cancelled, is reported as ended; its follow-ups are
queued; and the queued tasks after it may be skipped now. -/
def finishOne (env : QueueEnv) (s : QueueState) (p : Settling) : QueueState :=
  let res := p.result
  let duplicate := res.stop == Stop.duplicateKey
  let s := if duplicate then s
    else
      { s with
        inflight := s.inflight.filter (· != res.task.key)
        doneKeys := if s.doneKeys.contains res.task.key then s.doneKeys else res.task.key :: s.doneKeys }
  let s := if duplicate ∨ res.stop == Stop.deferred then s else s.report (.ended res p.attempt)
  let s := s.report (.finished res)
  let s := extendCore env s (env.followUp res)
  if duplicate then s else skipStartable env s ((s.successors res.task.key).map (·.task.id))

/-- Finish the results that wait, and those their follow-ups add (`_settle`), at most `fuel`
of them. -/
def drain (env : QueueEnv) : Nat → QueueState → QueueState
  | 0, s => s
  | fuel + 1, s =>
    match s.settling with
    | [] => s
    | p :: rest => drain env fuel (finishOne env { s with settling := rest } p)

/-- Finish a result now (`_settle`, with no drain under way). -/
def settle (env : QueueEnv) (s : QueueState) (result : TaskResult) (attempt : Nat) : QueueState :=
  drain env env.fuel (s.push result attempt)

/-- A queued task is not launched (`_defer`): reported as deferred, then finished as such.
The task has left the queue. -/
def defer (env : QueueEnv) (s : QueueState) (task : Task) (why : Deferral) : QueueState :=
  settle env (s.report (.deferred task (some why.cause))) (TaskResult.deferred task why) 0

def deferEach (env : QueueEnv) (s : QueueState) : List (Task × Deferral) → QueueState
  | [] => s
  | (task, why) :: rest => deferEach env (defer env s task why) rest

/-- Take each of `tasks` out of the queue, then defer them one by one. -/
def deferAll (env : QueueEnv) (s : QueueState) (tasks : List (Task × Deferral)) : QueueState :=
  deferEach env (tasks.foldl (fun s tw => s.dequeue tw.1.id) s) tasks

/-! ## What the queue is told -/

/-- Queue one task (`add`). -/
def add (env : QueueEnv) (s : QueueState) (task : Task) : QueueState × Bool :=
  let (s, accepted) := addCore env s task
  (drain env env.fuel s, accepted)

/-- Queue tasks (`extend`), each finished as far as it goes before the next. -/
def extend (env : QueueEnv) (s : QueueState) : List Task → QueueState
  | [] => s
  | task :: rest =>
    if s.known.contains task.id then extend env s rest
    else
      match add env s task with
      | (s, true) => extend env s rest
      | (s, false) => extend env (settle env s (TaskResult.duplicateKey task) 0) rest

/-- Cancel the task of `key` (`cancel`): whether one was queued or running. One queued
finishes `cancelled` now; one running is marked, and is not retried. -/
def cancel (env : QueueEnv) (s : QueueState) (key : Key) : QueueState × Bool :=
  match s.queued.find? (·.task.key == key) with
  | some e =>
    let result := TaskResult.cancelled e.task
    (settle env ((s.dequeue e.task.id).report (.result result 0)) result e.attempt, true)
  | none =>
    if s.running.any (·.task.key == key) then
      ({ s with running := s.running.map fun r =>
          if r.task.key == key then { r with cancelled := true } else r }, true)
    else (s, false)

/-! ## A pass -/

/-- Defer every queued task that a time box no longer lets launch (`_defer_closed`). -/
def deferClosed (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) : QueueState :=
  deferAll env s (s.queued.filterMap fun e => (closed cfg now e.task).map fun why => (e.task, why))

/-- Each task's wait starts when a pass first finds its dependencies done. -/
def markReady (now : Time) (s : QueueState) : QueueState :=
  { s with queued := s.queued.map fun e =>
      if e.readySince.isNone ∧ startable now s e then { e with readySince := some now } else e }

/-- The pass's memory as it goes down the order: the first task that could not start for
what it needs, whether the starvation guard holds its place, and how many tasks the pass
started. -/
structure Sweep where
  head : Option Task := none
  guarded : Bool := false
  started : Nat := 0

/-- Go down the order (`_start_ready`'s loop). Each task still queued starts when a slot is
free, no box closed it, its dependencies are done, what it needs is free, the starvation
guard does not hold it back and the runner does not defer it. When every slot is taken and
the pass started a task, the late tasks it did not reach are deferred. -/
def sweep (cfg : QueueConfig) (env : QueueEnv) (now : Time) (late : List (String × Deferral)) :
    List QueueEntry → Sweep → QueueState → QueueState
  | [], _, s => s
  | e :: rest, w, s =>
    if s.running.length ≥ slots cfg now s then
      if w.started > 0 then
        let ids := (e :: rest).map (·.task.id)
        deferAll env s (s.queued.filterMap fun q =>
          if ids.contains q.task.id then (late.lookup q.task.id).map fun why => (q.task, why) else none)
      else s
    else
      match s.queued.find? (·.task.id == e.task.id) with
      | none => sweep cfg env now late rest w s
      | some e =>
        if (closed cfg now e.task).isSome then sweep cfg env now late rest w s
        else if ¬ startable now s e then sweep cfg env now late rest w s
        else if ¬ free env s e.task then
          match w.head with
          | none =>
            sweep cfg env now late rest
              { w with head := some e.task, guarded := overdue cfg now e && possible env e.task } s
          | some _ => sweep cfg env now late rest w s
        else if w.guarded ∧ (w.head.map (takes env s e.task)).getD false then
          sweep cfg env now late rest w s
        else
          match env.deferral e.task with
          | some why => sweep cfg env now late rest w (defer env (s.dequeue e.task.id) e.task why)
          | none =>
            let task := if e.task.fingerprintAtStart then env.starting e.task else e.task
            let attempt := e.attempt + 1
            let s := s.dequeue e.task.id
            let s := s.report (.start task attempt (s.running.length + 1) (slots cfg now s))
            let s := { s with running := s.running ++
              [{ e with task := task, attempt := attempt, readySince := none, notBefore := none }] }
            sweep cfg env now late rest { w with started := w.started + 1 } s

/-- Whether `a` comes before `b` in the order, or with it. -/
def orderLe (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState)
    (a b : QueueEntry) : Bool :=
  lexLe (orderKey cfg env now s a) (orderKey cfg env now s b)

/-- One pass (`_start_ready`) at `now`: defer what a time box closed, then go down the
order, the late tasks last. -/
def pass (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) : QueueState :=
  let s := markReady now (deferClosed cfg env now s)
  let late := lateTasks cfg env now s
  let order := s.queued.mergeSort (orderLe cfg env now s)
  let isLate := fun (e : QueueEntry) => (late.lookup e.task.id).isSome
  sweep cfg env now late (order.filter (! isLate ·) ++ order.filter isLate) {} s

/-! ## A task ends -/

/-- A running task ends with `outcome` (`_on_done`), at `now`. A `deferred` outcome
finishes as a deferral. Else the result is recorded, two throttled results in a row halve
the slots for `throttleS`, and the task is queued again, first, after `waitS`, when its
stop is one to retry, the result is retryable, it started one attempt, no box of its is
past its deadline, and it was not cancelled. Else it finishes. -/
def done (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) : QueueState :=
  match s.running.find? (·.task.id == id) with
  | none => s
  | some e =>
    let s := { s with running := s.running.filter (·.task.id != id) }
    let result : TaskResult :=
      { task := e.task, ok := outcome.ok, stop := outcome.stop, cause := outcome.cause,
        retryable := outcome.retryable }
    if outcome.stop == Stop.deferred then
      settle env (s.report (.deferred e.task outcome.cause)) result e.attempt
    else
      let s := s.report (.result result e.attempt)
      let s :=
        if cfg.throttleOn.contains outcome.stop then
          let s := { s with consecThrottled := s.consecThrottled + 1 }
          if s.consecThrottled ≥ 2 ∧ ¬ throttled now s then
            let s := { s with throttledUntil := some (now + cfg.throttleS) }
            s.report (.throttle e.task (slots cfg now s))
          else s
        else { s with consecThrottled := 0 }
      let pastADeadline := (boxes cfg e.task).any fun box => decide (now ≥ box.deadlineAt)
      if cfg.retryOn.contains outcome.stop ∧ outcome.retryable ∧ e.attempt < 2 ∧ ¬ pastADeadline
          ∧ ¬ e.cancelled then
        let s := s.report (.retry e.task outcome.stop waitS)
        { s with queued := { e with notBefore := some (now + waitS), readySince := none } :: s.queued }
      else settle env s result e.attempt

/-! ## The loop -/

/-- When the next retry wait ends, if a queued task waits for one (`_sleep_until_retry`). -/
def nextRetry (now : Time) (s : QueueState) : Option Time :=
  (s.queued.filterMap fun e => e.notBefore.filter fun t => decide (t > now)).foldl
    (fun best t =>
      match best with
      | none => some t
      | some b => some (min b t))
    none

/-- Nothing can launch what is queued (`_defer_all`): each task is deferred, its
dependency never queued. -/
def giveUp (env : QueueEnv) (s : QueueState) : QueueState :=
  deferAll env s (s.queued.map fun e =>
    (e.task, { cause := { cause := "dependency_not_queued" } }))

/-- What the loop of `run_async` does once a pass took the queue from `before` to `after`.
`again`: the pass finished a task, so it makes another pass. `wait`: tasks run. `retryAt`:
nothing runs and a queued task waits for its retry. `giveUp`: nothing runs, the pass
started and finished nothing, and no retry is waited for. `stop`: nothing is queued or
running. -/
inductive AfterPass where
  | again
  | wait
  | retryAt (t : Time)
  | giveUp
  | stop
  deriving Repr

def afterPass (now : Time) (before after : QueueState) : AfterPass :=
  if after.finishedCount ≠ before.finishedCount then .again
  else if ¬ after.running.isEmpty then .wait
  else if after.queued.isEmpty then .stop
  else
    match nextRetry now after with
    | some t => .retryAt t
    | none => .giveUp

end Contraagent
