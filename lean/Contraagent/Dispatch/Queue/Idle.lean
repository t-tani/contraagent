import Contraagent.Dispatch.Queue.Ids

/-!
# No slot idles

A pass that reports nothing started nothing and deferred nothing. When a slot was free at
such a pass, every queued task was held back for a reason (`Reachable.pass_quiet`): a task
it comes after has not finished, or it waits for its retry, or what it needs is not free,
or starting it would take what an earlier task of the order still waits for (the
starvation guard). So the queue leaves no slot idle while a task could start.

The queue's log only grows (`pass_log`), so a pass whose log is as long as before changed
nothing a report tells of.
-/

namespace Contraagent

/-! ## The log only grows -/

theorem skipStartable_log (env : QueueEnv) : ∀ (ids : List String) (s : QueueState),
    s.log.length ≤ (skipStartable env s ids).log.length := by
  intro ids
  induction ids with
  | nil => intro s; exact Nat.le_refl _
  | cons id rest ih =>
    intro s
    unfold skipStartable
    split
    · exact ih s
    · split
      · dsimp only
        split
        · refine Nat.le_trans ?_ (ih _)
          exact Nat.le_refl _
        · refine Nat.le_trans ?_ (ih _)
          exact Nat.le_refl _
      · exact ih s

theorem addCore_log (env : QueueEnv) (s : QueueState) (task : Task) :
    s.log.length ≤ (addCore env s task).1.log.length := by
  unfold addCore
  split
  · exact Nat.le_refl _
  · dsimp only
    split
    · simp [QueueState.report]
    · split
      · simp [QueueState.report, QueueState.push]
      · refine Nat.le_trans ?_ (skipStartable_log env _ _)
        simp [QueueState.report]

