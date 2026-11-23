import Contraagent.Execution.Services.Once

/-!
# The run's end stops the services in the reverse order of their starts

Of the description of `Services`: when the run's end closes the services of a state the
run reached, `services.jsonl` gets one stop for each start that went well, the last started
first (`Reachable.close_reverse`).

The services keep the order of their starts as a number each (`started`), and the run's end
sorts them by it. The proof keeps, for every state before the run's end, that the names of
the starts that went well are those of the services that are up, and that their numbers
fall as the log goes back (`Ordered`).
-/

namespace Contraagent

/-- The names of the starts that went well in a log, the latest first. -/
def startedNames (log : List ServiceEvent) : List String :=
  log.filterMap fun
    | .start name _ _ none => some name
    | _ => none

/-- The names of the stops in a log, the latest first. -/
def stoppedNames (log : List ServiceEvent) : List String :=
  log.filterMap fun
    | .stop name _ _ => some name
    | _ => none

theorem lookup_of_mem {α : Type} (entries : List (String × α)) (nodup : (entries.map (·.1)).Nodup)
    (name : String) (value : α) (held : (name, value) ∈ entries) : entries.lookup name = some value := by
  induction entries with
  | nil => cases held
  | cons entry rest ih =>
    obtain ⟨key, other⟩ := entry
    rw [List.map_cons, List.nodup_cons] at nodup
    rw [List.lookup_cons]
    rcases List.mem_cons.mp held with here | later
    · simp only [Prod.mk.injEq] at here
      simp [here.1, here.2]
    · have differs : (name == key) = false := by
        simp only [beq_eq_false_iff_ne, ne_eq]
        intro same
        apply nodup.1
        rw [← same]
        exact List.mem_map.mpr ⟨(name, value), later, rfl⟩
      simp only [differs]
      exact ih nodup.2 later

theorem mem_of_lookup {α : Type} (entries : List (String × α)) (name : String) (value : α)
    (found : entries.lookup name = some value) : (name, value) ∈ entries := by
  induction entries with
  | nil => simp at found
  | cons entry rest ih =>
    obtain ⟨key, other⟩ := entry
    rw [List.lookup_cons] at found
    cases same : name == key with
    | true =>
      simp only [same, Option.some.injEq] at found
      have is : name = key := by simpa using same
      rw [is, found]
      exact List.mem_cons_self
    | false =>
      simp only [same] at found
      exact List.mem_cons_of_mem _ (ih found)

namespace ServicesState

theorem stateOf_of_mem (s : ServicesState) (nodup : (s.states.map (·.1)).Nodup) (name : String)
    (state : ServiceState) (held : (name, state) ∈ s.states) : s.stateOf name = state := by
  simp [stateOf, lookup_of_mem s.states nodup name state held]

/-- A service that is up has an entry among the states. -/
theorem mem_of_up (s : ServicesState) (name : String) (up : (s.stateOf name).up = true) :
    (name, s.stateOf name) ∈ s.states := by
  unfold stateOf at up ⊢
  cases found : s.states.lookup name with
  | none => simp [found] at up
  | some state => exact mem_of_lookup s.states name state found

theorem setState_nodup (s : ServicesState) (name : String) (state : ServiceState)
    (nodup : (s.states.map (·.1)).Nodup) : ((s.setState name state).states.map (·.1)).Nodup := by
  unfold setState
  simp only [List.map_cons, List.nodup_cons]
  refine ⟨?_, List.Nodup.sublist (List.filter_sublist.map _) nodup⟩
  intro held
  obtain ⟨entry, there, is⟩ := List.mem_map.mp held
  have kept := (List.mem_filter.mp there).2
  simp only [bne_iff_ne, ne_eq] at kept
  exact kept is

