import Contraagent.Routing.Quota

/-!
# What rests a credential, and for how long

Of the description of `CredentialRests`: a credential that was refused on a coding agent
and a model rests there in every state the run reaches after (`Steps.refused_rests`); a
rest the quota rule gave an end holds to that end, whatever the readings and the rule say
meanwhile (`judge_ruled`); and a credential with no reading does not rest on its quota
(`memberRest_unread`).
-/

namespace Contraagent

theorem lookup_of_any {κ α : Type} [BEq κ] [LawfulBEq κ] (entries : List (κ × α)) (key : κ)
    (held : entries.any (·.1 == key) = true) : ∃ value, entries.lookup key = some value := by
  induction entries with
  | nil => simp at held
  | cons entry rest ih =>
    obtain ⟨k, v⟩ := entry
    rw [List.lookup_cons]
    cases same : key == k with
    | true => exact ⟨v, rfl⟩
    | false =>
      simp only [List.any_cons, Bool.or_eq_true] at held
      rcases held with first | later
      · have is : k = key := by simpa using first
        rw [is] at same
        simp at same
      · exact ih later

theorem lookup_of_not_any {κ α : Type} [BEq κ] [LawfulBEq κ] (entries : List (κ × α)) (key : κ)
    (absent : entries.any (·.1 == key) = false) : entries.lookup key = none := by
  induction entries with
  | nil => rfl
  | cons entry rest ih =>
    obtain ⟨k, v⟩ := entry
    simp only [List.any_cons, Bool.or_eq_false_iff] at absent
    rw [List.lookup_cons]
    cases same : key == k with
    | true =>
      have is : key = k := by simpa using same
      rw [is] at absent
      simp at absent
    | false => exact ih absent.2

namespace RestsConfig

/-- Judging a credential leaves the refused credentials as they are. -/
theorem judge_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (key : RestKey) :
    (cfg.judge env now clock s name pool key).1.refused = s.refused := by
  unfold judge
  dsimp only
  repeat' split
  all_goals rfl

theorem memberRest_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (kind agent model : String) :
    (cfg.memberRest env now clock s name pool kind agent model).1.refused = s.refused := by
  unfold memberRest
  split
  · rfl
  · dsimp only
    generalize (if (s.latest.any fun entry => entry.1.1 == name) = true then env.account name else "") = account
    have kept := cfg.judge_refused env now clock s name pool (name, account)
    repeat' split
    all_goals exact kept

theorem memberRests_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time)
    (pool kind agent model : String) (members : List String) :
    ∀ s : RestsState, (cfg.memberRests env now clock pool kind agent model s members).1.refused = s.refused := by
  induction members with
  | nil => intro s; rfl
  | cons member others ih =>
    intro s
    unfold memberRests
    dsimp only
    rw [ih, memberRest_refused]

/-- Asking why a credential rests leaves the refused credentials as they are. -/
theorem rests_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name kind agent model : String) :
    (cfg.rests env now clock s name kind agent model).1.refused = s.refused := by
  unfold rests
  split
  · exact cfg.memberRests_refused env now clock name kind agent model _ s
  · exact cfg.memberRest_refused env now clock s name none kind agent model

theorem restingMembers_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (pool kind agent model : String) :
    (cfg.restingMembers env now clock s pool kind agent model).1.refused = s.refused := by
  unfold restingMembers
  split
  · exact cfg.memberRests_refused env now clock pool kind agent model _ s
  · rfl

