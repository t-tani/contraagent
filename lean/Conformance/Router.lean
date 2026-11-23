import Lean.Data.Json
import Contraagent.Routing.Router

/-!
# Scenarios of the failover breaker

A scenario is a chain of routes and a list of steps, each a call of a `Router` method at a
time the scenario gives. `runScenario` plays it on the specification and returns what each
call answers, then the switches recorded. `tests/lean/router_scenarios.py` plays the same
scenario on `Router`; the two must answer the same.
-/

namespace Conformance.Router

open Lean (FromJson ToJson Json)
open Contraagent

structure ScenarioRoute where
  agent : String
  model : String
  credential : String
  stops : List String
  deriving FromJson

/-- One call. `op`: `pick`, `look` (a pick that takes no probe), `active`, `rate_limited`,
`succeeded` or `next_route_after`. `route`: a place in the scenario's `routes`, which
hold the chain's and others; `none`: no route. -/
structure Step where
  now : Int
  op : String
  route : Option Nat
  retryAfterS : Option Int
  started : Option Int
  stop : String
  deriving FromJson

/-- `routes`: every route the steps name. `primary` and `fallbacks`: places in it. -/
structure Scenario where
  routes : List ScenarioRoute
  primary : Nat
  fallbacks : List Nat
  probeIntervalS : Int
  maxProbeIntervalS : Int
  steps : List Step
  deriving FromJson

def toRoute (r : ScenarioRoute) : Route :=
  { agent := r.agent, model := r.model, credential := r.credential, stops := r.stops }

def Scenario.route? (sc : Scenario) (place : Option Nat) : Option Route :=
  place.bind fun i => (sc.routes[i]?).map toRoute

def named (route : Option Route) : Json :=
  match route with
  | some r => r.name
  | none => Json.null

/-- Play one step: the breaker after it, and what the call answers. -/
def step (sc : Scenario) (cfg : RouterConfig) (s : RouterState) (st : Step) : RouterState × Json :=
  match st.op with
  | "pick" => let (s, r) := cfg.pick st.now true s; (s, named r)
  | "look" => let (s, r) := cfg.pick st.now false s; (s, named r)
  | "active" => (s, named (cfg.active s))
  | "rate_limited" =>
    let (s, told) := cfg.rateLimited st.now s (sc.route? st.route) st.retryAfterS st.started
    (s, told)
  | "succeeded" => (cfg.succeeded s (sc.route? st.route) st.started, Json.null)
  | "next_route_after" =>
    match sc.route? st.route with
    | some r => (s, named (cfg.nextRouteAfter r st.stop))
    | none => (s, Json.null)
  | _ => (s, "unknown step")

/-- Play a scenario from its JSON: what each step answers, then the switches recorded, or
why the scenario could not be played. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    match sc.route? (some sc.primary) with
    | none => Json.mkObj [("error", "the scenario has no primary")]
    | some primary =>
      let cfg : RouterConfig :=
        { routes := chainOf primary (sc.fallbacks.filterMap fun i => sc.route? (some i)),
          probeIntervalS := sc.probeIntervalS, maxProbeIntervalS := sc.maxProbeIntervalS }
      let (state, answers) := sc.steps.foldl
        (fun (acc : RouterState × Array Json) st =>
          let (s, answer) := step sc cfg acc.1 st
          (s, acc.2.push answer))
        (cfg.start, #[])
      let switches := state.switches.map fun pair => Json.arr #[pair.1, pair.2]
      Json.mkObj [("answers", Json.arr answers), ("switches", Json.arr switches.toArray)]

end Conformance.Router
