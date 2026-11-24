import Contraagent.Dispatch.Flow.Reachable

/-!
# Each task goes to the queue once, and a wait for a task is not closed

The driver gives the queue a key once, whatever the flow code does with it: creates its
task twice, waits for it in several flow calls, or names it again after its result was
given (`Reachable.sent_once`). A key it cancels on the queue is one it gave the queue
(`Reachable.cancels_sent`).

`open` holds the keys the driver queued whose result it did not give yet, and each wait
that goes on is for one of them. So when the driver closes the flow calls that nothing
will answer (`closeStuck`), no flow call waits for a task, and every task the driver
queued has given its result (`Reachable.stuck_waits_for_no_task`): what it closes waits
for something else, which no task answers.
-/

namespace Contraagent

namespace FlowDriverState

/-- The driver's keys agree: each key was queued once and is with the queue or waits for
it, in that order; `open` is the keys queued with no result given; and each wait, each
creator and each cancel is of such a key. -/
structure KeysOnce (s : FlowDriverState) : Prop where
  once : s.queuedKeys.Nodup
  sent : s.sent.reverse ++ s.outbox = s.queuedKeys
  attached : s.attached = true → s.outbox = []
  unattached : s.attached = false → s.cancels = []
  opened : s.«open» = s.queuedKeys.filter fun key => !s.isDone key
  waits : ∀ waiter ∈ s.waiters, waiter.1 ∈ s.«open»
  creators : ∀ creator ∈ s.creators, creator.1 ∈ s.«open»
  cancels : ∀ key ∈ s.cancels ++ s.toCancel, key ∈ s.queuedKeys

