import Contraagent.Dispatch.Queue.Idle

/-!
# The queue ends

The loop of the queue makes a pass, and then makes another when the pass finished a task,
waits for a running task to end, waits for a retry, or gives up what nothing can launch
(`afterPass`). `Round` is one round of it. Every round lowers the queue's `load`, but for
seven for each task the queue is newly given (`Round.lowers`). So a run of the loop in
which the queue is given a bounded number of tasks has a bounded number of rounds
(`Rounds.bounded`): from an empty queue, at most seven for each task.

The load counts what each task may still do. A queued task that has started no attempt may
start, end, wait for its retry, be queued again, start again, end and finish; one that has
started an attempt has less of that left; a running task has what follows its start; a
result that waits to finish has one step. A task's end, a start, a deferral and the end of
a retry wait each take at least one from it, and a follow-up adds at most six for a task
the queue was not given before.
-/

namespace Contraagent

/-- What a queued task that started `attempt` attempts may still do. -/
def queuedSteps (attempt : Nat) : Nat :=
  if attempt = 0 then 6 else 3

/-- What a running task on its attempt `attempt` may still do. -/
def runningSteps (attempt : Nat) : Nat :=
  if attempt = 0 then 8 else if attempt = 1 then 5 else 2

/-- One for a queued task that waits for its retry at `now`. -/
def waitStep (now : Time) (e : QueueEntry) : Nat :=
  match e.notBefore with
  | some t => if t > now then 1 else 0
  | none => 0

def queuedLoad (now : Time) (l : List QueueEntry) : Nat :=
  (l.map fun e => queuedSteps e.attempt + waitStep now e).sum

def runningLoad (l : List QueueEntry) : Nat :=
  (l.map fun e => runningSteps e.attempt).sum

/-- What the tasks the queue holds may still do, at `now`. -/
def load (now : Time) (s : QueueState) : Nat :=
  queuedLoad now s.queued + runningLoad s.running + s.settling.length

