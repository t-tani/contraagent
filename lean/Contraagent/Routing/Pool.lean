import Contraagent.Dispatch.Task

/-!
# Credential pools

What `CredentialPool` of `src/contraagent/_internal/routing/pool.py` decides: which member
of a pool the next launch uses, and which members rest after a 429.

A function here is one method of the code and takes the clock's reading (`now`). Left out:
the lock, and the text of `describe`.
-/

namespace Contraagent

/-- What a pool is built with (`Pool`): its members' names in order, whether each launch
turns to the next member (`round_robin`) or uses the first that does not cool down
(`in_order`), and how long a member cools down when the provider states no time. -/
structure PoolConfig where
  members : List String
  roundRobin : Bool := false
  cooldownS : Duration := 900
  deriving Repr

/-- A pool's record for one run: the member a round robin starts from, and until when each
member cools down on each model. -/
structure PoolState where
  next : Nat := 0
  coolingUntil : List ((String × String) × Time) := []
  deriving Repr

namespace PoolConfig

/-- Whether a member cools down on a model now. -/
def cooling (now : Time) (s : PoolState) (member model : String) : Bool :=
  match s.coolingUntil.lookup (member, model) with
  | some till => decide (till > now)
  | none => false

/-- The member the next launch of `model` uses (`pick`), `none` when every one cools down
or is excluded: the first that neither cools down on the model nor is excluded, from the
first member, or in a round robin from the member after the one picked last. -/
def pick (cfg : PoolConfig) (now : Time) (s : PoolState) (model : String) (exclude : List String) :
    PoolState × Option String :=
  let n := cfg.members.length
  let start := if cfg.roundRobin then s.next else 0
  let places := (List.range n).map fun i => (start + i) % n
  match places.find? fun place =>
      match cfg.members[place]? with
      | some member => ! exclude.contains member && ! cooling now s member model
      | none => false with
  | none => (s, none)
  | some place =>
    (if cfg.roundRobin then { s with next := (place + 1) % n } else s, cfg.members[place]?)

/-- How long a member cools down after a 429: the provider's stated time, or the pool's
own when the provider states none. -/
def waitFor (cfg : PoolConfig) (retryAfterS : Option Duration) : Duration :=
  match retryAfterS with
  | some stated => if stated = 0 then cfg.cooldownS else stated
  | none => cfg.cooldownS

/-- A member answered 429 on a model (`rate_limited`): it cools down on that model
(`waitFor`). -/
def rateLimited (cfg : PoolConfig) (now : Time) (s : PoolState) (member model : String)
    (retryAfterS : Option Duration) : PoolState :=
  { s with coolingUntil :=
      ((member, model), now + cfg.waitFor retryAfterS) :: s.coolingUntil.filter (·.1 != (member, model)) }

end PoolConfig

end Contraagent
