import Contraagent.Execution.Services

/-!
# A service starts once, and the run's end stops it

Of the description of `Services`: in every state a run reaches, the log shows at most one
start that went well for each claim name (`Reachable.started_once`); once the run's end
closed the services, a task starts none (`hold_closed`); and the run's end leaves no
service up (`close_none_up`).
-/

namespace Contraagent

/-- Whether an event is a start of `name` that went well. -/
def ServiceEvent.startedWell (name : String) : ServiceEvent → Bool
  | .start started _ _ none => started == name
  | _ => false

/-- How many starts of `name` that went well a log shows. -/
def startsOf (name : String) (log : List ServiceEvent) : Nat :=
  log.countP (ServiceEvent.startedWell name)

namespace ServicesState

theorem lookup_filter_ne (states : List (String × ServiceState)) (name other : String)
    (differs : other ≠ name) : (states.filter (·.1 != name)).lookup other = states.lookup other := by
  induction states with
  | nil => rfl
  | cons entry rest ih =>
    obtain ⟨key, state⟩ := entry
    by_cases same : key = name
    · subst same
      have miss : (other == key) = false := by simpa using differs
      simp [List.lookup_cons, miss, ih]
    · have keep : (key != name) = true := by simpa using same
      simp only [List.filter_cons, keep, ↓reduceIte, List.lookup_cons]
      rw [ih]

theorem stateOf_setState_self (s : ServicesState) (name : String) (state : ServiceState) :
    (s.setState name state).stateOf name = state := by
  simp [stateOf, setState]

theorem stateOf_setState_other (s : ServicesState) (name other : String) (state : ServiceState)
    (differs : other ≠ name) : (s.setState name state).stateOf other = s.stateOf other := by
  have miss : (other == name) = false := by simpa using differs
  simp [stateOf, setState, List.lookup_cons, miss, lookup_filter_ne _ _ _ differs]

theorem stateOf_congr {s s' : ServicesState} (same : s'.states = s.states) (name : String) :
    s'.stateOf name = s.stateOf name := by
  unfold stateOf
  rw [same]

/-- What every reachable state keeps: a name's start went well at most once, and not at all
while its service is not up and the run has not ended. -/
def Once (s : ServicesState) : Prop :=
  ∀ name, startsOf name s.log ≤ if (s.stateOf name).up || s.closed then 1 else 0

theorem Once.congr {s s' : ServicesState} (h : Once s) (log : s'.log = s.log)
    (closed : s'.closed = s.closed) (up : ∀ name, (s'.stateOf name).up = (s.stateOf name).up) :
    Once s' := by
  intro name
  rw [log, closed, up name]
  exact h name

