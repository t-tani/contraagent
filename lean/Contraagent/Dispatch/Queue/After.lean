import Contraagent.Dispatch.Queue.Reachable

/-!
# No task starts before the tasks it comes after have finished

`StartsAfter` reads what the queue reported: each task it shows starting names in `after`
only keys of tasks that the log shows finished earlier. `AfterDone` adds that every key the
queue holds as done is one of those. Every function of `Queue.lean` keeps it, so it holds
in every state the queue reaches (`Reachable.starts_after`).

A task finishes with any result: `after` orders tasks, and says nothing of success. A
task as it starts comes after the tasks it came after (`QueueEnv.started_after`).
-/

namespace Contraagent

/-- Whether an event reports a task's start. -/
def QueueEvent.isStart : QueueEvent → Bool
  | .start _ _ _ _ => true
  | _ => false

/-- The keys of the tasks a log shows finished: a refused duplicate is none, its key is the
other task's. -/
def finishedKeys (log : List QueueEvent) : List Key :=
  log.filterMap fun
    | .finished result => if result.stop != Stop.duplicateKey then some result.task.key else none
    | _ => none

/-- Every task a log shows starting comes after tasks that it shows finished before. The
log holds the latest event first. -/
def StartsAfter : List QueueEvent → Prop
  | [] => True
  | event :: earlier =>
    (match event with
      | .start task _ _ _ => ∀ key ∈ task.after, key ∈ finishedKeys earlier
      | _ => True) ∧ StartsAfter earlier

/-- What the queue keeps: its log shows no task starting before the tasks it comes after
finished, and every key it holds as done is of a task the log shows finished. -/
def AfterDone (s : QueueState) : Prop :=
  StartsAfter s.log ∧ ∀ key ∈ s.doneKeys, key ∈ finishedKeys s.log

theorem finishedKeys_later (event : QueueEvent) (log : List QueueEvent) (key : Key)
    (h : key ∈ finishedKeys log) : key ∈ finishedKeys (event :: log) := by
  unfold finishedKeys
  rw [List.filterMap_cons]
  split
  · exact h
  · exact List.mem_cons_of_mem _ h

theorem AfterDone.congr {s s' : QueueState} (h : AfterDone s) (hl : s'.log = s.log)
    (hd : s'.doneKeys = s.doneKeys) : AfterDone s' := by
  unfold AfterDone
  rw [hl, hd]
  exact h

/-- Reporting an event that is no start keeps it. -/
theorem afterDone_report {s : QueueState} (event : QueueEvent) (other : event.isStart = false)
    (h : AfterDone s) : AfterDone (s.report event) := by
  refine ⟨?_, fun key mem => finishedKeys_later event s.log key (h.2 key mem)⟩
  show StartsAfter (event :: s.log)
  refine ⟨?_, h.1⟩
  cases event <;> simp_all [QueueEvent.isStart]

/-- Reporting the start of a task whose dependencies are done keeps it. -/
theorem afterDone_start {s : QueueState} (task : Task) (attempt running slots : Nat)
    (deps : ∀ key ∈ task.after, key ∈ s.doneKeys) (h : AfterDone s) :
    AfterDone (s.report (.start task attempt running slots)) := by
  refine ⟨?_, fun key mem => finishedKeys_later _ s.log key (h.2 key mem)⟩
  show StartsAfter (QueueEvent.start task attempt running slots :: s.log)
  exact ⟨fun key mem => h.2 key (deps key mem), h.1⟩

theorem afterDone_push {s : QueueState} (result : TaskResult) (attempt : Nat) (h : AfterDone s) :
    AfterDone (s.push result attempt) :=
  h.congr rfl rfl

theorem afterDone_dequeue {s : QueueState} (id : String) (h : AfterDone s) : AfterDone (s.dequeue id) :=
  h.congr rfl rfl

theorem afterDone_skipStartable (env : QueueEnv) :
    ∀ (ids : List String) (s : QueueState), AfterDone s → AfterDone (skipStartable env s ids) := by
  intro ids
  induction ids with
  | nil => intro s h; exact h
  | cons id rest ih =>
    intro s h
    unfold skipStartable
    split
    · exact ih s h
    · split
      · dsimp only
        split
        · exact ih _ (afterDone_push _ _ (afterDone_dequeue _ h))
        · exact ih _ (h.congr rfl rfl)
      · exact ih s h

theorem afterDone_addCore (env : QueueEnv) (s : QueueState) (task : Task) (h : AfterDone s) :
    AfterDone (addCore env s task).1 := by
  unfold addCore
  split
  · exact h
  · dsimp only
    split
    · exact afterDone_report _ rfl (h.congr rfl rfl)
    · split
      · exact afterDone_push _ _ (afterDone_report _ rfl (h.congr rfl rfl))
      · apply afterDone_skipStartable
        exact (afterDone_report (.queued task) rfl (h.congr (s' := { s with
          known := task.id :: s.known, nextSeq := s.nextSeq + 1, inflight := task.key :: s.inflight }) rfl rfl)).congr
          rfl rfl

