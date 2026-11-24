import Lean.Data.Json
import Contraagent.Execution.Services

/-!
# Scenarios of the services

A scenario is the claim names that stand for a service, each name's environment variable
and the address its service gives, the cool-off, and a list of steps: a task that comes to hold the services it claims, or the
run's end. Each step gives what the code reads from outside then: the clock, whether a
signal is stopping the run, and what the start or the stop of each service does.
`runScenario` plays it on the specification and returns what each step answers and what was
written to `services.jsonl`. `tests/lean/services_scenarios.py` plays the same scenario on
`Services`.
-/

namespace Conformance.Services

open Lean (FromJson ToJson Json)
open Contraagent

/-- A start of `name` that raises `error` in a step, after `took`. -/
structure StartScript where
  name : String
  error : String
  took : Int
  deriving FromJson

/-- A stop of `name` that raises `error` in a step. -/
structure StopScript where
  name : String
  error : String
  deriving FromJson

/-- One step. `op`: `hold` (the task of `key`, with `claims`, `plays`, `now`, `refused` and
the starts that raise) or `close` (with `cause` and the stops that raise). A start that
does not raise gives the name's address, and takes no time. -/
structure Step where
  op : String
  now : Int
  refused : Bool
  key : String
  claims : List String
  plays : Bool
  starts : List StartScript
  cause : String
  stops : List StopScript
  deriving FromJson

structure Scenario where
  services : List String
  variables : List (String × String)
  addresses : List (String × String)
  cooloffS : Option Int
  steps : List Step
  deriving FromJson

def optional : Option String → Json
  | some text => text
  | none => Json.null

def failure : ServiceFailure → Json
  | .clash first second => Json.mkObj [("why", "clash"), ("first", first), ("second", second)]
  | .notStarted name error => Json.mkObj [("why", "not_started"), ("name", name), ("error", error)]
  | .ending name => Json.mkObj [("why", "ending"), ("name", name)]

def event : ServiceEvent → Json
  | .start name key address error =>
    Json.mkObj [("event", "start"), ("name", name), ("key", key), ("address", optional address),
      ("error", optional error)]
  | .stop name cause error =>
    Json.mkObj [("event", "stop"), ("name", name),
      ("cause", match cause with | .runEnd => "run_end" | .interrupted => "interrupted"),
      ("error", optional error)]

/-- What acquiring `name` reads from outside in a step. -/
def outside (sc : Scenario) (step : Step) (name : String) : ServiceOutside :=
  { now := step.now, refused := step.refused,
    start := match step.starts.find? (·.name == name) with
      | some script => .raised script.error (step.now + script.took)
      | none => .gave (sc.addresses.lookup name) }

/-- Play a scenario from its JSON: what each step answers, and the lines of
`services.jsonl`, the first written first. -/
def runScenario (text : String) : Json :=
  match Json.parse text >>= fun json => (FromJson.fromJson? json : Except String Scenario) with
  | .error message => Json.mkObj [("error", message)]
  | .ok sc =>
    let cfg : ServicesConfig := { cooloffS := sc.cooloffS }
    let (s, answers) := sc.steps.foldl
      (fun (acc : ServicesState × Array Json) step =>
        match step.op with
        | "hold" =>
          let env : ServicesEnv :=
            { stands := sc.services.contains, variableOf := fun name => (sc.variables.lookup name).getD name,
              plays := fun _ => step.plays }
          let task : Task := { kind := "step", unit := step.key, id := step.key, key := step.key, claims := step.claims }
          let (s, answer) := cfg.hold env acc.1 task (outside sc step)
          (s, acc.2.push (match answer with
            | .ok held => Json.mkObj [("held", Json.arr (held.map fun (name, address) => Json.arr #[name, optional address]).toArray)]
            | .error why => Json.mkObj [("failed", failure why)]))
        | _ =>
          let cause := if step.cause == "interrupted" then ServiceStopCause.interrupted else .runEnd
          let stop := fun name => (step.stops.find? (·.name == name)).map (·.error)
          (acc.1.close cause stop, acc.2.push Json.null))
      ({}, #[])
    Json.mkObj [("answers", Json.arr answers), ("events", Json.arr (s.log.reverse.map event).toArray)]

end Conformance.Services