/-- Changing what a name's service holds, but whether it is up, keeps it. -/
theorem Once.setState {s : ServicesState} (h : Once s) (name : String) (state : ServiceState)
    (up : state.up = (s.stateOf name).up) : Once (s.setState name state) := by
  refine Once.congr (s' := s.setState name state) h rfl rfl ?_
  intro other
  by_cases same : other = name
  · rw [same, stateOf_setState_self, up]
  · rw [stateOf_setState_other _ _ _ _ same]

/-- Writing a line that is no start that went well keeps it. -/
theorem Once.wrote {s s' : ServicesState} (h : Once s) (event : ServiceEvent)
    (other : ∀ name, event.startedWell name = false) (log : s'.log = event :: s.log)
    (closed : s'.closed = s.closed) (up : ∀ name, (s'.stateOf name).up = (s.stateOf name).up) :
    Once s' := by
  intro name
  rw [log, closed, up name]
  simpa [startsOf, List.countP_cons, other name] using h name

/-- A service that was not up starts well before the run's end: it keeps it. -/
theorem Once.started {s s' : ServicesState} (h : Once s) (name key : String) (address : Option String)
    (log : s'.log = .start name key address none :: s.log) (closed : s'.closed = s.closed)
    (down : (s.stateOf name).up = false) (going : s.closed = false)
    (up : (s'.stateOf name).up = true)
    (others : ∀ other, other ≠ name → (s'.stateOf other).up = (s.stateOf other).up) : Once s' := by
  intro other
  rw [log, closed]
  by_cases hit : other = name
  · have none := h name
    rw [down, going] at none
    rw [hit, up]
    simp only [startsOf] at none ⊢
    simp only [List.countP_cons, ServiceEvent.startedWell, beq_self_eq_true]
    simp at none ⊢
    omega
  · have miss : (name == other) = false := by simpa using fun eq : name = other => hit eq.symm
    rw [others other hit]
    simpa [startsOf, List.countP_cons, ServiceEvent.startedWell, miss] using h other

end ServicesState

open ServicesState

namespace ServicesConfig

theorem start_once {s : ServicesState} (h : Once s) (name : String) (key : Key) (state : ServiceState)
    (answer : StartAnswer) (down : (s.stateOf name).up = false) (same : state.up = false)
    (going : s.closed = false) : Once (start s name key state answer).1 := by
  cases answer with
  | raised error failedAt =>
    refine Once.wrote (h.setState name { state with failed := some error, failedAt := failedAt }
      (by rw [down]; exact same)) (.start name key none (some error)) (fun _ => rfl) rfl rfl ?_
    intro other
    rfl
  | gave address =>
    refine Once.started h name key address rfl rfl down going ?_ ?_
    · exact congrArg ServiceState.up (stateOf_setState_self s name _)
    · intro other differs
      exact congrArg ServiceState.up (stateOf_setState_other s name other _ differs)

theorem acquire_once (cfg : ServicesConfig) {s : ServicesState} (h : Once s) (name : String) (key : Key)
    (outside : ServiceOutside) : Once (cfg.acquire s name key outside).1 := by
  unfold acquire
  dsimp only
  split
  · exact h
  · have cleared := h.setState name { s.stateOf name with failed := none } rfl
    split
    · exact cleared
    · rename_i going
      split
      · exact cleared
      · rename_i down
        simp at going down
        apply start_once cleared
        · rw [stateOf_setState_self]; exact down
        · exact down
        · exact going.1

theorem acquireAll_once (cfg : ServicesConfig) (key : Key) (outside : String → ServiceOutside)
    (names : List String) : ∀ (s : ServicesState) (held : List (String × Option String)), Once s →
      Once (cfg.acquireAll key outside s names held).1 := by
  induction names with
  | nil => intro s held h; exact h
  | cons name rest ih =>
    intro s held h
    unfold acquireAll
    have one := cfg.acquire_once h name key (outside name)
    split
    · rename_i s' failure eq
      rw [eq] at one
      exact one
    · rename_i s' address eq
      rw [eq] at one
      exact ih s' _ one

theorem hold_once (cfg : ServicesConfig) (env : ServicesEnv) {s : ServicesState} (h : Once s)
    (task : Task) (outside : String → ServiceOutside) : Once (cfg.hold env s task outside).1 := by
  unfold hold
  dsimp only
  split
  · exact h
  · split
    · exact h
    · exact cfg.acquireAll_once task.key outside _ s [] h

/-- A service whose start raised rests: until the cool-off has passed since, and for the
whole run with no cool-off, a task that claims the name fails with what the start raised,
and nothing else happens. -/
theorem acquire_resting (cfg : ServicesConfig) (s : ServicesState) (name : String) (key : Key)
    (outside : ServiceOutside) (error : String) (failed : (s.stateOf name).failed = some error)
    (within : ∀ cooloff, cfg.cooloffS = some cooloff → outside.now - (s.stateOf name).failedAt < cooloff) :
    cfg.acquire s name key outside = (s, .error (.notStarted name error)) := by
  have rests : cfg.resting outside.now (s.stateOf name) = true := by
    unfold resting
    rw [failed]
    cases cooloff : cfg.cooloffS with
    | none => rfl
    | some length => simpa using within length cooloff
  simp [acquire, rests, failed]

/-- A start that raised leaves the service resting with what it raised and when. -/
theorem start_raised (s : ServicesState) (name : String) (key : Key) (state : ServiceState)
    (error : String) (failedAt : Time) :
    ((start s name key state (.raised error failedAt)).1.stateOf name).failed = some error ∧
      ((start s name key state (.raised error failedAt)).1.stateOf name).failedAt = failedAt :=
  ⟨congrArg ServiceState.failed (stateOf_setState_self s name _),
    congrArg ServiceState.failedAt (stateOf_setState_self s name _)⟩

/-- Once the run's end closed the services, acquiring a name fails and starts nothing. -/
theorem acquire_closed (cfg : ServicesConfig) (s : ServicesState) (name : String) (key : Key)
    (outside : ServiceOutside) (closed : s.closed = true) :
    (cfg.acquire s name key outside).1.log = s.log ∧ (cfg.acquire s name key outside).1.closed = true ∧
      ∃ failure, (cfg.acquire s name key outside).2 = .error failure := by
  unfold acquire
  dsimp only
  split
  · exact ⟨rfl, closed, _, rfl⟩
  · have still : (s.setState name { s.stateOf name with failed := none }).closed = true := closed
    simp only [still, Bool.true_or, ↓reduceIte]
    exact ⟨rfl, trivial, _, rfl⟩

/-- Once the run's end closed the services, a task starts none: nothing is written to
`services.jsonl`, and the services stay closed. -/
theorem hold_closed (cfg : ServicesConfig) (env : ServicesEnv) (s : ServicesState) (task : Task)
    (outside : String → ServiceOutside) (closed : s.closed = true) :
    (cfg.hold env s task outside).1.log = s.log ∧ (cfg.hold env s task outside).1.closed = true := by
  unfold hold
  dsimp only
  split
  · exact ⟨rfl, closed⟩
  · split
    · exact ⟨rfl, closed⟩
    · cases env.names task with
      | nil => exact ⟨rfl, closed⟩
      | cons name rest =>
        unfold acquireAll
        obtain ⟨log, still, failure, failed⟩ := cfg.acquire_closed s name task.key (outside name) closed
        split
        · rename_i s' _ eq
          rw [eq] at log still
          exact ⟨log, still⟩
        · rename_i s' _ eq
          rw [eq] at failed
          cases failed

end ServicesConfig

namespace ServicesState

theorem stopOne_closed (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name : String) : (stopOne cause stop s name).closed = s.closed := by
  unfold stopOne
  dsimp only
  split <;> rfl

theorem stopOne_starts (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name other : String) : startsOf other (stopOne cause stop s name).log = startsOf other s.log := by
  unfold stopOne
  dsimp only
  split
  · simp [startsOf, ServiceEvent.startedWell]
  · rfl

/-- Stopping a service starts none. -/
theorem stopOne_down (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name other : String) (down : (s.stateOf other).up = false) :
    ((stopOne cause stop s name).stateOf other).up = false := by
  unfold stopOne
  dsimp only
  split
  · by_cases hit : other = name
    · rw [hit]
      exact congrArg ServiceState.up (stateOf_setState_self s name _)
    · exact (congrArg ServiceState.up (stateOf_setState_other s name other _ hit)).trans down
  · exact down

theorem stopOne_self (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name : String) : ((stopOne cause stop s name).stateOf name).up = false := by
  unfold stopOne
  dsimp only
  split
  · exact congrArg ServiceState.up (stateOf_setState_self s name _)
  · rename_i down
    simpa using down

theorem stops_down (cause : ServiceStopCause) (stop : String → Option String) (other : String)
    (names : List String) : ∀ s : ServicesState, (s.stateOf other).up = false →
      ((names.foldl (stopOne cause stop) s).stateOf other).up = false := by
  induction names with
  | nil => intro s down; exact down
  | cons name rest ih => intro s down; exact ih _ (stopOne_down cause stop s name other down)

theorem stops_named (cause : ServiceStopCause) (stop : String → Option String) (other : String)
    (names : List String) : ∀ s : ServicesState, other ∈ names →
      ((names.foldl (stopOne cause stop) s).stateOf other).up = false := by
  induction names with
  | nil => intro s named; cases named
  | cons name rest ih =>
    intro s named
    by_cases hit : other = name
    · rw [hit]
      exact stops_down cause stop name rest _ (stopOne_self cause stop s name)
    · exact ih _ ((List.mem_cons.mp named).resolve_left hit)

/-- The run's end leaves no service up. -/
theorem close_none_up (s : ServicesState) (cause : ServiceStopCause) (stop : String → Option String)
    (name : String) : ((s.close cause stop).stateOf name).up = false := by
  unfold close
  by_cases named : name ∈ s.closeOrder
  · exact stops_named cause stop name _ _ named
  · apply stops_down
    have absent : s.states.lookup name = none := by
      rw [List.lookup_eq_none_iff]
      intro entry held
      simp only [closeOrder, List.mem_map, List.mem_mergeSort, not_exists, not_and] at named
      simpa using fun eq : name = entry.1 => named entry held eq.symm
    simp [stateOf, absent]

theorem close_once {s : ServicesState} (h : Once s) (cause : ServiceStopCause)
    (stop : String → Option String) : Once (s.close cause stop) := by
  have bound : ∀ name, startsOf name s.log ≤ 1 := fun name => by
    have := h name
    split at this <;> omega
  suffices kept : ∀ (names : List String) (s' : ServicesState), s'.closed = true →
      (∀ name, startsOf name s'.log ≤ 1) →
      (names.foldl (stopOne cause stop) s').closed = true ∧
        ∀ name, startsOf name (names.foldl (stopOne cause stop) s').log ≤ 1 by
    obtain ⟨closed, once⟩ := kept s.closeOrder { s with closed := true } rfl bound
    intro name
    unfold close
    rw [closed]
    simpa using once name
  intro names
  induction names with
  | nil => intro s' closed once; exact ⟨closed, once⟩
  | cons name rest ih =>
    intro s' closed once
    apply ih
    · rw [stopOne_closed]; exact closed
    · intro other; rw [stopOne_starts]; exact once other

end ServicesState

/-- The states a run's services reach: from none, by tasks that come to hold the services
they claim and by ends of the run, at any times and whatever the starts and the stops do. -/
inductive ServicesConfig.Reachable (cfg : ServicesConfig) : ServicesState → Prop
  | none : cfg.Reachable {}
  | hold (env : ServicesEnv) (s : ServicesState) (task : Task) (outside : String → ServiceOutside) :
    cfg.Reachable s → cfg.Reachable (cfg.hold env s task outside).1
  | close (s : ServicesState) (cause : ServiceStopCause) (stop : String → Option String) :
    cfg.Reachable s → cfg.Reachable (s.close cause stop)

/-- In every state a run reaches, `services.jsonl` shows at most one start that went well
for each claim name: a service that is up is not started again, and none starts after the
run's end stopped it. -/
theorem ServicesConfig.Reachable.started_once {cfg : ServicesConfig} {s : ServicesState}
    (reached : cfg.Reachable s) (name : String) : startsOf name s.log ≤ 1 := by
  have once : Once s := by
    induction reached with
    | none => intro name; simp [startsOf]
    | hold env s task outside _ ih => exact cfg.hold_once env ih task outside
    | close s cause stop _ ih => exact close_once ih cause stop
  have := once name
  split at this <;> omega

/-- info: 'Contraagent.ServicesConfig.Reachable.started_once' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms ServicesConfig.Reachable.started_once

end Contraagent
