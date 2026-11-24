import Contraagent.Execution.Runner

/-!
# An attempt ends

Of the description of an attempt's walk: on a chain with no two hops of one identity, the
walk ends within `rounds` rounds, whatever its launches give and whatever other tasks do to
the breaker (`runWithFailover_ends`). So an attempt launches at most that many times.

The walk's own hop only moves down the chain (`nextRouteAfter_later`), and a task on the
breaker's hops ends after as many 429s as the chain has hops.
-/

namespace Contraagent.RouterConfig

/-- No two hops of the chain have one identity. -/
def Distinct (cfg : RouterConfig) : Prop :=
  cfg.routes.Pairwise fun a b => a.identity ≠ b.identity

/-- The place of a route in the chain; the chain's length for a route of no chain. -/
def place (cfg : RouterConfig) (route : Route) : Nat :=
  (cfg.indexOf route).getD cfg.routes.length

/-- The hop after a hop is further down the chain. -/
theorem nextRouteAfter_later (cfg : RouterConfig) (distinct : cfg.Distinct) (route next : Route)
    (stop : String) (found : cfg.nextRouteAfter route stop = some next) :
    cfg.place route < cfg.place next ∧ cfg.place next < cfg.routes.length := by
  unfold nextRouteAfter at found
  cases at_ : cfg.indexOf route with
  | none => rw [at_] at found; cases found
  | some i =>
    rw [at_] at found
    dsimp only at found
    obtain ⟨k, held⟩ := List.mem_iff_getElem?.mp (List.mem_of_find?_eq_some found)
    rw [List.getElem?_drop] at held
    obtain ⟨within, is⟩ := List.getElem?_eq_some_iff.mp held
    have place_next : cfg.indexOf next = some (i + 1 + k) := by
      unfold indexOf
      rw [List.findIdx?_eq_some_iff_getElem]
      refine ⟨within, by rw [is]; simp, ?_⟩
      intro j before
      have differs := List.pairwise_iff_getElem.mp distinct j (i + 1 + k) (Nat.lt_trans before within) within before
      rw [is] at differs
      simpa using differs
    unfold place
    rw [at_, place_next]
    exact ⟨by simp; omega, by simpa using within⟩

/-- The hop a task can use from a hop is that hop or one further down the chain. -/
theorem usable_later (cfg : RouterConfig) (distinct : cfg.Distinct) (rest : Route → Option RestWhy)
    (stop : String) : ∀ (fuel : Nat) (here : Route) (skipped : List SkippedHop) (found : Route)
      (after : List SkippedHop), cfg.usable rest stop fuel here skipped = (some found, after) →
      found = here ∨ (cfg.place here < cfg.place found ∧ cfg.place found < cfg.routes.length) := by
  intro fuel
  induction fuel with
  | zero => intro here skipped found after h; simp [usable] at h
  | succ fuel ih =>
    intro here skipped found after h
    unfold usable at h
    split at h
    · left
      cases h
      rfl
    · dsimp only at h
      split at h
      · cases h
      · rename_i next onward
        have down := cfg.nextRouteAfter_later distinct here next _ onward
        rcases ih next _ found after h with same | further
        · right; rw [same]; exact down
        · right; exact ⟨Nat.lt_trans down.1 further.1, further.2⟩

/-- The rounds a walk has left at most: on the breaker's hops, the 429s before it ends and
then a walk of its own; on its own walk, the hops below its hop. -/
def left (cfg : RouterConfig) (w : Walk) : Nat :=
  match w.pinned with
  | none => cfg.routes.length + (cfg.routes.length - w.hops)
  | some hop => cfg.routes.length - cfg.place hop

/-- What a walk keeps between rounds: fewer 429s than the chain has hops while it is on
the breaker's hops, and an own hop that is of the chain. -/
def Sound (cfg : RouterConfig) (w : Walk) : Prop :=
  match w.pinned with
  | none => w.hops < cfg.routes.length
  | some hop => cfg.place hop < cfg.routes.length

