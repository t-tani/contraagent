/-!
# The facts a run records

What `src/contraagent/_internal/dispatch/records.py` defines, with the fields the schedulers
decide by: why a task was deferred, what `services.jsonl` records of a service, a quota
reading and why a credential rests.
-/

namespace Contraagent

/-- A flow call's id: `0`, `0.1`, `0.1.2`. -/
abbrev FlowCallId := String

/-- A length of time: the code's fields named `_s`. Its unit is left open: lengths are
added and compared, nothing else. -/
abbrev Duration := Int

/-- Why a task was deferred, as data (`DeferralCause`). `cause` is `deadline`,
`grace_window`, `cannot_finish` (with `needS` and `leftS`), `dependency_not_queued`,
`no_capacity`, `dependency_cycle`, or a runner's own name (`rest`). `flowCall` names the
time box when the deadline is a flow call's, not the run's. -/
structure DeferralCause where
  cause : String
  needS : Option Duration := none
  leftS : Option Duration := none
  flowCall : Option FlowCallId := none
  deriving DecidableEq, Repr

/-- Why a service stopped (`ServiceStopCause`): the run ended, or a signal stopped the run. -/
inductive ServiceStopCause where
  | runEnd
  | interrupted
  deriving DecidableEq, Repr

/-- One line of `services.jsonl` (`ServiceEvent`). A service started for the task of `key`
and gave `address`, or did not start (`error`); or it stopped, and `error` is what its stop
raised. -/
inductive ServiceEvent where
  | start (name : String) (key : String) (address : Option String) (error : Option String)
  | stop (name : String) (cause : ServiceStopCause) (error : Option String)
  deriving DecidableEq, Repr

/-- One window of a quota reading (`QuotaWindow`): its utilization in percent and when it
resets. -/
structure QuotaWindow where
  pct : Option Int := none
  resetsAt : Option Int := none
  deriving DecidableEq, Repr

/-- A subscription's utilization as a coding agent reported it (`QuotaReading`), with the
fields the rests decide by. `fiveHour` and `sevenDay` are the fields of those two windows;
`windows` is every window the reading names besides, by name, in order. -/
structure QuotaReading where
  observedAt : Option Int := none
  credential : String := ""
  account : String := ""
  fiveHour : QuotaWindow := {}
  sevenDay : QuotaWindow := {}
  windows : List (String × QuotaWindow) := []
  deriving DecidableEq, Repr

/-- Why a credential rests (`Rest`): past the cap of a window (`window`, `pct`, `cap`), by
the quota rule (`rule`), or because a launch as it was refused (`stop` is `auth_failed`) on
a coding agent and a model. `until`: when the rest ends, `none` when unknown and for a
refused credential. -/
structure Rest where
  credential : String
  window : String := ""
  pct : Option Int := none
  cap : Option Int := none
  rule : String := ""
  «until» : Option Int := none
  account : String := ""
  stop : String := ""
  agent : String := ""
  model : String := ""
  deriving DecidableEq, Repr

end Contraagent
