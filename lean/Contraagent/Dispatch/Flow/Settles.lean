import Contraagent.Dispatch.Flow.Calls

/-!
# A run does not wait for what nothing will answer

The queue's loop ends when no task is queued or running and no flow call runs. A flow call
that waits for what nothing will answer would keep it going for ever.

`settle_ends`: when the driver closes the flow calls that nothing will answer, they have
their turn, and none of their code creates a flow call or a task, no flow call runs after
the settle, whatever their code does with the cancellation: one that ends is ended, and one
that goes on to wait again is ended by the driver (`endStuck`).

`Runs` puts the driver beside a queue that holds the tasks it was given until it finishes
each. `Runs.none_open`: once the queue holds no task and the driver keeps no result, no key
is open, so the driver closes every flow call that runs. With `settle_ends`
(`Runs.settles`): in a run whose queue holds no task and whose results were all given, one
settle ends every flow call, unless flow code creates a task or a flow call in it. A run
whose flow code creates a bounded number of tasks and of flow calls therefore ends: the
queue's own work is bounded (`Rounds.bounded` of the queue), and each settle after it ends
the flow calls or brings new work.
-/

namespace Contraagent

namespace FlowDriverState

/-! ## What ending a flow call leaves as it was -/

/-- The fields that say whether something may still answer a flow call, and the flow calls
the latest `closeStuck` cancelled. -/
def Waiting (s t : FlowDriverState) : Prop :=
  t.«open» = s.«open» ∧ t.results = s.results ∧ t.replayed = s.replayed ∧ t.stuck = s.stuck

theorem Waiting.refl (s : FlowDriverState) : Waiting s s :=
  ⟨rfl, rfl, rfl, rfl⟩

theorem Waiting.trans {s t u : FlowDriverState} (first : Waiting s t) (second : Waiting t u) : Waiting s u :=
  ⟨second.1.trans first.1, second.2.1.trans first.2.1, second.2.2.1.trans first.2.2.1, second.2.2.2.trans first.2.2.2⟩

theorem cancelUnwaited_waiting (s : FlowDriverState) (key : Key) : Waiting s (s.cancelUnwaited key) := by
  rcases cancelUnwaited_cases s key with eq | ⟨_, _, _, eq⟩ | ⟨_, _, _, eq⟩ <;> rw [eq] <;> exact ⟨rfl, rfl, rfl, rfl⟩

theorem cancelEach_waiting (s : FlowDriverState) (keys : List Key) :
    Waiting s (keys.foldl FlowDriverState.cancelUnwaited s) := by
  induction keys generalizing s with
  | nil => exact Waiting.refl s
  | cons key rest ih => exact (cancelUnwaited_waiting s key).trans (ih _)

theorem endCall_waiting (s : FlowDriverState) (call : FlowCallPath) (state : FlowCallState) :
    Waiting s (s.endCall call state) := by
  unfold FlowDriverState.endCall
  split
  · exact Waiting.refl s
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte]; exact Waiting.refl s
    · simp only [over, Bool.false_eq_true, ↓reduceIte]
      have base : Waiting s { (s.setCall call fun c => { c with state := state }) with running := s.running - 1 } :=
        ⟨rfl, rfl, rfl, rfl⟩
      by_cases closed : (state == FlowCallState.closed) = true
      · simp only [closed, ↓reduceIte]; exact base.trans (cancelEach_waiting _ _)
      · simp only [closed, Bool.false_eq_true, ↓reduceIte]; exact base

theorem ended_waiting (s : FlowDriverState) (call : FlowCallPath) (how : TaskEnd) : Waiting s (s.ended call how).1 := by
  unfold FlowDriverState.ended
  split
  · exact Waiting.refl s
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte]; exact Waiting.refl s
    · simp only [over, Bool.false_eq_true, ↓reduceIte]; exact endCall_waiting _ _ _

