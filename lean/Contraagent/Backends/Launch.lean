import Contraagent.Dispatch.Task

/-!
# The stops of a launch

What `Stop` of `src/contraagent/_internal/backends/launch.py` names: why one launch of a
coding agent ended. The result of a task holds one of these, or one of a task's own
(`Stop.named`): `partial`, `skipped`, `deferred`, `cancelled` or `duplicate_key`.

Left out: everything else of a launch (its command, its limits, its transcript and what it
spent).
-/

namespace Contraagent

/-- The stops a launch ends with (the members of `Stop` in `launch.py`), in its order. -/
def launchStops : List Stop :=
  ["completed", "timeout", "max_turns", "budget", "context_budget", "stalled", "auth_failed", "api_error",
    "rate_limited", "refused", "aborted", "denied", "error", "no_output", "launch_failed", "invalid_output",
    "invalid_input", "credential_mismatch"]

end Contraagent
