import Contraagent.Dispatch.Queue

/-!
# The states a queue reaches

What the theorems about the queue assume of its runner, and the states they speak of.
-/

namespace Contraagent

/-- The runner gives a task as it starts with the key it was given. -/
def QueueEnv.KeepsKey (env : QueueEnv) : Prop :=
  ∀ task, (env.starting task).key = task.key

/-- The runner gives a task as it starts with the dependencies it was given. -/
def QueueEnv.KeepsAfter (env : QueueEnv) : Prop :=
  ∀ task, (env.starting task).after = task.after

/-- What is assumed of the runner: the task it gives as a task starts (`starting`) is the
task it was given, its fingerprint completed. It has the same key and comes after the same
tasks. -/
structure QueueEnv.Keeps (env : QueueEnv) : Prop where
  key : env.KeepsKey
  after : env.KeepsAfter

/-- The states a queue reaches: it starts empty, and each step is something it is told
(`add`, `extend`, `cancel`), a pass, a task's end, or giving up what nothing can launch,
at any time and with any answers of its callbacks, as long as the runner gives a task as
it starts with the key and the dependencies it was given (`QueueEnv.Keeps`). -/
inductive Reachable (cfg : QueueConfig) : QueueState → Prop where
  | start : Reachable cfg {}
  | added (env : QueueEnv) (keeps : env.Keeps) (s : QueueState) (task : Task) :
      Reachable cfg s → Reachable cfg (add env s task).1
  | extended (env : QueueEnv) (keeps : env.Keeps) (s : QueueState) (tasks : List Task) :
      Reachable cfg s → Reachable cfg (extend env s tasks)
  | cancelled (env : QueueEnv) (keeps : env.Keeps) (s : QueueState) (key : Key) :
      Reachable cfg s → Reachable cfg (cancel env s key).1
  | passed (env : QueueEnv) (keeps : env.Keeps) (now : Time) (s : QueueState) :
      Reachable cfg s → Reachable cfg (pass cfg env now s)
  | ended (env : QueueEnv) (keeps : env.Keeps) (now : Time) (s : QueueState) (id : String)
      (outcome : Outcome) (waitS : Duration) :
      Reachable cfg s → Reachable cfg (done cfg env now s id outcome waitS)
  | gaveUp (env : QueueEnv) (keeps : env.Keeps) (s : QueueState) :
      Reachable cfg s → Reachable cfg (giveUp env s)

end Contraagent
