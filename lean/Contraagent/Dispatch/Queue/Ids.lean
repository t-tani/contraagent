import Contraagent.Dispatch.Queue.Keys

/-!
# Each task finishes once

The queue finishes a task in one place, where it reports `finished` and calls the
follow-up. `IdsOnce` counts, for each task id, the places the task is held (queued,
running, taken out of the queue to be deferred, or with a result that waits to finish)
and the times the log shows it finished. That count is at most one, and none for an id the
queue was never given; and it is at least the times the log shows the task accepted
(`queued`). Every function of `Queue.lean` keeps it. So no task finishes twice
(`Reachable.finished_once`), and once nothing is queued, running or waiting to finish,
every task the queue accepted has finished (`Reachable.accepted_finished`).

The assumption is about the runner: the task it gives as a task starts has the id of the
task it was given (`QueueEnv.KeepsId`).
-/

namespace Contraagent

/-! ## Counting ids -/

/-- The entries of an id among those that `filter` keeps when it drops the entries of
`out`: none of `out`'s own, all of any other. -/
theorem countP_drop_id (id out : String) (l : List QueueEntry) :
    (l.filter (·.task.id != out)).countP (·.task.id == id) = if id = out then 0 else l.countP (·.task.id == id) := by
  induction l with
  | nil => simp
  | cons e l ih =>
    rw [List.filter_cons]
    by_cases dropped : e.task.id = out
    · have gone : (e.task.id != out) = false := by simp [dropped]
      simp only [gone, Bool.false_eq_true, ↓reduceIte]
      rw [ih, List.countP_cons]
      by_cases same : id = out
      · simp [same]
      · have other : (e.task.id == id) = false := by
          rw [dropped]
          simpa using fun eq : out = id => same eq.symm
        simp [same, other]
    · have keep : (e.task.id != out) = true := by simpa using dropped
      simp only [keep, ↓reduceIte, List.countP_cons]
      rw [ih]
      by_cases same : id = out
      · simp [same, dropped]
      · simp [same]

theorem one_le_countP_id (e : QueueEntry) (l : List QueueEntry) (mem : e ∈ l) :
    1 ≤ l.countP (·.task.id == e.task.id) :=
  List.countP_pos_iff.mpr ⟨e, mem, by simp⟩

/-- The places a task of `id` is held: queued, running, or with a result that waits to
finish. -/
def idCount (id : String) (s : QueueState) : Nat :=
  s.queued.countP (·.task.id == id) + s.running.countP (·.task.id == id)
    + s.settling.countP (·.result.task.id == id)

/-- How many times a log shows the task of `id` finished. -/
def finishedOf (id : String) (log : List QueueEvent) : Nat :=
  log.countP fun
    | .finished result => result.task.id == id
    | _ => false

/-- How many times a log shows the task of `id` accepted. -/
def acceptedOf (id : String) (log : List QueueEvent) : Nat :=
  log.countP fun
    | .queued task => task.id == id
    | _ => false

/-- How many tasks of `id` the queue may hold or have finished: one once it was given the
id, none before. -/
def knownBound (s : QueueState) (id : String) : Nat :=
  if id ∈ s.known then 1 else 0

/-- For each id: the places a task of the id is held, counting the tasks of `limbo` (taken
out of the queue, to be deferred), and the times it finished, are at most one, none for an
id the queue was not given, and at least the times it was accepted. -/
def IdsOnce (s : QueueState) (limbo : List Task) : Prop :=
  ∀ id, acceptedOf id s.log ≤ idCount id s + limbo.countP (·.id == id) + finishedOf id s.log ∧
    idCount id s + limbo.countP (·.id == id) + finishedOf id s.log ≤ knownBound s id

