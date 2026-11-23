import Contraagent.Backends.Launch

/-!
# A launch does not end with a stop of a task's own

A task that was not launched ends `deferred`, `skipped`, `cancelled` or `duplicate_key`.
No launch ends with one of these (`launchStops_not_own`): a result with such a stop is of a
task that nothing launched for, and a result of a launch is never taken for one.
-/

namespace Contraagent

/-- The stops of a task that was not launched. -/
def notLaunchedStops : List Stop :=
  [Stop.deferred, Stop.skipped, Stop.cancelled, Stop.duplicateKey]

/-- No launch ends with a stop of a task that was not launched. -/
theorem launchStops_not_own : ∀ stop ∈ launchStops, stop ∉ notLaunchedStops := by decide

/-- No launch ends `deferred`. -/
theorem launchStops_not_deferred {stop : Stop} (launched : stop ∈ launchStops) : stop ≠ Stop.deferred :=
  fun eq => launchStops_not_own stop launched (by rw [eq]; decide)

/-- info: 'Contraagent.launchStops_not_own' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms launchStops_not_own

end Contraagent