/-- A flow call that runs after another ended ran before it. -/
theorem ended_running (s : FlowDriverState) (call : FlowCallPath) (how : TaskEnd) :
    ∀ after ∈ (s.ended call how).1.calls, after.state = .running →
      ∃ before ∈ s.calls, before.path = after.path ∧ before.state = .running := by
  intro after mem runs
  unfold FlowDriverState.ended at mem
  split at mem
  · exact ⟨after, mem, rfl, runs⟩
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte] at mem
      exact ⟨after, mem, rfl, runs⟩
    · simp only [over, Bool.false_eq_true, ↓reduceIte] at mem
      rcases endCall_cases s call (FlowDriverState.endState found.closing how) with ⟨eq, _⟩ | ⟨_, _, _, calls, _, _⟩
      · rw [eq] at mem
        exact ⟨after, mem, rfl, runs⟩
      · rw [calls] at mem
        obtain ⟨before, held, rfl⟩ := List.mem_map.mp mem
        by_cases here : (before.path == call) = true
        · simp only [here, ↓reduceIte] at runs
          exact absurd runs (endState_over _ _)
        · simp only [here, Bool.false_eq_true, ↓reduceIte] at runs ⊢
          exact ⟨before, held, rfl, runs⟩

theorem waited_waiting (s : FlowDriverState) (call : Option FlowCallPath) (stop : Stop) (past : Bool) :
    Waiting s (s.waited call stop past).1 := by
  unfold FlowDriverState.waited
  cases call with
  | none => exact Waiting.refl s
  | some path =>
    by_cases closes : (stop == Stop.deferred && past) = true
    · simp only [closes, ↓reduceIte]; exact ⟨rfl, rfl, rfl, rfl⟩
    · simp only [closes, Bool.false_eq_true, ↓reduceIte]; exact Waiting.refl s

/-! ## A settle -/

/-- What the flow calls that `closeStuck` cancelled do in their turn, when none of their
code creates a flow call or a task: a wait is cancelled, a flow call ends, or a wait that
had its result goes on. -/
inductive Unwinds : FlowDriverState → FlowDriverState → Prop
  | here (s : FlowDriverState) : Unwinds s s
  | cancelled {s t : FlowDriverState} (call : FlowCallPath) : Unwinds s t → Unwinds s (t.cancelled call)
  | ended {s t : FlowDriverState} (call : FlowCallPath) (how : TaskEnd) : Unwinds s t → Unwinds s (t.ended call how).1
  | waited {s t : FlowDriverState} (call : Option FlowCallPath) (stop : Stop) (past : Bool) : Unwinds s t →
      Unwinds s (t.waited call stop past).1

/-- Every flow call that runs is one that `closeStuck` cancelled. -/
def Covered (s : FlowDriverState) : Prop :=
  ∀ call ∈ s.calls, call.state = .running → call.path ∈ s.stuck

theorem Unwinds.keeps {s t : FlowDriverState} (turn : Unwinds s t) (numbered : Numbered s) (covered : Covered s) :
    Numbered t ∧ Covered t ∧ Waiting s t := by
  induction turn with
  | here => exact ⟨numbered, covered, Waiting.refl s⟩
  | cancelled call _ ih =>
    obtain ⟨still, all, same⟩ := ih
    exact ⟨still.same rfl rfl rfl, all, same.trans ⟨rfl, rfl, rfl, rfl⟩⟩
  | @ended t call how _ ih =>
    obtain ⟨still, all, same⟩ := ih
    have here := ended_waiting t call how
    refine ⟨still.ended call how, ?_, same.trans here⟩
    intro after mem runs
    obtain ⟨before, held, path, ran⟩ := ended_running t call how after mem runs
    rw [here.2.2.2, ← path]
    exact all before held ran
  | @waited t call stop past _ ih =>
    obtain ⟨still, all, same⟩ := ih
    refine ⟨still.waited call stop past, ?_, ?_⟩
    · unfold FlowDriverState.waited
      cases call with
      | none => exact all
      | some path =>
        by_cases closes : (stop == Stop.deferred && past) = true
        · simp only [closes, ↓reduceIte]
          intro after mem runs
          obtain ⟨before, held, rfl⟩ := List.mem_map.mp mem
          by_cases its : (before.path == path) = true
          · simp only [its, ↓reduceIte] at runs ⊢
            exact all before held runs
          · simp only [its, Bool.false_eq_true, ↓reduceIte] at runs ⊢
            exact all before held runs
        · simp only [closes, Bool.false_eq_true, ↓reduceIte]
          exact all
    · exact same.trans (waited_waiting t call stop past)

