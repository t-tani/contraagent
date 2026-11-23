import Contraagent.Dispatch.Queue.Reachable

/-!
# A claim capacity is not passed

Of the description of the work queue: while the capacity of a claim name is the number `n`
at every pass, at most `n` running tasks hold the name (`ReachableWithin.capacity`). Only a
pass starts a task, and it starts one only while every name the task claims has room
(`free`); everything else the queue does leaves the running tasks as they are, or ends one.

The assumption is about the runner: the task it gives as a task starts claims the names of
the task it was given (`QueueEnv.KeepsClaims`).
-/

namespace Contraagent

/-- The runner gives a task as it starts with the claims it was given. -/
def QueueEnv.KeepsClaims (env : QueueEnv) : Prop :=
  ∀ task, (env.starting task).claims = task.claims

namespace QueueState

theorem held_of_running {s s' : QueueState} (same : s'.running = s.running) (name : String) :
    s'.held name = s.held name := by
  unfold held
  rw [same]

end QueueState

/-! ## What leaves the running tasks as they are -/

theorem skipStartable_running (env : QueueEnv) : ∀ (ids : List String) (s : QueueState),
    (skipStartable env s ids).running = s.running := by
  intro ids
  induction ids with
  | nil => intro s; rfl
  | cons id rest ih =>
    intro s
    unfold skipStartable
    split
    · exact ih s
    · split
      · dsimp only
        split
        · exact ih _
        · exact ih _
      · exact ih s

theorem addCore_running (env : QueueEnv) (s : QueueState) (task : Task) :
    (addCore env s task).1.running = s.running := by
  unfold addCore
  split
  · rfl
  · dsimp only
    split
    · rfl
    · split
      · rfl
      · exact skipStartable_running env _ _

