import Contraagent.Routing.Router

/-!
# One attempt of an agent task, and the attempts after it

What `AgentRunner` and `RetryingRunner` of `src/contraagent/_internal/execution/runner.py`
decide: the hops an attempt launches on along its kind's failover chain
(`_run_with_failover`), the hops it passes over because their credential rests (`_usable`),
when it is deferred instead (`deferral`, `_passed_over`), which launch's result is the
attempt's (`_own`), and whether a fresh attempt follows (`RetryingRunner.run`).

One round of the code's loop is `choose`, up to the launch, and `landed`, after it. Both
take what the round reads from outside (`HopOutside`): whether the task was cancelled, the
clock, which credentials rest, what the launch gives, and what other tasks did to the
breaker meanwhile. Left out: a task of a kind with no chain, the members of a credential
pool on one hop, the checks before the first hop, the spend, the times and the reasons.
-/

namespace Contraagent

/-- Why the credential of a hop rests (`Rest`): on its quota, which ends, or because a
launch as it was refused (`auth_failed`), for the rest of the run. -/
inductive RestWhy where
  | quota
  | refused
  deriving DecidableEq, Repr

/-- A hop an attempt passed over without a launch (`SkippedHop`): its label, and why its
credential rests. -/
structure SkippedHop where
  route : String
  why : RestWhy
  deriving DecidableEq, Repr

/-- One launch on one route (`Hop`): the route's label and how the launch ended. -/
structure Hop where
  route : String
  stop : String
  deriving DecidableEq, Repr

/-- What one launch on a route gave (`_run_once`), as the walk reads it. `signalled`: a
signal from outside ended it (`_signalled`). `safetyStop`: it ended well with a safety stop
its kind fails over on (`_safety_failover`). `retryAfterS`: the time a 429 stated. -/
structure Launched where
  stop : String
  ok : Bool
  signalled : Bool := false
  safetyStop : Bool := false
  retryAfterS : Option Duration := none
  deriving Repr

/-- The result of an attempt, with the fields of `TaskResult` the walk decides: the label
of the route it ran on, each launch, and each hop passed over. A deferred result has stop
`deferred`, and `skippedHops` are the rests of its cause. -/
structure AttemptResult where
  ok : Bool
  stop : String
  route : String := ""
  hops : List Hop := []
  skippedHops : List SkippedHop := []
  retryable : Bool := true
  deriving DecidableEq, Repr

/-- What one round of the walk reads from outside. `cancelled`: `stop_requested()` as the
round begins. `now`: the clock as the hop is picked and its launch begins. `rest`: why the
credential of a route rests now, `none` when it does not. `launch`: what a launch on a
route gives. `meanwhile`: what other tasks did to the breaker during the launch. `ended`:
the clock after the launch. -/
structure HopOutside where
  cancelled : Bool := false
  now : Time
  rest : Route → Option RestWhy := fun _ => none
  launch : Route → Launched
  meanwhile : RouterState → RouterState := id
  ended : Time

/-- An attempt's own record of its walk (the locals of `_run_with_failover`). `hops`: its
429s. `pinned`: the hop of its own walk, after a failure other than a 429 or a hop passed
over. `walk`: the stop that moved it to `pinned`. `trail`: its launches. `skipped`: the
hops it passed over. `last`: the result of its last launch. `ran`: the result and the
label of the last launch that was not refused for its credential. -/
structure Walk where
  hops : Nat := 0
  pinned : Option Route := none
  walk : String := ""
  trail : List Hop := []
  skipped : List SkippedHop := []
  last : Option AttemptResult := none
  ran : Option (AttemptResult × String) := none

/-- The stops after which another hop cannot help (`NO_FAILOVER`). -/
def noFailover : List String := ["invalid_input", "credential_mismatch"]

/-- The stops after which no fresh attempt follows (`NOT_RETRIED`). -/
def notRetried : List String := ["refused", "invalid_input", "auth_failed", Stop.cancelled]

/-- The stop a resting hop passes a task on as (`_rest_stop`). -/
def RestWhy.stop : RestWhy → String
  | .quota => "rate_limited"
  | .refused => "auth_failed"

/-- Whether one of the hops passed over rests on its quota (`_quota_rest`). -/
def quotaRest (skipped : List SkippedHop) : Bool :=
  skipped.any (·.why == .quota)

/-- A failed launch moves its task to the next hop, unless another hop cannot fix it or a
signal from outside ended it (`_fails_over`). -/
def Launched.failsOver (launched : Launched) : Bool :=
  !launched.ok && !noFailover.contains launched.stop && !launched.signalled

/-- The stop a launch moves its task on as, choosing the hop after it: `refused` for a
launch that ended well with a safety stop. -/
def Launched.movesAs (launched : Launched) : String :=
  if launched.ok && launched.safetyStop then "refused" else launched.stop

/-- The result of a task that launched nothing, every hop it could take resting
(`_passed_over`): deferred when one of the rests is a quota rest, else failed
`auth_failed`. -/
def passedOver (skipped : List SkippedHop) : AttemptResult :=
  if quotaRest skipped then { ok := false, stop := Stop.deferred, skippedHops := skipped }
  else { ok := false, stop := "auth_failed", skippedHops := skipped }

