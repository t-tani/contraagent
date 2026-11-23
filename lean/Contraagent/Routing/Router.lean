import Contraagent.Dispatch.Task

/-!
# The failover breaker

What `Router` of `src/contraagent/_internal/routing/router.py` decides: which route the
next task runs on, how a 429 moves the breaker along the chain, when one task probes the
primary again, and what closes the breaker.

A function here is one method of the code and takes the clock's reading (`now`). Left out:
the lock (each function is one critical section of the code), a chain's parsing from the
config, and the routes that one coding agent's own failover flag takes
(`same_agent_after`, `other_agents_after`).
-/

namespace Contraagent

/-- One (coding agent, model, credential) a run may use (`Route`). `stops`: the stops of an
earlier hop's launch that a failover hop is for; empty, every one. -/
structure Route where
  agent : String
  model : String
  credential : String := ""
  stops : List String := []
  deriving Repr

namespace Route

/-- Two routes with the same identity are one hop. -/
def identity (r : Route) : String × String × String :=
  (r.agent, r.model, r.credential)

/-- Whether a task whose launch ended on `stop` may fail over to this hop. -/
def takes (r : Route) (stop : String) : Bool :=
  r.stops.isEmpty || r.stops.contains stop

/-- The route as a log line names it (`__str__`). -/
def name (r : Route) : String :=
  let base := if r.model.isEmpty then r.agent else r.agent ++ "/" ++ r.model
  if r.credential == "" || r.credential == "ambient" then base else base ++ "@" ++ r.credential

end Route

/-- What a `Router` is built with. `routes`: the primary first, then the fallbacks. -/
structure RouterConfig where
  routes : List Route
  probeIntervalS : Duration := 900
  maxProbeIntervalS : Duration := 7200
  deriving Repr

/-- The chain of a router built from a primary and its fallbacks: a fallback with the
primary's identity is no hop of its own. -/
def chainOf (primary : Route) (fallbacks : List Route) : List Route :=
  primary :: fallbacks.filter (·.identity != primary.identity)

/-- The breaker's record. `index`: the hop in force. `probeAt`: when the next probe of the
primary is due. `interval`: the cool-off before a probe, which a failed probe doubles.
`openedAt`: when the breaker last moved off a hop (`none`: never). `probing`: when the
probe on the primary was picked (`none`: no probe is out). `switches`: each move, as the
labels of the two hops, the latest last. -/
structure RouterState where
  index : Nat := 0
  probeAt : Time := 0
  interval : Duration
  exhausted : Bool := false
  openedAt : Option Time := none
  probing : Option Time := none
  switches : List (String × String) := []
  deriving Repr

namespace RouterConfig

/-- The breaker as a new router has it: closed, on the primary. -/
def start (cfg : RouterConfig) : RouterState :=
  { interval := cfg.probeIntervalS }

/-- The place of a route in the chain, by its identity (`_index_of`). -/
def indexOf (cfg : RouterConfig) (route : Route) : Option Nat :=
  cfg.routes.findIdx? (·.identity == route.identity)

/-- `hop 2/3 omp/m2`: the form every log and journal line uses (`label_of`); empty for a
place the chain does not have. -/
def label (cfg : RouterConfig) (index : Nat) : String :=
  match cfg.routes[index]? with
  | some r => s!"hop {index + 1}/{cfg.routes.length} {r.name}"
  | none => ""

/-- The first hop after `route` in chain order that is for `stop` (any hop with no `stop`);
`none` when there is none, or the chain does not have `route` (`next_route_after`). -/
def nextRouteAfter (cfg : RouterConfig) (route : Route) (stop : String) : Option Route :=
  match cfg.indexOf route with
  | none => none
  | some idx => (cfg.routes.drop (idx + 1)).find? fun r => stop.isEmpty || r.takes stop

/-- The route in force, ignoring any due probe (`active`). -/
def active (cfg : RouterConfig) (s : RouterState) : Option Route :=
  if s.exhausted then none else cfg.routes[s.index]?