/-- What `closeStuck` leaves when it closes: nothing may answer a flow call, and every flow
call that runs is one it cancelled. -/
theorem closeStuck_covered {s : FlowDriverState} (numbered : Numbered s) (ready : Bool)
    (closes : (s.closeStuck ready).2 = true) :
    Numbered (s.closeStuck ready).1 ∧ Covered (s.closeStuck ready).1
      ∧ (s.closeStuck ready).1.answerable false = false := by
  refine ⟨numbered.closeStuck ready, ?_, ?_⟩
  all_goals unfold FlowDriverState.closeStuck at closes ⊢
  all_goals by_cases quiet : (s.running == 0 || s.answerable ready) = true
  all_goals simp only [quiet, ↓reduceIte, Bool.false_eq_true] at closes ⊢
  · intro after mem runs
    obtain ⟨before, held, rfl⟩ := List.mem_map.mp mem
    have ran : before.state = .running := by
      by_cases its : (before.state == FlowCallState.running) = true
      · simpa using its
      · simpa [its] using runs
    have path : (if (before.state == FlowCallState.running) = true then { before with closing := true } else before).path
        = before.path := by
      by_cases its : (before.state == FlowCallState.running) = true <;> simp [its]
    rw [path]
    exact List.mem_map.mpr ⟨before, List.mem_filter.mpr ⟨held, by simp [ran]⟩, rfl⟩
  · simp only [Bool.or_eq_true, not_or, Bool.not_eq_true] at quiet
    have none := quiet.2
    unfold FlowDriverState.answerable at none ⊢
    simp only [Bool.or_eq_false_iff] at none
    simp [none.1.1.2, none.1.2, none.2]

/-- When the driver closes the flow calls that nothing will answer, they have their turn,
and none of their code creates a flow call or a task, no flow call runs after the settle. -/
theorem settle_ends {replay : List (Key × Nat)} {s t : FlowDriverState} (reached : Reachable replay s) (ready : Bool)
    (closes : (s.closeStuck ready).2 = true) (turn : Unwinds (s.closeStuck ready).1 t) :
    (t.endStuck false).alive = false := by
  obtain ⟨numbered, covered, quiet⟩ := closeStuck_covered reached.numbered ready closes
  obtain ⟨still, all, same⟩ := turn.keeps numbered covered
  have unanswerable : t.answerable false = false := by
    unfold FlowDriverState.answerable at quiet ⊢
    rw [same.1, same.2.1, same.2.2.1]
    exact quiet
  have cleared : Numbered { t with stuck := [] } := still.same rfl rfl rfl
  have closed := cleared.closeEach t.stuck
  have none_runs := closed.2 all
  unfold FlowDriverState.endStuck
  simp only [unanswerable, Bool.false_eq_true, ↓reduceIte]
  unfold FlowDriverState.alive
  rw [closed.1.count, decide_eq_false_iff_not, Nat.not_lt, Nat.le_zero, List.countP_eq_zero]
  exact fun call mem runs => none_runs call mem (by simpa using runs)

/-! ## The driver beside a queue -/

/-- A run: the driver's record, and the keys of the tasks the queue holds and has not
finished. -/
structure Running where
  driver : FlowDriverState
  flying : List Key

/-- Whether `enqueue` gives the queue a task of `key`: the key was not queued, and no result
of it was given. -/
def sends (s : FlowDriverState) (key : Key) : Bool :=
  !(s.queuedKeys.contains key || s.isDone key)

/-- What the queue does with a task the driver gives it (`WorkQueue.extend`): it holds the
task, or, holding a task of the same key, refuses it at once, and the driver gets the
result of a duplicate key. -/
def taken (replay : List (Key × Nat)) (driver : FlowDriverState) (flying : List Key) (key : Key) : Running :=
  if flying.contains key then ⟨followUp replay driver ⟨key, Stop.duplicateKey⟩, flying⟩ else ⟨driver, key :: flying⟩

