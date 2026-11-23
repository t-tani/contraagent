import Contraagent.Routing.Router

/-!
# What moves the breaker

Of the description of `Router`: only the probe and the hop in force move the breaker, one
task probes in a cool-off, and an exhausted chain stays exhausted.
-/

namespace Contraagent.RouterConfig

/-- While the breaker is open, a 429 on the primary of a launch that is no probe changes
nothing: one that began before the probe was picked, or while no probe is out. -/
theorem rateLimited_no_probe (cfg : RouterConfig) (now : Time) (s : RouterState) (route : Route)
    (retryAfterS : Option Duration) (began : Time)
    (primary : cfg.indexOf route = some 0) (isOpen : s.index ≠ 0)
    (noProbe : s.probing = none ∨ ∃ picked, s.probing = some picked ∧ began < picked) :
    (cfg.rateLimited now s (some route) retryAfterS (some began)).1 = s := by
  unfold rateLimited
  simp only [primary]
  split
  · rfl
  · rcases noProbe with none | ⟨picked, some, before⟩
    · simp [isOpen, none]
    · simp [isOpen, some, before]

/-- A 429 on a hop of the chain that is neither the hop in force nor the primary changes
nothing: a hop the breaker left, or one a task reached on its own walk. -/
theorem rateLimited_other_hop (cfg : RouterConfig) (now : Time) (s : RouterState) (route : Route)
    (retryAfterS : Option Duration) (started : Option Time) (idx : Nat)
    (place : cfg.indexOf route = some idx) (other : idx ≠ s.index) (fallback : idx ≠ 0) :
    (cfg.rateLimited now s (some route) retryAfterS started).1 = s := by
  unfold rateLimited
  simp only [place]
  split
  · rfl
  · simp [fallback, other]

/-- The task picked the primary as the probe starts the cool-off again: until it has
passed, every other task is picked the hop in force, and the breaker stays as it is. -/
theorem pick_after_probe (cfg : RouterConfig) (now later : Time) (s : RouterState)
    (running : s.exhausted = false) (isOpen : s.index ≠ 0) (due : now ≥ s.probeAt)
    (within : later < now + s.interval) :
    cfg.pick later true (cfg.pick now true s).1
      = ((cfg.pick now true s).1, cfg.routes[s.index]?) := by
  have notDue : ¬ later ≥ now + s.interval := Int.not_le.mpr within
  simp [pick, running, isOpen, due, notDue]

/-- A look takes no probe: it leaves the breaker as it is. -/
theorem pick_look (cfg : RouterConfig) (now : Time) (s : RouterState) :
    (cfg.pick now false s).1 = s := by
  unfold pick
  repeat' split
  all_goals first | rfl | contradiction

/-- An exhausted chain gives no route. -/
theorem pick_exhausted (cfg : RouterConfig) (now : Time) (probe : Bool) (s : RouterState)
    (spent : s.exhausted = true) : cfg.pick now probe s = (s, none) := by
  simp [pick, spent]

/-- A 429 leaves an exhausted chain exhausted, and as it is. -/
theorem rateLimited_exhausted (cfg : RouterConfig) (now : Time) (s : RouterState) (route : Option Route)
    (retryAfterS : Option Duration) (started : Option Time) (spent : s.exhausted = true) :
    cfg.rateLimited now s route retryAfterS started = (s, "") := by
  simp [rateLimited, spent]

/-- A launch that lands leaves an exhausted chain exhausted. -/
theorem succeeded_exhausted (cfg : RouterConfig) (s : RouterState) (route : Option Route)
    (started : Option Time) (spent : s.exhausted = true) :
    (cfg.succeeded s route started).exhausted = true := by
  unfold succeeded
  dsimp only
  repeat' split
  all_goals exact spent

/-- info: 'Contraagent.RouterConfig.pick_after_probe' depends on axioms: [propext] -/
#guard_msgs in
#print axioms pick_after_probe

end Contraagent.RouterConfig
