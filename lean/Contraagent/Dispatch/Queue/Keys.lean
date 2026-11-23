import Contraagent.Dispatch.Queue

/-!
# No key is in flight twice

A key the queue accepted and has not finished is in flight. `KeysOnce` says that at most
one task of each key is queued, running, taken out of the queue to be deferred, or
waiting to finish, and that its key is then among `QueueState.inflight`. Every function
of `Queue.lean` keeps it, so no two tasks of one key ever run at once
(`running_keys_distinct`).

The one assumption is about the runner: the task it gives as a task starts
(`QueueEnv.starting`) has the key of the task it was given.
-/

namespace Contraagent

/-! ## Counting in lists -/

theorem countP_filter_le {α : Type} (p q : α → Bool) (l : List α) :
    (l.filter q).countP p ≤ l.countP p := by
  induction l with
  | nil => simp
  | cons a l ih =>
    by_cases hq : q a = true <;> by_cases hp : p a = true <;>
      simp [hq, hp] <;> omega

/-- Filtering out an element that `p` counts lowers the count. -/
theorem countP_filter_lt {α : Type} (p q : α → Bool) (l : List α) (a : α) (mem : a ∈ l)
    (counted : p a = true) (out : q a = false) : (l.filter q).countP p + 1 ≤ l.countP p := by
  induction l with
  | nil => simp at mem
  | cons b l ih =>
    rcases List.mem_cons.mp mem with rfl | mem
    · have := countP_filter_le p q l
      simp [counted, out]
      omega
    · have := ih mem
      by_cases hq : q b = true <;> by_cases hp : p b = true <;>
        simp [hq, hp] <;> omega

/-- How many tasks of `key` the queue holds: queued, running, or with a result that waits
to finish. A refused duplicate is not counted: its key is the other task's. -/
def keyCount (key : Key) (s : QueueState) : Nat :=
  s.queued.countP (·.task.key == key) + s.running.countP (·.task.key == key)
    + s.settling.countP fun p => p.result.stop != Stop.duplicateKey && p.result.task.key == key

/-- How many tasks of `key` the queue may hold: one while the key is in flight, none else. -/
def flightBound (s : QueueState) (key : Key) : Nat :=
  if key ∈ s.inflight then 1 else 0

/-- At most one task of each key is held, counting the tasks of `limbo` (taken out of the
queue, to be deferred), and a key that is held is in flight. -/
def KeysOnce (s : QueueState) (limbo : List Task) : Prop :=
  ∀ key, keyCount key s + limbo.countP (·.key == key) ≤ flightBound s key

/-- The runner gives a task as it starts with the key it was given. -/
def QueueEnv.KeepsKey (env : QueueEnv) : Prop :=
  ∀ task, (env.starting task).key = task.key

theorem keyCount_push (key : Key) (s : QueueState) (result : TaskResult) (attempt : Nat) :
    keyCount key (s.push result attempt)
      = keyCount key s + if (result.stop != Stop.duplicateKey && result.task.key == key) then 1 else 0 := by
  simp only [keyCount, QueueState.push, List.countP_append, List.countP_cons, List.countP_nil]
  split <;> simp_all <;> omega

theorem keyCount_dequeue_le (key : Key) (s : QueueState) (id : String) :
    keyCount key (s.dequeue id) ≤ keyCount key s := by
  have := countP_filter_le (fun e : QueueEntry => e.task.key == key) (·.task.id != id) s.queued
  simp only [keyCount, QueueState.dequeue]
  omega

/-- Taking a queued task out of the queue lowers the count of its key. -/
theorem keyCount_dequeue_lt (s : QueueState) (e : QueueEntry) (mem : e ∈ s.queued) :
    keyCount e.task.key (s.dequeue e.task.id) + 1 ≤ keyCount e.task.key s := by
  have := countP_filter_lt (fun q : QueueEntry => q.task.key == e.task.key) (·.task.id != e.task.id)
    s.queued e mem (by simp) (by simp)
  simp only [keyCount, QueueState.dequeue]
  omega

