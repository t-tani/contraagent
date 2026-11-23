/-!
# The facts a run records

What `src/contraagent/_internal/dispatch/records.py` defines, with the fields the schedulers
decide by: why a task was deferred.
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

end Contraagent