/-- The attempt's result when its chain ends on `result` (`_own`): that of the last launch
that was not refused for its credential, when `result` is a hop refused after it. -/
def own (result : AttemptResult) (ran : Option (AttemptResult × String)) : AttemptResult :=
  match ran with
  | some (ownResult, label) =>
    if result.stop == "auth_failed" then
      { ownResult with hops := result.hops, skippedHops := result.skippedHops, route := label }
    else result
  | none => result

/-- The walk after a launch on the route of `label` that gave `launched`: one more launch
on its trail, the launch's result as its last, and as the last that ran unless the launch
was refused for its credential. -/
def Walk.launchedOn (w : Walk) (label : String) (launched : Launched) : Walk :=
  let trail := w.trail ++ [{ route := label, stop := launched.stop }]
  let result : AttemptResult :=
    { ok := launched.ok, stop := launched.stop, hops := trail, skippedHops := w.skipped }
  { w with
    trail := trail
    last := some result
    ran := if launched.stop == "auth_failed" then w.ran else some (result, label) }

/-- The result of the walk's last launch, as the attempt's: on the route of `label`. -/
def Walk.ended (w : Walk) (label : String) : AttemptResult :=
  match w.last with
  | some result => { result with route := label }
  | none => { ok := false, stop := "error", route := label }

namespace RouterConfig

/-- The label of a route of the chain (`label_of`). -/
def labelOf (cfg : RouterConfig) (route : Route) : String :=
  match cfg.indexOf route with
  | some index => cfg.label index
  | none => ""

/-- `route`, or the first hop after it whose credential does not rest (`_usable`), with
the hops passed over added to `skipped`; `none` when every one rests. A hop after a resting
one is for `stop`, or for the rest's own stop when `stop` is empty. `fuel`: the hops the
chain has. -/
def usable (cfg : RouterConfig) (rest : Route → Option RestWhy) (stop : String) :
    Nat → Route → List SkippedHop → Option Route × List SkippedHop
  | 0, _, skipped => (none, skipped)
  | fuel + 1, here, skipped =>
    match rest here with
    | none => (some here, skipped)
    | some why =>
      let skipped := skipped ++ [{ route := cfg.labelOf here, why := why }]
      match cfg.nextRouteAfter here (if stop.isEmpty then why.stop else stop) with
      | none => (none, skipped)
      | some next => cfg.usable rest stop fuel next skipped

/-- Why a task cannot launch now (`deferral`): the hops it would pass over, when every hop
it could take, from the one the breaker picks, is on a resting credential and one of them
rests on its quota. `none` when a hop does not rest, the chain is exhausted, or only
refused credentials rest. -/
def deferral (cfg : RouterConfig) (now : Time) (rest : Route → Option RestWhy) (s : RouterState) :
    Option (List SkippedHop) :=
  match (cfg.pick now false s).2 with
  | none => none
  | some route =>
    match cfg.usable rest "" cfg.routes.length route [] with
    | (some _, _) => none
    | (none, skipped) => if quotaRest skipped then some skipped else none

/-- A round of the walk up to its launch: the attempt's result when it ends here, else the
walk and the route to launch on. A cancelled task launches no later hop; the route is the
task's own hop or the one the breaker picks; a hop whose credential rests is passed over. -/
def choose (cfg : RouterConfig) (out : HopOutside) (w : Walk) (s : RouterState) :
    RouterState × (AttemptResult ⊕ (Walk × Route)) :=
  match (if out.cancelled then w.last else none) with
  | some last => (s, .inl (own last w.ran))
  | none =>
    let (s, route) := match w.pinned with
      | some pinned => (s, some pinned)
      | none => cfg.pick out.now true s
    match route with
    | none => (s, .inl { ok := false, stop := "rate_limited", hops := w.trail })
    | some route =>
      match cfg.usable out.rest w.walk cfg.routes.length route w.skipped with
      | (none, skipped) =>
        (s, .inl (match w.last with
          | none => passedOver skipped
          | some last => own { last with skippedHops := skipped } w.ran))
      | (some usable, skipped) =>
        let pinned := if usable.identity == route.identity then w.pinned else some usable
        (s, .inr ({ w with skipped := skipped, pinned := pinned }, usable))

/-- Whether a launch on `route` that met no 429 moves its task alone to the next hop: it
failed with a stop another hop may fix, or it ended well with a safety stop and the chain
has a hop for refusals after `route`. -/
def movesOn (cfg : RouterConfig) (route : Route) (launched : Launched) : Bool :=
  launched.stop != "rate_limited" &&
    (launched.failsOver || (launched.ok && launched.safetyStop && (cfg.nextRouteAfter route "refused").isSome))