/-- The runs of a driver over a queue. The queue holds the tasks it was given, its own
(`own`) and the driver's, until it finishes each, and gives the driver each result
(`finish`); what flow code and the driver do is any of the driver's steps, in any order. -/
inductive Runs (replay : List (Key × Nat)) : Running → Prop
  | start (own : List Key) : Runs replay ⟨({} : FlowDriverState).attach, own⟩
  | createTop {r : Running} : Runs replay r → Runs replay ⟨(r.driver.create none).1, r.flying⟩
  | create {r : Running} (up : FlowCallPath) : Runs replay r → (r.driver.callOf up).isSome = true →
      Runs replay ⟨(r.driver.create (some up)).1, r.flying⟩
  | add {r : Running} (call : Option FlowCallPath) (key : Key) (cancellable : Bool) : Runs replay r →
      Runs replay (if r.driver.sends key then taken replay (r.driver.add call key cancellable) r.flying key
        else ⟨r.driver.add call key cancellable, r.flying⟩)
  | wait {r : Running} (call : Option FlowCallPath) (key : Key) : Runs replay r →
      Runs replay (if r.driver.sends key then taken replay (r.driver.wait call key).1 r.flying key
        else ⟨(r.driver.wait call key).1, r.flying⟩)
  | waited {r : Running} (call : Option FlowCallPath) (stop : Stop) (past : Bool) : Runs replay r →
      Runs replay ⟨(r.driver.waited call stop past).1, r.flying⟩
  | finish {r : Running} (key : Key) (stop : Stop) : Runs replay r → key ∈ r.flying → stop ≠ Stop.duplicateKey →
      Runs replay ⟨followUp replay r.driver ⟨key, stop⟩, r.flying.erase key⟩
  | give {r : Running} : Runs replay r → Runs replay ⟨r.driver.give.1, r.flying⟩
  | cancelled {r : Running} (call : FlowCallPath) : Runs replay r → Runs replay ⟨r.driver.cancelled call, r.flying⟩
  | ended {r : Running} (call : FlowCallPath) (how : TaskEnd) : Runs replay r →
      Runs replay ⟨(r.driver.ended call how).1, r.flying⟩
  | closeStuck {r : Running} (ready : Bool) : Runs replay r → Runs replay ⟨(r.driver.closeStuck ready).1, r.flying⟩
  | endStuck {r : Running} (ready : Bool) : Runs replay r → Runs replay ⟨r.driver.endStuck ready, r.flying⟩

/-- The driver keeps a result of `key` that is its own, not a duplicate's: it came, and the
flow code is still to be given it. -/
def Kept (s : FlowDriverState) (key : Key) : Prop :=
  (∃ result ∈ s.results, result.key = key ∧ result.stop ≠ Stop.duplicateKey)
    ∨ ∃ entry ∈ s.replayed, entry.2.2.key = key ∧ entry.2.2.stop ≠ Stop.duplicateKey

/-- Every open key is of a task the queue holds, or of a result the driver keeps. -/
def Held (r : Running) : Prop :=
  ∀ key ∈ r.driver.«open», key ∈ r.flying ∨ Kept r.driver key

theorem Kept.same {s t : FlowDriverState} {key : Key} (kept : Kept s key) (results : t.results = s.results)
    (replayed : t.replayed = s.replayed) : Kept t key := by
  unfold Kept at *
  rw [results, replayed]
  exact kept

theorem followUp_open (replay : List (Key × Nat)) (s : FlowDriverState) (result : FlowResult) :
    (followUp replay s result).«open» = s.«open» := by
  unfold FlowDriverState.followUp
  split <;> rfl

theorem followUp_kept (replay : List (Key × Nat)) (s : FlowDriverState) (result : FlowResult) :
    (∀ key, Kept s key → Kept (followUp replay s result) key)
      ∧ (result.stop ≠ Stop.duplicateKey → Kept (followUp replay s result) result.key) := by
  unfold FlowDriverState.followUp
  split
  · refine ⟨fun key kept => kept.imp id fun ⟨entry, mem, its⟩ => ⟨entry, List.mem_append_left _ mem, its⟩, fun own => ?_⟩
    exact Or.inr ⟨_, List.mem_append_right _ List.mem_cons_self, rfl, own⟩
  · refine ⟨fun key kept => kept.imp (fun ⟨res, mem, its⟩ => ⟨res, List.mem_append_left _ mem, its⟩) id, fun own => ?_⟩
    exact Or.inl ⟨result, List.mem_append_right _ List.mem_cons_self, rfl, own⟩

