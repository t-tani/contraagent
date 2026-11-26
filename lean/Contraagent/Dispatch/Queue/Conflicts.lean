import Contraagent.Dispatch.Queue.Capacity

/-!
# No task runs beside one it conflicts with

Of the description of the work queue: while the conflict relation is `c` at every pass, of
every two running tasks, the one that started later does not conflict with the other
(`ReachableApart.apart`); with a relation that does not depend on the order of its two
tasks, neither conflicts with the other (`ReachableApart.apart_both`). Only a pass starts a
task, and it starts one only while no running task conflicts with it (`apart`, a part of
`free`); everything else the queue does leaves the running tasks as they are, or ends one.

A task as it starts is the task the queue held with its fingerprint completed
(`QueueEnv.started`), so the relation is assumed to read no fingerprint
(`ReadsNoFingerprint`). The code's reads, of each task, its working directory and its
`changes` patterns, which the task graph holds by its key.
-/

namespace Contraagent

/-- A relation between tasks that reads none of what `QueueEnv.started` completes of its
first task: the fingerprint, the outside state's digest and the fingerprint's parts. -/
def ReadsNoFingerprint (c : Task → Task → Bool) : Prop :=
  ∀ (t u : Task) (fingerprint outside : String) (parts : List (String × String)),
    c { t with fingerprint := fingerprint, outside := outside, fingerprintParts := parts } u = c t u

theorem ReadsNoFingerprint.started {c : Task → Task → Bool} (reads : ReadsNoFingerprint c)
    (env : QueueEnv) (t u : Task) : c (env.started t) u = c t u :=
  reads t u _ _ _

/-- Of every two running tasks, in the order they started, the later does not conflict with
the earlier. -/
def Apart (c : Task → Task → Bool) (s : QueueState) : Prop :=
  (s.running.map (·.task)).Pairwise fun earlier later => c later earlier = false

theorem Apart.of_running {c : Task → Task → Bool} {s s' : QueueState} (same : s'.running = s.running)
    (h : Apart c s) : Apart c s' := by
  unfold Apart
  rw [same]
  exact h

/-- With nothing running, a task is apart from every running task. -/
theorem apart_of_none_running (env : QueueEnv) (s : QueueState) (task : Task) (none : s.running = []) :
    apart env s task = true := by
  unfold apart
  rw [none]
  rfl

/-! ## A pass -/