/-- What every state the run reaches keeps: no two entries of one name among the states;
and, before the run's end, no stop in the log, the services that are up are those whose
start went well, the numbers of their starts fall as the log goes back, and none is past
the count of the starts. -/
structure Ordered (s : ServicesState) : Prop where
  names : (s.states.map (·.1)).Nodup
  running : s.closed = false →
    stoppedNames s.log = [] ∧
    (∀ name, (s.stateOf name).up = true ↔ name ∈ startedNames s.log) ∧
    (startedNames s.log).Pairwise (fun a b => (s.stateOf a).started > (s.stateOf b).started) ∧
    ∀ name ∈ startedNames s.log, (s.stateOf name).started ≤ s.starts

/-- What changes neither the starts and stops of the log nor whether a service is up or
the number of its start keeps it. -/
theorem Ordered.congr {s s' : ServicesState} (h : Ordered s) (names : (s'.states.map (·.1)).Nodup)
    (closed : s'.closed = s.closed) (started : startedNames s'.log = startedNames s.log)
    (stopped : stoppedNames s'.log = stoppedNames s.log) (starts : s'.starts = s.starts)
    (up : ∀ name, (s'.stateOf name).up = (s.stateOf name).up)
    (number : ∀ name, (s'.stateOf name).started = (s.stateOf name).started) : Ordered s' := by
  refine ⟨names, ?_⟩
  intro going
  rw [closed] at going
  obtain ⟨none, ups, falls, bound⟩ := h.running going
  rw [started, stopped, starts]
  refine ⟨none, ?_, ?_, ?_⟩
  · intro name
    rw [up name]
    exact ups name
  · refine List.Pairwise.imp ?_ falls
    intro a b gt
    rw [number a, number b]
    exact gt
  · intro name held
    rw [number name]
    exact bound name held

theorem Ordered.setState {s : ServicesState} (h : Ordered s) (name : String) (state : ServiceState)
    (up : state.up = (s.stateOf name).up) (number : state.started = (s.stateOf name).started) :
    Ordered (s.setState name state) := by
  refine h.congr (s.setState_nodup name state h.names) rfl rfl rfl rfl ?_ ?_
  · intro other
    by_cases same : other = name
    · rw [same, stateOf_setState_self, up]
    · rw [stateOf_setState_other _ _ _ _ same]
  · intro other
    by_cases same : other = name
    · rw [same, stateOf_setState_self, number]
    · rw [stateOf_setState_other _ _ _ _ same]

/-- A service that was not up starts well before the run's end, as the latest started: it
keeps it. -/
theorem Ordered.started {s s' : ServicesState} (h : Ordered s) (name key : String) (address : Option String)
    (names : (s'.states.map (·.1)).Nodup) (log : s'.log = .start name key address none :: s.log)
    (starts : s'.starts = s.starts + 1) (down : (s.stateOf name).up = false) (going : s.closed = false)
    (up : (s'.stateOf name).up = true) (number : (s'.stateOf name).started = s.starts + 1)
    (others : ∀ other, other ≠ name → s'.stateOf other = s.stateOf other) : Ordered s' := by
  refine ⟨names, ?_⟩
  intro _
  obtain ⟨none, ups, falls, bound⟩ := h.running going
  have fresh : name ∉ startedNames s.log := fun held => by
    have isUp := (ups name).mpr held
    rw [down] at isUp
    cases isUp
  have listed : startedNames s'.log = name :: startedNames s.log := by rw [log]; rfl
  have quiet : stoppedNames s'.log = stoppedNames s.log := by rw [log]; rfl
  rw [listed, quiet, starts]
  refine ⟨none, ?_, ?_, ?_⟩
  · intro other
    by_cases same : other = name
    · rw [same, up]
      simp
    · rw [others other same]
      constructor
      · intro isUp
        exact List.mem_cons_of_mem _ ((ups other).mp isUp)
      · intro held
        exact (ups other).mpr ((List.mem_cons.mp held).resolve_left same)
  · rw [List.pairwise_cons]
    constructor
    · intro other held
      have differs : other ≠ name := fun eq => fresh (eq ▸ held)
      rw [number, others other differs]
      have := bound other held
      omega
    · refine List.Pairwise.imp_of_mem ?_ falls
      intro a b ha hb gt
      rw [others a (fun eq => fresh (eq ▸ ha)), others b (fun eq => fresh (eq ▸ hb))]
      exact gt
  · intro other held
    rcases List.mem_cons.mp held with first | later
    · rw [first, number]
      exact Nat.le_refl _
    · rw [others other (fun eq => fresh (eq ▸ later))]
      have := bound other later
      omega

end ServicesState

open ServicesState

namespace ServicesConfig

theorem start_ordered {s : ServicesState} (h : Ordered s) (name : String) (key : Key) (state : ServiceState)
    (answer : StartAnswer) (down : (s.stateOf name).up = false) (same : state.up = false)
    (number : state.started = (s.stateOf name).started) (going : s.closed = false) :
    Ordered (start s name key state answer).1 := by
  cases answer with
  | raised error failedAt =>
    have base := h.setState name { state with failed := some error, failedAt := failedAt }
      (by rw [down]; exact same) number
    exact base.congr base.names rfl rfl rfl rfl (fun _ => rfl) (fun _ => rfl)
  | gave address =>
    refine Ordered.started h name key address (s.setState_nodup name _ h.names) rfl rfl down going ?_ ?_ ?_
    · exact congrArg ServiceState.up (stateOf_setState_self s name _)
    · exact congrArg ServiceState.started (stateOf_setState_self s name _)
    · intro other differs
      exact stateOf_setState_other s name other _ differs

theorem acquire_ordered (cfg : ServicesConfig) {s : ServicesState} (h : Ordered s) (name : String) (key : Key)
    (outside : ServiceOutside) : Ordered (cfg.acquire s name key outside).1 := by
  unfold acquire
  dsimp only
  split
  · exact h
  · have cleared := h.setState name { s.stateOf name with failed := none } rfl rfl
    split
    · exact cleared
    · rename_i going
      split
      · exact cleared
      · rename_i down
        simp at going down
        apply start_ordered cleared
        · rw [stateOf_setState_self]; exact down
        · exact down
        · rw [stateOf_setState_self]
        · exact going.1

theorem acquireAll_ordered (cfg : ServicesConfig) (key : Key) (outside : String → ServiceOutside)
    (names : List String) : ∀ (s : ServicesState) (held : List (String × Option String)), Ordered s →
      Ordered (cfg.acquireAll key outside s names held).1 := by
  induction names with
  | nil => intro s held h; exact h
  | cons name rest ih =>
    intro s held h
    unfold acquireAll
    have one := cfg.acquire_ordered h name key (outside name)
    split
    · rename_i s' failure eq
      rw [eq] at one
      exact one
    · rename_i s' address eq
      rw [eq] at one
      exact ih s' _ one

theorem hold_ordered (cfg : ServicesConfig) (env : ServicesEnv) {s : ServicesState} (h : Ordered s)
    (task : Task) (outside : String → ServiceOutside) : Ordered (cfg.hold env s task outside).1 := by
  unfold hold
  dsimp only
  split
  · exact h
  · split
    · exact h
    · exact cfg.acquireAll_ordered task.key outside _ s [] h

end ServicesConfig

namespace ServicesState

theorem stopOne_nodup (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name : String) (nodup : (s.states.map (·.1)).Nodup) :
    ((stopOne cause stop s name).states.map (·.1)).Nodup := by
  unfold stopOne
  dsimp only
  split
  · exact s.setState_nodup name _ nodup
  · exact nodup

theorem close_ordered {s : ServicesState} (h : Ordered s) (cause : ServiceStopCause)
    (stop : String → Option String) : Ordered (s.close cause stop) := by
  suffices kept : ∀ (names : List String) (t : ServicesState), (t.states.map (·.1)).Nodup → t.closed = true →
      ((names.foldl (stopOne cause stop) t).states.map (·.1)).Nodup ∧
        (names.foldl (stopOne cause stop) t).closed = true by
    obtain ⟨nodup, closed⟩ := kept s.closeOrder { s with closed := true } h.names rfl
    exact ⟨nodup, fun going => by rw [close, closed] at going; cases going⟩
  intro names
  induction names with
  | nil => intro t nodup closed; exact ⟨nodup, closed⟩
  | cons name rest ih =>
    intro t nodup closed
    exact ih _ (stopOne_nodup cause stop t name nodup) (by rw [stopOne_closed]; exact closed)

end ServicesState

/-- Among values whose numbers fall along a list, two with one number are one. -/
theorem eq_of_falls {α : Type} (number : α → Nat) : ∀ (l : List α), l.Pairwise (fun a b => number a > number b) →
    ∀ a ∈ l, ∀ b ∈ l, number a = number b → a = b
  | [], _, a, held, _, _, _ => by cases held
  | first :: rest, falls, a, ha, b, hb, same => by
    rw [List.pairwise_cons] at falls
    rcases List.mem_cons.mp ha with rfl | ha' <;> rcases List.mem_cons.mp hb with rfl | hb'
    · rfl
    · have := falls.1 b hb'
      omega
    · have := falls.1 a ha'
      omega
    · exact eq_of_falls number rest falls.2 a ha' b hb' same

namespace ServicesState

theorem stopOne_other (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name other : String) (differs : other ≠ name) : (stopOne cause stop s name).stateOf other = s.stateOf other := by
  unfold stopOne
  dsimp only
  split
  · exact stateOf_setState_other s name other _ differs
  · rfl

theorem stopOne_stopped (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name : String) :
    stoppedNames (stopOne cause stop s name).log =
      if (s.stateOf name).up then name :: stoppedNames s.log else stoppedNames s.log := by
  unfold stopOne
  dsimp only
  split <;> rfl

/-- A walk through names of which no two are one writes a stop for each that is up, in the
walk's order: the last walked is the latest in the log. -/
theorem stops_written (cause : ServiceStopCause) (stop : String → Option String) :
    ∀ (names : List String) (t : ServicesState), names.Nodup →
      stoppedNames (names.foldl (stopOne cause stop) t).log =
        (names.filter fun name => (t.stateOf name).up).reverse ++ stoppedNames t.log := by
  intro names
  induction names with
  | nil => intro t _; rfl
  | cons name rest ih =>
    intro t nodup
    rw [List.nodup_cons] at nodup
    have same : (rest.filter fun other => ((stopOne cause stop t name).stateOf other).up) =
        rest.filter fun other => (t.stateOf other).up := by
      apply List.filter_congr
      intro other held
      rw [stopOne_other cause stop t name other (fun eq => nodup.1 (eq ▸ held))]
    rw [List.foldl_cons, ih _ nodup.2, same, stopOne_stopped, List.filter_cons]
    cases (t.stateOf name).up <;> simp

/-- The order the run's end goes through the names: no name twice. -/
theorem closeOrder_nodup (s : ServicesState) (h : Ordered s) : s.closeOrder.Nodup := by
  unfold closeOrder
  exact ((List.mergeSort_perm s.states _).map _).nodup_iff.mpr h.names

/-- Before the run's end, the services that are up, in the order the run's end goes
through them, are those whose start went well, the latest first. -/
theorem closeOrder_up (s : ServicesState) (h : Ordered s) (going : s.closed = false) :
    (s.closeOrder.filter fun name => (s.stateOf name).up) = startedNames s.log := by
  obtain ⟨_, ups, falls, _⟩ := h.running going
  have perm := List.mergeSort_perm s.states fun a b => decide (a.2.started ≥ b.2.started)
  have sorted : (s.states.mergeSort fun a b => decide (a.2.started ≥ b.2.started)).Pairwise
      fun a b => decide (a.2.started ≥ b.2.started) = true :=
    List.pairwise_mergeSort (fun a b c ab bc => by simp only [decide_eq_true_eq] at ab bc ⊢; omega)
      (fun a b => by simp only [Bool.or_eq_true, decide_eq_true_eq]; omega) _
  have own : ∀ entry ∈ s.states.mergeSort (fun a b => decide (a.2.started ≥ b.2.started)),
      s.stateOf entry.1 = entry.2 := fun entry held =>
    stateOf_of_mem s h.names entry.1 entry.2 (perm.mem_iff.mp held)
  have byNumber : s.closeOrder.Pairwise fun a b => (s.stateOf a).started ≥ (s.stateOf b).started := by
    unfold closeOrder
    rw [List.pairwise_map]
    refine List.Pairwise.imp_of_mem ?_ sorted
    intro a b ha hb le
    rw [own a ha, own b hb]
    simpa using le
  have started : (startedNames s.log).Nodup :=
    List.Pairwise.imp (fun {a b} (gt : (s.stateOf a).started > (s.stateOf b).started) (eq : a = b) => by
      rw [eq] at gt
      omega) falls
  have same : (s.closeOrder.filter fun name => (s.stateOf name).up).Perm (startedNames s.log) := by
    rw [List.perm_ext_iff_of_nodup (List.Nodup.sublist List.filter_sublist (s.closeOrder_nodup h)) started]
    intro name
    rw [List.mem_filter]
    constructor
    · intro held
      exact (ups name).mp held.2
    · intro held
      have up := (ups name).mpr held
      refine ⟨?_, up⟩
      unfold closeOrder
      exact List.mem_map.mpr ⟨(name, s.stateOf name), perm.mem_iff.mpr (s.mem_of_up name up), rfl⟩
  refine List.Perm.eq_of_pairwise (le := fun a b => (s.stateOf a).started ≥ (s.stateOf b).started) ?_
    (byNumber.filter _) (falls.imp fun gt => Nat.le_of_lt gt) same
  intro a b ha hb ab ba
  exact eq_of_falls (fun name => (s.stateOf name).started) _ falls a ((ups a).mp (List.mem_filter.mp ha).2) b hb
    (Nat.le_antisymm ba ab)

end ServicesState

theorem ServicesConfig.Reachable.ordered {cfg : ServicesConfig} {s : ServicesState} (reached : cfg.Reachable s) :
    Ordered s := by
  induction reached with
  | none =>
    refine ⟨List.nodup_nil, fun _ => ⟨rfl, ?_, List.Pairwise.nil, ?_⟩⟩
    · intro name
      simp [ServicesState.stateOf, startedNames]
    · intro name held
      cases held
  | hold env s task outside _ ih => exact cfg.hold_ordered env ih task outside
  | close s cause stop _ ih => exact close_ordered ih cause stop

/-- The run's end stops the services in the reverse order of their starts: when it closes
the services of a state the run reached, the stops in `services.jsonl`, the latest first,
are the starts that went well, the earliest first. Each service that started is stopped
once, and the last started is stopped first. -/
theorem ServicesConfig.Reachable.close_reverse {cfg : ServicesConfig} {s : ServicesState}
    (reached : cfg.Reachable s) (going : s.closed = false) (cause : ServiceStopCause)
    (stop : String → Option String) :
    stoppedNames (s.close cause stop).log = (startedNames s.log).reverse := by
  have h := reached.ordered
  have none := (h.running going).1
  have written := stops_written cause stop s.closeOrder { s with closed := true } (s.closeOrder_nodup h)
  have ups : (s.closeOrder.filter fun name => (({ s with closed := true } : ServicesState).stateOf name).up) =
      startedNames s.log := s.closeOrder_up h going
  unfold ServicesState.close
  rw [written, ups]
  show (startedNames s.log).reverse ++ stoppedNames s.log = _
  rw [none, List.append_nil]

/-- info: 'Contraagent.ServicesConfig.Reachable.close_reverse' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms ServicesConfig.Reachable.close_reverse

end Contraagent