/-- The queue taking a task keeps every open key held, and holds the task's key. -/
theorem taken_held (replay : List (Key × Nat)) {driver : FlowDriverState} {flying : List Key} (key : Key)
    (held : ∀ other ∈ driver.«open», other = key ∨ other ∈ flying ∨ Kept driver other) :
    Held (taken replay driver flying key) := by
  unfold taken
  by_cases flies : flying.contains key = true
  · simp only [flies, ↓reduceIte]
    intro other mem
    rw [followUp_open] at mem
    rcases held other mem with same | still | kept
    · exact Or.inl (by rw [same]; exact List.contains_iff_mem.mp flies)
    · exact Or.inl still
    · exact Or.inr ((followUp_kept replay driver _).1 other kept)
  · simp only [flies, Bool.false_eq_true, ↓reduceIte]
    intro other mem
    rcases held other mem with same | still | kept
    · exact Or.inl (by rw [same]; exact List.mem_cons_self)
    · exact Or.inl (List.mem_cons_of_mem _ still)
    · exact Or.inr kept

/-- What giving a task to the queue leaves of the open keys: one more, the task's key, when
the driver gives the queue the task, and the same otherwise. -/
theorem enqueue_open_eq (s : FlowDriverState) (key : Key) :
    (s.enqueue key).results = s.results ∧ (s.enqueue key).replayed = s.replayed
      ∧ (s.enqueue key).«open» = if s.sends key then s.«open» ++ [key] else s.«open» := by
  unfold sends
  rcases enqueue_cases s key with ⟨eq, known⟩ | ⟨fresh, undone, _, eq⟩ | ⟨fresh, undone, _, eq⟩ <;> rw [eq]
  · refine ⟨rfl, rfl, ?_⟩
    rcases known with queued | given
    · simp [queued]
    · simp [given]
  · exact ⟨rfl, rfl, by simp [fresh, undone]⟩
  · exact ⟨rfl, rfl, by simp [fresh, undone]⟩

theorem created_same (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) (cancellable : Bool) :
    (s.created call key cancellable).results = s.results ∧ (s.created call key cancellable).replayed = s.replayed
      ∧ (s.created call key cancellable).«open» = s.«open»
      ∧ (s.created call key cancellable).sends key = s.sends key := by
  unfold FlowDriverState.created
  cases call with
  | none => exact ⟨rfl, rfl, rfl, rfl⟩
  | some path =>
    simp only []
    split <;> exact ⟨rfl, rfl, rfl, rfl⟩

theorem ownWaited_same (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) :
    (s.ownWaited call key).results = s.results ∧ (s.ownWaited call key).replayed = s.replayed
      ∧ (s.ownWaited call key).«open» = s.«open» ∧ (s.ownWaited call key).sends key = s.sends key
      ∧ (s.ownWaited call key).isDone key = s.isDone key := by
  unfold FlowDriverState.ownWaited
  cases call with
  | none => exact ⟨rfl, rfl, rfl, rfl, rfl⟩
  | some path =>
    simp only []
    split <;> exact ⟨rfl, rfl, rfl, rfl, rfl⟩

theorem add_open (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) (cancellable : Bool) :
    (s.add call key cancellable).results = s.results ∧ (s.add call key cancellable).replayed = s.replayed
      ∧ (s.add call key cancellable).«open» = if s.sends key then s.«open» ++ [key] else s.«open» := by
  unfold FlowDriverState.add
  have before := created_same s call key cancellable
  have after := enqueue_open_eq (s.created call key cancellable) key
  rw [before.2.2.2, before.2.2.1] at after
  exact ⟨after.1.trans before.1, after.2.1.trans before.2.1, after.2.2⟩

