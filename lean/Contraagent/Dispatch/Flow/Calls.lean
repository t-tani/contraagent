import Contraagent.Dispatch.Flow.Keys

/-!
# Each flow call has its own id, and the driver counts those that run

No two flow calls have one path, so none have one id: a top flow call takes the next
number of the driver, and a Task that flow code creates takes the next number of its
parent (`Reachable.calls_distinct`). `running` is the number of flow calls that run
(`Reachable.running_counts`), so the driver says that a flow call still runs exactly when
one does (`Reachable.alive_iff`); a flow call that ended does not count twice, for it ends
once. When the run is over and the driver has closed the rest, no flow call runs
(`Reachable.none_runs_after_close`).
-/

namespace Contraagent

namespace FlowDriverState

/-- The flow calls are numbered: no two have one path; a top flow call has a number below
the next; the parent of any other is held, and has counted it; and `running` counts those
that run. -/
structure Numbered (s : FlowDriverState) : Prop where
  distinct : s.calls.Pairwise fun a b => a.path ≠ b.path
  nonempty : ∀ call ∈ s.calls, call.path ≠ []
  top : ∀ call ∈ s.calls, ∀ n, call.path = [n] → n < s.tops
  under : ∀ call ∈ s.calls, ∀ up n, up ≠ [] → call.path = up ++ [n] →
    (∃ parent ∈ s.calls, parent.path = up) ∧ ∀ parent ∈ s.calls, parent.path = up → n ≤ parent.children
  count : s.running = s.calls.countP (·.state == .running)