theorem extendCore_running (env : QueueEnv) : ∀ (tasks : List Task) (s : QueueState),
    (extendCore env s tasks).running = s.running := by
  intro tasks
  induction tasks with
  | nil => intro s; rfl
  | cons task rest ih =>
    intro s
    unfold extendCore
    split
    · exact ih s
    · have one := addCore_running env s task
      split
      · rename_i s' eq
        rw [eq] at one
        exact (ih s').trans one
      · rename_i s' eq
        rw [eq] at one
        exact (ih _).trans one

theorem finishOne_running (env : QueueEnv) (s : QueueState) (p : Settling) :
    (finishOne env s p).running = s.running := by
  have marked : (reportEnd (markDone s p.result) p).running = s.running := by
    unfold reportEnd markDone
    dsimp only
    repeat' split
    all_goals rfl
  unfold finishOne
  dsimp only
  split
  · exact (extendCore_running env _ _).trans marked
  · exact (skipStartable_running env _ _).trans ((extendCore_running env _ _).trans marked)

theorem drain_running (env : QueueEnv) : ∀ (fuel : Nat) (s : QueueState), (drain env fuel s).running = s.running := by
  intro fuel
  induction fuel with
  | zero => intro s; rfl
  | succ fuel ih =>
    intro s
    unfold drain
    split
    · rfl
    · exact (ih _).trans (finishOne_running env _ _)

theorem settle_running (env : QueueEnv) (s : QueueState) (result : TaskResult) (attempt : Nat) :
    (settle env s result attempt).running = s.running :=
  drain_running env env.fuel _

theorem defer_running (env : QueueEnv) (s : QueueState) (task : Task) (why : Deferral) :
    (defer env s task why).running = s.running :=
  settle_running env _ _ _

theorem deferEach_running (env : QueueEnv) : ∀ (tasks : List (Task × Deferral)) (s : QueueState),
    (deferEach env s tasks).running = s.running := by
  intro tasks
  induction tasks with
  | nil => intro s; rfl
  | cons tw rest ih =>
    intro s
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    exact (ih _).trans (defer_running env s task why)

theorem dequeued_running (tasks : List (Task × Deferral)) : ∀ s : QueueState,
    (tasks.foldl (fun s tw => s.dequeue tw.1.id) s).running = s.running := by
  induction tasks with
  | nil => intro s; rfl
  | cons tw rest ih => intro s; exact ih _

theorem deferAll_running (env : QueueEnv) (s : QueueState) (tasks : List (Task × Deferral)) :
    (deferAll env s tasks).running = s.running :=
  (deferEach_running env tasks _).trans (dequeued_running tasks s)

/-! ## A pass -/

/-- A task that starts while what it needs is free leaves each name within its capacity:
it takes one place on each name it claims, and each had room. -/
theorem start_within (env : QueueEnv) (s s' : QueueState) (found entry : QueueEntry) (name : String) (n : Nat)
    (cap : env.capacity name = .number n) (isFree : free env s found.task = true)
    (claims : entry.task.claims = found.task.claims) (running : s'.running = s.running ++ [entry])
    (within : s.held name ≤ n) : s'.held name ≤ n := by
  unfold QueueState.held at within ⊢
  rw [running, List.countP_append, List.countP_singleton, claims]
  by_cases claimed : found.task.claims.contains name = true
  · have room : s.held name < n := by
      unfold free at isFree
      simp only [Bool.and_eq_true, List.all_eq_true, decide_eq_true_eq] at isFree
      have here := isFree.2 name (by simpa using claimed)
      rw [cap] at here
      exact here
    unfold QueueState.held at room
    simp only [claimed, ↓reduceIte]
    omega
  · simp only [claimed, Bool.false_eq_true, ↓reduceIte]
    omega

/-- Going down the order keeps a name within its capacity. -/
theorem sweep_held (cfg : QueueConfig) (env : QueueEnv) (claims : env.KeepsClaims) (now : Time)
    (late : List (String × Deferral)) (name : String) (n : Nat) (cap : env.capacity name = .number n) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      s.held name ≤ n → (sweep cfg env now late order w s).held name ≤ n := by
  intro order
  induction order with
  | nil => intro w s h; unfold sweep; exact h
  | cons e rest ih =>
    intro w s h
    unfold sweep
    split
    · split
      · dsimp only
        rw [QueueState.held_of_running (deferAll_running env s _)]
        exact h
      · exact h
    · split
      · exact ih w s h
      · rename_i _ found isFound
        repeat' split
        all_goals first
          | exact ih _ s h
          | (apply ih
             rw [QueueState.held_of_running (defer_running env _ _ _)]
             exact h)
          | (apply ih
             refine start_within env s _ found _ name n cap (Decidable.of_not_not ‹_›) ?_ rfl h
             first | exact claims found.task | rfl)

theorem pass_held (cfg : QueueConfig) (env : QueueEnv) (claims : env.KeepsClaims) (now : Time) (s : QueueState)
    (name : String) (n : Nat) (cap : env.capacity name = .number n) (within : s.held name ≤ n) :
    (pass cfg env now s).held name ≤ n := by
  unfold pass
  dsimp only
  apply sweep_held cfg env claims now _ name n cap
  have same : (markReady now (deferClosed cfg env now s)).running = s.running := deferAll_running env s _
  rw [QueueState.held_of_running same]
  exact within

/-! ## Everything else the queue does -/

theorem add_running (env : QueueEnv) (s : QueueState) (task : Task) : (add env s task).1.running = s.running :=
  (drain_running env env.fuel _).trans (addCore_running env s task)

theorem extend_running (env : QueueEnv) : ∀ (tasks : List Task) (s : QueueState),
    (extend env s tasks).running = s.running := by
  intro tasks
  induction tasks with
  | nil => intro s; rfl
  | cons task rest ih =>
    intro s
    unfold extend
    split
    · exact ih s
    · have one := add_running env s task
      split
      · rename_i s' eq
        rw [eq] at one
        exact (ih s').trans one
      · rename_i s' eq
        rw [eq] at one
        exact (ih _).trans ((settle_running env _ _ _).trans one)

/-- Cancelling a task starts none. -/
theorem cancel_held (env : QueueEnv) (s : QueueState) (key : Key) (name : String) :
    (cancel env s key).1.held name = s.held name := by
  unfold cancel
  split
  · exact QueueState.held_of_running (settle_running env _ _ _) name
  · split
    · unfold QueueState.held
      dsimp only
      rw [List.countP_map]
      congr 1
      funext r
      dsimp only [Function.comp]
      split <;> rfl
    · rfl

theorem countThrottle_running (cfg : QueueConfig) (now : Time) (task : Task) (stop : Stop) (s : QueueState) :
    (countThrottle cfg now task stop s).running = s.running := by
  unfold countThrottle
  split
  · dsimp only
    split <;> rfl
  · rfl

/-- A task's end leaves the running tasks as they are, or without the task that ended. -/
theorem done_running (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) :
    (done cfg env now s id outcome waitS).running = s.running ∨
      (done cfg env now s id outcome waitS).running = s.running.filter (·.task.id != id) := by
  unfold done
  split
  · exact Or.inl rfl
  · right
    dsimp only
    split
    · exact settle_running env _ _ _
    · split
      · exact countThrottle_running cfg now _ _ _
      · exact (settle_running env _ _ _).trans (countThrottle_running cfg now _ _ _)

/-- A task's end starts none: it leaves those that run. -/
theorem done_held (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) (name : String) :
    (done cfg env now s id outcome waitS).held name ≤ s.held name := by
  rcases done_running cfg env now s id outcome waitS with same | fewer
  · rw [QueueState.held_of_running same]
    exact Nat.le_refl _
  · unfold QueueState.held
    rw [fewer]
    exact List.filter_sublist.countP_le

theorem giveUp_running (env : QueueEnv) (s : QueueState) : (giveUp env s).running = s.running := by
  unfold giveUp
  dsimp only
  split <;> exact deferAll_running env s _

/-- The states a queue reaches while the capacity of `name` is the number `n` at every
pass, and the runner gives a task as it starts with the claims it was given. -/
inductive ReachableWithin (cfg : QueueConfig) (name : String) (n : Nat) : QueueState → Prop where
  | start : ReachableWithin cfg name n {}
  | added (env : QueueEnv) (s : QueueState) (task : Task) :
      ReachableWithin cfg name n s → ReachableWithin cfg name n (add env s task).1
  | extended (env : QueueEnv) (s : QueueState) (tasks : List Task) :
      ReachableWithin cfg name n s → ReachableWithin cfg name n (extend env s tasks)
  | cancelled (env : QueueEnv) (s : QueueState) (key : Key) :
      ReachableWithin cfg name n s → ReachableWithin cfg name n (cancel env s key).1
  | passed (env : QueueEnv) (claims : env.KeepsClaims) (cap : env.capacity name = .number n) (now : Time)
      (s : QueueState) : ReachableWithin cfg name n s → ReachableWithin cfg name n (pass cfg env now s)
  | ended (env : QueueEnv) (now : Time) (s : QueueState) (id : String) (outcome : Outcome) (waitS : Duration) :
      ReachableWithin cfg name n s → ReachableWithin cfg name n (done cfg env now s id outcome waitS)
  | gaveUp (env : QueueEnv) (s : QueueState) :
      ReachableWithin cfg name n s → ReachableWithin cfg name n (giveUp env s)

/-- While the capacity of a claim name is the number `n`, at most `n` running tasks hold
the name. -/
theorem ReachableWithin.capacity {cfg : QueueConfig} {name : String} {n : Nat} {s : QueueState}
    (reached : ReachableWithin cfg name n s) : s.held name ≤ n := by
  induction reached with
  | start => simp [QueueState.held]
  | added env s task _ ih => rw [QueueState.held_of_running (add_running env s task)]; exact ih
  | extended env s tasks _ ih => rw [QueueState.held_of_running (extend_running env tasks s)]; exact ih
  | cancelled env s key _ ih => rw [cancel_held]; exact ih
  | passed env claims cap now s _ ih => exact pass_held cfg env claims now s name n cap ih
  | ended env now s id outcome waitS _ ih => exact Nat.le_trans (done_held cfg env now s id outcome waitS name) ih
  | gaveUp env s _ ih => rw [QueueState.held_of_running (giveUp_running env s)]; exact ih

/-- info: 'Contraagent.ReachableWithin.capacity' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms ReachableWithin.capacity

end Contraagent