/-- A record that differs only in what the keys do not read. -/
theorem KeysOnce.congr {s s' : FlowDriverState} (h : KeysOnce s) (queuedKeys : s'.queuedKeys = s.queuedKeys)
    (sent : s'.sent = s.sent) (outbox : s'.outbox = s.outbox) (attached : s'.attached = s.attached)
    (cancels : s'.cancels = s.cancels) (toCancel : s'.toCancel = s.toCancel) (opened : s'.«open» = s.«open»)
    (done : s'.done = s.done) (waiters : ∀ waiter ∈ s'.waiters, waiter ∈ s.waiters)
    (creators : ∀ creator ∈ s'.creators, creator ∈ s.creators) : KeysOnce s' := by
  have isDone : ∀ key, s'.isDone key = s.isDone key := fun key => by simp [FlowDriverState.isDone, done]
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · rw [queuedKeys]; exact h.once
  · rw [sent, outbox, queuedKeys]; exact h.sent
  · rw [attached, outbox]; exact h.attached
  · rw [attached, cancels]; exact h.unattached
  · rw [opened, queuedKeys, h.opened]; exact List.filter_congr fun key _ => by rw [isDone]
  · intro waiter mem; rw [opened]; exact h.waits waiter (waiters waiter mem)
  · intro creator mem; rw [opened]; exact h.creators creator (creators creator mem)
  · rw [cancels, toCancel, queuedKeys]; exact h.cancels

theorem open_queued {s : FlowDriverState} (h : KeysOnce s) {key : Key} (mem : key ∈ s.«open») :
    key ∈ s.queuedKeys ∧ s.isDone key = false := by
  rw [h.opened, List.mem_filter] at mem
  exact ⟨mem.1, by simpa using mem.2⟩

/-! ## Giving a task to the queue -/

/-- What `enqueue` does: nothing for a key that was queued or has its result given; else
the key is queued and open, and goes to the queue, or waits for it. -/
theorem enqueue_cases (s : FlowDriverState) (key : Key) :
    (s.enqueue key = s ∧ (key ∈ s.queuedKeys ∨ s.isDone key = true))
      ∨ (key ∉ s.queuedKeys ∧ s.isDone key = false ∧ s.attached = true
          ∧ s.enqueue key = { s with queuedKeys := s.queuedKeys ++ [key], «open» := s.«open» ++ [key], sent := key :: s.sent })
      ∨ (key ∉ s.queuedKeys ∧ s.isDone key = false ∧ s.attached = false
          ∧ s.enqueue key
            = { s with queuedKeys := s.queuedKeys ++ [key], «open» := s.«open» ++ [key], outbox := s.outbox ++ [key] }) := by
  unfold FlowDriverState.enqueue
  by_cases queued : key ∈ s.queuedKeys
  · exact Or.inl ⟨by simp [queued], Or.inl queued⟩
  · by_cases given : s.isDone key = true
    · exact Or.inl ⟨by simp [given], Or.inr given⟩
    · have undone : s.isDone key = false := by simpa using given
      by_cases attached : s.attached = true
      · exact Or.inr (Or.inl ⟨queued, undone, attached, by simp [queued, undone, attached]⟩)
      · have loose : s.attached = false := by simpa using attached
        exact Or.inr (Or.inr ⟨queued, undone, loose, by simp [queued, undone, loose]⟩)

theorem enqueue_same (s : FlowDriverState) (key : Key) :
    (s.enqueue key).done = s.done ∧ (s.enqueue key).waiters = s.waiters ∧ (s.enqueue key).creators = s.creators
      ∧ (s.enqueue key).calls = s.calls ∧ (s.enqueue key).running = s.running ∧ (s.enqueue key).tops = s.tops := by
  rcases enqueue_cases s key with ⟨eq, _⟩ | ⟨_, _, _, eq⟩ | ⟨_, _, _, eq⟩ <;> rw [eq] <;> simp

/-- A key the driver gives the queue stays open, and a key with no result given is open
once the driver was asked to queue it. -/
theorem enqueue_open {s : FlowDriverState} (h : KeysOnce s) (key : Key) :
    (∀ other ∈ s.«open», other ∈ (s.enqueue key).«open») ∧ (s.isDone key = false → key ∈ (s.enqueue key).«open») := by
  rcases enqueue_cases s key with ⟨eq, known⟩ | ⟨_, _, _, eq⟩ | ⟨_, _, _, eq⟩ <;> rw [eq]
  · refine ⟨fun _ mem => mem, fun fresh => ?_⟩
    rw [h.opened, List.mem_filter]
    rcases known with queued | given
    · exact ⟨queued, by simp [fresh]⟩
    · rw [fresh] at given; cases given
  · exact ⟨fun other mem => List.mem_append_left _ mem, fun _ => by simp⟩
  · exact ⟨fun other mem => List.mem_append_left _ mem, fun _ => by simp⟩

/-- As `KeysOnce`, between the two steps of `add` and of `wait`: a wait or a creator may be
of `key` before it is queued, when no result of it was given. -/
structure KeysBefore (key : Key) (s : FlowDriverState) : Prop where
  once : s.queuedKeys.Nodup
  sent : s.sent.reverse ++ s.outbox = s.queuedKeys
  attached : s.attached = true → s.outbox = []
  unattached : s.attached = false → s.cancels = []
  opened : s.«open» = s.queuedKeys.filter fun key => !s.isDone key
  waits : ∀ waiter ∈ s.waiters, waiter.1 ∈ s.«open» ∨ (waiter.1 = key ∧ s.isDone key = false)
  creators : ∀ creator ∈ s.creators, creator.1 ∈ s.«open» ∨ (creator.1 = key ∧ s.isDone key = false)
  cancels : ∀ key ∈ s.cancels ++ s.toCancel, key ∈ s.queuedKeys

theorem KeysOnce.before {s : FlowDriverState} (h : KeysOnce s) (key : Key) : KeysBefore key s :=
  ⟨h.once, h.sent, h.attached, h.unattached, h.opened, fun waiter mem => Or.inl (h.waits waiter mem),
    fun creator mem => Or.inl (h.creators creator mem), h.cancels⟩

theorem KeysBefore.enqueue {s : FlowDriverState} {key : Key} (h : KeysBefore key s) : KeysOnce (s.enqueue key) := by
  have fresh_once : key ∉ s.queuedKeys → (s.queuedKeys ++ [key]).Nodup := fun fresh =>
    List.nodup_append.mpr ⟨h.once, by simp, fun a mem b other => by
      simp only [List.mem_singleton] at other; subst other; exact fun same => fresh (same ▸ mem)⟩
  have fresh_open : s.isDone key = false →
      s.«open» ++ [key] = (s.queuedKeys ++ [key]).filter fun other => !s.isDone other := fun undone => by
    rw [List.filter_append, ← h.opened]; simp [undone]
  have later : ∀ other : Key, other ∈ s.«open» ∨ (other = key ∧ s.isDone key = false) → other ∈ s.«open» ++ [key] :=
    fun other mem => mem.elim (List.mem_append_left _) fun new => by simp [new.1]
  rcases enqueue_cases s key with ⟨eq, known⟩ | ⟨fresh, undone, attached, eq⟩ | ⟨fresh, undone, attached, eq⟩ <;> rw [eq]
  · have kept : ∀ other : Key, other ∈ s.«open» ∨ (other = key ∧ s.isDone key = false) → other ∈ s.«open» := by
      intro other mem
      rcases mem with mem | ⟨same, undone⟩
      · exact mem
      · rw [same, h.opened, List.mem_filter]
        rcases known with queued | given
        · exact ⟨queued, by simp [undone]⟩
        · rw [undone] at given; cases given
    exact ⟨h.once, h.sent, h.attached, h.unattached, h.opened, fun waiter mem => kept _ (h.waits waiter mem),
      fun creator mem => kept _ (h.creators creator mem), h.cancels⟩
  · refine ⟨fresh_once fresh, ?_, fun _ => h.attached attached, ?_, fresh_open undone, ?_, ?_, ?_⟩
    · have sent := h.sent
      rw [h.attached attached] at sent ⊢
      simp only [List.reverse_cons, List.append_nil] at sent ⊢
      rw [sent]
    · intro loose; rw [attached] at loose; cases loose
    · exact fun waiter mem => later _ (h.waits waiter mem)
    · exact fun creator mem => later _ (h.creators creator mem)
    · exact fun other mem => List.mem_append_left _ (h.cancels other mem)
  · refine ⟨fresh_once fresh, ?_, ?_, fun _ => h.unattached attached, fresh_open undone, ?_, ?_, ?_⟩
    · show s.sent.reverse ++ (s.outbox ++ [key]) = s.queuedKeys ++ [key]
      rw [← List.append_assoc, h.sent]
    · intro tied; rw [attached] at tied; cases tied
    · exact fun waiter mem => later _ (h.waits waiter mem)
    · exact fun creator mem => later _ (h.creators creator mem)
    · exact fun other mem => List.mem_append_left _ (h.cancels other mem)

/-! ## The calls keep the keys -/

theorem KeysOnce.setCall {s : FlowDriverState} (h : KeysOnce s) (path : FlowCallPath) (change : FlowCall → FlowCall) :
    KeysOnce (s.setCall path change) :=
  h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)

theorem KeysOnce.create {s : FlowDriverState} (h : KeysOnce s) (parent : Option FlowCallPath) :
    KeysOnce (s.create parent).1 := by
  cases parent <;> exact h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)

theorem KeysOnce.add {s : FlowDriverState} (h : KeysOnce s) (call : Option FlowCallPath) (key : Key)
    (cancellable : Bool) : KeysOnce (s.add call key cancellable) := by
  unfold FlowDriverState.add
  refine KeysBefore.enqueue ?_
  unfold FlowDriverState.created
  cases call with
  | none => exact h.before key
  | some path =>
    by_cases fresh : (cancellable && !s.isDone key && !s.creators.any (·.1 == key)) = true
    · simp only [fresh, ↓reduceIte]
      have undone : s.isDone key = false := by
        simp only [Bool.and_eq_true, Bool.not_eq_true'] at fresh
        exact fresh.1.2
      refine ⟨h.once, h.sent, h.attached, h.unattached, h.opened, fun waiter mem => Or.inl (h.waits waiter mem), ?_, h.cancels⟩
      intro creator mem
      rcases List.mem_append.mp mem with old | new
      · exact Or.inl (h.creators creator old)
      · simp only [List.mem_singleton] at new
        exact Or.inr ⟨by rw [new], undone⟩
    · simp only [fresh, Bool.false_eq_true, ↓reduceIte]
      exact h.before key

theorem KeysOnce.ownWaited {s : FlowDriverState} (h : KeysOnce s) (call : Option FlowCallPath) (key : Key) :
    KeysOnce (s.ownWaited call key) := by
  unfold FlowDriverState.ownWaited
  cases call with
  | none => exact h
  | some path =>
    by_cases created : s.creators.any (·.1 == key) = true
    · simp only [created, ↓reduceIte]; exact h.setCall _ _
    · simp only [created, Bool.false_eq_true, ↓reduceIte]; exact h

theorem KeysOnce.wait {s : FlowDriverState} (h : KeysOnce s) (call : Option FlowCallPath) (key : Key) :
    KeysOnce (s.wait call key).1 := by
  unfold FlowDriverState.wait
  have base := h.ownWaited call key
  by_cases given : (s.ownWaited call key).isDone key = true
  · simp only [given, ↓reduceIte]; exact base
  · simp only [given, Bool.false_eq_true, ↓reduceIte]
    have undone : (s.ownWaited call key).isDone key = false := by simpa using given
    refine KeysBefore.enqueue ?_
    unfold FlowDriverState.waiting
    cases call with
    | none => exact base.before key
    | some path =>
      refine ⟨base.once, base.sent, base.attached, base.unattached, base.opened, ?_,
        fun creator mem => Or.inl (base.creators creator mem), base.cancels⟩
      intro waiter mem
      rcases List.mem_append.mp mem with old | new
      · exact Or.inl (base.waits waiter old)
      · simp only [List.mem_singleton] at new
        exact Or.inr ⟨by rw [new], undone⟩

theorem KeysOnce.waited {s : FlowDriverState} (h : KeysOnce s) (call : Option FlowCallPath) (stop : Stop)
    (past : Bool) : KeysOnce (s.waited call stop past).1 := by
  unfold FlowDriverState.waited
  cases call with
  | none => exact h
  | some path =>
    by_cases closes : (stop == Stop.deferred && past) = true
    · simp only [closes, ↓reduceIte]; exact h.setCall _ _
    · simp only [closes, Bool.false_eq_true, ↓reduceIte]; exact h

theorem KeysOnce.followUp (replay : List (Key × Nat)) {s : FlowDriverState} (h : KeysOnce s) (result : FlowResult) :
    KeysOnce (FlowDriverState.followUp replay s result) := by
  unfold FlowDriverState.followUp
  split <;> exact h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)

theorem KeysOnce.takeNext {s : FlowDriverState} (h : KeysOnce s) : KeysOnce s.takeNext := by
  unfold FlowDriverState.takeNext
  split <;> exact h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)

