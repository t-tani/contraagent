import Contraagent.Dispatch.Queue

/-!
# The states a queue reaches

The states the theorems about the queue speak of, and what holds of a task as it starts:
the queue takes only the fingerprint of the task its runner gives then (`QueueEnv.started`),
so the task that starts has the id, the key, the dependencies and the claims of the task
the queue held. The theorems therefore assume nothing of the runner.
-/

namespace Contraagent

/-- A task as it starts has the key the queue held it by. -/
theorem QueueEnv.started_key (env : QueueEnv) (task : Task) : (env.started task).key = task.key := rfl

/-- A task as it starts comes after the tasks it came after. -/
theorem QueueEnv.started_after (env : QueueEnv) (task : Task) : (env.started task).after = task.after := rfl

/-- A task as it starts has the id the queue held it by. -/
theorem QueueEnv.started_id (env : QueueEnv) (task : Task) : (env.started task).id = task.id := rfl

/-- A task as it starts claims the names it claimed. -/
theorem QueueEnv.started_claims (env : QueueEnv) (task : Task) : (env.started task).claims = task.claims := rfl

/-- The states a queue reaches: it starts empty, and each step is something it is told
(`add`, `extend`, `cancel`), a pass, a task's end, or giving up what nothing can launch,
at any time and with any answers of its callbacks. -/
inductive Reachable (cfg : QueueConfig) : QueueState → Prop where
  | start : Reachable cfg {}
  | added (env : QueueEnv) (s : QueueState) (task : Task) :
      Reachable cfg s → Reachable cfg (add env s task).1
  | extended (env : QueueEnv) (s : QueueState) (tasks : List Task) :
      Reachable cfg s → Reachable cfg (extend env s tasks)
  | cancelled (env : QueueEnv) (s : QueueState) (key : Key) :
      Reachable cfg s → Reachable cfg (cancel env s key).1
  | passed (env : QueueEnv) (now : Time) (s : QueueState) :
      Reachable cfg s → Reachable cfg (pass cfg env now s)
  | ended (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
      (outcome : Outcome) (waitS : Duration) :
      Reachable cfg s → Reachable cfg (done cfg env now s id outcome waitS)
  | gaveUp (env : QueueEnv) (s : QueueState) :
      Reachable cfg s → Reachable cfg (giveUp env s)

end Contraagent