/-- The route a round launches on is the task's own hop or one below it, and a task with
no hop of its own before the round and after it stayed on the breaker's. -/
theorem choose_launch (cfg : RouterConfig) (distinct : cfg.Distinct) (out : HopOutside) (w w' : Walk)
    (route : Route) (s s' : RouterState) (chosen : cfg.choose out w s = (s', .inr (w', route))) :
    w'.hops = w.hops ∧ (w'.pinned = none → w.pinned = none) ∧
      ∀ hop, w.pinned = some hop → cfg.place hop ≤ cfg.place route := by
  unfold choose at chosen
  split at chosen
  · cases chosen
  · dsimp only at chosen
    split at chosen
    · cases chosen
    · rename_i picked route₀ eq
      split at chosen
      · cases chosen
      · rename_i found skipped usable_eq
        have later := cfg.usable_later distinct _ _ _ _ _ _ _ usable_eq
        simp only [Prod.mk.injEq, Sum.inr.injEq] at chosen
        obtain ⟨_, walk_eq, route_eq⟩ := chosen
        subst route_eq
        subst walk_eq
        refine ⟨rfl, ?_, ?_⟩
        · intro unpinned
          dsimp only at unpinned
          split at unpinned
          · exact unpinned
          · cases unpinned
        · intro hop pinned
          rw [pinned] at eq
          simp only [Option.some.injEq] at eq
          rw [← eq] at later
          rcases later with same | further
          · rw [same]; exact Nat.le_refl _
          · exact Nat.le_of_lt further.1

/-- A round that does not end the attempt moves the task to a hop further down the chain
than the one it launched on, or leaves it on the breaker's hops with one more 429, fewer
than the chain has hops. -/
theorem landed_onward (cfg : RouterConfig) (distinct : cfg.Distinct) (out : HopOutside) (w w' : Walk)
    (route : Route) (s s' : RouterState) (went : cfg.landed out w route s = (s', .inr w')) :
    (∃ next, w'.pinned = some next ∧ cfg.place route < cfg.place next ∧ cfg.place next < cfg.routes.length) ∨
      (w.pinned = none ∧ w'.pinned = none ∧ w'.hops = w.hops + 1 ∧ w'.hops < cfg.routes.length) := by
  unfold landed at went
  dsimp only at went
  by_cases moves : cfg.movesOn route (out.launch route) = true
  · simp only [moves, ↓reduceIte] at went
    cases onward : cfg.nextRouteAfter route (out.launch route).movesAs with
    | none => simp [onward] at went
    | some next =>
      simp only [onward, Prod.mk.injEq, Sum.inr.injEq] at went
      left
      refine ⟨next, ?_, cfg.nextRouteAfter_later distinct route next _ onward⟩
      rw [← went.2]
  · simp only [moves, Bool.false_eq_true, ↓reduceIte] at went
    by_cases limited : ((out.launch route).stop != "rate_limited") = true
    · simp [limited] at went
    · simp only [limited, Bool.false_eq_true, ↓reduceIte] at went
      have same : (w.launchedOn (cfg.labelOf route) (out.launch route)).pinned = w.pinned := rfl
      cases own : w.pinned with
      | some hop =>
        simp only [same, own] at went
        cases onward : cfg.nextRouteAfter route "rate_limited" with
        | none => simp [onward] at went
        | some next =>
          simp only [onward, Prod.mk.injEq, Sum.inr.injEq] at went
          left
          refine ⟨next, ?_, cfg.nextRouteAfter_later distinct route next _ onward⟩
          rw [← went.2]
      | none =>
        simp only [same, own] at went
        split at went
        · simp at went
        · rename_i goes
          simp only [Prod.mk.injEq, Sum.inr.injEq] at went
          right
          simp only [Bool.or_eq_true, decide_eq_true_eq, not_or, Nat.not_le] at goes
          rw [← went.2]
          exact ⟨rfl, rfl, rfl, goes.2⟩

/-- A round that does not end the attempt leaves fewer rounds. -/
theorem round_left (cfg : RouterConfig) (distinct : cfg.Distinct) (out : HopOutside) (w w₁ w₂ : Walk)
    (route : Route) (s s₁ s₂ : RouterState) (sound : cfg.Sound w)
    (chosen : cfg.choose out w s = (s₁, .inr (w₁, route)))
    (went : cfg.landed out w₁ route s₁ = (s₂, .inr w₂)) : cfg.Sound w₂ ∧ cfg.left w₂ < cfg.left w := by
  obtain ⟨hops, stays, below⟩ := cfg.choose_launch distinct out w w₁ route s s₁ chosen
  rcases cfg.landed_onward distinct out w₁ w₂ route s₁ s₂ went with ⟨next, pinned, down, within⟩ | ⟨unpinned, still, more, few⟩
  · unfold Sound left at *
    rw [pinned]
    refine ⟨within, ?_⟩
    cases own : w.pinned with
    | none =>
      rw [own] at sound
      dsimp only at sound ⊢
      omega
    | some hop =>
      have := below hop own
      dsimp only
      omega
  · have before := stays unpinned
    unfold Sound left at *
    rw [still]
    rw [before] at sound ⊢
    dsimp only at sound ⊢
    omega

/-- A walk that keeps `Sound` ends within the rounds it has left. -/
theorem walk_ends (cfg : RouterConfig) (distinct : cfg.Distinct) (outside : Nat → HopOutside) :
    ∀ (fuel : Nat) (w : Walk) (s : RouterState), cfg.Sound w → cfg.left w < fuel →
      ∃ result, (cfg.walk outside fuel w s).2 = some result := by
  intro fuel
  induction fuel with
  | zero => intro w s _ none; cases none
  | succ fuel ih =>
    intro w s sound enough
    unfold walk
    dsimp only
    split
    · exact ⟨_, rfl⟩
    · rename_i s₁ w₁ route chosen
      split
      · exact ⟨_, rfl⟩
      · rename_i s₂ w₂ went
        obtain ⟨sound₂, fewer⟩ := cfg.round_left distinct _ w w₁ w₂ route s s₁ s₂ sound chosen went
        exact ih w₂ s₂ sound₂ (by omega)

/-- On a chain with no two hops of one identity, an attempt ends: its walk gives a result
within `rounds` rounds, whatever its launches give, whichever credentials rest and whatever
other tasks do to the breaker. Each round launches once at most, so an attempt launches at
most `rounds` times. -/
theorem runWithFailover_ends (cfg : RouterConfig) (distinct : cfg.Distinct) (hops : cfg.routes ≠ [])
    (outside : Nat → HopOutside) (s : RouterState) :
    ∃ result, (cfg.runWithFailover outside s).2 = some result := by
  have some : 0 < cfg.routes.length := List.length_pos_iff.mpr hops
  apply cfg.walk_ends distinct
  · exact some
  · show cfg.routes.length + (cfg.routes.length - 0) < 2 * cfg.routes.length + 1
    omega

/-- The chain of a router has no two hops of one identity. -/
theorem chainOf_distinct (primary : Route) (fallbacks : List Route) :
    (chainOf primary fallbacks).Pairwise fun a b => a.identity ≠ b.identity := by
  unfold chainOf
  suffices kept : ∀ (routes chain : List Route), chain.Pairwise (fun a b => a.identity ≠ b.identity) →
      (routes.foldl (fun chain route =>
        if chain.any (·.identity == route.identity) then chain else chain ++ [route]) chain).Pairwise
        fun a b => a.identity ≠ b.identity from kept _ [] List.Pairwise.nil
  intro routes
  induction routes with
  | nil => intro chain distinct; exact distinct
  | cons route rest ih =>
    intro chain distinct
    rw [List.foldl_cons]
    apply ih
    split
    · exact distinct
    · rename_i fresh
      rw [List.pairwise_append]
      refine ⟨distinct, List.pairwise_singleton _ _, ?_⟩
      intro earlier held later is
      rw [List.mem_singleton.mp is]
      intro same
      apply fresh
      rw [List.any_eq_true]
      exact ⟨earlier, held, by simpa using same⟩

/-- info: 'Contraagent.RouterConfig.runWithFailover_ends' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms runWithFailover_ends

end Contraagent.RouterConfig