theorem wait_open (s : FlowDriverState) (call : Option FlowCallPath) (key : Key) :
    (s.wait call key).1.results = s.results ∧ (s.wait call key).1.replayed = s.replayed
      ∧ (s.wait call key).1.«open» = if s.sends key then s.«open» ++ [key] else s.«open» := by
  unfold FlowDriverState.wait
  have before := ownWaited_same s call key
  by_cases given : (s.ownWaited call key).isDone key = true
  · simp only [given, ↓reduceIte]
    have done : s.isDone key = true := before.2.2.2.2 ▸ given
    exact ⟨before.1, before.2.1, by simp [sends, done, before.2.2.1]⟩
  · simp only [given, Bool.false_eq_true, ↓reduceIte]
    have waiting : ((s.ownWaited call key).waiting call key).results = (s.ownWaited call key).results
        ∧ ((s.ownWaited call key).waiting call key).replayed = (s.ownWaited call key).replayed
        ∧ ((s.ownWaited call key).waiting call key).«open» = (s.ownWaited call key).«open»
        ∧ ((s.ownWaited call key).waiting call key).sends key = (s.ownWaited call key).sends key := by
      unfold FlowDriverState.waiting
      cases call <;> exact ⟨rfl, rfl, rfl, rfl⟩
    have after := enqueue_open_eq ((s.ownWaited call key).waiting call key) key
    rw [waiting.2.2.2, waiting.2.2.1, before.2.2.2.1, before.2.2.1] at after
    exact ⟨after.1.trans (waiting.1.trans before.1), after.2.1.trans (waiting.2.1.trans before.2.1), after.2.2⟩

/-- A step that leaves the open keys and the kept results as they were keeps them held. -/
theorem Held.same {r : Running} (held : Held r) {driver : FlowDriverState} (opened : driver.«open» = r.driver.«open»)
    (results : driver.results = r.driver.results) (replayed : driver.replayed = r.driver.replayed) :
    Held ⟨driver, r.flying⟩ := by
  intro key mem
  rw [opened] at mem
  exact (held key mem).imp id fun kept => kept.same results replayed

/-- The flow code is given the next result: an open key that stays open is held as it was. -/
theorem Held.give {r : Running} (held : Held r) : Held ⟨r.driver.give.1, r.flying⟩ := by
  unfold FlowDriverState.give
  cases next : r.driver.next with
  | none => exact held
  | some result =>
    simp only []
    intro key mem
    have taken : r.driver.takeNext.«open» = r.driver.«open» := by
      unfold FlowDriverState.takeNext
      split <;> rfl
    -- The key was open before, and is not the key of the result given unless that is a duplicate's.
    have before : key ∈ r.driver.«open» ∧ (result.stop ≠ Stop.duplicateKey → key ≠ result.key) := by
      unfold FlowDriverState.got at mem
      by_cases duplicate : (result.stop == Stop.duplicateKey) = true
      · simp only [duplicate, ↓reduceIte] at mem
        exact ⟨taken ▸ mem, fun own => absurd (by simpa using duplicate) own⟩
      · simp only [duplicate, Bool.false_eq_true, ↓reduceIte] at mem
        obtain ⟨was, other⟩ := List.mem_filter.mp mem
        exact ⟨taken ▸ was, fun _ => by simpa using other⟩
    rcases held key before.1 with flies | kept
    · exact Or.inl flies
    · refine Or.inr ?_
      have got_results : (r.driver.takeNext.got result).results = r.driver.takeNext.results := by
        unfold FlowDriverState.got
        split <;> rfl
      have got_replayed : (r.driver.takeNext.got result).replayed = r.driver.takeNext.replayed := by
        unfold FlowDriverState.got
        split <;> rfl
      unfold Kept at kept ⊢
      rw [got_results, got_replayed]
      unfold FlowDriverState.next at next
      unfold FlowDriverState.takeNext
      cases replayed : r.driver.replayed with
      | nil =>
        rw [replayed] at next kept
        simp only []
        rcases kept with ⟨res, has, its, own⟩ | ⟨entry, has, _⟩
        · refine Or.inl ⟨res, ?_, its, own⟩
          cases results : r.driver.results with
          | nil => rw [results] at has; cases has
          | cons first rest =>
            rw [results] at has next
            simp only [List.head?_cons, Option.some.injEq] at next
            rcases List.mem_cons.mp has with same | later
            · exact absurd (its ▸ same ▸ next ▸ rfl) (before.2 (next ▸ same ▸ own))
            · simpa using later
        · cases has
      | cons first rest =>
        rw [replayed] at next kept
        simp only [Option.some.injEq] at next
        rcases kept with ⟨res, has, its, own⟩ | ⟨entry, has, its, own⟩
        · exact Or.inl ⟨res, has, its, own⟩
        · refine Or.inr ⟨entry, ?_, its, own⟩
          by_cases chosen : entry = rest.foldl earlier first
          · rw [← chosen] at next
            exact absurd (its ▸ next ▸ rfl) (before.2 (next ▸ own))
          · exact (List.mem_erase_of_ne chosen).mpr has

