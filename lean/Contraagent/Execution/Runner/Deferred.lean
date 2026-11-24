import Contraagent.Execution.Runner
import Contraagent.Backends.Launch.Own

/-!
# A deferred attempt launched nothing

Of the description of an attempt's walk: an attempt ends deferred only before its first
launch, with every hop it could take passed over and one of them resting on its quota
(`runWithFailover_deferred`). It holds of launches that end with a stop of a launch
(`launchStops`, the members of `Stop` in `backends/launch.py`) or as a partial result: none
of those is `deferred`, which is a task's own.

`deferral`, which the queue asks before it starts a task, says the same as the attempt's
first round would (`choose_deferral`): a task the queue starts after `deferral` gave none
is not deferred by its first round, while the clock, the rests and the breaker stand.
-/

namespace Contraagent

theorem own_stop (result : AttemptResult) (ran : Option (AttemptResult × String)) :
    (own result ran).stop = result.stop ∨ ∃ kept label, ran = some (kept, label) ∧ (own result ran).stop = kept.stop := by
  unfold own
  split
  · rename_i kept label
    split
    · exact Or.inr ⟨kept, label, rfl, rfl⟩
    · exact Or.inl rfl
  · exact Or.inl rfl

/-- No result the walk holds is a deferral: each is a launch's. -/
def Walk.Launching (w : Walk) : Prop :=
  (∀ result, w.last = some result → result.stop ≠ Stop.deferred) ∧
    ∀ result label, w.ran = some (result, label) → result.stop ≠ Stop.deferred

theorem Walk.Launching.own {w : Walk} (launching : w.Launching) (result : AttemptResult)
    (launched : result.stop ≠ Stop.deferred) : (Contraagent.own result w.ran).stop ≠ Stop.deferred := by
  rcases own_stop result w.ran with same | ⟨kept, label, held, same⟩
  · rw [same]; exact launched
  · rw [same]; exact launching.2 kept label held

theorem passedOver_deferred (skipped : List SkippedHop) (deferred : (passedOver skipped).stop = Stop.deferred) :
    quotaRest skipped = true ∧ passedOver skipped = { ok := false, stop := Stop.deferred, skippedHops := skipped } := by
  unfold passedOver at deferred ⊢
  split
  · rename_i quota
    exact ⟨quota, rfl⟩
  · rename_i none
    simp only [none, Bool.false_eq_true, ↓reduceIte] at deferred
    exact absurd deferred (by decide)

namespace RouterConfig