/-- The route the next task runs on (`pick`), `none` when the chain is exhausted. While
the breaker is open and the cool-off has passed, it is the primary: with `probe`, that
task is the probe, and the tasks picked a route before its verdict, or before another
cool-off, get the hop in force. Without `probe` it only looks. -/
def pick (cfg : RouterConfig) (now : Time) (probe : Bool) (s : RouterState) :
    RouterState × Option Route :=
  if s.exhausted then (s, none)
  else if s.index = 0 then (s, cfg.routes[0]?)
  else if now ≥ s.probeAt then
    (if probe then { s with probing := some now, probeAt := now + s.interval } else s, cfg.routes[0]?)
  else (s, cfg.routes[s.index]?)

/-- The cool-off before the next probe (`_next_interval`): double the last, between the
configured interval and the longest one; the provider's own number when it is longer, up to
the longest one. -/
def nextInterval (cfg : RouterConfig) (retryAfterS : Option Duration) (s : RouterState) :
    RouterState × Duration :=
  let base := min (max (s.interval * 2) cfg.probeIntervalS) cfg.maxProbeIntervalS
  let s := { s with interval := base }
  match retryAfterS with
  | some given => if given = 0 then (s, base) else (s, max base (min given cfg.maxProbeIntervalS))
  | none => (s, base)

/-- A 429 on `route` (`rate_limited`), with what the next task is told: the label of the
hop in force, or nothing when the chain is exhausted. `route` `none` stands for the hop
in force. `started`: when the launch began.

While the breaker is open, a 429 on the primary is the probe's: the breaker holds its hop
and the next probe waits longer. It changes nothing when the launch is known to be no
probe: it began before the probe was picked, or no probe is out. A 429 on the hop in force
moves the breaker to the next hop for a rate limit, or exhausts the chain. A 429 on any
other hop of the chain changes nothing. -/
def rateLimited (cfg : RouterConfig) (now : Time) (s : RouterState) (route : Option Route)
    (retryAfterS : Option Duration) (started : Option Time) : RouterState × String :=
  let idx := match route with
    | none => some s.index
    | some r => cfg.indexOf r
  if s.exhausted then (s, "")
  else if idx = some 0 ∧ s.index ≠ 0 then
    let noProbe := match started with
      | none => false
      | some began =>
        match s.probing with
        | none => true
        | some picked => decide (began < picked)
    if noProbe then (s, cfg.label s.index)
    else
      let (s, wait) := cfg.nextInterval retryAfterS s
      ({ s with probing := none, probeAt := now + wait }, ((cfg.routes[s.index]?).map (·.name)).getD "")
  else if idx.isSome ∧ idx ≠ some s.index then (s, cfg.label s.index)
  else
    match (List.range cfg.routes.length).find? fun i =>
        decide (i > s.index) && ((cfg.routes[i]?).map (·.takes "rate_limited")).getD false with
    | none => ({ s with exhausted := true }, "")
    | some next =>
      ({ s with
          index := next
          openedAt := some now
          probing := none
          interval := cfg.probeIntervalS
          probeAt := now + cfg.probeIntervalS
          switches := s.switches ++ [(cfg.label s.index, cfg.label next)] },
        cfg.label next)

/-- A launch landed on `route` (`succeeded`). One that began before the breaker last
opened says nothing of the limit since, and changes nothing. On the primary while the
breaker is open, it closes the breaker; while it is closed, the cool-off starts short
again. -/
def succeeded (cfg : RouterConfig) (s : RouterState) (route : Option Route) (started : Option Time) :
    RouterState :=
  let before := match started, s.openedAt with
    | some began, some opened => decide (began < opened)
    | _, _ => false
  let onPrimary := match route with
    | some r => cfg.indexOf r == some 0
    | none => false
  if before then s
  else if onPrimary ∧ s.index ≠ 0 then
    { s with
      index := 0
      probing := none
      interval := cfg.probeIntervalS
      probeAt := 0
      switches := s.switches ++ [(cfg.label s.index, cfg.label 0 ++ " (primary recovered)")] }
  else if s.index = 0 then { s with interval := cfg.probeIntervalS, probeAt := 0 }
  else s

end RouterConfig

end Contraagent