/-- Once a result of a key was given, the key is done, and every other key is as it was. -/
theorem any_done_got (done : List FlowResult) (result : FlowResult) (key : Key) :
    (done.filter (·.key != result.key) ++ [result]).any (·.key == key)
      = (done.any (·.key == key) || key == result.key) := by
  induction done with
  | nil =>
    by_cases same : key = result.key
    · simp [same]
    · have other : (result.key == key) = false := by simpa using fun eq : result.key = key => same eq.symm
      have differs : (key == result.key) = false := by simpa using same
      simp [other, differs]
  | cons first rest ih =>
    rw [List.filter_cons]
    by_cases its : first.key = result.key
    · have gone : (first.key != result.key) = false := by simp [its]
      simp only [gone, Bool.false_eq_true, ↓reduceIte, List.any_cons]
      rw [ih]
      by_cases same : key = result.key
      · simp [same]
      · have other : (first.key == key) = false := by
          rw [its]; simpa using fun eq : result.key = key => same eq.symm
        simp [other]
    · have keep : (first.key != result.key) = true := by simpa using its
      simp only [keep, ↓reduceIte, List.cons_append, List.any_cons]
      rw [ih, Bool.or_assoc]

theorem KeysOnce.got {s : FlowDriverState} (h : KeysOnce s) (result : FlowResult) : KeysOnce (s.got result) := by
  unfold FlowDriverState.got
  by_cases duplicate : (result.stop == Stop.duplicateKey) = true
  · simp only [duplicate, ↓reduceIte]
    exact h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => (List.mem_filter.mp mem).1) (fun _ mem => mem)
  · simp only [duplicate, Bool.false_eq_true, ↓reduceIte]
    refine ⟨h.once, h.sent, h.attached, h.unattached, ?_, ?_, ?_, h.cancels⟩
    · show s.«open».filter (· != result.key)
        = s.queuedKeys.filter fun key => !(s.done.filter (·.key != result.key) ++ [result]).any (·.key == key)
      rw [h.opened, List.filter_filter]
      refine List.filter_congr fun key _ => ?_
      rw [any_done_got]
      simp only [FlowDriverState.isDone]
      cases s.done.any (·.key == key) <;> cases same : (key == result.key) <;> simp [bne, same]
    · intro waiter mem
      have old := List.mem_filter.mp mem
      exact List.mem_filter.mpr ⟨h.waits waiter old.1, old.2⟩
    · intro creator mem
      have old := List.mem_filter.mp mem
      exact List.mem_filter.mpr ⟨h.creators creator old.1, old.2⟩