/-- A round of the walk after its launch on `route`: the attempt's result when it ends
here, else the walk for the next round. A failure other than a 429 moves the task alone to
the next hop for its stop; a launch that neither failed over nor met a 429 ends the
attempt, and tells the breaker when it ended well; a 429 moves the breaker, and the task
goes on with the breaker, or by itself when it is on its own walk. -/
def landed (cfg : RouterConfig) (out : HopOutside) (w : Walk) (route : Route) (s : RouterState) :
    RouterState × (AttemptResult ⊕ Walk) :=
  let label := cfg.labelOf route
  let launched := out.launch route
  let s := out.meanwhile s
  let w := w.launchedOn label launched
  if cfg.movesOn route launched then
    match cfg.nextRouteAfter route launched.movesAs with
    | none => (s, .inl (own (w.ended label) w.ran))
    | some next => (s, .inr { w with pinned := some next, walk := launched.movesAs })
  else if launched.stop != "rate_limited" then
    (if launched.ok then cfg.succeeded s (some route) (some out.now) else s, .inl (w.ended label))
  else
    let limited := cfg.rateLimited out.ended s (some route) launched.retryAfterS (some out.now)
    let w := { w with hops := w.hops + 1 }
    match w.pinned with
    | some _ =>
      match cfg.nextRouteAfter route "rate_limited" with
      | none => (limited.1, .inl (own (w.ended label) w.ran))
      | some next => (limited.1, .inr { w with pinned := some next, walk := "rate_limited" })
    | none =>
      if limited.2.isEmpty || w.hops ≥ cfg.routes.length then (limited.1, .inl (w.ended label))
      else (limited.1, .inr w)

/-- The rounds of the walk (`_run_with_failover`'s loop): the breaker after them and the
attempt's result, `none` when `fuel` rounds did not end it. `outside` gives what each
round reads, by the number of launches before it. -/
def walk (cfg : RouterConfig) (outside : Nat → HopOutside) :
    Nat → Walk → RouterState → RouterState × Option AttemptResult
  | 0, _, s => (s, none)
  | fuel + 1, w, s =>
    let out := outside w.trail.length
    match cfg.choose out w s with
    | (s, .inl result) => (s, some result)
    | (s, .inr (w, route)) =>
      match cfg.landed out w route s with
      | (s, .inl result) => (s, some result)
      | (s, .inr w) => cfg.walk outside fuel w s

/-- The rounds an attempt takes at most: its 429s on the breaker's hops, then its own walk
down the chain. -/
def rounds (cfg : RouterConfig) : Nat :=
  2 * cfg.routes.length + 1

/-- One attempt of a task on its kind's chain (`_run_with_failover`). -/
def runWithFailover (cfg : RouterConfig) (outside : Nat → HopOutside) (s : RouterState) :
    RouterState × Option AttemptResult :=
  cfg.walk outside cfg.rounds {} s

end RouterConfig

/-- The result of an attempt of a task that was cancelled (the end of `AgentRunner.run`):
one that did not end well ends `cancelled`, and no fresh attempt follows it. -/
def AttemptResult.whenCancelled (result : AttemptResult) (cancelled : Bool) : AttemptResult :=
  if cancelled && !result.ok then { result with stop := Stop.cancelled, retryable := false } else result

/-- What a kind gives its attempts (`KindConfig`): the fresh attempts after the first
(`retries`), and whether a task stopped on its turn cap gets no more turns the next time
(`max_turns_growth` is 1). -/
structure RetryConfig where
  retries : Int := 0
  sameTurnCap : Bool := true
  deriving Repr

namespace RetryConfig

/-- Whether a fresh attempt may follow an attempt that ended on `result`
(`RetryingRunner.run`): not after one that ended well, was deferred, ended on a stop that
another launch cannot change, or is not retryable. -/
def again (cfg : RetryConfig) (result : AttemptResult) : Bool :=
  !(result.stop == Stop.deferred || result.ok || notRetried.contains result.stop ||
    (result.stop == "max_turns" && cfg.sameTurnCap) || !result.retryable)

/-- The attempts of a task from attempt `attempt` on, `left` of them at most: the
surroundings after them, each result the journal gets (`on_attempt`), in order, and the
task's result, the last attempt's. `run` gives the result of each attempt by its number,
and what the attempt did to the surroundings. A deferred attempt launched nothing: the
journal does not get it. -/
def attemptsFrom {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult) :
    Nat → Nat → σ → σ × List AttemptResult × Option AttemptResult
  | 0, _, surroundings => (surroundings, [], none)
  | left + 1, attempt, surroundings =>
    let (surroundings, result) := run attempt surroundings
    if result.stop == Stop.deferred then (surroundings, [], some result)
    else if cfg.again result && left > 0 then
      let (surroundings, journaled, last) := cfg.attemptsFrom run left (attempt + 1) surroundings
      (surroundings, result :: journaled, last)
    else (surroundings, [result], some result)

/-- The attempts of a task (`RetryingRunner.run`): one, and `retries` more at most. -/
def attempts {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult) (surroundings : σ) :
    σ × List AttemptResult × Option AttemptResult :=
  cfg.attemptsFrom run (1 + cfg.retries.toNat) 0 surroundings

end RetryConfig

end Contraagent