theorem closeEach_waiting (s : FlowDriverState) (paths : List FlowCallPath) :
    Waiting s (paths.foldl (fun s path => s.endCall path .closed) s) := by
  induction paths generalizing s with
  | nil => exact Waiting.refl s
  | cons path rest ih => exact (endCall_waiting s path .closed).trans (ih _)

/-- In every run, each open key is of a task the queue holds or of a result the driver
keeps. -/
theorem Runs.held {replay : List (Key × Nat)} {r : Running} (runs : Runs replay r) : Held r := by
  induction runs with
  | start own => intro key mem; cases mem
  | @createTop r _ ih => exact ih.same (by rfl) rfl rfl
  | @create r up _ _ ih => exact ih.same (by rfl) rfl rfl
  | @add r call key cancellable _ ih =>
    have opened := add_open r.driver call key cancellable
    by_cases sent : r.driver.sends key = true
    · simp only [sent, ↓reduceIte] at opened ⊢
      refine taken_held replay key fun other mem => ?_
      rw [opened.2.2] at mem
      rcases List.mem_append.mp mem with old | new
      · exact Or.inr ((ih other old).imp id fun kept => kept.same opened.1 opened.2.1)
      · exact Or.inl (by simpa using new)
    · simp only [sent, Bool.false_eq_true, ↓reduceIte] at opened ⊢
      exact ih.same opened.2.2 opened.1 opened.2.1
  | @wait r call key _ ih =>
    have opened := wait_open r.driver call key
    by_cases sent : r.driver.sends key = true
    · simp only [sent, ↓reduceIte] at opened ⊢
      refine taken_held replay key fun other mem => ?_
      rw [opened.2.2] at mem
      rcases List.mem_append.mp mem with old | new
      · exact Or.inr ((ih other old).imp id fun kept => kept.same opened.1 opened.2.1)
      · exact Or.inl (by simpa using new)
    · simp only [sent, Bool.false_eq_true, ↓reduceIte] at opened ⊢
      exact ih.same opened.2.2 opened.1 opened.2.1
  | @waited r call stop past _ ih =>
    have same := waited_waiting r.driver call stop past
    exact ih.same same.1 same.2.1 same.2.2.1
  | @finish r key stop _ flies own ih =>
    intro other mem
    rw [followUp_open] at mem
    have kept := followUp_kept replay r.driver ⟨key, stop⟩
    rcases ih other mem with still | was
    · by_cases same : other = key
      · exact Or.inr (same ▸ kept.2 own)
      · exact Or.inl ((List.mem_erase_of_ne same).mpr still)
    · exact Or.inr (kept.1 other was)
  | give _ ih => exact ih.give
  | @cancelled r call _ ih => exact ih.same (by rfl) rfl rfl
  | @ended r call how _ ih =>
    have same := ended_waiting r.driver call how
    exact ih.same same.1 same.2.1 same.2.2.1
  | @closeStuck r ready _ ih =>
    have same : (r.driver.closeStuck ready).1.«open» = r.driver.«open»
        ∧ (r.driver.closeStuck ready).1.results = r.driver.results
        ∧ (r.driver.closeStuck ready).1.replayed = r.driver.replayed := by
      unfold FlowDriverState.closeStuck
      split <;> exact ⟨rfl, rfl, rfl⟩
    exact ih.same same.1 same.2.1 same.2.2
  | @endStuck r ready _ ih =>
    have same : Waiting { r.driver with stuck := [] } (r.driver.endStuck ready) := by
      unfold FlowDriverState.endStuck
      split
      · exact Waiting.refl _
      · exact closeEach_waiting _ _
    exact ih.same same.1 same.2.1 same.2.2.1