theorem KeysOnce.give {s : FlowDriverState} (h : KeysOnce s) : KeysOnce s.give.1 := by
  unfold FlowDriverState.give
  split
  · exact h
  · exact h.takeNext.got _

theorem KeysOnce.cancelled {s : FlowDriverState} (h : KeysOnce s) (call : FlowCallPath) : KeysOnce (s.cancelled call) :=
  h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => (List.mem_filter.mp mem).1) (fun _ mem => mem)

theorem lookup_mem {α : Type} (key : Key) (value : α) (entries : List (Key × α))
    (found : entries.lookup key = some value) : (key, value) ∈ entries := by
  obtain ⟨before, after, eq, _⟩ := List.lookup_eq_some_iff.mp found
  rw [eq]; simp

/-- What `cancelUnwaited` does: nothing, or the key has a creator, loses it, and is cancelled
on the queue, or waits for the queue to be cancelled. -/
theorem cancelUnwaited_cases (s : FlowDriverState) (key : Key) :
    s.cancelUnwaited key = s
      ∨ (∃ creator, s.creators.lookup key = some creator ∧ s.attached = true
          ∧ s.cancelUnwaited key = { s with creators := s.creators.filter (·.1 != key), cancels := key :: s.cancels })
      ∨ (∃ creator, s.creators.lookup key = some creator ∧ s.attached = false
          ∧ s.cancelUnwaited key
            = { s with creators := s.creators.filter (·.1 != key), toCancel := s.toCancel ++ [key] }) := by
  unfold FlowDriverState.cancelUnwaited
  split
  · exact Or.inl rfl
  · rename_i creator found
    by_cases kept : ((s.callOf creator).map (·.state) != some FlowCallState.closed || s.isDone key) = true
    · exact Or.inl (by simp only [kept, ↓reduceIte])
    · by_cases waited : s.waiters.any (·.1 == key) = true
      · exact Or.inl (by simp only [kept, waited, Bool.false_eq_true, ↓reduceIte])
      · by_cases attached : s.attached = true
        · exact Or.inr (Or.inl ⟨creator, found, attached, by simp [kept, waited, attached]⟩)
        · have loose : s.attached = false := by simpa using attached
          exact Or.inr (Or.inr ⟨creator, found, loose, by simp [kept, waited, loose]⟩)

