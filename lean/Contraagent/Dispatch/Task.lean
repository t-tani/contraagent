import Contraagent.Dispatch.Records

/-!
# The task envelope

What `src/contraagent/_internal/dispatch/task.py` defines, with the fields the schedulers
decide by: a task, its result, a time box and a deferral. A field that only travels with a
task or a result is left out: its params and payload, a launch's record, and the one line
that words a result or a deferral for a reader (`reason`).
-/

namespace Contraagent

/-- A task's stable identity (`Task.key`): what `after` names, and what a resumed run
recognizes as the same work. -/
abbrev Key := String

/-- The class of work (`Task.kind`). The schedulers compare kinds and never interpret one. -/
abbrev Kind := String

/-- A reading of the queue's clock (`time.monotonic()`), in the unit of `Duration`: readings
are compared with each other and moved by a `Duration`, nothing else. -/
abbrev Time := Int

/-- How a task ended (`TaskResult.stop`): one of the values `task.py` names, below, or one
that a domain adds. The schedulers compare stop values and never interpret another one. -/
abbrev Stop := String

namespace Stop

def completed : Stop := "completed"
def error : Stop := "error"
/-- A resume skipped it. -/
def skipped : Stop := "skipped"
def launchFailed : Stop := "launch_failed"
def invalidInput : Stop := "invalid_input"
def invalidOutput : Stop := "invalid_output"
/-- Not launched: past a deadline, its work too long to finish before it, or with no way to
launch. -/
def deferred : Stop := "deferred"
/-- Not queued: a task with the same key was in flight. -/
def duplicateKey : Stop := "duplicate_key"
/-- A task that did part of its work: ok, and a resume runs it again. -/
def «partial» : Stop := "partial"
/-- A cancellable task that no flow call waits for any longer. -/
def cancelled : Stop := "cancelled"

/-- The stop values `task.py` names (its `STOP_*` constants), in its order. -/
def named : List Stop :=
  [completed, error, skipped, launchFailed, invalidInput, invalidOutput, deferred, duplicateKey,
    «partial», cancelled]

end Stop

/-- A deadline over the tasks of one flow call and of the flow calls it starts (`TimeBox`).
From `deadlineAt` on, only `finishingKinds` still launch, for `graceS`; from
`deadlineAt - slackS` on, the queue orders its tasks for the deadline. `flowCall` is the
flow call it bounds, `none` for the queue's own deadline over the whole run. -/
structure TimeBox where
  deadlineAt : Time
  deadlineS : Duration
  graceS : Duration
  slackS : Duration := 0
  finishingKinds : List Kind := []
  flowCall : Option FlowCallId := none
  deriving DecidableEq, Repr

/-- Why a task is not launched (`Deferral`). -/
structure Deferral where
  cause : DeferralCause
  deriving DecidableEq, Repr

/-- One schedulable unit of work (`Task`). `id` is fresh for each task and names it in the
queue's own bookkeeping; `key` is the identity of its work, which `after` names. `key` and
`unit` are as the code leaves them once the task is built: neither is empty. `fingerprint`
is empty for a task whose builder gives none. -/
structure Task where
  kind : Kind
  unit : String
  after : List Key := []
  claims : List String := []
  timeBoxes : List TimeBox := []
  rerunOnResume : Bool := false
  estimateS : Option Duration := none
  tailS : Option Duration := none
  /-- A tie-breaker in the queue's order, higher first: only compared. -/
  priority : Int := 0
  attempt : Nat := 0
  id : String
  key : Key
  fingerprint : String := ""
  fingerprintAtStart : Bool := false
  /-- A digest of each part of what the fingerprint covers, by the part's name. -/
  fingerprintParts : List (String × String) := []
  cancellable : Bool := false
  deriving DecidableEq, Repr

/-- A task's final result: how its last attempt ended (`TaskResult`). `cause` is a deferred
result's cause, `none` for any other result. -/
structure TaskResult where
  task : Task
  ok : Bool
  stop : Stop
  cause : Option DeferralCause := none
  retryable : Bool := true
  deriving DecidableEq, Repr

namespace TaskResult

/-- The result of a task that a resume skipped. -/
def skipped (task : Task) : TaskResult :=
  { task := task, ok := true, stop := Stop.skipped }

/-- The result of a task that was not launched. -/
def deferred (task : Task) (deferral : Deferral) : TaskResult :=
  { task := task, ok := false, stop := Stop.deferred, cause := some deferral.cause }

/-- The result of a task cancelled before it launched. -/
def cancelled (task : Task) : TaskResult :=
  { task := task, ok := false, stop := Stop.cancelled }

/-- The result of a task that was not queued: its key was in flight. -/
def duplicateKey (task : Task) : TaskResult :=
  { task := task, ok := false, stop := Stop.duplicateKey }

def launchFailed (task : Task) : TaskResult :=
  { task := task, ok := false, stop := Stop.launchFailed }

end TaskResult

end Contraagent