theorem extendCore_log (env : QueueEnv) : ∀ (tasks : List Task) (s : QueueState),
    s.log.length ≤ (extendCore env s tasks).log.length := by
  intro tasks
  induction tasks with
  | nil => intro s; exact Nat.le_refl _
  | cons task rest ih =>
    intro s
    unfold extendCore
    split
    · exact ih s
    · have one := addCore_log env s task
      split
      · rename_i s' eq
        rw [eq] at one
        exact Nat.le_trans one (ih s')
      · rename_i s' eq
        rw [eq] at one
        refine Nat.le_trans one (Nat.le_trans ?_ (ih _))
        exact Nat.le_refl _

/-- Closing one task reports it: the log is longer. -/
theorem finishOne_log (env : QueueEnv) (s : QueueState) (p : Settling) :
    s.log.length < (finishOne env s p).log.length := by
  have ended : s.log.length < (reportEnd (markDone s p.result) p).log.length := by
    unfold reportEnd markDone
    dsimp only
    repeat' split
    all_goals (simp only [QueueState.report, List.length_cons]; omega)
  unfold finishOne
  dsimp only
  split
  · exact Nat.lt_of_lt_of_le ended (extendCore_log env _ _)
  · exact Nat.lt_of_lt_of_le ended (Nat.le_trans (extendCore_log env _ _) (skipStartable_log env _ _))

theorem drain_log (env : QueueEnv) : ∀ (fuel : Nat) (s : QueueState), s.log.length ≤ (drain env fuel s).log.length := by
  intro fuel
  induction fuel with
  | zero => intro s; exact Nat.le_refl _
  | succ fuel ih =>
    intro s
    unfold drain
    split
    · exact Nat.le_refl _
    · rename_i p rest _
      have step := finishOne_log env { s with settling := rest } p
      exact Nat.le_trans (Nat.le_of_lt step) (ih _)

/-- Deferring a task reports it: the log is longer. -/
theorem defer_log (env : QueueEnv) (s : QueueState) (task : Task) (why : Deferral) :
    s.log.length < (defer env s task why).log.length := by
  unfold defer settle
  refine Nat.lt_of_lt_of_le ?_ (drain_log env env.fuel _)
  simp [QueueState.report, QueueState.push]

theorem deferEach_log (env : QueueEnv) : ∀ (tasks : List (Task × Deferral)) (s : QueueState),
    s.log.length ≤ (deferEach env s tasks).log.length := by
  intro tasks
  induction tasks with
  | nil => intro s; exact Nat.le_refl _
  | cons tw rest ih =>
    intro s
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    exact Nat.le_trans (Nat.le_of_lt (defer_log env s task why)) (ih _)

theorem dequeued_log (tasks : List (Task × Deferral)) : ∀ s : QueueState,
    (tasks.foldl (fun s tw => s.dequeue tw.1.id) s).log = s.log := by
  induction tasks with
  | nil => intro s; rfl
  | cons tw rest ih => intro s; exact ih _

theorem deferAll_log (env : QueueEnv) (s : QueueState) (tasks : List (Task × Deferral)) :
    s.log.length ≤ (deferAll env s tasks).log.length := by
  unfold deferAll
  refine Nat.le_trans ?_ (deferEach_log env tasks _)
  rw [dequeued_log]
  exact Nat.le_refl _

/-- Deferring some tasks, one at least, makes the log longer. -/
theorem deferAll_log_lt (env : QueueEnv) (s : QueueState) (tasks : List (Task × Deferral)) (some : tasks ≠ []) :
    s.log.length < (deferAll env s tasks).log.length := by
  unfold deferAll
  cases tasks with
  | nil => exact absurd rfl some
  | cons tw rest =>
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    refine Nat.lt_of_lt_of_le ?_ (deferEach_log env rest _)
    refine Nat.lt_of_le_of_lt ?_ (defer_log env _ task why)
    rw [dequeued_log]
    exact Nat.le_refl _

theorem sweep_log (cfg : QueueConfig) (env : QueueEnv) (now : Time) (late : List (String × Deferral)) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      s.log.length ≤ (sweep cfg env now late order w s).log.length := by
  intro order
  induction order with
  | nil => intro w s; unfold sweep; exact Nat.le_refl _
  | cons e rest ih =>
    intro w s
    unfold sweep
    split
    · split
      · exact deferAll_log env s _
      · exact Nat.le_refl _
    · split
      · exact ih w s
      · repeat' split
        all_goals first
          | exact ih _ s
          | (refine Nat.le_trans ?_ (ih _ _)
             exact Nat.le_of_lt (defer_log env (s.dequeue _) _ _))
          | (refine Nat.le_trans ?_ (ih _ _)
             simp [QueueState.report, QueueState.dequeue])

/-- A pass only adds to the log. -/
theorem pass_log (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) :
    s.log.length ≤ (pass cfg env now s).log.length := by
  unfold pass
  dsimp only
  refine Nat.le_trans ?_ (sweep_log cfg env now _ _ _ _)
  exact deferAll_log env s _

/-! ## A pass that reports nothing -/

/-- Why a queued task does not start while a slot is free: a task it comes after has not
finished or it waits for its retry (it is not startable), or what it needs is not free, or
starting it would take what a task that waits for room still needs. -/
def HeldBack (env : QueueEnv) (now : Time) (s : QueueState) (q : QueueEntry) : Prop :=
  startable now s q = false ∨ free env s q.task = false ∨
    ∃ head : Task, free env s head = false ∧ takes env s q.task head = true

/-- Going down the order without a report, with a slot free: each task of the order that
is queued is closed by a time box or held back. -/
theorem sweep_quiet (cfg : QueueConfig) (env : QueueEnv) (now : Time) (late : List (String × Deferral)) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      (∀ head, w.head = some head → free env s head = false) →
      (sweep cfg env now late order w s).log.length = s.log.length →
      s.running.length < slots cfg now s →
      ∀ e ∈ order, ∀ q, s.queued.find? (·.task.id == e.task.id) = some q →
        (closed cfg now q.task).isSome = true ∨ HeldBack env now s q := by
  intro order
  induction order with
  | nil => intro w s _ _ _ e mem; cases mem
  | cons e rest ih =>
    intro w s guard quiet room e' mem q' found'
    unfold sweep at quiet
    simp only [ge_iff_le, Nat.not_le.mpr room, ↓reduceIte] at quiet
    cases found : s.queued.find? (·.task.id == e.task.id) with
    | none =>
      simp only [found] at quiet
      rcases List.mem_cons.mp mem with rfl | later
      · rw [found] at found'
        cases found'
      · exact ih w s guard quiet room e' later q' found'
    | some q =>
      simp only [found] at quiet
      have ofHead : ((closed cfg now q.task).isSome = true ∨ HeldBack env now s q) →
          (e' = e → (closed cfg now q'.task).isSome = true ∨ HeldBack env now s q') := by
        intro verdict same
        rw [same, found] at found'
        cases found'
        exact verdict
      by_cases isClosed : (closed cfg now q.task).isSome = true
      · simp only [isClosed, ↓reduceIte] at quiet
        rcases List.mem_cons.mp mem with same | later
        · exact ofHead (Or.inl isClosed) same
        · exact ih w s guard quiet room e' later q' found'
      · simp only [isClosed, Bool.false_eq_true, ↓reduceIte] at quiet
        by_cases canStart : startable now s q = true
        · simp only [canStart, not_true_eq_false, ↓reduceIte] at quiet
          by_cases isFree : free env s q.task = true
          · simp only [isFree, not_true_eq_false, ↓reduceIte] at quiet
            by_cases held : (w.guarded = true ∧ (Option.map (takes env s q.task) w.head).getD false = true)
            · simp only [held, and_self, ↓reduceIte] at quiet
              rcases List.mem_cons.mp mem with same | later
              · refine ofHead (Or.inr (Or.inr (Or.inr ?_))) same
                cases head : w.head with
                | none => simp [head] at held
                | some task =>
                  simp only [head, Option.map_some, Option.getD_some] at held
                  exact ⟨task, guard task head, held.2⟩
              · exact ih w s guard quiet room e' later q' found'
            · simp only [held, ↓reduceIte] at quiet
              cases deferred : env.deferral q.task with
              | some why =>
                simp only [deferred] at quiet
                refine absurd quiet (Nat.ne_of_gt (Nat.lt_of_lt_of_le ?_ (sweep_log cfg env now late rest _ _)))
                exact defer_log env (s.dequeue q.task.id) q.task why
              | none =>
                simp only [deferred] at quiet
                refine absurd quiet (Nat.ne_of_gt (Nat.lt_of_lt_of_le ?_ (sweep_log cfg env now late rest _ _)))
                simp [QueueState.report, QueueState.dequeue]
          · simp only [isFree] at quiet
            have notFree : free env s q.task = false := by simpa using isFree
            rcases List.mem_cons.mp mem with same | later
            · exact ofHead (Or.inr (Or.inr (Or.inl notFree))) same
            · cases head : w.head with
              | none =>
                simp only [head] at quiet
                refine ih _ s ?_ quiet room e' later q' found'
                intro task is
                simp only [Option.some.injEq] at is
                rw [← is]
                exact notFree
              | some task =>
                simp only [head] at quiet
                exact ih w s guard quiet room e' later q' found'
        · simp only [canStart] at quiet
          rcases List.mem_cons.mp mem with same | later
          · exact ofHead (Or.inr (Or.inl (by simpa using canStart))) same
          · exact ih w s guard quiet room e' later q' found'

/-- The one entry of an id in a list is the one a search by that id finds. -/
theorem find_of_once (l : List QueueEntry) (e : QueueEntry) (mem : e ∈ l)
    (once : l.countP (·.task.id == e.task.id) = 1) : l.find? (·.task.id == e.task.id) = some e := by
  induction l with
  | nil => cases mem
  | cons a rest ih =>
    rw [List.countP_cons] at once
    by_cases same : a.task.id = e.task.id
    · have here : (a.task.id == e.task.id) = true := by simpa using same
      rw [List.find?_cons, here]
      rcases List.mem_cons.mp mem with is | later
      · rw [is]
      · have more := one_le_countP_id e rest later
        simp only [here, ↓reduceIte] at once
        omega
    · have miss : (a.task.id == e.task.id) = false := by simpa using same
      rw [List.find?_cons, miss]
      simp only [miss, Bool.false_eq_true, ↓reduceIte, Nat.add_zero] at once
      rcases List.mem_cons.mp mem with is | later
      · rw [is] at same
        exact absurd rfl same
      · exact ih later once

/-- A queued entry as a pass marks it (`markReady`): since when it is ready. -/
def marked (now : Time) (s : QueueState) (q : QueueEntry) : QueueEntry :=
  if q.readySince.isNone ∧ startable now s q then { q with readySince := some now } else q

theorem markReady_queued (now : Time) (s : QueueState) : (markReady now s).queued = s.queued.map (marked now s) := rfl

theorem marked_task (now : Time) (s : QueueState) (q : QueueEntry) : (marked now s q).task = q.task := by
  unfold marked
  split <;> rfl

theorem marked_notBefore (now : Time) (s : QueueState) (q : QueueEntry) :
    (marked now s q).notBefore = q.notBefore := by
  unfold marked
  split <;> rfl

/-- No slot idles. When a pass reports nothing, it started nothing and deferred nothing;
when a slot was free then, every queued task was held back: it is not startable (a task it
comes after has not finished, or it waits for its retry), or what it needs is not free, or
starting it would take what a task that waits for room still needs. -/
theorem Reachable.pass_quiet {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s)
    (env : QueueEnv) (now : Time) (quiet : (pass cfg env now s).log.length = s.log.length)
    (room : s.running.length < slots cfg now s) : ∀ e ∈ s.queued, HeldBack env now s e := by
  intro e mem
  unfold pass at quiet
  dsimp only at quiet
  -- Nothing was deferred for a closed time box: the log would be longer.
  have none : (s.queued.filterMap fun q => (closed cfg now q.task).map fun why => (q.task, why)) = [] := by
    cases tasks : s.queued.filterMap fun q => (closed cfg now q.task).map fun why => (q.task, why) with
    | nil => rfl
    | cons tw rest =>
      have longer := deferAll_log_lt env s (tw :: rest) (by simp)
      have after := sweep_log cfg env now (lateTasks cfg env now (markReady now (deferClosed cfg env now s)))
        (((markReady now (deferClosed cfg env now s)).queued.mergeSort
            (orderLe cfg env now (markReady now (deferClosed cfg env now s)))).filter
              (fun q => !((lateTasks cfg env now (markReady now (deferClosed cfg env now s))).lookup q.task.id).isSome) ++
          ((markReady now (deferClosed cfg env now s)).queued.mergeSort
            (orderLe cfg env now (markReady now (deferClosed cfg env now s)))).filter
              (fun q => ((lateTasks cfg env now (markReady now (deferClosed cfg env now s))).lookup q.task.id).isSome))
        {} (markReady now (deferClosed cfg env now s))
      have marked : (markReady now (deferClosed cfg env now s)).log = (deferClosed cfg env now s).log := rfl
      unfold deferClosed at after marked
      rw [tasks] at after marked
      rw [marked] at after
      unfold deferClosed at quiet
      rw [tasks] at quiet
      omega
  have same : deferClosed cfg env now s = s := by
    unfold deferClosed
    rw [none]
    rfl
  rw [same] at quiet
  -- The entry as the pass marks it, the one entry of its id.
  have alone := (idsOnce_queued_alone reached.idsOnce e mem).1
  have inMarked : marked now s e ∈ (markReady now s).queued := by
    rw [markReady_queued]
    exact List.mem_map.mpr ⟨e, mem, rfl⟩
  have once : (markReady now s).queued.countP (·.task.id == (marked now s e).task.id) = 1 := by
    rw [marked_task, markReady_queued, List.countP_map, ← alone]
    apply List.countP_congr
    intro q _
    simp only [Function.comp, marked_task]
  have found := find_of_once _ _ inMarked once
  have verdict := sweep_quiet cfg env now _ _ {} (markReady now s) (fun head is => by cases is) quiet room
    (marked now s e)
    (by
      rw [List.mem_append, List.mem_filter, List.mem_filter, List.mem_mergeSort]
      cases ((lateTasks cfg env now (markReady now s)).lookup (marked now s e).task.id).isSome
      · exact Or.inl ⟨inMarked, rfl⟩
      · exact Or.inr ⟨inMarked, rfl⟩)
    _ found
  rcases verdict with isClosed | held
  · -- A queued task that a box closed would have been deferred.
    rw [marked_task] at isClosed
    have listed : (e.task, (closed cfg now e.task).get isClosed) ∈
        s.queued.filterMap fun q => (closed cfg now q.task).map fun why => (q.task, why) :=
      List.mem_filterMap.mpr ⟨e, mem, by simp⟩
    rw [none] at listed
    cases listed
  · have sameStart : startable now (markReady now s) (marked now s e) = startable now s e := by
      unfold startable
      rw [marked_task, marked_notBefore]
      rfl
    rw [HeldBack, sameStart, marked_task] at held
    exact held

/-- info: 'Contraagent.Reachable.pass_quiet' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Reachable.pass_quiet

end Contraagent