/-- A state with the same tasks, the same ids given and a log that shows the same tasks
accepted and finished keeps the ids once. -/
theorem IdsOnce.congr {s s' : QueueState} {limbo : List Task} (h : IdsOnce s limbo)
    (hq : s'.queued = s.queued) (hr : s'.running = s.running) (hs : s'.settling = s.settling)
    (hk : s'.known = s.known) (ha : ∀ id, acceptedOf id s'.log = acceptedOf id s.log)
    (hf : ∀ id, finishedOf id s'.log = finishedOf id s.log) : IdsOnce s' limbo := by
  intro id
  have := h id
  simp only [idCount, knownBound, hq, hr, hs, hk, ha, hf] at this ⊢
  exact this

/-- Whether an event shows a task accepted or finished. -/
def QueueEvent.counts : QueueEvent → Bool
  | .queued _ => true
  | .finished _ => true
  | _ => false

theorem acceptedOf_report (id : String) (s : QueueState) (event : QueueEvent) (plain : event.counts = false) :
    acceptedOf id (s.report event).log = acceptedOf id s.log := by
  cases event <;> simp_all [acceptedOf, QueueState.report, QueueEvent.counts]

theorem finishedOf_report (id : String) (s : QueueState) (event : QueueEvent) (plain : event.counts = false) :
    finishedOf id (s.report event).log = finishedOf id s.log := by
  cases event <;> simp_all [finishedOf, QueueState.report, QueueEvent.counts]

/-- Reporting an event that shows no task accepted or finished keeps the ids once. -/
theorem idsOnce_of_report {s : QueueState} {limbo : List Task} (event : QueueEvent)
    (plain : event.counts = false) (h : IdsOnce s limbo) : IdsOnce (s.report event) limbo :=
  h.congr rfl rfl rfl rfl (fun id => acceptedOf_report id s event plain) (fun id => finishedOf_report id s event plain)

/-- A result of the task of an id, among those that wait: 1 for that id. -/
def pushedId (result : TaskResult) (id : String) : Nat :=
  if result.task.id == id then 1 else 0

theorem idCount_push (id : String) (s : QueueState) (result : TaskResult) (attempt : Nat) :
    idCount id (s.push result attempt) = idCount id s + pushedId result id := by
  simp only [idCount, pushedId, QueueState.push, List.countP_append, List.countP_cons, List.countP_nil]
  split <;> simp_all <;> omega

theorem idsOnce_push {s : QueueState} {limbo : List Task} (result : TaskResult) (attempt : Nat)
    (h : ∀ id, acceptedOf id s.log ≤ idCount id s + pushedId result id + limbo.countP (·.id == id) + finishedOf id s.log ∧
      idCount id s + pushedId result id + limbo.countP (·.id == id) + finishedOf id s.log ≤ knownBound s id) :
    IdsOnce (s.push result attempt) limbo := by
  intro id
  have := h id
  rw [idCount_push]
  exact this

theorem idCount_dequeue (id out : String) (s : QueueState) :
    idCount id (s.dequeue out) + (if id = out then s.queued.countP (·.task.id == id) else 0) = idCount id s := by
  have dropped := countP_drop_id id out s.queued
  simp only [idCount, QueueState.dequeue]
  by_cases same : id = out
  · simp only [same, ↓reduceIte] at dropped ⊢
    omega
  · simp only [same, ↓reduceIte] at dropped ⊢
    omega

/-- Marking queued entries, their tasks unchanged, changes no count. -/
theorem idCount_map_queued (id : String) (s : QueueState) (f : QueueEntry → QueueEntry)
    (same : ∀ e, (f e).task = e.task) :
    idCount id { s with queued := s.queued.map f } = idCount id s := by
  simp only [idCount, List.countP_map]
  congr 2
  apply List.countP_congr
  intro e _
  simp [Function.comp, same]

/-- Marking running entries, their tasks unchanged, changes no count. -/
theorem idCount_map_running (id : String) (s : QueueState) (f : QueueEntry → QueueEntry)
    (same : ∀ e, (f e).task = e.task) :
    idCount id { s with running := s.running.map f } = idCount id s := by
  simp only [idCount, List.countP_map]
  congr 2
  apply List.countP_congr
  intro e _
  simp [Function.comp, same]

/-- A queued task is the one task of its id: nothing else of the id is held or finished. -/
theorem idsOnce_queued_alone {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo) (e : QueueEntry)
    (mem : e ∈ s.queued) :
    s.queued.countP (·.task.id == e.task.id) = 1 ∧ idCount e.task.id s = 1 ∧
      limbo.countP (·.id == e.task.id) = 0 ∧ finishedOf e.task.id s.log = 0 := by
  have present := one_le_countP_id e s.queued mem
  have upper := (h e.task.id).2
  have atMost : knownBound s e.task.id ≤ 1 := by
    unfold knownBound
    split <;> omega
  simp only [idCount] at upper ⊢
  omega

/-- Moving a queued task out of the queue and its result among those that wait keeps the
ids once, when the result is of a task with the same id. -/
theorem idsOnce_dequeue_push {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.queued) (result : TaskResult) (attempt : Nat)
    (sameId : result.task.id = e.task.id) :
    IdsOnce ((s.dequeue e.task.id).push result attempt) limbo := by
  apply idsOnce_push
  intro id
  obtain ⟨lower, upper⟩ := h id
  obtain ⟨one, _, _, _⟩ := idsOnce_queued_alone h e mem
  have moved := idCount_dequeue id e.task.id s
  have bound : knownBound (s.dequeue e.task.id) id = knownBound s id := rfl
  have log : (s.dequeue e.task.id).log = s.log := rfl
  rw [bound, log]
  by_cases hk : id = e.task.id
  · subst hk
    have own : pushedId result e.task.id = 1 := by simp [pushedId, sameId]
    simp only [↓reduceIte] at moved
    omega
  · have none : pushedId result id = 0 := by
      simp only [pushedId, sameId]
      have : (e.task.id == id) = false := by simpa using fun eq : e.task.id = id => hk eq.symm
      simp [this]
    simp only [hk, ↓reduceIte] at moved
    omega

/-- `skip` asked about queued tasks keeps the ids once. -/
theorem idsOnce_skipStartable (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) :
    ∀ (ids : List String) (s : QueueState), IdsOnce s limbo → IdsOnce (skipStartable env s ids) limbo := by
  intro ids
  induction ids with
  | nil => intro s h; exact h
  | cons id rest ih =>
    intro s h
    unfold skipStartable
    split
    · exact ih s h
    · rename_i e found
      have mem : e ∈ s.queued := List.mem_of_find?_eq_some found
      have ide : e.task.id = id := by
        have := List.find?_some found
        simpa using this
      split
      · dsimp only
        split
        · apply ih
          rw [← ide]
          exact idsOnce_dequeue_push h e mem _ 0 (keeps e.task)
        · apply ih
          intro other
          have := h other
          rw [idCount_map_queued other s _ (by intro q; split <;> rfl)]
          exact this
      · exact ih s h

/-- A task of an id the queue was not given is nowhere: not held, not accepted, not
finished. -/
theorem idsOnce_fresh {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo) (id : String)
    (fresh : id ∉ s.known) :
    idCount id s = 0 ∧ limbo.countP (·.id == id) = 0 ∧ finishedOf id s.log = 0 ∧ acceptedOf id s.log = 0 := by
  obtain ⟨lower, upper⟩ := h id
  simp only [knownBound, fresh, ↓reduceIte] at upper
  omega

/-- Queueing one task keeps the ids once: its id is given now, and it is held once when it
is accepted. -/
theorem idsOnce_addCore (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task)
    (s : QueueState) (task : Task) (h : IdsOnce s limbo) :
    IdsOnce (addCore env s task).1 limbo := by
  unfold addCore
  split
  · exact h
  · rename_i unknown
    have fresh : task.id ∉ s.known := by simpa using unknown
    obtain ⟨held0, limbo0, fin0, acc0⟩ := idsOnce_fresh h task.id fresh
    dsimp only
    split
    · intro id
      obtain ⟨lower, upper⟩ := h id
      simp only [idCount, knownBound, finishedOf, acceptedOf, QueueState.report, List.countP_cons, List.mem_cons] at lower upper ⊢
      by_cases hk : id = task.id
      · subst hk
        simp only [idCount, finishedOf, acceptedOf] at held0 fin0 acc0
        simp
        omega
      · simp [hk] at lower upper ⊢
        omega
    · split
      · intro id
        obtain ⟨lower, upper⟩ := h id
        simp only [idCount, knownBound, finishedOf, acceptedOf, QueueState.report, QueueState.push, List.countP_append,
          List.countP_cons, List.countP_nil, List.mem_cons, TaskResult.skipped] at lower upper ⊢
        by_cases hk : id = task.id
        · subst hk
          simp only [idCount, finishedOf, acceptedOf] at held0 fin0 acc0
          simp
          omega
        · have ne : (task.id == id) = false := by simpa using fun e => hk e.symm
          simp [hk, ne] at lower upper ⊢
          omega
      · apply idsOnce_skipStartable env keeps
        intro id
        obtain ⟨lower, upper⟩ := h id
        simp only [idCount, knownBound, finishedOf, acceptedOf, QueueState.report, List.countP_append, List.countP_cons,
          List.countP_nil, List.mem_cons] at lower upper ⊢
        by_cases hk : id = task.id
        · subst hk
          simp only [idCount, finishedOf, acceptedOf] at held0 fin0 acc0
          simp
          omega
        · have ne : (task.id == id) = false := by simpa using fun e => hk e.symm
          simp [hk, ne] at lower upper ⊢
          omega

/-- A task that is refused for its key, of an id the queue was not given: its id is given,
and nothing else changes. -/
theorem addCore_refused (env : QueueEnv) (s : QueueState) (task : Task) (fresh : s.known.contains task.id = false)
    (refused : (addCore env s task).2 = false) :
    (addCore env s task).1 =
      ({ s with known := task.id :: s.known, nextSeq := s.nextSeq + 1 } : QueueState).report (.duplicateKeyRefused task) := by
  unfold addCore at refused ⊢
  simp only [fresh, Bool.false_eq_true, ↓reduceIte] at refused ⊢
  split
  · rfl
  · rename_i free
    simp only [free, Bool.false_eq_true, ↓reduceIte] at refused
    split at refused <;> cases refused

/-- The result of a refused task, among those that wait, after its id was given. -/
theorem idsOnce_refused {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo) (task : Task)
    (fresh : task.id ∉ s.known) (attempt : Nat) :
    IdsOnce ((({ s with known := task.id :: s.known, nextSeq := s.nextSeq + 1 } : QueueState).report
      (.duplicateKeyRefused task)).push (TaskResult.duplicateKey task) attempt) limbo := by
  obtain ⟨held0, limbo0, fin0, acc0⟩ := idsOnce_fresh h task.id fresh
  intro id
  obtain ⟨lower, upper⟩ := h id
  simp only [idCount, knownBound, finishedOf, acceptedOf, QueueState.report, QueueState.push, List.countP_append,
    List.countP_cons, List.countP_nil, List.mem_cons, TaskResult.duplicateKey] at lower upper ⊢
  by_cases hk : id = task.id
  · subst hk
    simp only [idCount, finishedOf, acceptedOf] at held0 fin0 acc0
    simp
    omega
  · have ne : (task.id == id) = false := by simpa using fun e => hk e.symm
    simp [hk, ne] at lower upper ⊢
    omega

/-- Queueing follow-up work keeps the ids once: a refused task's result waits to finish,
once. -/
theorem idsOnce_extendCore (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) :
    ∀ (tasks : List Task) (s : QueueState), IdsOnce s limbo → IdsOnce (extendCore env s tasks) limbo := by
  intro tasks
  induction tasks with
  | nil => intro s h; exact h
  | cons task rest ih =>
    intro s h
    unfold extendCore
    split
    · exact ih s h
    · rename_i unknown
      have fresh : s.known.contains task.id = false := by simpa using unknown
      have added := idsOnce_addCore env keeps limbo s task h
      split
      · rename_i s' heq
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        have refused := addCore_refused env s task fresh (by rw [heq])
        rw [heq] at refused
        apply ih
        rw [show s' = _ from refused]
        exact idsOnce_refused h task (by simpa using fresh) 0

/-- Taking the first waiting result to finish it: the task is no longer held, and the log
shows it finished. -/
theorem idsOnce_pop {s s1 : QueueState} {limbo : List Task} (p : Settling) (rest : List Settling)
    (h : IdsOnce { s with settling := p :: rest } limbo)
    (hq : s1.queued = s.queued) (hr : s1.running = s.running) (hs : s1.settling = rest)
    (hk : s1.known = s.known) (ha : ∀ id, acceptedOf id s1.log = acceptedOf id s.log)
    (hf : ∀ id, finishedOf id s1.log = finishedOf id s.log + if p.result.task.id == id then 1 else 0) :
    IdsOnce s1 limbo := by
  intro id
  obtain ⟨lower, upper⟩ := h id
  simp only [idCount, knownBound, hq, hr, hs, hk, ha, hf, List.countP_cons] at lower upper ⊢
  omega

theorem reportEnd_accepted (s : QueueState) (p : Settling) (id : String) :
    acceptedOf id (reportEnd s p).log = acceptedOf id s.log := by
  unfold reportEnd
  dsimp only
  split <;> simp [acceptedOf, QueueState.report]

theorem reportEnd_finished (s : QueueState) (p : Settling) (id : String) :
    finishedOf id (reportEnd s p).log = finishedOf id s.log + if p.result.task.id == id then 1 else 0 := by
  unfold reportEnd
  dsimp only
  split <;> simp [finishedOf, QueueState.report, List.countP_cons]

/-- Closing one task keeps the ids once: it is no longer held and the log shows it
finished, and what its follow-ups queue and what a resume then skips keep them once. -/
theorem idsOnce_finishOne (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task)
    (s : QueueState) (p : Settling) (rest : List Settling)
    (h : IdsOnce { s with settling := p :: rest } limbo) :
    IdsOnce (finishOne env { s with settling := rest } p) limbo := by
  unfold finishOne
  dsimp only
  have marked : ∀ t : QueueState, (markDone t p.result).queued = t.queued ∧ (markDone t p.result).running = t.running ∧
      (markDone t p.result).settling = t.settling ∧ (markDone t p.result).known = t.known ∧
      (markDone t p.result).log = t.log := by
    intro t
    unfold markDone
    split <;> exact ⟨rfl, rfl, rfl, rfl, rfl⟩
  have reported : ∀ t : QueueState, (reportEnd t p).queued = t.queued ∧ (reportEnd t p).running = t.running ∧
      (reportEnd t p).settling = t.settling ∧ (reportEnd t p).known = t.known := by
    intro t
    unfold reportEnd
    dsimp only
    split <;> exact ⟨rfl, rfl, rfl, rfl⟩
  have ended : IdsOnce (reportEnd (markDone { s with settling := rest } p.result) p) limbo := by
    obtain ⟨mq, mr, ms, mk, ml⟩ := marked { s with settling := rest }
    obtain ⟨rq, rr, rs, rk⟩ := reported (markDone { s with settling := rest } p.result)
    refine idsOnce_pop p rest h (rq.trans mq) (rr.trans mr) (rs.trans ms) (rk.trans mk) ?_ ?_
    · intro id
      rw [reportEnd_accepted, ml]
    · intro id
      rw [reportEnd_finished, ml]
  split
  · exact idsOnce_extendCore env keeps limbo _ _ ended
  · apply idsOnce_skipStartable env keeps
    exact idsOnce_extendCore env keeps limbo _ _ ended

/-- Finishing the results that wait keeps the ids once. -/
theorem idsOnce_drain (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) :
    ∀ (fuel : Nat) (s : QueueState), IdsOnce s limbo → IdsOnce (drain env fuel s) limbo := by
  intro fuel
  induction fuel with
  | zero => intro s h; exact h
  | succ fuel ih =>
    intro s h
    unfold drain
    split
    · exact h
    · rename_i p rest heq
      apply ih
      exact idsOnce_finishOne env keeps limbo s p rest (h.congr rfl rfl heq.symm rfl (fun _ => rfl) (fun _ => rfl))

theorem idsOnce_settle (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (result : TaskResult) (attempt : Nat) (h : IdsOnce (s.push result attempt) limbo) :
    IdsOnce (settle env s result attempt) limbo :=
  idsOnce_drain env keeps limbo _ _ h

/-- The result of a task that was taken out, among those that wait. -/
theorem idsOnce_limbo_push {s : QueueState} {limbo : List Task} (task : Task) (result : TaskResult)
    (attempt : Nat) (same : result.task.id = task.id) (h : IdsOnce s (task :: limbo)) :
    IdsOnce (s.push result attempt) limbo := by
  apply idsOnce_push
  intro id
  obtain ⟨lower, upper⟩ := h id
  simp only [List.countP_cons] at lower upper
  simp only [pushedId, same]
  omega

/-- Deferring a task that was taken out of the queue keeps the ids once. -/
theorem idsOnce_defer (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (task : Task) (why : Deferral) (h : IdsOnce s (task :: limbo)) :
    IdsOnce (defer env s task why) limbo := by
  unfold defer
  apply idsOnce_settle env keeps
  exact idsOnce_limbo_push task _ 0 rfl (idsOnce_of_report _ rfl h)

theorem idsOnce_deferEach (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) :
    ∀ (tasks : List (Task × Deferral)) (s : QueueState),
      IdsOnce s (tasks.map (·.1) ++ limbo) → IdsOnce (deferEach env s tasks) limbo := by
  intro tasks
  induction tasks with
  | nil =>
    intro s h
    unfold deferEach
    simpa using h
  | cons tw rest ih =>
    intro s h
    obtain ⟨task, why⟩ := tw
    unfold deferEach
    apply ih
    apply idsOnce_defer env keeps
    simpa using h

/-! ## Taking several tasks out of the queue -/

/-- The tasks a selection makes of a list's entries are no more, for each id, than the
entries of that id it selects. -/
theorem countP_filterMap_le_id (f : QueueEntry → Option (Task × Deferral)) (sel : QueueEntry → Bool)
    (id : String) (l : List QueueEntry)
    (hf : ∀ e ∈ l, ∀ tw, f e = some tw → tw.1 = e.task ∧ sel e = true) :
    (l.filterMap f).countP (·.1.id == id) ≤ l.countP fun e => e.task.id == id && sel e := by
  induction l with
  | nil => simp
  | cons a l ih =>
    have rest := ih fun e mem tw eq => hf e (List.mem_cons_of_mem a mem) tw eq
    cases fa : f a with
    | none =>
      simp only [List.filterMap_cons, fa, List.countP_cons]
      omega
    | some tw =>
      obtain ⟨same, selected⟩ := hf a List.mem_cons_self tw fa
      simp only [List.filterMap_cons, fa, List.countP_cons, same, selected, Bool.and_true]
      omega

/-- Taking the tasks a selection makes of the queue's entries out of the queue and
deferring each keeps the ids once. -/
theorem idsOnce_deferAll (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (f : QueueEntry → Option (Task × Deferral)) (hf : ∀ e tw, f e = some tw → tw.1 = e.task)
    (h : IdsOnce s limbo) : IdsOnce (deferAll env s (s.queued.filterMap f)) limbo := by
  unfold deferAll
  apply idsOnce_deferEach env keeps
  rw [foldl_dequeue]
  intro id
  obtain ⟨lower, upper⟩ := h id
  have taken := countP_filterMap_le_id f
    (fun e => (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id) id s.queued (by
      intro e mem tw eq
      refine ⟨hf e tw eq, ?_⟩
      simp only [List.any_eq_true]
      exact ⟨tw, List.mem_filterMap.mpr ⟨e, mem, eq⟩, by simp [hf e tw eq]⟩)
  have parts := countP_split (fun e : QueueEntry => e.task.id == id)
    (fun e => (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id) s.queued
  have atMost : knownBound s id ≤ 1 := by
    unfold knownBound
    split <;> omega
  -- An entry of the id that the selection names has a task of the id among those taken.
  have given : (s.queued.countP fun e => e.task.id == id && (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id)
      ≤ (s.queued.filterMap f).countP (·.1.id == id) := by
    by_cases some : 0 < s.queued.countP fun e =>
        e.task.id == id && (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id
    · obtain ⟨e, _, named⟩ := List.countP_pos_iff.mp some
      simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at named
      obtain ⟨isId, tw, there, sameId⟩ := named
      have one : 0 < (s.queued.filterMap f).countP (·.1.id == id) :=
        List.countP_pos_iff.mpr ⟨tw, there, by rw [← isId]; simpa using sameId⟩
      simp only [idCount] at upper
      omega
    · omega
  simp only [idCount, knownBound, List.countP_append, List.countP_map] at lower upper atMost ⊢
  have same : (List.countP ((fun x => x.id == id) ∘ fun x => x.1) (s.queued.filterMap f))
      = (s.queued.filterMap f).countP (·.1.id == id) := rfl
  rw [same]
  omega

/-! ## What the queue is told, a pass, and a task's end -/

/-- A queued task taken out of the queue, to be deferred. -/
theorem idsOnce_dequeue_limbo {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.queued) : IdsOnce (s.dequeue e.task.id) (e.task :: limbo) := by
  intro id
  obtain ⟨lower, upper⟩ := h id
  obtain ⟨one, _, _, _⟩ := idsOnce_queued_alone h e mem
  have moved := idCount_dequeue id e.task.id s
  have bound : knownBound (s.dequeue e.task.id) id = knownBound s id := rfl
  have log : (s.dequeue e.task.id).log = s.log := rfl
  rw [bound, log]
  simp only [List.countP_cons]
  by_cases hk : id = e.task.id
  · subst hk
    simp only [↓reduceIte] at moved
    simp
    omega
  · have ne : (e.task.id == id) = false := by simpa using fun eq : e.task.id = id => hk eq.symm
    simp only [hk, ↓reduceIte] at moved
    simp [ne]
    omega

/-- A running task taken out of those that run, to be finished or queued again. -/
theorem idsOnce_unrun {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.running) :
    IdsOnce { s with running := s.running.filter (·.task.id != e.task.id) } (e.task :: limbo) := by
  intro id
  obtain ⟨lower, upper⟩ := h id
  have present := one_le_countP_id e s.running mem
  have own := (h e.task.id).2
  have atMost : knownBound s e.task.id ≤ 1 := by
    unfold knownBound
    split <;> omega
  have dropped := countP_drop_id id e.task.id s.running
  simp only [idCount, knownBound, List.countP_cons] at lower upper own atMost ⊢
  by_cases hk : id = e.task.id
  · subst hk
    simp only [↓reduceIte] at dropped
    simp
    omega
  · have ne : (e.task.id == id) = false := by simpa using fun eq : e.task.id = id => hk eq.symm
    simp only [hk, ↓reduceIte] at dropped
    simp [ne]
    omega

/-- A task that was taken out, queued again. -/
theorem idsOnce_limbo_enqueue {s : QueueState} {limbo : List Task} (task : Task) (entry : QueueEntry)
    (same : entry.task = task) (h : IdsOnce s (task :: limbo)) :
    IdsOnce { s with queued := entry :: s.queued } limbo := by
  intro id
  have base := h id
  simp only [idCount, knownBound, List.countP_cons, same] at base ⊢
  omega

/-- A task that was taken out, running. -/
theorem idsOnce_limbo_run {s : QueueState} {limbo : List Task} (task : Task) (entry : QueueEntry)
    (same : entry.task.id = task.id) (h : IdsOnce s (task :: limbo)) :
    IdsOnce { s with running := s.running ++ [entry] } limbo := by
  intro id
  have base := h id
  simp only [idCount, knownBound, List.countP_cons, List.countP_append, List.countP_nil, same] at base ⊢
  omega

theorem idsOnce_add (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (task : Task) (h : IdsOnce s limbo) : IdsOnce (add env s task).1 limbo := by
  have added := idsOnce_addCore env keeps limbo s task h
  unfold add
  cases res : addCore env s task with
  | mk s' accepted =>
    rw [res] at added
    exact idsOnce_drain env keeps limbo _ _ added

/-- A task refused for its key, of an id the queue was not given, counted as taken out:
its result is still to wait to finish. -/
theorem idsOnce_refused_limbo {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo) (task : Task)
    (fresh : task.id ∉ s.known) :
    IdsOnce (({ s with known := task.id :: s.known, nextSeq := s.nextSeq + 1 } : QueueState).report
      (.duplicateKeyRefused task)) (task :: limbo) := by
  obtain ⟨held0, limbo0, fin0, acc0⟩ := idsOnce_fresh h task.id fresh
  intro id
  obtain ⟨lower, upper⟩ := h id
  simp only [idCount, knownBound, finishedOf, acceptedOf, QueueState.report, List.countP_cons, List.mem_cons] at lower upper ⊢
  by_cases hk : id = task.id
  · subst hk
    simp only [idCount, finishedOf, acceptedOf] at held0 fin0 acc0
    simp
    omega
  · have ne : (task.id == id) = false := by simpa using fun e => hk e.symm
    simp [hk, ne] at lower upper ⊢
    omega

theorem idsOnce_extend (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) :
    ∀ (tasks : List Task) (s : QueueState), IdsOnce s limbo → IdsOnce (extend env s tasks) limbo := by
  intro tasks
  induction tasks with
  | nil => intro s h; unfold extend; exact h
  | cons task rest ih =>
    intro s h
    unfold extend
    split
    · exact ih s h
    · rename_i unknown
      have fresh : s.known.contains task.id = false := by simpa using unknown
      split
      · rename_i s' heq
        have added := idsOnce_add env keeps limbo s task h
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        -- The refused task counts as taken out while what waits is finished, then its result waits.
        have refused : IdsOnce s' (task :: limbo) := by
          have parts : (add env s task) = (drain env env.fuel (addCore env s task).1, (addCore env s task).2) := rfl
          rw [parts] at heq
          simp only [Prod.mk.injEq] at heq
          have core := addCore_refused env s task fresh heq.2
          rw [← heq.1, core]
          exact idsOnce_drain env keeps _ _ _ (idsOnce_refused_limbo h task (by simpa using fresh))
        apply ih
        apply idsOnce_settle env keeps
        exact idsOnce_limbo_push task _ 0 rfl refused

theorem idsOnce_cancel (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (key : Key) (h : IdsOnce s limbo) : IdsOnce (cancel env s key).1 limbo := by
  unfold cancel
  split
  · rename_i e found
    have mem : e ∈ s.queued := List.mem_of_find?_eq_some found
    apply idsOnce_settle env keeps
    exact idsOnce_limbo_push e.task _ e.attempt rfl (idsOnce_of_report _ rfl (idsOnce_dequeue_limbo h e mem))
  · split
    · intro id
      have := h id
      rw [idCount_map_running id s _ (by intro q; split <;> rfl)]
      exact this
    · exact h

theorem idsOnce_markReady (now : Time) (limbo : List Task) (s : QueueState) (h : IdsOnce s limbo) :
    IdsOnce (markReady now s) limbo := by
  intro id
  have := h id
  unfold markReady
  rw [idCount_map_queued id s _ (by intro q; split <;> rfl)]
  exact this

theorem idsOnce_deferClosed (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsId) (now : Time)
    (limbo : List Task) (s : QueueState) (h : IdsOnce s limbo) :
    IdsOnce (deferClosed cfg env now s) limbo := by
  unfold deferClosed
  apply idsOnce_deferAll env keeps limbo s _ _ h
  intro e tw eq
  simp at eq
  obtain ⟨why, _, rfl⟩ := eq
  rfl

/-- Going down the order keeps the ids once: a task that starts leaves the queue as it
joins those that run, with the id it had. -/
theorem idsOnce_sweep (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsId) (now : Time)
    (late : List (String × Deferral)) (limbo : List Task) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      IdsOnce s limbo → IdsOnce (sweep cfg env now late order w s) limbo := by
  intro order
  induction order with
  | nil => intro w s h; unfold sweep; exact h
  | cons e rest ih =>
    intro w s h
    unfold sweep
    split
    · split
      · dsimp only
        apply idsOnce_deferAll env keeps limbo s _ _ h
        intro q tw eq
        split at eq
        · simp at eq
          obtain ⟨why, _, rfl⟩ := eq
          rfl
        · simp at eq
      · exact h
    · split
      · exact ih w s h
      · rename_i _ found isFound
        have mem : found ∈ s.queued := List.mem_of_find?_eq_some isFound
        repeat' split
        all_goals first
          | exact ih _ s h
          | (apply ih
             apply idsOnce_defer env keeps
             exact idsOnce_dequeue_limbo h found mem)
          | (apply ih
             refine idsOnce_limbo_run found.task _ ?_ (idsOnce_of_report _ rfl (idsOnce_dequeue_limbo h found mem))
             first | exact keeps found.task | rfl)

theorem idsOnce_pass (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsId) (now : Time)
    (limbo : List Task) (s : QueueState) (h : IdsOnce s limbo) :
    IdsOnce (pass cfg env now s) limbo := by
  unfold pass
  dsimp only
  apply idsOnce_sweep cfg env keeps
  apply idsOnce_markReady
  exact idsOnce_deferClosed cfg env keeps now limbo s h

theorem idsOnce_countThrottle (cfg : QueueConfig) (now : Time) (task : Task) (stop : Stop)
    {s : QueueState} {limbo : List Task} (h : IdsOnce s limbo) :
    IdsOnce (countThrottle cfg now task stop s) limbo := by
  unfold countThrottle
  split
  · dsimp only
    split
    · exact idsOnce_of_report _ rfl (h.congr rfl rfl rfl rfl (fun _ => rfl) (fun _ => rfl))
    · exact h.congr rfl rfl rfl rfl (fun _ => rfl) (fun _ => rfl)
  · exact h.congr rfl rfl rfl rfl (fun _ => rfl) (fun _ => rfl)

/-- A task's end keeps the ids once: it leaves those that run, and its result waits to
finish or it is queued again. -/
theorem idsOnce_done (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsId) (now : Time)
    (limbo : List Task) (s : QueueState) (id : String) (outcome : Outcome) (waitS : Duration)
    (h : IdsOnce s limbo) : IdsOnce (done cfg env now s id outcome waitS) limbo := by
  unfold done
  split
  · exact h
  · rename_i _ e found
    have mem : e ∈ s.running := List.mem_of_find?_eq_some found
    have ide : e.task.id = id := by simpa using List.find?_some found
    have out := idsOnce_unrun h e mem
    rw [ide] at out
    dsimp only
    split
    · apply idsOnce_settle env keeps
      refine idsOnce_limbo_push e.task _ _ ?_ ?_
      · rfl
      · exact idsOnce_of_report _ rfl out
    · split
      · refine idsOnce_limbo_enqueue e.task _ ?_ ?_
        · rfl
        · apply idsOnce_of_report _ rfl
          apply idsOnce_countThrottle
          exact idsOnce_of_report _ rfl out
      · apply idsOnce_settle env keeps
        refine idsOnce_limbo_push e.task _ _ ?_ ?_
        · rfl
        · apply idsOnce_countThrottle
          exact idsOnce_of_report _ rfl out

theorem idsOnce_giveUp (env : QueueEnv) (keeps : env.KeepsId) (limbo : List Task) (s : QueueState)
    (h : IdsOnce s limbo) : IdsOnce (giveUp env s) limbo := by
  unfold giveUp
  dsimp only
  split
  · rw [map_eq_filterMap_some]
    apply idsOnce_deferAll env keeps limbo s _ _ h
    intro e tw eq
    simp at eq
    rw [← eq]
  · apply idsOnce_deferAll env keeps limbo s _ _ h
    intro e tw eq
    repeat' split at eq
    all_goals simp at eq
    all_goals rw [← eq]

/-! ## Every state the queue reaches -/

/-- In every state the queue reaches, each task is held or finished at most once, and a
task it accepted is held or finished. -/
theorem Reachable.idsOnce {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) :
    IdsOnce s [] := by
  induction reached with
  | start => intro id; simp [idCount, knownBound, finishedOf, acceptedOf]
  | added env keeps s task _ ih => exact idsOnce_add env keeps.id [] s task ih
  | extended env keeps s tasks _ ih => exact idsOnce_extend env keeps.id [] tasks s ih
  | cancelled env keeps s key _ ih => exact idsOnce_cancel env keeps.id [] s key ih
  | passed env keeps now s _ ih => exact idsOnce_pass _ env keeps.id now [] s ih
  | ended env keeps now s id outcome waitS _ ih => exact idsOnce_done _ env keeps.id now [] s id outcome waitS ih
  | gaveUp env keeps s _ ih => exact idsOnce_giveUp env keeps.id [] s ih

/-- No task finishes twice: in every state the queue reaches, the log shows each task
finished once at most. -/
theorem Reachable.finished_once {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) (id : String) :
    finishedOf id s.log ≤ 1 := by
  have upper := (reached.idsOnce id).2
  have atMost : knownBound s id ≤ 1 := by
    unfold knownBound
    split <;> omega
  omega

/-- Once nothing is queued, running or waiting to finish, every task the queue accepted has
finished: with `finished_once`, each of them finished once. -/
theorem Reachable.accepted_finished {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s)
    (queued : s.queued = []) (running : s.running = []) (settling : s.settling = []) (id : String) :
    acceptedOf id s.log ≤ finishedOf id s.log := by
  have lower := (reached.idsOnce id).1
  simp only [idCount, queued, running, settling, List.countP_nil] at lower
  omega

/-- info: 'Contraagent.Reachable.finished_once' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Reachable.finished_once

end Contraagent