/-- Marking queued entries, their tasks unchanged, changes no count. -/
theorem keyCount_map_queued (key : Key) (s : QueueState) (f : QueueEntry → QueueEntry)
    (same : ∀ e, (f e).task = e.task) :
    keyCount key { s with queued := s.queued.map f } = keyCount key s := by
  simp only [keyCount, List.countP_map]
  congr 2
  apply List.countP_congr
  intro e _
  simp [Function.comp, same]

/-- A result of a task of a key pushed among those that wait: 1 for that key when the
result is not a refused duplicate's. -/
def pushed (result : TaskResult) (key : Key) : Nat :=
  if (result.stop != Stop.duplicateKey && result.task.key == key) then 1 else 0

theorem keysOnce_push {s : QueueState} {limbo : List Task} (result : TaskResult) (attempt : Nat)
    (h : ∀ key, keyCount key s + pushed result key + limbo.countP (·.key == key) ≤ flightBound s key) :
    KeysOnce (s.push result attempt) limbo := by
  intro key
  have := h key
  rw [keyCount_push]
  exact this

theorem pushed_own (task : Task) (ok : Bool) (stop : Stop) (cause : Option DeferralCause)
    (retryable : Bool) (notDuplicate : stop ≠ Stop.duplicateKey) :
    pushed { task := task, ok := ok, stop := stop, cause := cause, retryable := retryable } task.key = 1 := by
  simp [pushed, notDuplicate]

theorem pushed_other (result : TaskResult) (key : Key) (other : result.task.key ≠ key) :
    pushed result key = 0 := by
  simp [pushed, other]

theorem pushed_le (result : TaskResult) (key : Key) : pushed result key ≤ 1 := by
  unfold pushed
  split <;> omega

/-- Moving a queued task out of the queue and its result among those that wait keeps the
keys once, when the result is of a task with the same key. -/
theorem keysOnce_dequeue_push {s : QueueState} {limbo : List Task} (h : KeysOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.queued) (result : TaskResult) (attempt : Nat)
    (sameKey : result.task.key = e.task.key) :
    KeysOnce ((s.dequeue e.task.id).push result attempt) limbo := by
  apply keysOnce_push
  intro key
  have le := keyCount_dequeue_le key s e.task.id
  have lt := keyCount_dequeue_lt s e mem
  have base := h key
  have bound : flightBound (s.dequeue e.task.id) key = flightBound s key := rfl
  have one := pushed_le result key
  rw [bound]
  by_cases hk : e.task.key = key
  · subst hk
    omega
  · have := pushed_other result key (by rw [sameKey]; exact hk)
    omega

/-- `skip` asked about queued tasks keeps the keys once. -/
theorem keysOnce_skipStartable (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) :
    ∀ (ids : List String) (s : QueueState), KeysOnce s limbo → KeysOnce (skipStartable env s ids) limbo := by
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
          exact keysOnce_dequeue_push h e mem _ 0 (keeps e.task)
        · apply ih
          intro key
          have := h key
          rw [keyCount_map_queued key s _ (by intro q; split <;> rfl)]
          exact this
      · exact ih s h

/-- Queueing one task keeps the keys once: a task whose key is in flight is refused. -/
theorem keysOnce_addCore (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task)
    (s : QueueState) (task : Task) (h : KeysOnce s limbo) :
    KeysOnce (addCore env s task).1 limbo := by
  unfold addCore
  split
  · exact h
  · dsimp only
    split
    · exact h
    · rename_i fresh
      have absent : task.key ∉ s.inflight := by simpa using fresh
      split
      · intro key
        have base := h key
        simp only [keyCount, flightBound, QueueState.report, QueueState.push, List.countP_append,
          List.countP_cons, List.countP_nil, List.mem_cons, TaskResult.skipped] at base ⊢
        by_cases hk : key = task.key
        · subst hk
          simp [Stop.skipped, Stop.duplicateKey] at base ⊢
          simp only [absent, ite_false] at base
          omega
        · have ne : (task.key == key) = false := by simpa using fun e => hk e.symm
          simp [hk, ne] at base ⊢
          omega
      · apply keysOnce_skipStartable env keeps
        intro key
        have base := h key
        simp only [keyCount, flightBound, QueueState.report, List.countP_append, List.countP_cons,
          List.countP_nil, List.mem_cons] at base ⊢
        by_cases hk : key = task.key
        · subst hk
          simp at base ⊢
          simp only [absent, ite_false] at base
          omega
        · have ne : (task.key == key) = false := by simpa using fun e => hk e.symm
          simp [hk, ne] at base ⊢
          omega