theorem KeysOnce.cancelUnwaited {s : FlowDriverState} (h : KeysOnce s) (key : Key) : KeysOnce (s.cancelUnwaited key) := by
  have queued : ∀ creator, s.creators.lookup key = some creator → key ∈ s.queuedKeys := fun creator found =>
    (open_queued h (h.creators _ (lookup_mem key creator s.creators found))).1
  rcases cancelUnwaited_cases s key with eq | ⟨creator, found, attached, eq⟩ | ⟨creator, found, attached, eq⟩ <;> rw [eq]
  · exact h
  · refine ⟨h.once, h.sent, h.attached, ?_, h.opened, h.waits,
      fun creator mem => h.creators creator (List.mem_filter.mp mem).1, ?_⟩
    · intro loose; rw [attached] at loose; cases loose
    · intro other mem
      simp only [List.cons_append, List.mem_cons] at mem
      exact mem.elim (fun same => same ▸ queued creator found) (h.cancels other)
  · refine ⟨h.once, h.sent, h.attached, h.unattached, h.opened, h.waits,
      fun creator mem => h.creators creator (List.mem_filter.mp mem).1, ?_⟩
    intro other mem
    rw [← List.append_assoc] at mem
    rcases List.mem_append.mp mem with old | new
    · exact h.cancels other old
    · simp only [List.mem_singleton] at new; exact new ▸ queued creator found