/-- Once the queue holds no task and the driver keeps no result, no key is open: every task
the driver queued has given its result. -/
theorem Runs.none_open {replay : List (Key × Nat)} {r : Running} (runs : Runs replay r) (idle : r.flying = [])
    (results : r.driver.results = []) (replayed : r.driver.replayed = []) : r.driver.«open» = [] := by
  cases opened : r.driver.«open» with
  | nil => rfl
  | cons key rest =>
    rcases runs.held key (by rw [opened]; exact List.mem_cons_self) with flies | kept
    · rw [idle] at flies; cases flies
    · unfold Kept at kept
      rw [results, replayed] at kept
      rcases kept with ⟨_, has, _⟩ | ⟨_, has, _⟩ <;> cases has

/-- The driver of a run is a driver's record. -/
theorem Runs.reachable {replay : List (Key × Nat)} {r : Running} (runs : Runs replay r) : Reachable replay r.driver := by
  induction runs with
  | start own => exact Reachable.attach Reachable.start
  | createTop _ ih => exact ih.createTop
  | create up _ held ih => exact ih.create up held
  | @add r call key cancellable _ ih =>
    have step := ih.add call key cancellable
    by_cases sent : r.driver.sends key = true
    · simp only [sent, ↓reduceIte]
      unfold taken
      split
      · exact Reachable.followUp ⟨key, Stop.duplicateKey⟩ step
      · exact step
    · simp only [sent, Bool.false_eq_true, ↓reduceIte]; exact step
  | @wait r call key _ ih =>
    have step := ih.wait call key
    by_cases sent : r.driver.sends key = true
    · simp only [sent, ↓reduceIte]
      unfold taken
      split
      · exact Reachable.followUp ⟨key, Stop.duplicateKey⟩ step
      · exact step
    · simp only [sent, Bool.false_eq_true, ↓reduceIte]; exact step
  | waited call stop past _ ih => exact ih.waited call stop past
  | finish key stop _ _ _ ih => exact ih.followUp _
  | give _ ih => exact ih.give
  | cancelled call _ ih => exact ih.cancelled call
  | ended call how _ ih => exact ih.ended call how
  | closeStuck ready _ ih => exact ih.closeStuck ready
  | endStuck ready _ ih => exact ih.endStuck ready

/-- In a run whose queue holds no task and whose results were all given, while a flow call
runs and no callback is ready: the driver closes the flow calls, and after their turn, when
none of their code creates a flow call or a task, no flow call runs. The queue's loop then
ends. -/
theorem Runs.settles {replay : List (Key × Nat)} {r : Running} (runs : Runs replay r) (idle : r.flying = [])
    (results : r.driver.results = []) (replayed : r.driver.replayed = []) (alive : r.driver.alive = true) :
    (r.driver.closeStuck false).2 = true
      ∧ ∀ t, Unwinds (r.driver.closeStuck false).1 t → (t.endStuck false).alive = false := by
  have closes : (r.driver.closeStuck false).2 = true := by
    have opened := runs.none_open idle results replayed
    have running : (r.driver.running == 0) = false := by
      unfold FlowDriverState.alive at alive
      have positive : r.driver.running > 0 := by simpa using alive
      simp
      omega
    simp [FlowDriverState.closeStuck, FlowDriverState.answerable, results, replayed, opened, running]
  exact ⟨closes, fun t turn => settle_ends runs.reachable false closes turn⟩

end FlowDriverState

/-- info: 'Contraagent.FlowDriverState.settle_ends' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.settle_ends

/-- info: 'Contraagent.FlowDriverState.Runs.settles' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Runs.settles

end Contraagent