/-- A record whose flow calls changed in what is neither their path nor their children. -/
theorem Numbered.renumbered {s s' : FlowDriverState} (h : Numbered s) (change : FlowCall → FlowCall)
    (keeps : ∀ call, (change call).path = call.path ∧ (change call).children = call.children)
    (calls : s'.calls = s.calls.map change) (tops : s'.tops = s.tops)
    (count : s'.running = s'.calls.countP (·.state == .running)) : Numbered s' := by
  refine ⟨?_, ?_, ?_, ?_, count⟩
  · rw [calls, List.pairwise_map]
    exact h.distinct.imp fun differ => by rw [(keeps _).1, (keeps _).1]; exact differ
  · intro call mem
    rw [calls] at mem
    obtain ⟨old, oldMem, rfl⟩ := List.mem_map.mp mem
    rw [(keeps old).1]; exact h.nonempty old oldMem
  · intro call mem n eq
    rw [calls] at mem
    obtain ⟨old, oldMem, rfl⟩ := List.mem_map.mp mem
    rw [(keeps old).1] at eq
    rw [tops]; exact h.top old oldMem n eq
  · intro call mem up n deep eq
    rw [calls] at mem ⊢
    obtain ⟨old, oldMem, rfl⟩ := List.mem_map.mp mem
    rw [(keeps old).1] at eq
    obtain ⟨⟨parent, held, place⟩, all⟩ := h.under old oldMem up n deep eq
    refine ⟨⟨change parent, List.mem_map_of_mem held, by rw [(keeps parent).1]; exact place⟩, ?_⟩
    intro other otherMem otherAt
    obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp otherMem
    rw [(keeps was).1] at otherAt
    rw [(keeps was).2]
    exact all was wasMem otherAt

/-- A record whose flow calls changed in what is not their path, their children or their
state. -/
theorem Numbered.changed {s s' : FlowDriverState} (h : Numbered s) (change : FlowCall → FlowCall)
    (keeps : ∀ call, (change call).path = call.path ∧ (change call).children = call.children
      ∧ (change call).state = call.state)
    (calls : s'.calls = s.calls.map change) (tops : s'.tops = s.tops) (running : s'.running = s.running) :
    Numbered s' :=
  h.renumbered change (fun call => ⟨(keeps call).1, (keeps call).2.1⟩) calls tops (by
    rw [running, calls, List.countP_map, h.count]
    exact List.countP_congr fun call _ => by simp [(keeps call).2.2])

theorem Numbered.same {s s' : FlowDriverState} (h : Numbered s) (calls : s'.calls = s.calls)
    (tops : s'.tops = s.tops) (running : s'.running = s.running) : Numbered s' :=
  h.changed id (fun _ => ⟨rfl, rfl, rfl⟩) (by rw [calls, List.map_id]) tops running

theorem Numbered.setCall {s : FlowDriverState} (h : Numbered s) (path : FlowCallPath) (change : FlowCall → FlowCall)
    (keeps : ∀ call, (change call).path = call.path ∧ (change call).children = call.children
      ∧ (change call).state = call.state) : Numbered (s.setCall path change) :=
  h.changed (fun call => if call.path == path then change call else call)
    (fun call => by by_cases here : (call.path == path) = true <;> simp [here, keeps call]) rfl rfl rfl

/-- Two flow calls of one path are one flow call. -/
theorem same_call {calls : List FlowCall} (distinct : calls.Pairwise fun a b => a.path ≠ b.path) {a b : FlowCall}
    (first : a ∈ calls) (second : b ∈ calls) (path : a.path = b.path) : a = b := by
  induction calls with
  | nil => cases first
  | cons call rest ih =>
    rw [List.pairwise_cons] at distinct
    rcases List.mem_cons.mp first with rfl | firstLater <;> rcases List.mem_cons.mp second with rfl | secondLater
    · rfl
    · exact absurd path (distinct.1 b secondLater)
    · exact absurd path.symm (distinct.1 a firstLater)
    · exact ih distinct.2 firstLater secondLater

theorem callOf_some {s : FlowDriverState} {path : FlowCallPath} {found : FlowCall} (eq : s.callOf path = some found) :
    found ∈ s.calls ∧ found.path = path :=
  ⟨List.mem_of_find?_eq_some eq, by simpa using List.find?_some eq⟩

/-! ## A Task is created -/

theorem Numbered.createTop {s : FlowDriverState} (h : Numbered s) : Numbered (s.create none).1 := by
  refine ⟨?_, ?_, ?_, ?_, ?_⟩
  · refine List.pairwise_append.mpr ⟨h.distinct, List.pairwise_singleton _ _, ?_⟩
    intro old mem new last
    simp only [List.mem_singleton] at last
    subst last
    exact fun eq => Nat.lt_irrefl _ (h.top old mem s.tops eq)
  · intro call mem
    rcases List.mem_append.mp mem with old | new
    · exact h.nonempty call old
    · simp only [List.mem_singleton] at new; subst new; simp
  · intro call mem n eq
    rcases List.mem_append.mp mem with old | new
    · exact Nat.lt_succ_of_lt (h.top call old n eq)
    · simp only [List.mem_singleton] at new
      subst new
      have : s.tops = n := by simpa using eq
      show n < s.tops + 1
      omega
  · intro call mem up n deep eq
    rcases List.mem_append.mp mem with old | new
    · obtain ⟨⟨parent, held, place⟩, all⟩ := h.under call old up n deep eq
      refine ⟨⟨parent, List.mem_append_left _ held, place⟩, ?_⟩
      intro other otherMem otherAt
      rcases List.mem_append.mp otherMem with was | made
      · exact all other was otherAt
      · simp only [List.mem_singleton] at made
        subst made
        exact absurd (h.top parent held s.tops (place.trans otherAt.symm)) (Nat.lt_irrefl _)
    · simp only [List.mem_singleton] at new
      subst new
      have length := congrArg List.length eq
      simp only [List.length_cons, List.length_nil, List.length_append] at length
      exact absurd (List.length_eq_zero_iff.mp (by omega)) deep
  · show s.running + 1 = (s.calls ++ [({ path := [s.tops] } : FlowCall)]).countP (·.state == .running)
    rw [List.countP_append, ← h.count]
    rfl

theorem Numbered.createUnder {s : FlowDriverState} (h : Numbered s) (up : FlowCallPath)
    (held : (s.callOf up).isSome = true) : Numbered (s.create (some up)).1 := by
  obtain ⟨found, eq⟩ := Option.isSome_iff_exists.mp held
  obtain ⟨foundMem, foundAt⟩ := callOf_some eq
  have deep : up ≠ [] := foundAt ▸ h.nonempty found foundMem
  have fresh : ∀ call ∈ s.calls, call.path ≠ up ++ [found.children + 1] := fun call mem at_ =>
    absurd ((h.under call mem up _ deep at_).2 found foundMem foundAt) (by omega)
  have keeps : ∀ call : FlowCall, (if call.path == up then { call with children := found.children + 1 } else call).path
      = call.path ∧ (if call.path == up then { call with children := found.children + 1 } else call).state = call.state :=
    fun call => by by_cases here : (call.path == up) = true <;> simp [here]
  have made : (s.create (some up)).1.calls
      = s.calls.map (fun call => if call.path == up then { call with children := found.children + 1 } else call)
        ++ [{ path := up ++ [found.children + 1] }] := by
    simp [FlowDriverState.create, eq, FlowDriverState.setCall]
  have tops : (s.create (some up)).1.tops = s.tops := rfl
  have running : (s.create (some up)).1.running = s.running + 1 := rfl
  refine ⟨?_, ?_, ?_, ?_, ?_⟩
  · rw [made]
    refine List.pairwise_append.mpr ⟨?_, List.pairwise_singleton _ _, ?_⟩
    · rw [List.pairwise_map]
      exact h.distinct.imp fun differ => by rw [(keeps _).1, (keeps _).1]; exact differ
    · intro old mem new last
      simp only [List.mem_singleton] at last
      subst last
      obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp mem
      rw [(keeps was).1]
      exact fresh was wasMem
  · intro call mem
    rw [made] at mem
    rcases List.mem_append.mp mem with old | new
    · obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp old
      rw [(keeps was).1]; exact h.nonempty was wasMem
    · simp only [List.mem_singleton] at new; subst new; simp
  · intro call mem n at_
    rw [made] at mem
    rw [tops]
    rcases List.mem_append.mp mem with old | new
    · obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp old
      rw [(keeps was).1] at at_
      exact h.top was wasMem n at_
    · simp only [List.mem_singleton] at new
      subst new
      have length := congrArg List.length at_
      simp only [List.length_cons, List.length_nil, List.length_append] at length
      exact absurd (List.length_eq_zero_iff.mp (by omega)) deep
  · intro call mem above n aboveDeep at_
    rw [made] at mem ⊢
    rcases List.mem_append.mp mem with old | new
    · obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp old
      rw [(keeps was).1] at at_
      obtain ⟨⟨parent, parentMem, parentAt⟩, all⟩ := h.under was wasMem above n aboveDeep at_
      refine ⟨⟨_, List.mem_append_left _ (List.mem_map_of_mem parentMem), by rw [(keeps parent).1]; exact parentAt⟩, ?_⟩
      intro other otherMem otherAt
      rcases List.mem_append.mp otherMem with before | last
      · obtain ⟨one, oneMem, rfl⟩ := List.mem_map.mp before
        rw [(keeps one).1] at otherAt
        by_cases here : (one.path == up) = true
        · have same : above = up := otherAt.symm.trans (by simpa using here)
          have bound := all found foundMem (foundAt.trans same.symm)
          simp only [here, ↓reduceIte]
          omega
        · simp only [here, Bool.false_eq_true, ↓reduceIte]
          exact all one oneMem otherAt
      · simp only [List.mem_singleton] at last
        subst last
        exact absurd (parentAt.trans otherAt.symm) (fresh parent parentMem)
    · simp only [List.mem_singleton] at new
      subst new
      obtain ⟨sameUp, sameNumber⟩ := List.append_inj' at_ rfl
      have number : found.children + 1 = n := by simpa using sameNumber
      subst sameUp
      refine ⟨⟨_, List.mem_append_left _ (List.mem_map_of_mem foundMem), by rw [(keeps found).1]; exact foundAt⟩, ?_⟩
      intro other otherMem otherAt
      rcases List.mem_append.mp otherMem with before | last
      · obtain ⟨one, oneMem, rfl⟩ := List.mem_map.mp before
        rw [(keeps one).1] at otherAt
        have here : (one.path == up) = true := by simpa using otherAt
        simp only [here, ↓reduceIte]
        omega
      · simp only [List.mem_singleton] at last
        subst last
        have length := congrArg List.length otherAt
        simp only [List.length_append, List.length_cons, List.length_nil] at length
        omega
  · rw [running, made, List.countP_append, List.countP_map, h.count]
    have unchanged : s.calls.countP ((·.state == FlowCallState.running)
        ∘ fun call => if call.path == up then { call with children := found.children + 1 } else call)
        = s.calls.countP (·.state == .running) :=
      List.countP_congr fun call _ => by simp only [Function.comp_apply]; rw [(keeps call).2]
    rw [unchanged]
    rfl

/-! ## Flow code creates tasks and waits -/

theorem Numbered.add {s : FlowDriverState} (h : Numbered s) (call : Option FlowCallPath) (key : Key)
    (cancellable : Bool) : Numbered (s.add call key cancellable) := by
  have same := enqueue_same (s.created call key cancellable) key
  refine Numbered.same ?_ same.2.2.2.1 same.2.2.2.2.2 same.2.2.2.2.1
  unfold FlowDriverState.created
  cases call with
  | none => exact h
  | some path =>
    by_cases fresh : (cancellable && !s.isDone key && !s.creators.any (·.1 == key)) = true
    · simp only [fresh, ↓reduceIte]
      have owned : Numbered (s.own path key) := h.setCall path _ fun _ => ⟨rfl, rfl, rfl⟩
      exact owned.same rfl rfl rfl
    · simp only [fresh, Bool.false_eq_true, ↓reduceIte]; exact h

theorem Numbered.ownWaited {s : FlowDriverState} (h : Numbered s) (call : Option FlowCallPath) (key : Key) :
    Numbered (s.ownWaited call key) := by
  unfold FlowDriverState.ownWaited
  cases call with
  | none => exact h
  | some path =>
    by_cases created : s.creators.any (·.1 == key) = true
    · simp only [created, ↓reduceIte]; exact h.setCall path _ fun _ => ⟨rfl, rfl, rfl⟩
    · simp only [created, Bool.false_eq_true, ↓reduceIte]; exact h

theorem Numbered.wait {s : FlowDriverState} (h : Numbered s) (call : Option FlowCallPath) (key : Key) :
    Numbered (s.wait call key).1 := by
  unfold FlowDriverState.wait
  have base := h.ownWaited call key
  by_cases given : (s.ownWaited call key).isDone key = true
  · simp only [given, ↓reduceIte]; exact base
  · simp only [given, Bool.false_eq_true, ↓reduceIte]
    have same := enqueue_same ((s.ownWaited call key).waiting call key) key
    refine Numbered.same ?_ same.2.2.2.1 same.2.2.2.2.2 same.2.2.2.2.1
    cases call <;> exact base.same rfl rfl rfl

theorem Numbered.waited {s : FlowDriverState} (h : Numbered s) (call : Option FlowCallPath) (stop : Stop)
    (past : Bool) : Numbered (s.waited call stop past).1 := by
  unfold FlowDriverState.waited
  cases call with
  | none => exact h
  | some path =>
    by_cases closes : (stop == Stop.deferred && past) = true
    · simp only [closes, ↓reduceIte]; exact h.setCall path _ fun _ => ⟨rfl, rfl, rfl⟩
    · simp only [closes, Bool.false_eq_true, ↓reduceIte]; exact h

/-! ## Results come and are given -/

theorem Numbered.followUp (replay : List (Key × Nat)) {s : FlowDriverState} (h : Numbered s) (result : FlowResult) :
    Numbered (FlowDriverState.followUp replay s result) := by
  unfold FlowDriverState.followUp
  split <;> exact h.same rfl rfl rfl

theorem Numbered.give {s : FlowDriverState} (h : Numbered s) : Numbered s.give.1 := by
  unfold FlowDriverState.give
  split
  · exact h
  · have taken : Numbered s.takeNext := by
      unfold FlowDriverState.takeNext
      split <;> exact h.same rfl rfl rfl
    unfold FlowDriverState.got
    split <;> exact taken.same rfl rfl rfl

/-! ## A flow call ends -/

theorem cancelEach_same (s : FlowDriverState) (keys : List Key) :
    (keys.foldl FlowDriverState.cancelUnwaited s).calls = s.calls
      ∧ (keys.foldl FlowDriverState.cancelUnwaited s).running = s.running
      ∧ (keys.foldl FlowDriverState.cancelUnwaited s).tops = s.tops := by
  induction keys generalizing s with
  | nil => exact ⟨rfl, rfl, rfl⟩
  | cons key rest ih =>
    rw [List.foldl_cons]
    have step : (s.cancelUnwaited key).calls = s.calls ∧ (s.cancelUnwaited key).running = s.running
        ∧ (s.cancelUnwaited key).tops = s.tops := by
      rcases cancelUnwaited_cases s key with eq | ⟨_, _, _, eq⟩ | ⟨_, _, _, eq⟩ <;> rw [eq] <;> exact ⟨rfl, rfl, rfl⟩
    have rest := ih (s.cancelUnwaited key)
    exact ⟨rest.1.trans step.1, rest.2.1.trans step.2.1, rest.2.2.trans step.2.2⟩

/-- What `endCall` does to the flow calls: nothing, for a flow call the driver does not hold
or that ended; else the flow call, which ran, has its state, and one fewer runs. -/
theorem endCall_cases (s : FlowDriverState) (call : FlowCallPath) (state : FlowCallState) :
    (s.endCall call state = s
        ∧ (s.callOf call = none ∨ ∃ found, s.callOf call = some found ∧ found.state ≠ .running))
      ∨ ∃ found, s.callOf call = some found ∧ found.state = .running
          ∧ (s.endCall call state).calls
            = s.calls.map (fun c => if c.path == call then { c with state := state } else c)
          ∧ (s.endCall call state).running = s.running - 1 ∧ (s.endCall call state).tops = s.tops := by
  unfold FlowDriverState.endCall
  split
  · rename_i none
    exact Or.inl ⟨rfl, Or.inl none⟩
  · rename_i found eq
    by_cases over : (found.state != FlowCallState.running) = true
    · exact Or.inl ⟨by simp only [over, ↓reduceIte], Or.inr ⟨found, eq, by simpa using over⟩⟩
    · refine Or.inr ⟨found, eq, by simpa using over, ?_⟩
      simp only [over, Bool.false_eq_true, ↓reduceIte]
      by_cases closed : (state == FlowCallState.closed) = true
      · simp only [closed, ↓reduceIte]
        have same := cancelEach_same
          { (s.setCall call fun c => { c with state := state }) with running := s.running - 1 }
          (found.cancellable.mergeSort fun a b => decide (a ≤ b))
        exact ⟨same.1, same.2.1, same.2.2⟩
      · rw [ite_eq_right_of_eq_false _ _ (eq_false closed)]
        exact ⟨rfl, rfl, rfl⟩

/-- Ending the one flow call of a path, which runs, leaves one fewer that runs. -/
theorem countP_ended {calls : List FlowCall} (distinct : calls.Pairwise fun a b => a.path ≠ b.path)
    {found : FlowCall} (mem : found ∈ calls) (runs : found.state = .running) {state : FlowCallState}
    (over : state ≠ .running) :
    (calls.map fun c => if c.path == found.path then { c with state := state } else c).countP (·.state == .running) + 1
      = calls.countP (·.state == .running) := by
  induction calls with
  | nil => cases mem
  | cons call rest ih =>
    rw [List.pairwise_cons] at distinct
    rw [List.map_cons, List.countP_cons, List.countP_cons]
    rcases List.mem_cons.mp mem with rfl | later
    · have others : rest.map (fun c => if c.path == found.path then { c with state := state } else c) = rest := by
        have each : ∀ c ∈ rest, (if c.path == found.path then { c with state := state } else c) = c := fun c at_ => by
          have differ : (c.path == found.path) = false := by simpa using fun eq : c.path = found.path => distinct.1 c at_ eq.symm
          simp [differ]
        rw [List.map_congr_left each]; simp
      rw [others]
      have ended : (state == FlowCallState.running) = false := by simpa using over
      simp [runs, ended]
    · have differ : (call.path == found.path) = false := by simpa using distinct.1 found later
      simp only [differ, Bool.false_eq_true, ↓reduceIte]
      have rest := ih distinct.2 later
      omega

theorem Numbered.endCall {s : FlowDriverState} (h : Numbered s) (call : FlowCallPath) {state : FlowCallState}
    (over : state ≠ .running) : Numbered (s.endCall call state) := by
  rcases endCall_cases s call state with ⟨eq, _⟩ | ⟨found, eq, runs, calls, running, tops⟩
  · rw [eq]; exact h
  · obtain ⟨foundMem, foundAt⟩ := callOf_some eq
    refine h.renumbered (fun c => if c.path == call then { c with state := state } else c)
      (fun c => by by_cases here : (c.path == call) = true <;> simp [here]) calls tops ?_
    rw [running, calls, h.count]
    have fewer := countP_ended h.distinct foundMem runs over
    rw [foundAt] at fewer
    omega

theorem endState_over (closing : Bool) (how : TaskEnd) : FlowDriverState.endState closing how ≠ .running := by
  cases how <;> cases closing <;> simp [FlowDriverState.endState]

theorem Numbered.ended {s : FlowDriverState} (h : Numbered s) (call : FlowCallPath) (how : TaskEnd) :
    Numbered (s.ended call how).1 := by
  unfold FlowDriverState.ended
  split
  · exact h
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte]; exact h
    · simp only [over, Bool.false_eq_true, ↓reduceIte]; exact h.endCall call (endState_over _ _)

theorem Numbered.closeStuck {s : FlowDriverState} (h : Numbered s) (ready : Bool) : Numbered (s.closeStuck ready).1 := by
  unfold FlowDriverState.closeStuck
  split
  · exact h
  · exact h.changed (fun call => if call.state == .running then { call with closing := true } else call)
      (fun call => by by_cases runs : (call.state == FlowCallState.running) = true <;> simp [runs]) rfl rfl rfl

theorem Numbered.cancelRest {s : FlowDriverState} (h : Numbered s) : Numbered s.cancelRest :=
  h.changed (fun call => if call.state == .running then { call with closing := true } else call)
    (fun call => by by_cases runs : (call.state == FlowCallState.running) = true <;> simp [runs]) rfl rfl rfl

/-- Closing each flow call of `paths` keeps the numbering, and when every flow call that
runs is one of `paths`, none runs after. -/
theorem Numbered.closeEach {s : FlowDriverState} (h : Numbered s) (paths : List FlowCallPath) :
    Numbered (paths.foldl (fun s path => s.endCall path .closed) s)
      ∧ ((∀ call ∈ s.calls, call.state = .running → call.path ∈ paths) →
        ∀ call ∈ (paths.foldl (fun s path => s.endCall path .closed) s).calls, call.state ≠ .running) := by
  induction paths generalizing s with
  | nil => exact ⟨h, fun covered call mem runs => by cases covered call mem runs⟩
  | cons path rest ih =>
    rw [List.foldl_cons]
    have next := ih (h.endCall path (state := .closed) (by decide))
    refine ⟨next.1, fun covered => next.2 ?_⟩
    intro call mem runs
    rcases endCall_cases s path .closed with ⟨eq, quiet⟩ | ⟨found, eq, _, calls, _, _⟩
    · rw [eq] at mem
      rcases List.mem_cons.mp (covered call mem runs) with here | later
      · rcases quiet with none | ⟨found, eq, over⟩
        · have misses := List.find?_eq_none.mp none call mem
          simp [here] at misses
        · obtain ⟨foundMem, foundAt⟩ := callOf_some eq
          exact absurd (same_call h.distinct mem foundMem (here.trans foundAt.symm) ▸ runs) over
      · exact later
    · rw [calls] at mem
      obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp mem
      by_cases here : (was.path == path) = true
      · simp [here] at runs
      · simp only [here, Bool.false_eq_true, ↓reduceIte] at runs ⊢
        rcases List.mem_cons.mp (covered was wasMem runs) with same | later
        · simp [same] at here
        · exact later

theorem Numbered.closeRest {s : FlowDriverState} (h : Numbered s) :
    Numbered s.closeRest ∧ ∀ call ∈ s.closeRest.calls, call.state ≠ .running := by
  have each := h.closeEach ((s.calls.filter (·.state == .running)).map (·.path))
  refine ⟨each.1, each.2 fun call mem runs => ?_⟩
  exact List.mem_map.mpr ⟨call, List.mem_filter.mpr ⟨mem, by simp [runs]⟩, rfl⟩

/-! ## Every record the driver reaches -/

theorem Reachable.numbered {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) : Numbered s := by
  induction h with
  | start =>
    refine ⟨List.Pairwise.nil, ?_, ?_, ?_, rfl⟩ <;> intro _ mem <;> cases mem
  | createTop _ ih => exact ih.createTop
  | create up _ held ih => exact ih.createUnder up held
  | add call key cancellable _ ih => exact ih.add call key cancellable
  | wait call key _ ih => exact ih.wait call key
  | waited call stop past _ ih => exact ih.waited call stop past
  | followUp result _ ih => exact ih.followUp replay result
  | give _ ih => exact ih.give
  | cancelled call _ ih => exact ih.same rfl rfl rfl
  | ended call how _ ih => exact ih.ended call how
  | attach _ ih => exact ih.same rfl rfl rfl
  | closeStuck ready _ ih => exact ih.closeStuck ready
  | cancelRest _ ih => exact ih.cancelRest
  | closeRest _ ih => exact ih.closeRest.1

/-- No two flow calls have one path, and so none have one id. -/
theorem Reachable.calls_distinct {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) :
    s.calls.Pairwise fun a b => a.path ≠ b.path :=
  h.numbered.distinct

/-- `running` is the number of flow calls that run. -/
theorem Reachable.running_counts {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) :
    s.running = s.calls.countP (·.state == .running) :=
  h.numbered.count

/-- The driver says that a flow call still runs exactly when one does. -/
theorem Reachable.alive_iff {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) :
    s.alive = true ↔ ∃ call ∈ s.calls, call.state = .running := by
  unfold FlowDriverState.alive
  rw [h.running_counts, decide_eq_true_iff]
  show 0 < _ ↔ _
  rw [List.countP_pos_iff]
  exact ⟨fun ⟨call, mem, runs⟩ => ⟨call, mem, by simpa using runs⟩, fun ⟨call, mem, runs⟩ => ⟨call, mem, by simp [runs]⟩⟩

/-- Once the run is over and the driver has closed the flow calls that still ran, none
runs. -/
theorem Reachable.none_runs_after_close {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) :
    s.closeRest.alive = false ∧ ∀ call ∈ s.closeRest.calls, call.state ≠ .running := by
  have closed := h.numbered.closeRest
  refine ⟨?_, closed.2⟩
  unfold FlowDriverState.alive
  rw [closed.1.count, decide_eq_false_iff_not, Nat.not_lt, Nat.le_zero, List.countP_eq_zero]
  exact fun call mem runs => closed.2 call mem (by simpa using runs)

end FlowDriverState

/-- info: 'Contraagent.FlowDriverState.Reachable.calls_distinct' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Reachable.calls_distinct

/-- info: 'Contraagent.FlowDriverState.Reachable.alive_iff' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Reachable.alive_iff

/-- info: 'Contraagent.FlowDriverState.Reachable.none_runs_after_close' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Reachable.none_runs_after_close

end Contraagent