theorem afterDone_extendCore (env : QueueEnv) :
    ∀ (tasks : List Task) (s : QueueState), AfterDone s → AfterDone (extendCore env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s h; exact h
  | cons task rest ih =>
    intro s h
    unfold extendCore
    split
    · exact ih s h
    · have added := afterDone_addCore env s task h
      split
      · rename_i s' heq
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        rw [heq] at added
        exact ih _ (afterDone_push _ _ added)

theorem markDone_log (s : QueueState) (result : TaskResult) : (markDone s result).log = s.log := by
  unfold markDone
  split <;> rfl

/-- A key that is done once a task's key was marked was done before, or is that task's,
whose result is no refused duplicate's. -/
theorem markDone_doneKeys (s : QueueState) (result : TaskResult) (key : Key)
    (mem : key ∈ (markDone s result).doneKeys) :
    key ∈ s.doneKeys ∨ (key = result.task.key ∧ (result.stop != Stop.duplicateKey) = true) := by
  unfold markDone at mem
  split at mem
  · exact Or.inl mem
  · rename_i notDup
    dsimp only at mem
    split at mem
    · exact Or.inl mem
    · rcases List.mem_cons.mp mem with eq | mem
      · exact Or.inr ⟨eq, by simpa using notDup⟩
      · exact Or.inl mem

theorem reportEnd_doneKeys (s : QueueState) (p : Settling) : (reportEnd s p).doneKeys = s.doneKeys := by
  unfold reportEnd
  dsimp only
  split <;> rfl

/-- What reporting a task's end adds to the log: `finished`, after `ended` or not. -/
theorem reportEnd_log (s : QueueState) (p : Settling) :
    (reportEnd s p).log = .finished p.result :: s.log
      ∨ (reportEnd s p).log = .finished p.result :: .ended p.result p.attempt :: s.log := by
  unfold reportEnd
  dsimp only
  split
  · exact Or.inl rfl
  · exact Or.inr rfl

theorem finishedKeys_finished (result : TaskResult) (log : List QueueEvent)
    (notDup : (result.stop != Stop.duplicateKey) = true) :
    result.task.key ∈ finishedKeys (.finished result :: log) := by
  have ne : result.stop ≠ Stop.duplicateKey := by simpa using notDup
  simp [finishedKeys, ne]

/-- A finished task's key is done, and its end is reported: the key is then one of a task
the log shows finished. -/
theorem afterDone_reportEnd (s : QueueState) (p : Settling) (h : AfterDone s) :
    AfterDone (reportEnd (markDone s p.result) p) := by
  have logs := reportEnd_log (markDone s p.result) p
  rw [markDone_log] at logs
  refine ⟨?_, ?_⟩
  · rcases logs with eq | eq <;> rw [eq]
    · exact ⟨trivial, h.1⟩
    · exact ⟨trivial, trivial, h.1⟩
  · intro key mem
    rw [reportEnd_doneKeys] at mem
    rcases markDone_doneKeys s p.result key mem with held | ⟨own, notDup⟩
    · have before := h.2 key held
      rcases logs with eq | eq <;> rw [eq]
      · exact finishedKeys_later _ _ key before
      · exact finishedKeys_later _ _ key (finishedKeys_later _ _ key before)
    · rw [own]
      rcases logs with eq | eq <;> rw [eq] <;> exact finishedKeys_finished _ _ notDup

theorem afterDone_finishOne (env : QueueEnv) (s : QueueState) (p : Settling) (h : AfterDone s) :
    AfterDone (finishOne env s p) := by
  unfold finishOne
  dsimp only
  have ended := afterDone_reportEnd s p h
  split
  · exact afterDone_extendCore env _ _ ended
  · exact afterDone_skipStartable env _ _ (afterDone_extendCore env _ _ ended)

theorem afterDone_drain (env : QueueEnv) :
    ∀ (fuel : Nat) (s : QueueState), AfterDone s → AfterDone (drain env fuel s) := by
  intro fuel
  induction fuel with
  | zero => intro s h; exact h
  | succ fuel ih =>
    intro s h
    unfold drain
    split
    · exact h
    · exact ih _ (afterDone_finishOne env _ _ (h.congr rfl rfl))

theorem afterDone_settle (env : QueueEnv) (s : QueueState) (result : TaskResult) (attempt : Nat)
    (h : AfterDone s) : AfterDone (settle env s result attempt) :=
  afterDone_drain env _ _ (afterDone_push result attempt h)

theorem afterDone_defer (env : QueueEnv) (s : QueueState) (task : Task) (why : Deferral)
    (h : AfterDone s) : AfterDone (defer env s task why) :=
  afterDone_settle env _ _ _ (afterDone_report _ rfl h)

theorem afterDone_deferEach (env : QueueEnv) :
    ∀ (tasks : List (Task × Deferral)) (s : QueueState), AfterDone s → AfterDone (deferEach env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s h; unfold deferEach; exact h
  | cons tw rest ih =>
    intro s h
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    exact ih _ (afterDone_defer env s task why h)

theorem afterDone_dequeueAll (tasks : List (Task × Deferral)) :
    ∀ s : QueueState, AfterDone s → AfterDone (tasks.foldl (fun s tw => s.dequeue tw.1.id) s) := by
  induction tasks with
  | nil => intro s h; exact h
  | cons tw rest ih => intro s h; exact ih _ (afterDone_dequeue _ h)

theorem afterDone_deferAll (env : QueueEnv) (s : QueueState) (tasks : List (Task × Deferral))
    (h : AfterDone s) : AfterDone (deferAll env s tasks) :=
  afterDone_deferEach env _ _ (afterDone_dequeueAll tasks s h)

theorem afterDone_add (env : QueueEnv) (s : QueueState) (task : Task) (h : AfterDone s) :
    AfterDone (add env s task).1 := by
  have added := afterDone_addCore env s task h
  unfold add
  cases res : addCore env s task with
  | mk s' accepted =>
    rw [res] at added
    exact afterDone_drain env _ _ added

theorem afterDone_extend (env : QueueEnv) :
    ∀ (tasks : List Task) (s : QueueState), AfterDone s → AfterDone (extend env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s h; unfold extend; exact h
  | cons task rest ih =>
    intro s h
    unfold extend
    split
    · exact ih s h
    · have added := afterDone_add env s task h
      split
      · rename_i s' heq
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        rw [heq] at added
        exact ih _ (afterDone_settle env s' _ _ added)

theorem afterDone_cancel (env : QueueEnv) (s : QueueState) (key : Key) (h : AfterDone s) :
    AfterDone (cancel env s key).1 := by
  unfold cancel
  split
  · exact afterDone_settle env _ _ _ (afterDone_report _ rfl (afterDone_dequeue _ h))
  · split
    · exact h.congr rfl rfl
    · exact h

theorem afterDone_markReady (now : Time) (s : QueueState) (h : AfterDone s) : AfterDone (markReady now s) :=
  h.congr rfl rfl

theorem afterDone_deferClosed (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState)
    (h : AfterDone s) : AfterDone (deferClosed cfg env now s) :=
  afterDone_deferAll env s _ h

/-- The keys a task that may start comes after are done. -/
theorem deps_done_of_startable (now : Time) (s : QueueState) (e : QueueEntry)
    (ready : startable now s e = true) : ∀ key ∈ e.task.after, key ∈ s.doneKeys := by
  intro key mem
  simp only [startable, Bool.and_eq_true, List.all_eq_true] at ready
  simpa using ready.1 key mem

/-- Going down the order keeps it: a task starts only when the keys it comes after are
done. -/
theorem afterDone_sweep (cfg : QueueConfig) (env : QueueEnv) (now : Time)
    (late : List (String × Deferral)) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      AfterDone s → AfterDone (sweep cfg env now late order w s) := by
  intro order
  induction order with
  | nil => intro w s h; unfold sweep; exact h
  | cons e rest ih =>
    intro w s h
    unfold sweep
    split
    · split
      · exact afterDone_deferAll env s _ h
      · exact h
    · split
      · exact ih w s h
      · rename_i _ found isFound
        split
        · exact ih w s h
        · split
          · exact ih w s h
          · rename_i ready
            have deps := deps_done_of_startable now s found (by simpa using ready)
            split
            · split <;> exact ih _ s h
            · split
              · exact ih w s h
              · split
                · exact ih _ _ (afterDone_defer env _ _ _ (afterDone_dequeue _ h))
                · apply ih
                  refine (afterDone_start _ _ _ _ ?_ (afterDone_dequeue found.task.id h)).congr rfl rfl
                  intro key mem
                  apply deps
                  split at mem
                  · rw [env.started_after found.task] at mem
                    exact mem
                  · exact mem

theorem afterDone_pass (cfg : QueueConfig) (env : QueueEnv) (now : Time)
    (s : QueueState) (h : AfterDone s) : AfterDone (pass cfg env now s) := by
  unfold pass
  dsimp only
  exact afterDone_sweep cfg env now _ _ _ _
    (afterDone_markReady now _ (afterDone_deferClosed cfg env now s h))

theorem afterDone_countThrottle (cfg : QueueConfig) (now : Time) (task : Task) (stop : Stop)
    {s : QueueState} (h : AfterDone s) : AfterDone (countThrottle cfg now task stop s) := by
  unfold countThrottle
  split
  · dsimp only
    split
    · exact afterDone_report _ rfl (h.congr rfl rfl)
    · exact h.congr rfl rfl
  · exact h.congr rfl rfl

theorem afterDone_requeue {s : QueueState} (entry : QueueEntry) (h : AfterDone s) :
    AfterDone { s with queued := entry :: s.queued } :=
  h.congr rfl rfl

theorem afterDone_done (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) (h : AfterDone s) :
    AfterDone (done cfg env now s id outcome waitS) := by
  unfold done
  split
  · exact h
  · dsimp only
    split
    · exact afterDone_settle env _ _ _ (afterDone_report _ rfl (h.congr rfl rfl))
    · split
      · apply afterDone_requeue
        apply afterDone_report _ rfl
        apply afterDone_countThrottle
        exact afterDone_report _ rfl (h.congr rfl rfl)
      · exact afterDone_settle env _ _ _
          (afterDone_countThrottle cfg now _ _ (afterDone_report _ rfl (h.congr rfl rfl)))

theorem afterDone_giveUp (env : QueueEnv) (s : QueueState) (h : AfterDone s) : AfterDone (giveUp env s) := by
  unfold giveUp
  exact afterDone_deferAll env s _ h

/-! ## Every state the queue reaches -/

theorem Reachable.afterDone {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) :
    AfterDone s := by
  induction reached with
  | start => exact ⟨trivial, fun key mem => by simp at mem⟩
  | added env s task _ ih => exact afterDone_add env s task ih
  | extended env s tasks _ ih => exact afterDone_extend env tasks s ih
  | cancelled env s key _ ih => exact afterDone_cancel env s key ih
  | passed env now s _ ih => exact afterDone_pass _ env now s ih
  | ended env now s id outcome waitS _ ih => exact afterDone_done _ env now s id outcome waitS ih
  | gaveUp env s _ ih => exact afterDone_giveUp env s ih

/-- A start that a log shows, with everything it shows before it: the keys the task comes
after are of tasks that finished before. -/
theorem StartsAfter.of_start (later earlier : List QueueEvent) (task : Task) (attempt running slots : Nat)
    (h : StartsAfter (later ++ .start task attempt running slots :: earlier)) :
    ∀ key ∈ task.after, key ∈ finishedKeys earlier := by
  induction later with
  | nil => exact h.1
  | cons event later ih => exact ih h.2

/-- No task starts before the tasks it comes after have finished, in anything the queue
reports: wherever its log shows a task starting, each key the task names in `after` is of a
task that the log shows finished before. -/
theorem Reachable.starts_after {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s)
    (later earlier : List QueueEvent) (task : Task) (attempt running slots : Nat)
    (shown : s.log = later ++ .start task attempt running slots :: earlier) :
    ∀ key ∈ task.after, key ∈ finishedKeys earlier :=
  StartsAfter.of_start later earlier task attempt running slots (shown ▸ reached.afterDone.1)

/-- info: 'Contraagent.Reachable.starts_after' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Reachable.starts_after

end Contraagent