/-- Queueing follow-up work keeps the keys once: a refused task's result is no task's of
its key. -/
theorem keysOnce_extendCore (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) :
    ∀ (tasks : List Task) (s : QueueState), KeysOnce s limbo → KeysOnce (extendCore env s tasks) limbo := by
  intro tasks
  induction tasks with
  | nil => intro s h; exact h
  | cons task rest ih =>
    intro s h
    unfold extendCore
    split
    · exact ih s h
    · have added := keysOnce_addCore env keeps limbo s task h
      split
      · rename_i s' heq
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        rw [heq] at added
        have added : KeysOnce s' limbo := added
        apply ih
        apply keysOnce_push
        intro key
        have := added key
        have zero : pushed (TaskResult.duplicateKey task) key = 0 := by
          simp [pushed, TaskResult.duplicateKey]
        omega

/-- A state with the same tasks and the same keys in flight keeps the keys once. -/
theorem KeysOnce.congr {s s' : QueueState} {limbo : List Task} (h : KeysOnce s limbo)
    (hq : s'.queued = s.queued) (hr : s'.running = s.running) (hs : s'.settling = s.settling)
    (hi : s'.inflight = s.inflight) : KeysOnce s' limbo := by
  intro key
  have := h key
  simp only [keyCount, flightBound, hq, hr, hs, hi] at this ⊢
  exact this

/-- Taking the first waiting result to finish it: its key leaves the keys in flight, unless
it is a refused duplicate, whose key is the other task's. -/
theorem keysOnce_pop {s s1 : QueueState} {limbo : List Task} (p : Settling) (rest : List Settling)
    (h : KeysOnce { s with settling := p :: rest } limbo)
    (hq : s1.queued = s.queued) (hr : s1.running = s.running) (hs : s1.settling = rest)
    (hi : s1.inflight = if p.result.stop == Stop.duplicateKey then s.inflight
      else s.inflight.filter (· != p.result.task.key)) : KeysOnce s1 limbo := by
  intro key
  have base := h key
  have count : keyCount key { s with settling := p :: rest } = keyCount key s1 + pushed p.result key := by
    simp only [keyCount, pushed, hq, hr, hs, List.countP_cons]
    omega
  have atMost : flightBound { s with settling := p :: rest } key ≤ 1 := by
    unfold flightBound
    split <;> omega
  by_cases dup : (p.result.stop == Stop.duplicateKey) = true
  · have isDup : p.result.stop = Stop.duplicateKey := by simpa using dup
    have none : pushed p.result key = 0 := by simp [pushed, isDup]
    have bound : flightBound s1 key = flightBound { s with settling := p :: rest } key := by
      simp [flightBound, hi, dup]
    omega
  · have notDup : p.result.stop ≠ Stop.duplicateKey := by simpa using dup
    by_cases hk : p.result.task.key = key
    · have one : pushed p.result key = 1 := by simp [pushed, notDup, hk]
      have bound : flightBound s1 key = 0 := by
        subst hk
        simp [flightBound, hi, dup]
      omega
    · have none : pushed p.result key = 0 := by simp [pushed, hk]
      have bound : flightBound s1 key = flightBound { s with settling := p :: rest } key := by
        have ne : key ≠ p.result.task.key := fun e => hk e.symm
        simp [flightBound, hi, dup, List.mem_filter, ne]
      omega

/-- Closing one task keeps the keys once: its key leaves those in flight, and what its
follow-ups queue and what a resume then skips keep them once. -/
theorem keysOnce_finishOne (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task)
    (s : QueueState) (p : Settling) (rest : List Settling)
    (h : KeysOnce { s with settling := p :: rest } limbo) :
    KeysOnce (finishOne env { s with settling := rest } p) limbo := by
  unfold finishOne
  dsimp only
  have popped : ∀ s1 : QueueState, s1.queued = s.queued → s1.running = s.running → s1.settling = rest →
      (s1.inflight = if p.result.stop == Stop.duplicateKey then s.inflight
        else s.inflight.filter (· != p.result.task.key)) → KeysOnce s1 limbo :=
    fun s1 hq hr hs hi => keysOnce_pop p rest h hq hr hs hi
  split
  · apply keysOnce_extendCore env keeps
    apply popped <;> simp only [QueueState.report] <;> repeat' split
    all_goals first | rfl | simp_all
  · apply keysOnce_skipStartable env keeps
    apply keysOnce_extendCore env keeps
    apply popped <;> simp only [QueueState.report] <;> repeat' split
    all_goals first | rfl | simp_all

/-- Finishing the results that wait keeps the keys once. -/
theorem keysOnce_drain (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) :
    ∀ (fuel : Nat) (s : QueueState), KeysOnce s limbo → KeysOnce (drain env fuel s) limbo := by
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
      exact keysOnce_finishOne env keeps limbo s p rest (h.congr rfl rfl heq.symm rfl)

theorem keysOnce_settle (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (result : TaskResult) (attempt : Nat) (h : KeysOnce (s.push result attempt) limbo) :
    KeysOnce (settle env s result attempt) limbo :=
  keysOnce_drain env keeps limbo _ _ h

/-- Deferring a task that was taken out of the queue keeps the keys once. -/
theorem keysOnce_defer (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (task : Task) (why : Deferral) (h : KeysOnce s (task :: limbo)) :
    KeysOnce (defer env s task why) limbo := by
  unfold defer
  apply keysOnce_settle env keeps
  apply keysOnce_push
  intro key
  have base := h key
  have own : pushed (TaskResult.deferred task why) key = if task.key == key then 1 else 0 := by
    simp [pushed, TaskResult.deferred, Stop.deferred, Stop.duplicateKey]
  simp only [List.countP_cons] at base
  rw [own]
  show keyCount key s + _ + _ ≤ flightBound s key
  omega

theorem keysOnce_deferEach (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) :
    ∀ (tasks : List (Task × Deferral)) (s : QueueState),
      KeysOnce s (tasks.map (·.1) ++ limbo) → KeysOnce (deferEach env s tasks) limbo := by
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
    apply keysOnce_defer env keeps
    simpa using h

/-! ## Taking several tasks out of the queue -/

/-- What `p` counts in a list is what it counts among those `q` keeps and those it drops. -/
theorem countP_split {α : Type} (p q : α → Bool) (l : List α) :
    (l.filter fun a => !q a).countP p + l.countP (fun a => p a && q a) = l.countP p := by
  induction l with
  | nil => simp
  | cons a l ih =>
    by_cases hq : q a = true <;> by_cases hp : p a = true <;> simp [hq, hp] <;> omega

/-- The tasks a selection makes of a list's entries are no more, for each key, than the
entries of that key it selects. -/
theorem countP_filterMap_le (f : QueueEntry → Option (Task × Deferral)) (sel : QueueEntry → Bool)
    (key : Key) (l : List QueueEntry)
    (hf : ∀ e ∈ l, ∀ tw, f e = some tw → tw.1 = e.task ∧ sel e = true) :
    (l.filterMap f).countP (·.1.key == key) ≤ l.countP fun e => e.task.key == key && sel e := by
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

/-- The queue after each of `tasks` was taken out of it: the entries with none of their ids. -/
theorem foldl_dequeue (tasks : List (Task × Deferral)) :
    ∀ s : QueueState,
      tasks.foldl (fun s tw => s.dequeue tw.1.id) s
        = { s with queued := s.queued.filter fun e => !(tasks.any fun tw => tw.1.id == e.task.id) } := by
  induction tasks with
  | nil =>
    intro s
    cases s
    simp only [List.foldl_nil, List.any_nil, Bool.not_false]
    congr 1
    exact (List.filter_eq_self.mpr fun _ _ => rfl).symm
  | cons tw rest ih =>
    intro s
    rw [List.foldl_cons, ih]
    simp only [QueueState.dequeue, List.filter_filter, List.any_cons]
    congr 1
    apply List.filter_congr
    intro e _
    by_cases h : tw.1.id = e.task.id
    · simp [h]
    · have differ : (tw.1.id == e.task.id) = false := by simpa using h
      have differ' : (e.task.id != tw.1.id) = true := by simpa using fun eq : e.task.id = tw.1.id => h eq.symm
      simp [differ, differ']

/-- Taking the tasks a selection makes of the queue's entries out of the queue and
deferring each keeps the keys once. -/
theorem keysOnce_deferAll (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (f : QueueEntry → Option (Task × Deferral)) (hf : ∀ e tw, f e = some tw → tw.1 = e.task)
    (h : KeysOnce s limbo) : KeysOnce (deferAll env s (s.queued.filterMap f)) limbo := by
  unfold deferAll
  apply keysOnce_deferEach env keeps
  rw [foldl_dequeue]
  intro key
  have base := h key
  have taken := countP_filterMap_le f
    (fun e => (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id) key s.queued (by
      intro e mem tw eq
      refine ⟨hf e tw eq, ?_⟩
      simp only [List.any_eq_true]
      exact ⟨tw, List.mem_filterMap.mpr ⟨e, mem, eq⟩, by simp [hf e tw eq]⟩)
  have parts := countP_split (fun e : QueueEntry => e.task.key == key)
    (fun e => (s.queued.filterMap f).any fun tw => tw.1.id == e.task.id) s.queued
  simp only [keyCount, flightBound, List.countP_append, List.countP_map] at base ⊢
  have same : (List.countP ((fun x => x.key == key) ∘ fun x => x.1) (s.queued.filterMap f))
      = (s.queued.filterMap f).countP (·.1.key == key) := rfl
  rw [same]
  omega

/-! ## What the queue is told, a pass, and a task's end -/

/-- Marking running entries, their tasks unchanged, changes no count. -/
theorem keyCount_map_running (key : Key) (s : QueueState) (f : QueueEntry → QueueEntry)
    (same : ∀ e, (f e).task = e.task) :
    keyCount key { s with running := s.running.map f } = keyCount key s := by
  simp only [keyCount, List.countP_map]
  congr 2
  apply List.countP_congr
  intro e _
  simp [Function.comp, same]

/-- A queued task taken out of the queue, to be deferred. -/
theorem keysOnce_dequeue_limbo {s : QueueState} {limbo : List Task} (h : KeysOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.queued) : KeysOnce (s.dequeue e.task.id) (e.task :: limbo) := by
  intro key
  have le := keyCount_dequeue_le key s e.task.id
  have lt := keyCount_dequeue_lt s e mem
  have base := h key
  have bound : flightBound (s.dequeue e.task.id) key = flightBound s key := rfl
  simp only [List.countP_cons]
  rw [bound]
  by_cases hk : e.task.key = key
  · subst hk
    simp
    omega
  · have ne : (e.task.key == key) = false := by simpa using hk
    simp [ne]
    omega

/-- A running task taken out of those that run, to be finished or queued again. -/
theorem keysOnce_unrun {s : QueueState} {limbo : List Task} (h : KeysOnce s limbo)
    (e : QueueEntry) (mem : e ∈ s.running) :
    KeysOnce { s with running := s.running.filter (·.task.id != e.task.id) } (e.task :: limbo) := by
  intro key
  have base := h key
  have le := countP_filter_le (fun q : QueueEntry => q.task.key == key) (·.task.id != e.task.id) s.running
  have lt := countP_filter_lt (fun q : QueueEntry => q.task.key == e.task.key) (·.task.id != e.task.id)
    s.running e mem (by simp) (by simp)
  simp only [keyCount, flightBound, List.countP_cons] at base ⊢
  by_cases hk : e.task.key = key
  · subst hk
    simp
    omega
  · have ne : (e.task.key == key) = false := by simpa using hk
    simp [ne]
    omega

/-- The result of a task that was taken out, among those that wait. -/
theorem keysOnce_limbo_push {s : QueueState} {limbo : List Task} (task : Task) (result : TaskResult)
    (attempt : Nat) (same : result.task.key = task.key) (h : KeysOnce s (task :: limbo)) :
    KeysOnce (s.push result attempt) limbo := by
  apply keysOnce_push
  intro key
  have base := h key
  have one := pushed_le result key
  simp only [List.countP_cons] at base
  by_cases hk : task.key = key
  · subst hk
    simp at base
    omega
  · have none := pushed_other result key (by rw [same]; exact hk)
    have ne : (task.key == key) = false := by simpa using hk
    simp [ne] at base
    omega

/-- A task that was taken out, queued again. -/
theorem keysOnce_limbo_enqueue {s : QueueState} {limbo : List Task} (task : Task) (entry : QueueEntry)
    (same : entry.task = task) (h : KeysOnce s (task :: limbo)) :
    KeysOnce { s with queued := entry :: s.queued } limbo := by
  intro key
  have base := h key
  simp only [keyCount, flightBound, List.countP_cons, same] at base ⊢
  omega

/-- A task that was taken out, running. -/
theorem keysOnce_limbo_run {s : QueueState} {limbo : List Task} (task : Task) (entry : QueueEntry)
    (same : entry.task.key = task.key) (h : KeysOnce s (task :: limbo)) :
    KeysOnce { s with running := s.running ++ [entry] } limbo := by
  intro key
  have base := h key
  simp only [keyCount, flightBound, List.countP_cons, List.countP_append, List.countP_nil, same] at base ⊢
  omega

theorem keysOnce_add (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (task : Task) (h : KeysOnce s limbo) : KeysOnce (add env s task).1 limbo := by
  have added := keysOnce_addCore env keeps limbo s task h
  unfold add
  cases res : addCore env s task with
  | mk s' accepted =>
    rw [res] at added
    exact keysOnce_drain env keeps limbo _ _ added

theorem keysOnce_extend (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) :
    ∀ (tasks : List Task) (s : QueueState), KeysOnce s limbo → KeysOnce (extend env s tasks) limbo := by
  intro tasks
  induction tasks with
  | nil => intro s h; unfold extend; exact h
  | cons task rest ih =>
    intro s h
    unfold extend
    split
    · exact ih s h
    · have added := keysOnce_add env keeps limbo s task h
      split
      · rename_i s' heq
        rw [heq] at added
        exact ih s' added
      · rename_i s' heq
        rw [heq] at added
        have added : KeysOnce s' limbo := added
        apply ih
        apply keysOnce_settle env keeps
        apply keysOnce_push
        intro key
        have := added key
        have zero : pushed (TaskResult.duplicateKey task) key = 0 := by
          simp [pushed, TaskResult.duplicateKey]
        omega

theorem keysOnce_cancel (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (key : Key) (h : KeysOnce s limbo) : KeysOnce (cancel env s key).1 limbo := by
  unfold cancel
  split
  · rename_i e found
    have mem : e ∈ s.queued := List.mem_of_find?_eq_some found
    apply keysOnce_settle env keeps
    exact (keysOnce_dequeue_push h e mem (TaskResult.cancelled e.task) e.attempt rfl).congr rfl rfl rfl rfl
  · split
    · intro k
      have := h k
      rw [keyCount_map_running k s _ (by intro q; split <;> rfl)]
      exact this
    · exact h

theorem keysOnce_markReady (now : Time) (limbo : List Task) (s : QueueState) (h : KeysOnce s limbo) :
    KeysOnce (markReady now s) limbo := by
  intro key
  have := h key
  unfold markReady
  rw [keyCount_map_queued key s _ (by intro q; split <;> rfl)]
  exact this

theorem keysOnce_deferClosed (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsKey) (now : Time)
    (limbo : List Task) (s : QueueState) (h : KeysOnce s limbo) :
    KeysOnce (deferClosed cfg env now s) limbo := by
  unfold deferClosed
  apply keysOnce_deferAll env keeps limbo s _ _ h
  intro e tw eq
  simp at eq
  obtain ⟨why, _, rfl⟩ := eq
  rfl

/-- Going down the order keeps the keys once: a task that starts leaves the queue as it
joins those that run, with the key it had. -/
theorem keysOnce_sweep (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsKey) (now : Time)
    (late : List (String × Deferral)) (limbo : List Task) :
    ∀ (order : List QueueEntry) (w : Sweep) (s : QueueState),
      KeysOnce s limbo → KeysOnce (sweep cfg env now late order w s) limbo := by
  intro order
  induction order with
  | nil => intro w s h; unfold sweep; exact h
  | cons e rest ih =>
    intro w s h
    unfold sweep
    split
    · split
      · dsimp only
        apply keysOnce_deferAll env keeps limbo s _ _ h
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
             apply keysOnce_defer env keeps
             exact keysOnce_dequeue_limbo h found mem)
          | (apply ih
             refine (keysOnce_limbo_run found.task _ ?_ (keysOnce_dequeue_limbo h found mem)).congr rfl rfl rfl rfl
             first | exact keeps found.task | rfl)

theorem keysOnce_pass (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsKey) (now : Time)
    (limbo : List Task) (s : QueueState) (h : KeysOnce s limbo) :
    KeysOnce (pass cfg env now s) limbo := by
  unfold pass
  dsimp only
  apply keysOnce_sweep cfg env keeps
  apply keysOnce_markReady
  exact keysOnce_deferClosed cfg env keeps now limbo s h

theorem keysOnce_of_report {s : QueueState} {limbo : List Task} (event : QueueEvent)
    (h : KeysOnce s limbo) : KeysOnce (s.report event) limbo :=
  h.congr rfl rfl rfl rfl

theorem keysOnce_countThrottle (cfg : QueueConfig) (now : Time) (task : Task) (stop : Stop)
    {s : QueueState} {limbo : List Task} (h : KeysOnce s limbo) :
    KeysOnce (countThrottle cfg now task stop s) limbo := by
  unfold countThrottle
  split
  · dsimp only
    split <;> exact h.congr rfl rfl rfl rfl
  · exact h.congr rfl rfl rfl rfl

/-- A task's end keeps the keys once: it leaves those that run, and its result waits to
finish or it is queued again. -/
theorem keysOnce_done (cfg : QueueConfig) (env : QueueEnv) (keeps : env.KeepsKey) (now : Time)
    (limbo : List Task) (s : QueueState) (id : String) (outcome : Outcome) (waitS : Duration)
    (h : KeysOnce s limbo) : KeysOnce (done cfg env now s id outcome waitS) limbo := by
  unfold done
  split
  · exact h
  · rename_i _ e found
    have mem : e ∈ s.running := List.mem_of_find?_eq_some found
    have ide : e.task.id = id := by simpa using List.find?_some found
    have out := keysOnce_unrun h e mem
    rw [ide] at out
    dsimp only
    split
    · apply keysOnce_settle env keeps
      refine keysOnce_limbo_push e.task _ _ ?_ ?_
      · rfl
      · exact keysOnce_of_report _ out
    · split
      · refine keysOnce_limbo_enqueue e.task _ ?_ ?_
        · rfl
        · apply keysOnce_of_report
          apply keysOnce_countThrottle
          exact keysOnce_of_report _ out
      · apply keysOnce_settle env keeps
        refine keysOnce_limbo_push e.task _ _ ?_ ?_
        · rfl
        · apply keysOnce_countThrottle
          exact keysOnce_of_report _ out

theorem map_eq_filterMap_some {α β : Type} (f : α → β) (l : List α) :
    l.map f = l.filterMap fun a => some (f a) := by
  induction l with
  | nil => rfl
  | cons a l ih => simp only [List.map_cons, List.filterMap_cons, ih]

theorem keysOnce_giveUp (env : QueueEnv) (keeps : env.KeepsKey) (limbo : List Task) (s : QueueState)
    (h : KeysOnce s limbo) : KeysOnce (giveUp env s) limbo := by
  unfold giveUp
  dsimp only
  split
  · rw [map_eq_filterMap_some]
    apply keysOnce_deferAll env keeps limbo s _ _ h
    intro e tw eq
    simp at eq
    rw [← eq]
  · apply keysOnce_deferAll env keeps limbo s _ _ h
    intro e tw eq
    repeat' split at eq
    all_goals simp at eq
    all_goals rw [← eq]

/-! ## Every state the queue reaches -/

theorem keysOnce_start : KeysOnce {} [] := by
  intro key
  simp [keyCount, flightBound]

/-- The states a queue reaches: it starts empty, and each step is something it is told
(`add`, `extend`, `cancel`), a pass, a task's end, or giving up what nothing can launch,
at any time and with any answers of its callbacks, as long as the runner gives a task as
it starts with the key it was given. -/
inductive Reachable (cfg : QueueConfig) : QueueState → Prop where
  | start : Reachable cfg {}
  | added (env : QueueEnv) (keeps : env.KeepsKey) (s : QueueState) (task : Task) :
      Reachable cfg s → Reachable cfg (add env s task).1
  | extended (env : QueueEnv) (keeps : env.KeepsKey) (s : QueueState) (tasks : List Task) :
      Reachable cfg s → Reachable cfg (extend env s tasks)
  | cancelled (env : QueueEnv) (keeps : env.KeepsKey) (s : QueueState) (key : Key) :
      Reachable cfg s → Reachable cfg (cancel env s key).1
  | passed (env : QueueEnv) (keeps : env.KeepsKey) (now : Time) (s : QueueState) :
      Reachable cfg s → Reachable cfg (pass cfg env now s)
  | ended (env : QueueEnv) (keeps : env.KeepsKey) (now : Time) (s : QueueState) (id : String)
      (outcome : Outcome) (waitS : Duration) :
      Reachable cfg s → Reachable cfg (done cfg env now s id outcome waitS)
  | gaveUp (env : QueueEnv) (keeps : env.KeepsKey) (s : QueueState) :
      Reachable cfg s → Reachable cfg (giveUp env s)

/-- In every state the queue reaches, each key is held at most once, and a held key is in
flight. -/
theorem Reachable.keysOnce {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) :
    KeysOnce s [] := by
  induction reached with
  | start => exact keysOnce_start
  | added env keeps s task _ ih => exact keysOnce_add env keeps [] s task ih
  | extended env keeps s tasks _ ih => exact keysOnce_extend env keeps [] tasks s ih
  | cancelled env keeps s key _ ih => exact keysOnce_cancel env keeps [] s key ih
  | passed env keeps now s _ ih => exact keysOnce_pass _ env keeps now [] s ih
  | ended env keeps now s id outcome waitS _ ih => exact keysOnce_done _ env keeps now [] s id outcome waitS ih
  | gaveUp env keeps s _ ih => exact keysOnce_giveUp env keeps [] s ih

theorem nodup_of_countP_le_one (l : List Key) (h : ∀ key, l.countP (· == key) ≤ 1) : l.Nodup := by
  induction l with
  | nil => exact List.nodup_nil
  | cons a l ih =>
    rw [List.nodup_cons]
    constructor
    · intro mem
      have one := h a
      have pos : 0 < l.countP (· == a) := List.countP_pos_iff.mpr ⟨a, mem, by simp⟩
      simp only [List.countP_cons, beq_self_eq_true, ite_true] at one
      omega
    · apply ih
      intro key
      have := h key
      simp only [List.countP_cons] at this
      omega

/-- No two tasks of one key are queued or running at once, in any state the queue
reaches. -/
theorem Reachable.keys_distinct {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) :
    ((s.queued ++ s.running).map (·.task.key)).Nodup := by
  apply nodup_of_countP_le_one
  intro key
  have once := reached.keysOnce key
  have atMost : flightBound s key ≤ 1 := by
    unfold flightBound
    split <;> omega
  simp only [keyCount, List.countP_nil] at once
  simp only [List.map_append, List.countP_append, List.countP_map]
  have q : List.countP ((fun x => x == key) ∘ fun e : QueueEntry => e.task.key) s.queued
      = s.queued.countP (·.task.key == key) := rfl
  have r : List.countP ((fun x => x == key) ∘ fun e : QueueEntry => e.task.key) s.running
      = s.running.countP (·.task.key == key) := rfl
  rw [q, r]
  omega

/-- No two tasks of one key run at once, in any state the queue reaches. -/
theorem Reachable.running_keys_distinct {cfg : QueueConfig} {s : QueueState} (reached : Reachable cfg s) :
    (s.running.map (·.task.key)).Nodup := by
  have all := reached.keys_distinct
  rw [List.map_append] at all
  exact (List.nodup_append.mp all).2.1

/-- info: 'Contraagent.Reachable.keys_distinct' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Reachable.keys_distinct

end Contraagent