/-- A task that starts while no running task conflicts with it keeps the running tasks
apart: the task that starts is the one the queue held, or that task with its fingerprint
completed. -/
theorem start_apart (env : QueueEnv) (c : Task → Task → Bool) (same : env.conflicts = c)
    (reads : ReadsNoFingerprint c) (s s' : QueueState) (found entry : QueueEntry)
    (isFree : free env s found.task = true)
    (started : entry.task = env.started found.task ∨ entry.task = found.task)
    (running : s'.running = s.running ++ [entry]) (h : Apart c s) : Apart c s' := by
  unfold Apart at h ⊢
  rw [running, List.map_append, List.pairwise_append]
  refine ⟨h, List.pairwise_singleton _ _, ?_⟩
  intro earlier mem later isLater
  simp only [List.map_cons, List.map_nil, List.mem_singleton] at isLater
  subst isLater
  have notConflicting : c found.task earlier = false := by
    unfold free at isFree
    simp only [Bool.and_eq_true] at isFree
    have one := isFree.2
    unfold apart at one
    rw [List.all_eq_true] at one
    obtain ⟨r, member, rfl⟩ := List.mem_map.mp mem
    have := one r member
    rw [same] at this
    simpa using this
  rcases started with isStarted | isHeld
  · rw [isStarted, reads.started env]
    exact notConflicting
  · rw [isHeld]
    exact notConflicting

/-- Going down the order keeps the running tasks apart. -/
theorem sweep_apart (cfg : QueueConfig) (env : QueueEnv) (now : Time) (late : List (String × Deferral))
    (c : Task → Task → Bool) (same : env.conflicts = c) (reads : ReadsNoFingerprint c) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      Apart c s → Apart c (sweep cfg env now late order w s) := by
  intro order
  induction order with
  | nil => intro w s h; unfold sweep; exact h
  | cons e rest ih =>
    intro w s h
    unfold sweep
    split
    · split
      · exact Apart.of_running (deferAll_running env s _) h
      · exact h
    · split
      · exact ih w s h
      · rename_i _ found isFound
        repeat' split
        all_goals first
          | exact ih _ s h
          | exact ih _ _ (Apart.of_running (defer_running env _ _ _) h)
          | (apply ih
             refine start_apart env c same reads s _ found _ (Decidable.of_not_not ‹_›) ?_ rfl h
             first | exact Or.inl rfl | exact Or.inr rfl)

theorem pass_apart (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState)
    (c : Task → Task → Bool) (same : env.conflicts = c) (reads : ReadsNoFingerprint c)
    (h : Apart c s) : Apart c (pass cfg env now s) := by
  unfold pass
  dsimp only
  apply sweep_apart cfg env now _ c same reads
  exact Apart.of_running (deferAll_running env s _) h

/-! ## Everything else the queue does -/

/-- Cancelling a task marks a running one, and leaves the running tasks as they are. -/
theorem cancel_apart (env : QueueEnv) (s : QueueState) (key : Key) (c : Task → Task → Bool)
    (h : Apart c s) : Apart c (cancel env s key).1 := by
  unfold cancel
  split
  · exact Apart.of_running (settle_running env _ _ _) h
  · split
    · unfold Apart at h ⊢
      dsimp only
      rw [List.map_map]
      have tasks : ((·.task) ∘ fun r : QueueEntry =>
          if r.task.key == key then { r with cancelled := true } else r) = (·.task) := by
        funext r
        dsimp only [Function.comp]
        split <;> rfl
      rw [tasks]
      exact h
    · exact h

/-- A task's end leaves the running tasks as they are, or without the task that ended. -/
theorem done_apart (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) (c : Task → Task → Bool) (h : Apart c s) :
    Apart c (done cfg env now s id outcome waitS) := by
  rcases done_running cfg env now s id outcome waitS with same | fewer
  · exact Apart.of_running same h
  · unfold Apart at h ⊢
    rw [fewer]
    exact h.sublist (List.filter_sublist.map _)

/-- The states a queue reaches while the conflict relation is `c` at every pass. -/
inductive ReachableApart (cfg : QueueConfig) (c : Task → Task → Bool) : QueueState → Prop where
  | start : ReachableApart cfg c {}
  | added (env : QueueEnv) (s : QueueState) (task : Task) :
      ReachableApart cfg c s → ReachableApart cfg c (add env s task).1
  | extended (env : QueueEnv) (s : QueueState) (tasks : List Task) :
      ReachableApart cfg c s → ReachableApart cfg c (extend env s tasks)
  | cancelled (env : QueueEnv) (s : QueueState) (key : Key) :
      ReachableApart cfg c s → ReachableApart cfg c (cancel env s key).1
  | passed (env : QueueEnv) (same : env.conflicts = c) (now : Time) (s : QueueState) :
      ReachableApart cfg c s → ReachableApart cfg c (pass cfg env now s)
  | ended (env : QueueEnv) (now : Time) (s : QueueState) (id : String) (outcome : Outcome) (waitS : Duration) :
      ReachableApart cfg c s → ReachableApart cfg c (done cfg env now s id outcome waitS)
  | gaveUp (env : QueueEnv) (s : QueueState) :
      ReachableApart cfg c s → ReachableApart cfg c (giveUp env s)

/-- While the conflict relation is `c`, of every two running tasks, the one that started
later does not conflict with the other. -/
theorem ReachableApart.apart {cfg : QueueConfig} {c : Task → Task → Bool} {s : QueueState}
    (reads : ReadsNoFingerprint c) (reached : ReachableApart cfg c s) : Apart c s := by
  induction reached with
  | start => simp [Apart]
  | added env s task _ ih => exact Apart.of_running (add_running env s task) ih
  | extended env s tasks _ ih => exact Apart.of_running (extend_running env tasks s) ih
  | cancelled env s key _ ih => exact cancel_apart env s key c ih
  | passed env same now s _ ih => exact pass_apart cfg env now s c same reads ih
  | ended env now s id outcome waitS _ ih => exact done_apart cfg env now s id outcome waitS c ih
  | gaveUp env s _ ih => exact Apart.of_running (giveUp_running env s) ih

/-- While the conflict relation is `c`, and `c` does not depend on the order of its two
tasks, of every two running tasks neither conflicts with the other. -/
theorem ReachableApart.apart_both {cfg : QueueConfig} {c : Task → Task → Bool} {s : QueueState}
    (reads : ReadsNoFingerprint c) (symm : ∀ t u, c t u = c u t) (reached : ReachableApart cfg c s) :
    (s.running.map (·.task)).Pairwise fun a b => c a b = false ∧ c b a = false :=
  (reached.apart reads).imp fun later => ⟨(symm _ _).trans later, later⟩

/-- info: 'Contraagent.ReachableApart.apart_both' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms ReachableApart.apart_both

end Contraagent
