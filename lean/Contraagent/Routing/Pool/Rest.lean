import Contraagent.Routing.Pool

/-!
# A member that answered 429 rests

Of the description of `CredentialPool`: a member is not picked for a model while it cools
down on it, and a member that answered 429 cools down for the time it was given.
-/

namespace Contraagent.PoolConfig

/-- The member a pick gives does not cool down on the model and is not excluded. -/
theorem pick_rested (cfg : PoolConfig) (now : Time) (s : PoolState) (model : String)
    (exclude : List String) (member : String) (picked : (cfg.pick now s model exclude).2 = some member) :
    cooling now s member model = false ∧ member ∉ exclude := by
  unfold pick at picked
  dsimp only at picked
  split at picked
  · cases picked
  · rename_i place found
    have holds := List.find?_some found
    dsimp only at picked
    rw [picked] at holds
    simp at holds
    exact ⟨holds.2, holds.1⟩

/-- A member that answered 429 on a model cools down on it until its wait has passed. -/
theorem rateLimited_cooling (cfg : PoolConfig) (now later : Time) (s : PoolState) (member model : String)
    (retryAfterS : Option Duration) (within : later < now + cfg.waitFor retryAfterS) :
    cooling later (cfg.rateLimited now s member model retryAfterS) member model = true := by
  unfold rateLimited cooling
  simp [List.lookup]
  exact within

/-- So a pick for that model within the wait gives another member, or none. -/
theorem pick_after_rateLimited (cfg : PoolConfig) (now later : Time) (s : PoolState) (member model : String)
    (retryAfterS : Option Duration) (exclude : List String)
    (within : later < now + cfg.waitFor retryAfterS) :
    (cfg.pick later (cfg.rateLimited now s member model retryAfterS) model exclude).2 ≠ some member := by
  intro picked
  have rested := (pick_rested cfg later _ model exclude member picked).1
  rw [rateLimited_cooling cfg now later s member model retryAfterS within] at rested
  cases rested

/-- info: 'Contraagent.PoolConfig.pick_after_rateLimited' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms pick_after_rateLimited

end Contraagent.PoolConfig