/-- A credential that is refused on a coding agent and a model rests there, for a task of
any kind: a finishing kind has no grace window on it. -/
theorem memberRest_of_refused (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (kind agent model : String) (rest : Rest)
    (refused : s.refused.lookup (name, agent, model) = some rest) :
    (cfg.memberRest env now clock s name pool kind agent model).2 = some rest := by
  unfold memberRest
  rw [refused]

/-- A rest the quota rule gave an end holds to that end: the credential rests by it,
whatever its readings and the rule say meanwhile. -/
theorem judge_ruled (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (key : RestKey) (rest : Rest) («end» : Time)
    (ruled : s.ruled.lookup key = some (rest, «end»)) (before : now < «end») :
    (cfg.judge env now clock s name pool key).2.1 = some rest := by
  have held : (s.ruled.lookup key).filter (fun entry => decide (now < entry.2)) = some (rest, «end») := by
    rw [ruled]
    simp [Option.filter, before]
  unfold judge
  dsimp only
  simp only [held, Option.isSome_some, ↓reduceIte]
  split <;> rfl

theorem latestOf_unread (s : RestsState) (name account : String)
    (unread : s.latest.any (·.1.1 == name) = false) : s.latestOf name account = none := by
  have none : (s.latest.filter fun entry =>
      entry.1.1 == name && (account.isEmpty || entry.1.2 == account || entry.1.2.isEmpty)) = [] := by
    rw [List.filter_eq_nil_iff]
    intro entry held
    have differs := List.any_eq_false.mp unread entry held
    simp only [Bool.not_eq_true] at differs
    simp [differs]
  unfold RestsState.latestOf
  dsimp only
  rw [none]
  rfl

theorem judge_unread (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (key : RestKey) (reading : s.latestOf name key.2 = none)
    (unruled : s.ruled.lookup key = none) : (cfg.judge env now clock s name pool key).2.1 = none := by
  unfold judge
  simp only [reading, unruled, Option.filter_none, Option.isSome_none, Bool.false_eq_true, ↓reduceIte]
  split <;> rfl

/-- A credential with no reading, no rest of the rule in force and no refused launch does
not rest: only its 429s and its budgets stop it. -/
theorem memberRest_unread (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name : String) (pool : Option String) (kind agent model : String)
    (unread : s.latest.any (·.1.1 == name) = false) (unruled : s.ruled.lookup (name, "") = none)
    (launched : s.refused.lookup (name, agent, model) = none) :
    (cfg.memberRest env now clock s name pool kind agent model).2 = none := by
  have judged := cfg.judge_unread env now clock s name pool (name, "") (latestOf_unread s name "" unread) unruled
  unfold memberRest
  rw [launched]
  simp only [unread, Bool.false_eq_true, ↓reduceIte]
  cases result : cfg.judge env now clock s name pool (name, "") with
  | mk after pair =>
    cases pair with
    | mk rest first =>
      rw [result] at judged
      dsimp only at judged
      subst judged
      rfl

end RestsConfig

/-- What a run does to its rests, one step: a reading observed, a launch refused, or a
question, at any time and whatever the rule and the accounts answer. -/
inductive RestsConfig.Step (cfg : RestsConfig) : RestsState → RestsState → Prop
  | observe (s : RestsState) (reading : QuotaReading) : cfg.Step s (s.observe reading)
  | refuse (s : RestsState) (name agent model : String) : cfg.Step s (s.refuse name agent model)
  | rests (env : RestsEnv) (now clock : Time) (s : RestsState) (name kind agent model : String) :
    cfg.Step s (cfg.rests env now clock s name kind agent model).1
  | restingMembers (env : RestsEnv) (now clock : Time) (s : RestsState) (pool kind agent model : String) :
    cfg.Step s (cfg.restingMembers env now clock s pool kind agent model).1

/-- The states a run's rests reach from a state. -/
inductive RestsConfig.Steps (cfg : RestsConfig) : RestsState → RestsState → Prop
  | here (s : RestsState) : cfg.Steps s s
  | more (s between later : RestsState) : cfg.Steps s between → cfg.Step between later → cfg.Steps s later

namespace RestsConfig

theorem Step.refused_kept {cfg : RestsConfig} {s later : RestsState} (step : cfg.Step s later)
    (key : String × String × String) (rest : Rest) (refused : s.refused.lookup key = some rest) :
    later.refused.lookup key = some rest := by
  cases step with
  | observe s reading =>
    have same : (s.observe reading).refused = s.refused := by
      unfold RestsState.observe
      split
      · rfl
      · dsimp only
        repeat' split
        all_goals rfl
    rw [same]; exact refused
  | refuse s name agent model =>
    unfold RestsState.refuse
    split
    · exact refused
    · dsimp only
      rw [List.lookup_append, refused]
      rfl
  | rests env now clock s name kind agent model => rw [rests_refused]; exact refused
  | restingMembers env now clock s pool kind agent model => rw [restingMembers_refused]; exact refused

/-- A launch as a credential that was refused on a coding agent and a model rests the
credential there for the rest of the run: in every state the run reaches after, a task of
any kind is told so, whatever the readings, the rule and the time. -/
theorem Steps.refused_rests {cfg : RestsConfig} (s later : RestsState) (name agent model : String)
    (reached : cfg.Steps (s.refuse name agent model) later) (env : RestsEnv) (now clock : Time)
    (pool : Option String) (kind : String) :
    ∃ rest, (cfg.memberRest env now clock later name pool kind agent model).2 = some rest := by
  have began : ∃ rest, (s.refuse name agent model).refused.lookup (name, agent, model) = some rest := by
    unfold RestsState.refuse
    split
    · rename_i held
      exact lookup_of_any _ _ held
    · rename_i fresh
      dsimp only
      rw [List.lookup_append]
      rw [lookup_of_not_any _ _ ((Bool.not_eq_true _).mp fresh)]
      simp
  obtain ⟨rest, held⟩ := began
  have kept : later.refused.lookup (name, agent, model) = some rest := by
    induction reached with
    | here => exact held
    | more between later _ step ih => exact step.refused_kept _ rest ih
  exact ⟨rest, cfg.memberRest_of_refused env now clock later name pool kind agent model rest kept⟩

/-- info: 'Contraagent.RestsConfig.Steps.refused_rests' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Steps.refused_rests

end RestsConfig

end Contraagent