theorem KeysOnce.cancelEach {s : FlowDriverState} (h : KeysOnce s) (keys : List Key) :
    KeysOnce (keys.foldl FlowDriverState.cancelUnwaited s) := by
  induction keys generalizing s with
  | nil => exact h
  | cons key rest ih => exact ih (h.cancelUnwaited key)

theorem KeysOnce.endCall {s : FlowDriverState} (h : KeysOnce s) (call : FlowCallPath) (state : FlowCallState) :
    KeysOnce (s.endCall call state) := by
  unfold FlowDriverState.endCall
  split
  · exact h
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte]; exact h
    · simp only [over, Bool.false_eq_true, ↓reduceIte]
      have base : KeysOnce { (s.setCall call fun c => { c with state := state }) with running := s.running - 1 } :=
        h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)
      by_cases closed : (state == FlowCallState.closed) = true
      · simp only [closed, ↓reduceIte]; exact base.cancelEach _
      · simp only [closed, Bool.false_eq_true, ↓reduceIte]; exact base

theorem KeysOnce.ended {s : FlowDriverState} (h : KeysOnce s) (call : FlowCallPath) (how : TaskEnd) :
    KeysOnce (s.ended call how).1 := by
  unfold FlowDriverState.ended
  split
  · exact h
  · rename_i found _
    by_cases over : (found.state != FlowCallState.running) = true
    · simp only [over, ↓reduceIte]; exact h
    · simp only [over, Bool.false_eq_true, ↓reduceIte]; exact h.endCall _ _

theorem KeysOnce.attach {s : FlowDriverState} (h : KeysOnce s) : KeysOnce s.attach := by
  refine ⟨h.once, ?_, fun _ => rfl, ?_, h.opened, h.waits, h.creators, ?_⟩
  · show (s.outbox.reverse ++ s.sent).reverse ++ [] = s.queuedKeys
    rw [← h.sent]; simp
  · intro loose; cases loose
  · intro key mem
    refine h.cancels key ?_
    simp only [FlowDriverState.attach, List.append_nil, List.mem_append, List.mem_reverse] at mem
    exact List.mem_append.mpr mem.symm

theorem KeysOnce.closeStuck {s : FlowDriverState} (h : KeysOnce s) (ready : Bool) : KeysOnce (s.closeStuck ready).1 := by
  unfold FlowDriverState.closeStuck
  split
  · exact h
  · exact h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => (List.mem_filter.mp mem).1) (fun _ mem => mem)

theorem KeysOnce.cancelRest {s : FlowDriverState} (h : KeysOnce s) : KeysOnce s.cancelRest :=
  h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => by cases mem) (fun _ mem => mem)

theorem KeysOnce.closeEach {s : FlowDriverState} (h : KeysOnce s) (paths : List FlowCallPath) :
    KeysOnce (paths.foldl (fun s path => s.endCall path .closed) s) := by
  induction paths generalizing s with
  | nil => exact h
  | cons path rest ih => exact ih (h.endCall path .closed)

theorem KeysOnce.closeRest {s : FlowDriverState} (h : KeysOnce s) : KeysOnce s.closeRest :=
  h.closeEach _

theorem KeysOnce.endStuck {s : FlowDriverState} (h : KeysOnce s) (ready : Bool) : KeysOnce (s.endStuck ready) := by
  have cleared : KeysOnce { s with stuck := [] } :=
    h.congr rfl rfl rfl rfl rfl rfl rfl rfl (fun _ mem => mem) (fun _ mem => mem)
  unfold FlowDriverState.endStuck
  split
  · exact cleared
  · exact cleared.closeEach _

/-! ## Every record the driver reaches -/