/-- A round that ends the attempt before its launch defers it only before the first launch,
with a quota rest among the hops passed over. -/
theorem choose_deferred (cfg : RouterConfig) (out : HopOutside) (w : Walk) (s s' : RouterState)
    (result : AttemptResult) (launching : w.Launching)
    (ended : cfg.choose out w s = (s', .inl result)) (deferred : result.stop = Stop.deferred) :
    w.last = none ∧ result.hops = [] ∧ quotaRest result.skippedHops = true := by
  unfold choose at ended
  split at ended
  · rename_i last cancelled
    simp only [Prod.mk.injEq, Sum.inl.injEq] at ended
    have held : w.last = some last := by
      split at cancelled
      · exact cancelled
      · cases cancelled
    rw [← ended.2] at deferred
    exact absurd deferred (launching.own last (launching.1 last held))
  · dsimp only at ended
    split at ended
    · simp only [Prod.mk.injEq, Sum.inl.injEq] at ended
      rw [← ended.2] at deferred
      exact absurd deferred (show ("rate_limited" : String) ≠ Stop.deferred by decide)
    · split at ended
      · rename_i skipped _
        simp only [Prod.mk.injEq, Sum.inl.injEq] at ended
        cases last : w.last with
        | none =>
          rw [last] at ended
          dsimp only at ended
          rw [← ended.2] at deferred ⊢
          obtain ⟨quota, is⟩ := passedOver_deferred skipped deferred
          rw [is]
          exact ⟨rfl, rfl, quota⟩
        | some held =>
          rw [last] at ended
          dsimp only at ended
          rw [← ended.2] at deferred
          exact absurd deferred (launching.own { held with skippedHops := skipped } (launching.1 held last))
      · cases ended

/-- A round that goes on to its launch holds the results it held. -/
theorem choose_launching (cfg : RouterConfig) (out : HopOutside) (w w' : Walk) (route : Route)
    (s s' : RouterState) (launching : w.Launching) (chosen : cfg.choose out w s = (s', .inr (w', route))) :
    w'.Launching := by
  unfold choose at chosen
  split at chosen
  · cases chosen
  · dsimp only at chosen
    split at chosen
    · cases chosen
    · split at chosen
      · cases chosen
      · simp only [Prod.mk.injEq, Sum.inr.injEq] at chosen
        rw [← chosen.2.1]
        exact launching

theorem launchedOn_launching (w : Walk) (label : String) (launched : Launched) (launching : w.Launching)
    (stop : launched.stop ≠ Stop.deferred) : (w.launchedOn label launched).Launching := by
  refine ⟨?_, ?_⟩
  · intro result held
    simp only [Walk.launchedOn, Option.some.injEq] at held
    rw [← held]
    exact stop
  · intro result at_ held
    simp only [Walk.launchedOn] at held
    split at held
    · exact launching.2 result at_ held
    · simp only [Option.some.injEq, Prod.mk.injEq] at held
      rw [← held.1]
      exact stop

theorem ended_stop (w : Walk) (label : String) (launching : w.Launching) :
    (w.ended label).stop ≠ Stop.deferred := by
  unfold Walk.ended
  split
  · rename_i result held
    exact launching.1 result held
  · exact (by decide : ("error" : String) ≠ Stop.deferred)

/-- A round does not defer the attempt after its launch. -/
theorem landed_ended (cfg : RouterConfig) (out : HopOutside) (w : Walk) (route : Route)
    (s s' : RouterState) (result : AttemptResult) (launching : w.Launching)
    (stop : (out.launch route).stop ≠ Stop.deferred) (went : cfg.landed out w route s = (s', .inl result)) :
    result.stop ≠ Stop.deferred := by
  have after := launchedOn_launching w (cfg.labelOf route) (out.launch route) launching stop
  unfold landed at went
  dsimp only at went
  by_cases moves : cfg.movesOn route (out.launch route) = true
  · simp only [moves, ↓reduceIte] at went
    cases onward : cfg.nextRouteAfter route (out.launch route).movesAs with
    | none =>
      simp only [onward, Prod.mk.injEq, Sum.inl.injEq] at went
      rw [← went.2]
      exact after.own _ (ended_stop _ _ after)
    | some next => simp [onward] at went
  · simp only [moves, Bool.false_eq_true, ↓reduceIte] at went
    by_cases limited : ((out.launch route).stop != "rate_limited") = true
    · simp only [limited, ↓reduceIte, Prod.mk.injEq, Sum.inl.injEq] at went
      rw [← went.2]
      exact ended_stop _ _ after
    · simp only [limited, Bool.false_eq_true, ↓reduceIte] at went
      have same : (w.launchedOn (cfg.labelOf route) (out.launch route)).pinned = w.pinned := rfl
      cases own : w.pinned with
      | some hop =>
        simp only [same, own] at went
        cases onward : cfg.nextRouteAfter route "rate_limited" with
        | none =>
          simp only [onward, Prod.mk.injEq, Sum.inl.injEq] at went
          rw [← went.2]
          exact Walk.Launching.own (w := w.launchedOn (cfg.labelOf route) (out.launch route)) after _
            (ended_stop _ _ (show Walk.Launching _ from after))
        | some next => simp [onward] at went
      | none =>
        simp only [same, own] at went
        split at went
        · simp only [Prod.mk.injEq, Sum.inl.injEq] at went
          rw [← went.2]
          exact ended_stop _ _ (show Walk.Launching _ from after)
        · simp at went

/-- A round that goes on after its launch holds launches' results only, and one at least. -/
theorem landed_launching (cfg : RouterConfig) (out : HopOutside) (w w' : Walk) (route : Route)
    (s s' : RouterState) (launching : w.Launching) (stop : (out.launch route).stop ≠ Stop.deferred)
    (went : cfg.landed out w route s = (s', .inr w')) : w'.Launching ∧ w'.last ≠ none := by
  have after := launchedOn_launching w (cfg.labelOf route) (out.launch route) launching stop
  have some : (w.launchedOn (cfg.labelOf route) (out.launch route)).last ≠ none := by simp [Walk.launchedOn]
  unfold landed at went
  dsimp only at went
  by_cases moves : cfg.movesOn route (out.launch route) = true
  · simp only [moves, ↓reduceIte] at went
    cases onward : cfg.nextRouteAfter route (out.launch route).movesAs with
    | none => simp [onward] at went
    | some next =>
      simp only [onward, Prod.mk.injEq, Sum.inr.injEq] at went
      rw [← went.2]
      exact ⟨after, some⟩
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
          rw [← went.2]
          exact ⟨after, some⟩
      | none =>
        simp only [same, own] at went
        split at went
        · simp at went
        · simp only [Prod.mk.injEq, Sum.inr.injEq] at went
          rw [← went.2]
          exact ⟨after, some⟩

/-- A walk that holds launches' results only ends deferred only before its first launch. -/
theorem walk_deferred (cfg : RouterConfig) (outside : Nat → HopOutside)
    (stops : ∀ round route, ((outside round).launch route).stop ≠ Stop.deferred) :
    ∀ (fuel : Nat) (w : Walk) (s s' : RouterState) (result : AttemptResult), w.Launching →
      cfg.walk outside fuel w s = (s', some result) → result.stop = Stop.deferred →
      w.last = none ∧ result.hops = [] ∧ quotaRest result.skippedHops = true := by
  intro fuel
  induction fuel with
  | zero => intro w s s' result _ ended; simp [walk] at ended
  | succ fuel ih =>
    intro w s s' result launching ended deferred
    unfold walk at ended
    dsimp only at ended
    split at ended
    · rename_i s₁ early chosen
      simp only [Prod.mk.injEq, Option.some.injEq] at ended
      rw [← ended.2] at deferred ⊢
      exact cfg.choose_deferred _ w s s₁ early launching chosen deferred
    · rename_i s₁ w₁ route chosen
      have launching₁ := cfg.choose_launching _ w w₁ route s s₁ launching chosen
      split at ended
      · rename_i s₂ late went
        simp only [Prod.mk.injEq, Option.some.injEq] at ended
        rw [← ended.2] at deferred
        exact absurd deferred (cfg.landed_ended _ w₁ route s₁ s₂ late launching₁ (stops _ route) went)
      · rename_i s₂ w₂ went
        obtain ⟨launching₂, ran⟩ := cfg.landed_launching _ w₁ w₂ route s₁ s₂ launching₁ (stops _ route) went
        exact absurd (ih w₂ s₂ s' result launching₂ ended deferred).1 ran

/-- The stops the result of one launch on one hop has (`_run_as`): the launch's own, or
`partial` for a launch stopped for its time whose outputs passed every check. -/
def hopStops : List Stop :=
  Stop.partial :: launchStops

theorem hopStops_not_deferred {stop : Stop} (launched : stop ∈ hopStops) : stop ≠ Stop.deferred := by
  rcases List.mem_cons.mp launched with eq | launch
  · rw [eq]; decide
  · exact launchStops_not_deferred launch

/-- An attempt ends deferred only when it launched nothing: it passed over every hop it
could take, and one of them rests on its quota. Each launch ends with a stop of a launch,
or as a partial result (`hopStops`). -/
theorem runWithFailover_deferred (cfg : RouterConfig) (outside : Nat → HopOutside) (s s' : RouterState)
    (result : AttemptResult) (launches : ∀ round route, ((outside round).launch route).stop ∈ hopStops)
    (ended : cfg.runWithFailover outside s = (s', some result)) (deferred : result.stop = Stop.deferred) :
    result.hops = [] ∧ quotaRest result.skippedHops = true := by
  have stops : ∀ round route, ((outside round).launch route).stop ≠ Stop.deferred :=
    fun round route => hopStops_not_deferred (launches round route)
  have launching : ({} : Walk).Launching := by
    refine ⟨?_, ?_⟩
    · intro held is; cases is
    · intro held label is; cases is
  exact (cfg.walk_deferred outside stops cfg.rounds {} s s' result launching ended deferred).2

/-- A look and a pick give the same route. -/
theorem pick_route (cfg : RouterConfig) (now : Time) (s : RouterState) :
    (cfg.pick now true s).2 = (cfg.pick now false s).2 := by
  unfold pick
  repeat' split
  all_goals rfl

/-- What the first round of an attempt does before its launch, by what `deferral` says for
the same clock, rests and breaker: deferred with the same hops passed over when it gives
them, and not deferred when it gives none. -/
theorem choose_deferral (cfg : RouterConfig) (out : HopOutside) (s : RouterState) :
    match cfg.deferral out.now out.rest s with
    | some skipped => (cfg.choose out {} s).2 = .inl { ok := false, stop := Stop.deferred, skippedHops := skipped }
    | none => ∀ result, (cfg.choose out {} s).2 = .inl result → result.stop ≠ Stop.deferred := by
  have same := cfg.pick_route out.now s
  unfold deferral choose
  cases picked : cfg.pick out.now true s with
  | mk s₁ route =>
    rw [picked] at same
    dsimp only at same
    rw [← same]
    have first : (if out.cancelled = true then ({} : Walk).last else none) = none := by
      split <;> rfl
    simp only [first]
    cases route with
    | none =>
      dsimp only
      intro result is
      simp only [Sum.inl.injEq] at is
      rw [← is]
      exact (by decide : ("rate_limited" : String) ≠ Stop.deferred)
    | some route =>
      dsimp only
      cases reach : cfg.usable out.rest "" cfg.routes.length route [] with
      | mk found skipped =>
        cases found with
        | some hop => dsimp only; intro result is; cases is
        | none =>
          dsimp only
          by_cases quota : quotaRest skipped = true
          · simp only [quota, ↓reduceIte, passedOver]
          · simp only [quota, Bool.false_eq_true, ↓reduceIte]
            intro result is
            simp only [passedOver, quota, Bool.false_eq_true, ↓reduceIte, Sum.inl.injEq] at is
            rw [← is]
            exact (by decide : ("auth_failed" : String) ≠ Stop.deferred)

/-- info: 'Contraagent.RouterConfig.runWithFailover_deferred' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms runWithFailover_deferred

end RouterConfig

end Contraagent