/-- What a step of the queue does to the load: it forgets no finished task, and the load
after it, with `gain`, is at most the load before, with `extra` and seven for each task the
queue is newly given. A task that finishes takes one from the load. -/
structure Moves (now : Time) (gain extra : Nat) (s s' : QueueState) : Prop where
  finished : s.finishedCount ≤ s'.finishedCount
  load : load now s' + s'.finishedCount + 7 * s.known.length + gain
    ≤ load now s + s.finishedCount + 7 * s'.known.length + extra

/-- A step that adds nothing to the load. -/
abbrev Drops (now : Time) (s s' : QueueState) : Prop := Moves now 0 0 s s'

theorem Moves.refl (now : Time) (s : QueueState) : Drops now s s :=
  ⟨Nat.le_refl _, Nat.le_refl _⟩

theorem Moves.trans {now : Time} {g g' e e' : Nat} {s s' s'' : QueueState} (first : Moves now g e s s')
    (second : Moves now g' e' s' s'') : Moves now (g + g') (e + e') s s'' := by
  obtain ⟨f1, l1⟩ := first
  obtain ⟨f2, l2⟩ := second
  exact ⟨Nat.le_trans f1 f2, by omega⟩

/-- Less gained, or more allowed: the same step. -/
theorem Moves.weaken {now : Time} {g g' e e' : Nat} {s s' : QueueState} (h : Moves now g e s s')
    (enough : g' + e ≤ g + e') : Moves now g' e' s s' := by
  obtain ⟨f, l⟩ := h
  exact ⟨f, by omega⟩

/-- A state with the same tasks, the same ids given and as many tasks finished moves the
load as the other does. -/
theorem Moves.congr {now : Time} {g e : Nat} {s s' t : QueueState} (h : Moves now g e s s')
    (hq : t.queued = s'.queued) (hr : t.running = s'.running) (hs : t.settling = s'.settling)
    (hk : t.known = s'.known) (hf : t.finishedCount = s'.finishedCount) : Moves now g e s t := by
  obtain ⟨f, l⟩ := h
  refine ⟨by rw [hf]; exact f, ?_⟩
  simp only [Contraagent.load, hq, hr, hs, hk, hf] at l ⊢
  exact l

theorem queuedSteps_pos (attempt : Nat) : 3 ≤ queuedSteps attempt := by
  unfold queuedSteps
  split <;> omega

theorem queuedLoad_cons (now : Time) (e : QueueEntry) (l : List QueueEntry) :
    queuedLoad now (e :: l) = queuedSteps e.attempt + waitStep now e + queuedLoad now l := by
  simp [queuedLoad]

theorem queuedLoad_append (now : Time) (l l' : List QueueEntry) :
    queuedLoad now (l ++ l') = queuedLoad now l + queuedLoad now l' := by
  simp [queuedLoad]

theorem runningLoad_cons (e : QueueEntry) (l : List QueueEntry) :
    runningLoad (e :: l) = runningSteps e.attempt + runningLoad l := by
  simp [runningLoad]

theorem runningLoad_append (l l' : List QueueEntry) : runningLoad (l ++ l') = runningLoad l + runningLoad l' := by
  simp [runningLoad]

/-- Taking entries out of the queue does not add to its load. -/
theorem queuedLoad_filter_le (now : Time) (keep : QueueEntry → Bool) (l : List QueueEntry) :
    queuedLoad now (l.filter keep) ≤ queuedLoad now l := by
  induction l with
  | nil => simp
  | cons e l ih =>
    rw [List.filter_cons]
    split
    · rw [queuedLoad_cons, queuedLoad_cons]
      omega
    · rw [queuedLoad_cons]
      omega

/-- Taking a queued task out of the queue takes its steps from the load. -/
theorem queuedLoad_dequeue (now : Time) (e : QueueEntry) (l : List QueueEntry) (mem : e ∈ l) :
    queuedLoad now (l.filter (·.task.id != e.task.id)) + queuedSteps e.attempt ≤ queuedLoad now l := by
  induction l with
  | nil => cases mem
  | cons a l ih =>
    rw [List.filter_cons, queuedLoad_cons]
    rcases List.mem_cons.mp mem with is | later
    · have out : (a.task.id != e.task.id) = false := by simp [is]
      have rest := queuedLoad_filter_le now (·.task.id != e.task.id) l
      simp only [out, Bool.false_eq_true, ↓reduceIte]
      rw [← is]
      omega
    · have rest := ih later
      split
      · rw [queuedLoad_cons]
        omega
      · omega

theorem runningLoad_filter_le (keep : QueueEntry → Bool) (l : List QueueEntry) :
    runningLoad (l.filter keep) ≤ runningLoad l := by
  induction l with
  | nil => simp
  | cons e l ih =>
    rw [List.filter_cons]
    split
    · rw [runningLoad_cons, runningLoad_cons]
      omega
    · rw [runningLoad_cons]
      omega

/-- Taking a running task out of those that run takes its steps from the load. -/
theorem runningLoad_unrun (e : QueueEntry) (l : List QueueEntry) (mem : e ∈ l) :
    runningLoad (l.filter (·.task.id != e.task.id)) + runningSteps e.attempt ≤ runningLoad l := by
  induction l with
  | nil => cases mem
  | cons a l ih =>
    rw [List.filter_cons, runningLoad_cons]
    rcases List.mem_cons.mp mem with is | later
    · have out : (a.task.id != e.task.id) = false := by simp [is]
      have rest := runningLoad_filter_le (·.task.id != e.task.id) l
      simp only [out, Bool.false_eq_true, ↓reduceIte]
      rw [← is]
      omega
    · have rest := ih later
      split
      · rw [runningLoad_cons]
        omega
      · omega

/-- Marking queued entries, their attempts and their retry waits unchanged, changes no
load. -/
theorem queuedLoad_map (now : Time) (f : QueueEntry → QueueEntry) (l : List QueueEntry)
    (same : ∀ e, (f e).attempt = e.attempt ∧ (f e).notBefore = e.notBefore) :
    queuedLoad now (l.map f) = queuedLoad now l := by
  induction l with
  | nil => rfl
  | cons e l ih =>
    rw [List.map_cons, queuedLoad_cons, queuedLoad_cons, ih]
    simp only [waitStep, (same e).1, (same e).2]

theorem runningLoad_map (f : QueueEntry → QueueEntry) (l : List QueueEntry) (same : ∀ e, (f e).attempt = e.attempt) :
    runningLoad (l.map f) = runningLoad l := by
  induction l with
  | nil => rfl
  | cons e l ih => rw [List.map_cons, runningLoad_cons, runningLoad_cons, ih, same e]

/-! ## Each function of the queue -/

-- One tactic names the counts of every state these lemmas meet, so each use leaves some of
-- its rewrites unused.
set_option linter.unusedSimpArgs false

/-- Name the load, the tasks finished and the ids given of the states of a goal, and close
it by arithmetic. -/
local macro "count_load" : tactic =>
  `(tactic| (simp only [load, QueueState.report, QueueState.push, QueueState.dequeue, QueueState.finishedCount,
      List.countP_cons, List.length_cons, List.length_append, List.length_nil, Bool.false_eq_true, ↓reduceIte,
      Nat.add_zero] <;> omega))

/-- Whether an event shows a task finished. -/
def QueueEvent.finishes : QueueEvent → Bool
  | .finished _ => true
  | _ => false

theorem finishedCount_report (s : QueueState) (event : QueueEvent) :
    (s.report event).finishedCount = s.finishedCount + if event.finishes then 1 else 0 := by
  cases event <;> simp [QueueState.finishedCount, QueueState.report, QueueEvent.finishes]

/-- Reporting an event that shows no task finished moves no load. -/
theorem moves_report (now : Time) (s : QueueState) (event : QueueEvent) (other : event.finishes = false) :
    Drops now s (s.report event) := by
  have count := finishedCount_report s event
  simp only [other, Bool.false_eq_true, ↓reduceIte, Nat.add_zero] at count
  exact ⟨by rw [count]; exact Nat.le_refl _, by rw [count]; exact Nat.le_refl _⟩

/-- A result among those that wait: one more step. -/
theorem moves_push (now : Time) (s : QueueState) (result : TaskResult) (attempt : Nat) :
    Moves now 0 1 s (s.push result attempt) := by
  refine ⟨Nat.le_refl _, ?_⟩
  simp only [load, QueueState.push, QueueState.finishedCount, List.length_append, List.length_cons, List.length_nil]
  omega

/-- A queued task taken out of the queue: its steps leave the load. -/
theorem moves_dequeue (now : Time) (s : QueueState) (e : QueueEntry) (mem : e ∈ s.queued) :
    Moves now (queuedSteps e.attempt) 0 s (s.dequeue e.task.id) := by
  refine ⟨Nat.le_refl _, ?_⟩
  have out := queuedLoad_dequeue now e s.queued mem
  simp only [load, QueueState.dequeue, QueueState.finishedCount]
  omega

/-- A queued task out of the queue and a result among those that wait. -/
theorem moves_dequeue_push (now : Time) (s : QueueState) (e : QueueEntry) (mem : e ∈ s.queued)
    (result : TaskResult) (attempt : Nat) : Drops now s ((s.dequeue e.task.id).push result attempt) := by
  have steps := queuedSteps_pos e.attempt
  exact ((moves_dequeue now s e mem).trans (moves_push now _ result attempt)).weaken (by omega)

theorem moves_skipStartable (env : QueueEnv) (now : Time) : ∀ (ids : List String) (s : QueueState),
    Drops now s (skipStartable env s ids) := by
  intro ids
  induction ids with
  | nil => intro s; exact Moves.refl now s
  | cons id rest ih =>
    intro s
    unfold skipStartable
    split
    · exact ih s
    · rename_i e found
      have mem : e ∈ s.queued := List.mem_of_find?_eq_some found
      have ide : e.task.id = id := by
        have := List.find?_some found
        simpa using this
      split
      · dsimp only
        split
        · have step := moves_dequeue_push now s e mem (TaskResult.skipped (env.started e.task)) 0
          rw [ide] at step
          exact (step.trans (ih _)).weaken (Nat.le_refl _)
        · have step : Drops now s { s with queued := s.queued.map fun q =>
              if q.task.id == id then { q with asked := true } else q } := by
            refine ⟨Nat.le_refl _, ?_⟩
            have same := queuedLoad_map now (fun q : QueueEntry => if q.task.id == id then { q with asked := true } else q)
              s.queued (by intro q; split <;> exact ⟨rfl, rfl⟩)
            simp only [load, QueueState.finishedCount, same]
            omega
          exact (step.trans (ih _)).weaken (Nat.le_refl _)
      · exact ih s

/-- Queueing one task adds at most its steps, for a task the queue was not given. -/
theorem moves_addCore (env : QueueEnv) (now : Time) (s : QueueState) (task : Task) :
    Drops now s (addCore env s task).1 := by
  unfold addCore
  split
  · exact Moves.refl now s
  · dsimp only
    split
    · refine ⟨?_, ?_⟩ <;> count_load
    · split
      · refine ⟨?_, ?_⟩ <;> count_load
      · refine (Moves.trans ?_ (moves_skipStartable env now [task.id] _)).weaken (Nat.le_refl _)
        have fresh : queuedLoad now [({ task := task, seq := s.nextSeq } : QueueEntry)] = 6 := by
          simp [queuedLoad, queuedSteps, waitStep]
        refine ⟨?_, ?_⟩ <;>
          simp only [load, QueueState.report, QueueState.finishedCount, List.countP_cons, List.length_cons,
            queuedLoad_append, fresh, Bool.false_eq_true, ↓reduceIte, Nat.add_zero] <;> omega

theorem moves_extendCore (env : QueueEnv) (now : Time) : ∀ (tasks : List Task) (s : QueueState),
    Drops now s (extendCore env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s; exact Moves.refl now s
  | cons task rest ih =>
    intro s
    unfold extendCore
    split
    · exact ih s
    · rename_i unknown
      have fresh : s.known.contains task.id = false := by simpa using unknown
      split
      · rename_i s' heq
        have one := moves_addCore env now s task
        rw [heq] at one
        exact (one.trans (ih s')).weaken (Nat.le_refl _)
      · rename_i s' heq
        have refused := addCore_refused env s task fresh (by rw [heq])
        rw [heq] at refused
        have step : Drops now s (s'.push (TaskResult.duplicateKey task) 0) := by
          rw [show s' = _ from refused]
          refine ⟨?_, ?_⟩ <;> count_load
        exact (step.trans (ih _)).weaken (Nat.le_refl _)

/-- Closing the first result that waits: its step leaves the load as the log shows it
finished. -/
theorem moves_finishOne (env : QueueEnv) (now : Time) (s : QueueState) (p : Settling) (rest : List Settling)
    (waits : s.settling = p :: rest) : Drops now s (finishOne env { s with settling := rest } p) := by
  have ended : Drops now s (reportEnd (markDone { s with settling := rest } p.result) p) := by
    unfold reportEnd markDone
    dsimp only
    refine ⟨?_, ?_⟩ <;> repeat' split
    all_goals
      simp only [load, QueueState.report, QueueState.finishedCount, List.countP_cons, List.length_cons, waits,
        Bool.false_eq_true, ↓reduceIte, Nat.add_zero]
      omega
  unfold finishOne
  dsimp only
  split
  · exact (ended.trans (moves_extendCore env now _ _)).weaken (Nat.le_refl _)
  · exact ((ended.trans (moves_extendCore env now _ _)).trans (moves_skipStartable env now _ _)).weaken (Nat.le_refl _)

theorem moves_drain (env : QueueEnv) (now : Time) : ∀ (fuel : Nat) (s : QueueState), Drops now s (drain env fuel s) := by
  intro fuel
  induction fuel with
  | zero => intro s; exact Moves.refl now s
  | succ fuel ih =>
    intro s
    unfold drain
    split
    · exact Moves.refl now s
    · rename_i p rest waits
      exact ((moves_finishOne env now s p rest waits).trans (ih _)).weaken (Nat.le_refl _)

/-- A result that waits and is finished as far as the fuel goes: one step at most. -/
theorem moves_settle (env : QueueEnv) (now : Time) (s : QueueState) (result : TaskResult) (attempt : Nat) :
    Moves now 0 1 s (settle env s result attempt) :=
  ((moves_push now s result attempt).trans (moves_drain env now env.fuel _)).weaken (Nat.le_refl _)

theorem moves_defer (env : QueueEnv) (now : Time) (s : QueueState) (task : Task) (why : Deferral) :
    Moves now 0 1 s (defer env s task why) :=
  ((moves_report now s (.deferred task (some why.cause)) rfl).trans (moves_settle env now _ _ 0)).weaken (Nat.le_refl _)

theorem moves_deferEach (env : QueueEnv) (now : Time) : ∀ (tasks : List (Task × Deferral)) (s : QueueState),
    Moves now 0 tasks.length s (deferEach env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s; exact Moves.refl now s
  | cons tw rest ih =>
    intro s
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    exact ((moves_defer env now s task why).trans (ih _)).weaken (by simp only [List.length_cons]; omega)

/-- The entries a selection drops take three each from the load, at least. -/
theorem queuedLoad_selected (now : Time) (f : QueueEntry → Option (Task × Deferral)) (keep : QueueEntry → Bool)
    (l : List QueueEntry) (dropped : ∀ e ∈ l, ∀ tw, f e = some tw → keep e = false) :
    queuedLoad now (l.filter keep) + 3 * (l.filterMap f).length ≤ queuedLoad now l := by
  induction l with
  | nil => simp [queuedLoad]
  | cons a l ih =>
    have rest := ih fun e mem tw eq => dropped e (List.mem_cons_of_mem a mem) tw eq
    have steps := queuedSteps_pos a.attempt
    rw [List.filter_cons, queuedLoad_cons]
    cases fa : f a with
    | none =>
      simp only [List.filterMap_cons, fa]
      split
      · rw [queuedLoad_cons]
        omega
      · omega
    | some tw =>
      have out := dropped a List.mem_cons_self tw fa
      simp only [List.filterMap_cons, fa, out, Bool.false_eq_true, ↓reduceIte, List.length_cons]
      omega

/-- Taking the tasks a selection makes of the queue's entries out of the queue and
deferring each takes two from the load for each, at least. -/
theorem moves_deferAll (env : QueueEnv) (now : Time) (s : QueueState)
    (f : QueueEntry → Option (Task × Deferral)) (hf : ∀ e tw, f e = some tw → tw.1 = e.task) :
    Moves now (2 * (s.queued.filterMap f).length) 0 s (deferAll env s (s.queued.filterMap f)) := by
  unfold deferAll
  rw [foldl_dequeue]
  have out : Moves now (3 * (s.queued.filterMap f).length) 0 s
      { s with queued := s.queued.filter fun e => !((s.queued.filterMap f).any fun tw => tw.1.id == e.task.id) } := by
    refine ⟨Nat.le_refl _, ?_⟩
    have taken := queuedLoad_selected now f
      (fun e => !((s.queued.filterMap f).any fun tw => tw.1.id == e.task.id)) s.queued (by
        intro e mem tw eq
        simp only [Bool.not_eq_false', List.any_eq_true]
        exact ⟨tw, List.mem_filterMap.mpr ⟨e, mem, eq⟩, by simp [hf e tw eq]⟩)
    simp only [load, QueueState.finishedCount]
    omega
  exact (out.trans (moves_deferEach env now _ _)).weaken (by omega)

theorem moves_add (env : QueueEnv) (now : Time) (s : QueueState) (task : Task) : Drops now s (add env s task).1 :=
  ((moves_addCore env now s task).trans (moves_drain env now env.fuel _)).weaken (Nat.le_refl _)

theorem moves_extend (env : QueueEnv) (now : Time) : ∀ (tasks : List Task) (s : QueueState),
    Drops now s (extend env s tasks) := by
  intro tasks
  induction tasks with
  | nil => intro s; unfold extend; exact Moves.refl now s
  | cons task rest ih =>
    intro s
    unfold extend
    split
    · exact ih s
    · rename_i unknown
      have fresh : s.known.contains task.id = false := by simpa using unknown
      split
      · rename_i s' heq
        have one := moves_add env now s task
        rw [heq] at one
        exact (one.trans (ih s')).weaken (Nat.le_refl _)
      · rename_i s' heq
        have parts : (add env s task) = (drain env env.fuel (addCore env s task).1, (addCore env s task).2) := rfl
        rw [parts] at heq
        simp only [Prod.mk.injEq] at heq
        have core := addCore_refused env s task fresh heq.2
        -- The id is given, for seven; the refused task's result then waits, for one.
        have refused : Moves now 1 0 s (addCore env s task).1 := by
          rw [core]
          refine ⟨?_, ?_⟩ <;> count_load
        have drained := moves_drain env now env.fuel (addCore env s task).1
        rw [heq.1] at drained
        exact (((refused.trans drained).trans (moves_settle env now s' _ 0)).trans (ih _)).weaken (by omega)

theorem moves_cancel (env : QueueEnv) (now : Time) (s : QueueState) (key : Key) : Drops now s (cancel env s key).1 := by
  unfold cancel
  split
  · rename_i e found
    have mem : e ∈ s.queued := List.mem_of_find?_eq_some found
    have steps := queuedSteps_pos e.attempt
    exact (((moves_dequeue now s e mem).trans (moves_report now _ _ rfl)).trans (moves_settle env now _ _ _)).weaken
      (by omega)
  · split
    · refine ⟨Nat.le_refl _, ?_⟩
      have same := runningLoad_map (fun r : QueueEntry => if r.task.key == key then { r with cancelled := true } else r)
        s.running (by intro r; split <;> rfl)
      simp only [load, QueueState.finishedCount, same]
      omega
    · exact Moves.refl now s

theorem moves_markReady (now : Time) (s : QueueState) : Drops now s (markReady now s) := by
  refine ⟨Nat.le_refl _, ?_⟩
  have same := queuedLoad_map now (marked now s) s.queued (fun q => ⟨by unfold marked; split <;> rfl, marked_notBefore now s q⟩)
  rw [← markReady_queued] at same
  simp only [load, QueueState.finishedCount, same]
  have fields : (markReady now s).running = s.running ∧ (markReady now s).settling = s.settling ∧
      (markReady now s).known = s.known ∧ (markReady now s).log = s.log := ⟨rfl, rfl, rfl, rfl⟩
  rw [fields.1, fields.2.1, fields.2.2.1, fields.2.2.2]
  omega

theorem moves_deferClosed (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) :
    Drops now s (deferClosed cfg env now s) := by
  unfold deferClosed
  refine (moves_deferAll env now s _ ?_).weaken (by omega)
  intro e tw eq
  simp at eq
  obtain ⟨why, _, rfl⟩ := eq
  rfl

theorem steps_start (attempt : Nat) : runningSteps (attempt + 1) + 1 ≤ queuedSteps attempt := by
  unfold runningSteps queuedSteps
  repeat' split
  all_goals omega

/-- A queued task that starts: one step is taken. -/
theorem moves_started (now : Time) (s t : QueueState) (e entry : QueueEntry) (mem : e ∈ s.queued)
    (attempt : entry.attempt = e.attempt + 1) (hq : t.queued = (s.dequeue e.task.id).queued)
    (hr : t.running = s.running ++ [entry]) (hs : t.settling = s.settling) (hk : t.known = s.known)
    (hf : t.finishedCount = s.finishedCount) : Moves now 1 0 s t := by
  have out := queuedLoad_dequeue now e s.queued mem
  have steps := steps_start e.attempt
  refine ⟨by rw [hf]; exact Nat.le_refl _, ?_⟩
  simp only [load, hq, hr, hs, hk, hf, QueueState.dequeue, runningLoad_append, runningLoad_cons, attempt]
  simp only [runningLoad, List.map_nil, List.sum_nil]
  omega

/-- Going down the order adds nothing to the load. -/
theorem moves_sweep (cfg : QueueConfig) (env : QueueEnv) (now : Time) (late : List (String × Deferral)) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState), Drops now s (sweep cfg env now late order w s) := by
  intro order
  induction order with
  | nil => intro w s; unfold sweep; exact Moves.refl now s
  | cons e rest ih =>
    intro w s
    unfold sweep
    split
    · split
      · dsimp only
        refine (moves_deferAll env now s _ ?_).weaken (by omega)
        intro q tw eq
        split at eq
        · simp at eq
          obtain ⟨why, _, rfl⟩ := eq
          rfl
        · simp at eq
      · exact Moves.refl now s
    · split
      · exact ih w s
      · rename_i _ found isFound
        have mem : found ∈ s.queued := List.mem_of_find?_eq_some isFound
        have steps := queuedSteps_pos found.attempt
        repeat' split
        all_goals first
          | exact ih _ s
          | exact (((moves_dequeue now s found mem).trans (moves_defer env now _ _ _)).trans (ih _ _)).weaken (by omega)
          | (refine (Moves.trans (g := 1) (e := 0) (g' := 0) (e' := 0) ?_ (ih _ _)).weaken (by omega)
             exact moves_started now s _ found _ mem rfl rfl rfl rfl rfl
               (by simp [QueueState.finishedCount, QueueState.report, QueueState.dequeue]))

theorem moves_pass (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) :
    Drops now s (pass cfg env now s) := by
  unfold pass
  dsimp only
  exact (((moves_deferClosed cfg env now s).trans (moves_markReady now _)).trans
    (moves_sweep cfg env now _ _ _ _)).weaken (Nat.le_refl _)

theorem moves_countThrottle (cfg : QueueConfig) (now : Time) (task : Task) (stop : Stop) (s : QueueState) :
    Drops now s (countThrottle cfg now task stop s) := by
  unfold countThrottle
  split
  · dsimp only
    split
    · refine ⟨?_, ?_⟩ <;> count_load
    · exact ⟨Nat.le_refl _, Nat.le_refl _⟩
  · exact ⟨Nat.le_refl _, Nat.le_refl _⟩

theorem steps_requeue (attempt : Nat) (again : attempt < 2) : queuedSteps attempt + 2 ≤ runningSteps attempt := by
  unfold runningSteps queuedSteps
  repeat' split
  all_goals omega

theorem runningSteps_pos (attempt : Nat) : 2 ≤ runningSteps attempt := by
  unfold runningSteps
  repeat' split
  all_goals omega

theorem waitStep_le (now : Time) (e : QueueEntry) : waitStep now e ≤ 1 := by
  unfold waitStep
  repeat' split
  all_goals omega

/-- A running task taken out of those that run: its steps leave the load. -/
theorem moves_unrun (now : Time) (s : QueueState) (e : QueueEntry) (mem : e ∈ s.running) :
    Moves now (runningSteps e.attempt) 0 s { s with running := s.running.filter (·.task.id != e.task.id) } := by
  refine ⟨Nat.le_refl _, ?_⟩
  have out := runningLoad_unrun e s.running mem
  simp only [load, QueueState.finishedCount]
  omega

/-- A task's end takes a step: the task finishes, or it is queued again with less left. -/
theorem moves_done (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) (e : QueueEntry) (found : s.running.find? (·.task.id == id) = some e) :
    Moves now 1 0 s (done cfg env now s id outcome waitS) := by
  have mem : e ∈ s.running := List.mem_of_find?_eq_some found
  have ide : e.task.id = id := by simpa using List.find?_some found
  have out := moves_unrun now s e mem
  rw [ide] at out
  have atLeast := runningSteps_pos e.attempt
  unfold done
  rw [found]
  dsimp only
  split
  · exact ((out.trans (moves_report now _ _ rfl)).trans (moves_settle env now _ _ _)).weaken (by omega)
  · split
    · rename_i again
      have steps := steps_requeue e.attempt again.2.2.1
      have wait := waitStep_le now { e with notBefore := some (now + waitS), readySince := none }
      have before := ((out.trans (moves_report now _ (.result
          { task := e.task, ok := outcome.ok, stop := outcome.stop, cause := outcome.cause, retryable := outcome.retryable }
          e.attempt) rfl)).trans
        (moves_countThrottle cfg now e.task outcome.stop _)).trans (moves_report now _ (.retry e.task outcome.stop waitS) rfl)
      obtain ⟨f, l⟩ := before
      refine ⟨f, ?_⟩
      simp only [load, queuedLoad_cons] at l ⊢
      have requeued : queuedSteps ({ e with notBefore := some (now + waitS), readySince := none } : QueueEntry).attempt =
          queuedSteps e.attempt := rfl
      rw [requeued]
      have same : ∀ t : QueueState, ({ t with queued := { e with notBefore := some (now + waitS), readySince := none } :: t.queued } :
          QueueState).finishedCount = t.finishedCount := fun _ => rfl
      rw [same]
      omega
    · exact (((out.trans (moves_report now _ _ rfl)).trans (moves_countThrottle cfg now _ _ _)).trans
        (moves_settle env now _ _ _)).weaken (by omega)

/-- A task's end adds nothing to the load, whichever task it names. -/
theorem drops_done (cfg : QueueConfig) (env : QueueEnv) (now : Time) (s : QueueState) (id : String)
    (outcome : Outcome) (waitS : Duration) : Drops now s (done cfg env now s id outcome waitS) := by
  cases found : s.running.find? (·.task.id == id) with
  | none =>
    unfold done
    rw [found]
    exact Moves.refl now s
  | some e => exact (moves_done cfg env now s id outcome waitS e found).weaken (by omega)

/-- Giving up what nothing can launch takes a step when a task is queued. -/
theorem moves_giveUp (env : QueueEnv) (now : Time) (s : QueueState) (queued : s.queued ≠ []) :
    Moves now 1 0 s (giveUp env s) := by
  unfold giveUp
  dsimp only
  split
  · rename_i none
    rw [map_eq_filterMap_some]
    refine (moves_deferAll env now s _ ?_).weaken ?_
    · intro e tw eq
      simp at eq
      rw [← eq]
    · have all : (s.queued.filterMap fun e => some (e.task, ({ cause := { cause := "dependency_cycle" } } : Deferral))).length
          = s.queued.length := by
        rw [← map_eq_filterMap_some, List.length_map]
      have one : 0 < s.queued.length := List.length_pos_iff.mpr queued
      omega
  · rename_i stuck
    refine (moves_deferAll env now s _ ?_).weaken ?_
    · intro e tw eq
      repeat' split at eq
      all_goals simp at eq
      all_goals rw [← eq]
    · have one : 0 < (s.queued.filterMap fun e =>
          if (e.task.after.filter fun key => !s.doneKeys.contains key).any fun key => !s.inflight.contains key then
            some (e.task, ({ cause := { cause := "dependency_not_queued" } } : Deferral))
          else if (e.task.after.filter fun key => !s.doneKeys.contains key).isEmpty && !free env s e.task then
            some (e.task, { cause := { cause := "no_capacity" } })
          else none).length := by
        apply List.length_pos_iff.mpr
        intro empty
        apply stuck
        rw [empty]
        rfl
      omega

/-! ## The clock -/

theorem waitStep_later (now later : Time) (e : QueueEntry) (passed : now ≤ later) : waitStep later e ≤ waitStep now e := by
  unfold waitStep
  cases e.notBefore with
  | none => exact Nat.le_refl _
  | some t =>
    dsimp only
    by_cases after : t > later
    · have before : t > now := Int.lt_of_le_of_lt passed after
      simp [after, before]
    · simp [after]

theorem queuedLoad_later (now later : Time) (l : List QueueEntry) (passed : now ≤ later) :
    queuedLoad later l ≤ queuedLoad now l := by
  induction l with
  | nil => exact Nat.le_refl _
  | cons e l ih =>
    have one := waitStep_later now later e passed
    rw [queuedLoad_cons, queuedLoad_cons]
    omega

/-- The load does not grow as time passes. -/
theorem load_later (now later : Time) (s : QueueState) (passed : now ≤ later) : load later s ≤ load now s := by
  have queued := queuedLoad_later now later s.queued passed
  simp only [load]
  omega

/-- The time the loop waits to is the end of a queued task's retry wait, after `now`. -/
theorem nextRetry_waits (now : Time) (s : QueueState) (t : Time) (next : nextRetry now s = some t) :
    now < t ∧ ∃ e ∈ s.queued, e.notBefore = some t := by
  have among : ∀ (times : List Time) (best : Option Time),
      times.foldl (fun best t => match best with | none => some t | some b => some (min b t)) best = some t →
      best = some t ∨ t ∈ times := by
    intro times
    induction times with
    | nil => intro best is; exact Or.inl is
    | cons first rest ih =>
      intro best is
      rw [List.foldl_cons] at is
      rcases ih _ is with here | later
      · cases best with
        | none =>
          simp only [Option.some.injEq] at here
          exact Or.inr (by rw [here]; exact List.mem_cons_self)
        | some b =>
          simp only [Option.some.injEq] at here
          by_cases le : b ≤ first
          · rw [Int.min_eq_left le] at here
            exact Or.inl (by rw [here])
          · rw [Int.min_eq_right (Int.le_of_lt (Int.not_le.mp le))] at here
            exact Or.inr (by rw [here]; exact List.mem_cons_self)
      · exact Or.inr (List.mem_cons_of_mem _ later)
  unfold nextRetry at next
  rcases among _ none next with none | listed
  · cases none
  · obtain ⟨e, mem, is⟩ := List.mem_filterMap.mp listed
    cases wait : e.notBefore with
    | none => simp [wait] at is
    | some at_ =>
      simp only [wait, Option.filter] at is
      split at is
      · rename_i after
        simp only [Option.some.injEq] at is
        rw [← is]
        exact ⟨by simpa using after, e, mem, wait⟩
      · cases is

/-- Waiting to the end of a retry wait takes a step: that task waits no longer. -/
theorem load_retry (now t : Time) (s : QueueState) (next : nextRetry now s = some t) : load t s + 1 ≤ load now s := by
  obtain ⟨after, e, mem, wait⟩ := nextRetry_waits now s t next
  have one : ∀ l : List QueueEntry, e ∈ l → queuedLoad t l + 1 ≤ queuedLoad now l := by
    intro l
    induction l with
    | nil => intro held; cases held
    | cons a l ih =>
      intro held
      rw [queuedLoad_cons, queuedLoad_cons]
      have rest := queuedLoad_later now t l (Int.le_of_lt after)
      have own := waitStep_later now t a (Int.le_of_lt after)
      rcases List.mem_cons.mp held with is | later
      · have before : waitStep now a = 1 := by
          rw [← is]
          simp [waitStep, wait, after]
        have then_ : waitStep t a = 0 := by
          rw [← is]
          simp [waitStep, wait]
        omega
      · have := ih later
        omega
  have queued := one s.queued mem
  simp only [load]
  omega

/-! ## The loop -/

/-- One round of the queue's loop from a time and a state: a pass, and then what the loop
does (`afterPass`). It makes another pass, later, when the pass finished a task. It waits
for a running task, which ends in some way. It waits to the end of a retry wait. Or it
gives up what nothing can launch. The loop stops when `afterPass` says so: that is no
round. The answers of the callbacks are any, at each step. -/
inductive Round (cfg : QueueConfig) : Time × QueueState → Time × QueueState → Prop where
  | again (env : QueueEnv) (now later : Time) (s : QueueState) (passed : now ≤ later)
      (verdict : afterPass now s (pass cfg env now s) = .again) : Round cfg (now, s) (later, pass cfg env now s)
  | ended (env env' : QueueEnv) (now later : Time) (s : QueueState) (passed : now ≤ later)
      (verdict : afterPass now s (pass cfg env now s) = .wait) (e : QueueEntry) (runs : e ∈ (pass cfg env now s).running)
      (outcome : Outcome) (waitS : Duration) :
      Round cfg (now, s) (later, done cfg env' later (pass cfg env now s) e.task.id outcome waitS)
  | retried (env : QueueEnv) (now t : Time) (s : QueueState)
      (verdict : afterPass now s (pass cfg env now s) = .retryAt t) : Round cfg (now, s) (t, pass cfg env now s)
  | gaveUp (env env' : QueueEnv) (now later : Time) (s : QueueState) (passed : now ≤ later)
      (verdict : afterPass now s (pass cfg env now s) = .giveUp) :
      Round cfg (now, s) (later, giveUp env' (pass cfg env now s))

/-- A round takes a step from the load, but for seven for each task the queue is newly
given in it. -/
theorem Round.lowers {cfg : QueueConfig} {now later : Time} {s s' : QueueState}
    (round : Round cfg (now, s) (later, s')) :
    load later s' + 1 + 7 * s.known.length ≤ load now s + 7 * s'.known.length := by
  cases round with
  | again env _ _ _ passed verdict =>
    obtain ⟨f, l⟩ := moves_pass cfg env now s
    have time := load_later now later (pass cfg env now s) passed
    have more : (pass cfg env now s).finishedCount ≠ s.finishedCount := by
      unfold afterPass at verdict
      split at verdict
      · assumption
      · repeat' split at verdict
        all_goals cases verdict
    omega
  | ended env env' _ _ _ passed verdict e runs outcome waitS =>
    obtain ⟨f, l⟩ := moves_pass cfg env now s
    have time := load_later now later (pass cfg env now s) passed
    cases found : (pass cfg env now s).running.find? (·.task.id == e.task.id) with
    | none =>
      have := List.find?_eq_none.mp found e runs
      simp at this
    | some first =>
      obtain ⟨f', l'⟩ := moves_done cfg env' later (pass cfg env now s) e.task.id outcome waitS first found
      omega
  | retried env _ _ _ verdict =>
    obtain ⟨f, l⟩ := moves_pass cfg env now s
    have next : nextRetry now (pass cfg env now s) = some later := by
      unfold afterPass at verdict
      repeat' split at verdict
      all_goals first
        | (cases verdict; assumption)
        | cases verdict
    have step := load_retry now later (pass cfg env now s) next
    omega
  | gaveUp env env' _ _ _ passed verdict =>
    obtain ⟨f, l⟩ := moves_pass cfg env now s
    have time := load_later now later (pass cfg env now s) passed
    have queued : (pass cfg env now s).queued ≠ [] := by
      unfold afterPass at verdict
      intro empty
      repeat' split at verdict
      all_goals first
        | (cases verdict; simp_all)
        | cases verdict
    obtain ⟨f', l'⟩ := moves_giveUp env' later (pass cfg env now s) queued
    omega

/-- A run of the loop: rounds, and between them what is no round. Work outside the queue
gives it tasks (`add`, `extend`) or cancels one (`cancel`). And a wait may end with more
than one task ended: the first is its round's, each other is counted here. A wait that
ends with no task ended, because its poll time passed or a task was given, changes
nothing, and the loop makes its pass again. -/
inductive Rounds (cfg : QueueConfig) : Nat → Time × QueueState → Time × QueueState → Prop where
  | none (start : Time × QueueState) : Rounds cfg 0 start start
  | round (n : Nat) (start between after : Time × QueueState) :
      Rounds cfg n start between → Round cfg between after → Rounds cfg (n + 1) start after
  | ended (n : Nat) (start : Time × QueueState) (now : Time) (s : QueueState) (env : QueueEnv) (id : String)
      (outcome : Outcome) (waitS : Duration) :
      Rounds cfg n start (now, s) → Rounds cfg n start (now, done cfg env now s id outcome waitS)
  | given (n : Nat) (start : Time × QueueState) (now : Time) (s : QueueState) (env : QueueEnv) (tasks : List Task) :
      Rounds cfg n start (now, s) → Rounds cfg n start (now, extend env s tasks)
  | cancelled (n : Nat) (start : Time × QueueState) (now : Time) (s : QueueState) (env : QueueEnv) (key : Key) :
      Rounds cfg n start (now, s) → Rounds cfg n start (now, (cancel env s key).1)

/-- The queue ends. A run of `n` rounds of the loop takes `n` from the load at least, but
for seven for each task the queue is newly given: whatever the tasks' results are,
whenever they end and whatever the callbacks answer. -/
theorem Rounds.bounded {cfg : QueueConfig} {n : Nat} {now later : Time} {s s' : QueueState}
    (run : Rounds cfg n (now, s) (later, s')) :
    n + load later s' + 7 * s.known.length ≤ load now s + 7 * s'.known.length := by
  generalize first : (now, s) = start at run
  generalize last : (later, s') = after at run
  induction run generalizing later s' with
  | none =>
    rw [← first] at last
    cases last
    omega
  | round n _ between after _ step ih =>
    obtain ⟨mid, t⟩ := between
    subst first
    subst last
    have before := ih rfl rfl
    have lowered := step.lowers
    omega
  | ended n _ at_ t env id outcome waitS _ ih =>
    subst first
    cases last
    have before := ih rfl rfl
    obtain ⟨f, l⟩ := drops_done cfg env at_ t id outcome waitS
    omega
  | given n _ at_ t env tasks _ ih =>
    subst first
    cases last
    have before := ih rfl rfl
    obtain ⟨f, l⟩ := moves_extend env at_ tasks t
    omega
  | cancelled n _ at_ t env key _ ih =>
    subst first
    cases last
    have before := ih rfl rfl
    obtain ⟨f, l⟩ := moves_cancel env at_ t key
    omega

/-- From an empty queue, the loop makes at most seven rounds for each task the queue is
given. -/
theorem Rounds.from_empty {cfg : QueueConfig} {n : Nat} {now later : Time} {s' : QueueState}
    (run : Rounds cfg n (now, {}) (later, s')) : n ≤ 7 * s'.known.length := by
  have bound := run.bounded
  simp [load, queuedLoad, runningLoad] at bound
  omega

/-- info: 'Contraagent.Rounds.bounded' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Rounds.bounded

end Contraagent