theorem Reachable.keys {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) : KeysOnce s := by
  induction h with
  | start =>
    refine ⟨List.nodup_nil, rfl, fun _ => rfl, fun _ => rfl, rfl, ?_, ?_, ?_⟩ <;> intro _ mem <;> cases mem
  | createTop _ ih => exact ih.create none
  | create up _ _ ih => exact ih.create (some up)
  | add call key cancellable _ ih => exact ih.add call key cancellable
  | wait call key _ ih => exact ih.wait call key
  | waited call stop past _ ih => exact ih.waited call stop past
  | followUp result _ ih => exact ih.followUp replay result
  | give _ ih => exact ih.give
  | cancelled call _ ih => exact ih.cancelled call
  | ended call how _ ih => exact ih.ended call how
  | attach _ ih => exact ih.attach
  | closeStuck ready _ ih => exact ih.closeStuck ready
  | endStuck ready _ ih => exact ih.endStuck ready
  | cancelRest _ ih => exact ih.cancelRest
  | closeRest _ ih => exact ih.closeRest

/-- The queue is given each key once: what it was given holds no key twice, in whatever
order flow code created its tasks and waited for them. -/
theorem Reachable.sent_once {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s) :
    s.sent.Nodup := by
  have keys := h.keys
  have once := keys.once
  rw [← keys.sent, List.nodup_append] at once
  exact (List.pairwise_reverse.mp once.1).imp fun differ same => differ same.symm

/-- Once the queue is attached, it was given every key the driver queued, in the order the
driver queued them. -/
theorem Reachable.sent_all {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s)
    (attached : s.attached = true) : s.sent.reverse = s.queuedKeys := by
  have keys := h.keys
  have sent := keys.sent
  rw [keys.attached attached, List.append_nil] at sent
  exact sent

/-- A key the driver cancels on the queue is one it gave the queue. -/
theorem Reachable.cancels_sent {replay : List (Key × Nat)} {s : FlowDriverState} (h : Reachable replay s)
    (key : Key) (cancelled : key ∈ s.cancels) : key ∈ s.sent := by
  have keys := h.keys
  by_cases attached : s.attached = true
  · have queued := keys.cancels key (List.mem_append_left _ cancelled)
    rw [← h.sent_all attached] at queued
    exact List.mem_reverse.mp queued
  · rw [keys.unattached (by simpa using attached)] at cancelled
    cases cancelled

/-- When the driver closes the flow calls that nothing will answer, no flow call waits for
a task, and every task the driver queued has given its result. -/
theorem Reachable.stuck_waits_for_no_task {replay : List (Key × Nat)} {s : FlowDriverState}
    (h : Reachable replay s) (ready : Bool) (closes : (s.closeStuck ready).2 = true) :
    s.waiters = [] ∧ ∀ key ∈ s.queuedKeys, s.isDone key = true := by
  have keys := h.keys
  have none_open : s.«open» = [] := by
    unfold FlowDriverState.closeStuck FlowDriverState.answerable at closes
    by_cases quiet : (s.running == 0 || (ready || !s.results.isEmpty || !s.replayed.isEmpty || !s.«open».isEmpty)) = true
    · simp [quiet] at closes
    · simp only [Bool.or_eq_true, not_or, Bool.not_eq_true', Bool.not_eq_false, List.isEmpty_iff] at quiet
      exact quiet.2.2
  refine ⟨?_, ?_⟩
  · cases waiters : s.waiters with
    | nil => rfl
    | cons waiter rest =>
      have mem := keys.waits waiter (by rw [waiters]; exact List.mem_cons_self)
      rw [none_open] at mem
      cases mem
  · intro key queued
    have empty := keys.opened
    rw [none_open] at empty
    have none := List.filter_eq_nil_iff.mp empty.symm key queued
    simpa using none

end FlowDriverState

/-- info: 'Contraagent.FlowDriverState.Reachable.sent_once' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Reachable.sent_once

/-- info: 'Contraagent.FlowDriverState.Reachable.cancels_sent' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.Reachable.cancels_sent

/--
info: 'Contraagent.FlowDriverState.Reachable.stuck_waits_for_no_task' depends on axioms: [propext,
 Classical.choice,
 Quot.sound]
-/
#guard_msgs in
#print axioms FlowDriverState.Reachable.stuck_waits_for_no_task

end Contraagent
