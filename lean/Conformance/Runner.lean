import Lean.Data.Json
import Contraagent.Execution.Runner

/-!
# Scenarios of the attempts of agent tasks

A scenario is a failover chain, what a kind gives its attempts, and some tasks that run one
after the other on the chain's breaker. Each task scripts its attempts, and each attempt
its rounds: how long the launch takes, which routes rest, what a launch on each route
gives, whether the task is cancelled during the launch, and what other tasks do to the
breaker meanwhile. `runScenario` plays it on the specification and returns, for each task,
the results the journal gets, the task's result and the breaker's switches.
`tests/lean/attempt_scenarios.py` plays the same scenario on `RetryingRunner` and
`AgentRunner`.
-/

namespace Conformance.Runner

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioRoute where
  agent : String
  model : String
  stops : List String
  deriving FromJson

structure LaunchScript where
  stop : String
  signalled : Bool
  safetyStop : Bool
  retryAfterS : Option Int
  deriving FromJson

/-- A call of another task on the breaker during a launch. `op`: `rate_limited`,
`succeeded` or `pick`. `route`: a place in the chain. `startedAgo`: how long before the
call its launch began. -/
structure Meanwhile where
  op : String
  route : Nat
  retryAfterS : Option Int
  startedAgo : Int
  deriving FromJson

/-- One round of an attempt. `rests` and `launch` are by the place of a route in the
chain; a rest is `quota`, `refused` or none. -/
structure Round where
  took : Int
  rests : List (Option String)
  launch : List LaunchScript
  cancel : Bool
  meanwhile : List Meanwhile
  deriving FromJson

/-- One attempt: it begins `wait` after the last one ended. -/
structure AttemptScript where
  wait : Int
  rounds : List Round
  deriving FromJson

structure TaskScript where
  attempts : List AttemptScript
  deriving FromJson

/-- `routes`: the chain, the primary first. -/
structure Scenario where
  routes : List ScenarioRoute
  probeIntervalS : Int
  retries : Int
  sameTurnCap : Bool
  tasks : List TaskScript
  deriving FromJson

def result (r : AttemptResult) : Json :=
  Json.mkObj [("ok", r.ok), ("stop", r.stop), ("route", r.route),
    ("hops", Json.arr (r.hops.map fun hop => Json.arr #[hop.route, hop.stop]).toArray),
    ("skipped", Json.arr (r.skippedHops.map fun hop =>
      Json.arr #[hop.route, match hop.why with | .quota => "quota" | .refused => "refused"]).toArray)]

/-- What another task's call does to the breaker at `now`. -/
def meanwhile (cfg : RouterConfig) (now : Time) (s : RouterState) (call : Meanwhile) : RouterState :=
  let route := cfg.routes[call.route]?
  match call.op with
  | "rate_limited" => (cfg.rateLimited now s route call.retryAfterS (some (now - call.startedAgo))).1
  | "succeeded" => cfg.succeeded s route (some (now - call.startedAgo))
  | _ => (cfg.pick now true s).1

/-- What round `n` of an attempt that began at `began` reads from outside. In a round
after those the attempt scripts, no route rests and every launch ends `error` at once. -/
def outside (cfg : RouterConfig) (script : AttemptScript) (began : Time) (n : Nat) : HopOutside :=
  let before := (script.rounds.take n).foldl (fun sum round => sum + round.took) 0
  let place := fun (route : Route) => (cfg.indexOf route).getD 0
  let cancelled := (script.rounds.take n).any (·.cancel)
  match script.rounds[n]? with
  | none =>
    { cancelled := cancelled, now := began + before, launch := fun _ => { stop := "error", ok := false },
      ended := began + before }
  | some round =>
    { cancelled := cancelled
      now := began + before
      rest := fun route =>
        match (round.rests[place route]?).join with
        | some "quota" => some .quota
        | some _ => some .refused
        | none => none
      launch := fun route =>
        match round.launch[place route]? with
        | some l =>
          { stop := l.stop, ok := l.stop == "completed", signalled := l.signalled, safetyStop := l.safetyStop,
            retryAfterS := l.retryAfterS }
        | none => { stop := "error", ok := false }
      meanwhile := fun s => round.meanwhile.foldl (meanwhile cfg (began + before + round.took)) s
      ended := began + before + round.took }

/-- One attempt of a task on the breaker and the clock: both after it, and its result. An
attempt whose walk does not end within its rounds has stop `walk without end`. -/
def attempt (cfg : RouterConfig) (task : TaskScript) (number : Nat) (surroundings : RouterState × Time) :
    (RouterState × Time) × AttemptResult :=
  let (s, clock) := surroundings
  let script := (task.attempts[number]?).getD { wait := 0, rounds := [] }
  let began := clock + script.wait
  let (s, ended) := cfg.runWithFailover (outside cfg script began) s
  match ended with
  | none => ((s, began), { ok := false, stop := "walk without end" })
  | some r =>
    let launched := script.rounds.take r.hops.length
    ((s, began + launched.foldl (fun sum round => sum + round.took) 0), r.whenCancelled (launched.any (·.cancel)))

/-- Play a scenario from its JSON: for each task, the results the journal gets, the task's
result, and the breaker's switches after it. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    match sc.routes.map fun r => ({ agent := r.agent, model := r.model, stops := r.stops } : Route) with
    | [] => Json.mkObj [("error", "a scenario needs a route")]
    | primary :: fallbacks =>
      let cfg : RouterConfig := { routes := chainOf primary fallbacks, probeIntervalS := sc.probeIntervalS }
      let retry : RetryConfig := { retries := sc.retries, sameTurnCap := sc.sameTurnCap }
      let (_, answers) := sc.tasks.foldl
        (fun (acc : (RouterState × Time) × Array Json) task =>
          let (surroundings, journaled, last) := retry.attempts (attempt cfg task) acc.1
          (surroundings, acc.2.push (Json.mkObj [
            ("journaled", Json.arr (journaled.map result).toArray),
            ("result", match last with | some r => result r | none => Json.null),
            ("switches", Json.arr (surroundings.1.switches.map fun (a, b) => Json.arr #[a, b]).toArray)])))
        ((cfg.start, 0), #[])
      Json.arr answers

end Conformance.Runner
