import Contraagent.Dispatch.Task

/-!
# Services

What `Services` of `src/contraagent/_internal/execution/services.py` decides: when the
service a claim name stands for starts, which tasks a start that raised fails, and when and
in which order the services stop.

A function here is one method of the code. It takes what the method reads from outside:
the clock's reading, whether a signal is stopping the run, and what the start or the stop of
a service does. What the code writes to `services.jsonl` is part of the state (`log`). Left
out: the locks, the count of the tasks that hold a name, which decides nothing, how a running
task reads its services' addresses, and the progress lines.
-/

namespace Contraagent

/-- One claim name's service (`_State`): whether it is up and its address, what its last
start raised and when, and the order of its last start. -/
structure ServiceState where
  up : Bool := false
  address : Option String := none
  failed : Option String := none
  failedAt : Time := 0
  started : Nat := 0
  deriving DecidableEq, Repr

/-- What the start of a service does: it gives the service's address, or it raises, and
`failedAt` is the clock's reading then. -/
inductive StartAnswer where
  | gave (address : Option String)
  | raised (error : String) (failedAt : Time)
  deriving Repr

/-- What acquiring one name reads from outside: the clock, whether a signal is stopping the
run (`live_processes.launches_refused`), and what the service's start does when it is
asked to start. -/
structure ServiceOutside where
  now : Time
  refused : Bool := false
  start : StartAnswer
  deriving Repr

/-- Why a task cannot hold the services it claims (`ServiceFailed`): two of them share one
environment variable, a start raised (now, or before and the service still rests), or the
run is ending. -/
inductive ServiceFailure where
  | clash (first second : String)
  | notStarted (name : String) (error : String)
  | ending (name : String)
  deriving DecidableEq, Repr

/-- What `Services` is built with: the time after a start that raised before a task that
claims the name tries the start again (`cooloff_s`), `none` for never in the run. -/
structure ServicesConfig where
  cooloffS : Option Duration := none
  deriving Repr

/-- What `Services` asks of its surroundings: whether a claim name stands for a service
(`claim_entry` on the pipeline's services), the environment variable that holds a service's
address (`envvars.service`), and whether the run plays a task (`plays`). -/
structure ServicesEnv where
  stands : String → Bool
  variableOf : String → String
  plays : Task → Bool

/-- The services of one run (`Services`): each name's service, how many starts went well,
whether the run's end stopped them (`closed`), and what was written to `services.jsonl`,
the latest line first. -/
structure ServicesState where
  states : List (String × ServiceState) := []
  starts : Nat := 0
  closed : Bool := false
  log : List ServiceEvent := []
  deriving Repr

namespace ServicesEnv

/-- The names a task claims that stand for a service, each once, in the order the task
claims them (`names`). -/
def names (env : ServicesEnv) (task : Task) : List String :=
  task.claims.eraseDups.filter env.stands

/-- The first two of some names that share one environment variable (`env_clashes`): `seen`
are the names before `names`. -/
def clash (env : ServicesEnv) (seen : List String) : List String → Option (String × String)
  | [] => none
  | name :: rest =>
    match seen.find? fun earlier => env.variableOf earlier == env.variableOf name with
    | some earlier => some (earlier, name)
    | none => env.clash (seen ++ [name]) rest

end ServicesEnv

namespace ServicesState

/-- One name's service; a name that was never acquired has one that is not up. -/
def stateOf (s : ServicesState) (name : String) : ServiceState :=
  (s.states.lookup name).getD {}

def setState (s : ServicesState) (name : String) (state : ServiceState) : ServicesState :=
  { s with states := (name, state) :: s.states.filter (·.1 != name) }

end ServicesState

namespace ServicesConfig

/-- Whether a service rests after a start that raised: for the whole run with no cool-off,
else until the cool-off has passed. -/
def resting (cfg : ServicesConfig) (now : Time) (state : ServiceState) : Bool :=
  state.failed.isSome &&
    match cfg.cooloffS with
    | none => true
    | some cooloff => decide (now - state.failedAt < cooloff)

/-- A service starts for the task of `key` (`_start`): up with its address, as the latest
started; or its start raised, and it rests. -/
def start (s : ServicesState) (name : String) (key : Key) (state : ServiceState) :
    StartAnswer → ServicesState × Except ServiceFailure (Option String)
  | .raised error failedAt =>
    ({ s.setState name { state with failed := some error, failedAt := failedAt } with
        log := .start name key none (some error) :: s.log },
      .error (.notStarted name error))
  | .gave address =>
    ({ s.setState name { state with up := true, address := address, started := s.starts + 1 } with
        starts := s.starts + 1, log := .start name key address none :: s.log },
      .ok address)

/-- The task of `key` acquires one name (`_acquire`): the address of its service, which
starts when it is not up. A service that rests fails the task with what its start raised,
and no service starts once the run is ending. -/
def acquire (cfg : ServicesConfig) (s : ServicesState) (name : String) (key : Key)
    (outside : ServiceOutside) : ServicesState × Except ServiceFailure (Option String) :=
  let state := s.stateOf name
  if cfg.resting outside.now state then
    (s, .error (.notStarted name (state.failed.getD "")))
  else
    let state := { state with failed := none }
    let s := s.setState name state
    if s.closed || outside.refused then (s, .error (.ending name))
    else if state.up then (s, .ok state.address)
    else start s name key state outside.start

/-- The task of `key` acquires some names in order: their addresses, after those of `held`,
or the first failure. -/
def acquireAll (cfg : ServicesConfig) (key : Key) (outside : String → ServiceOutside) :
    ServicesState → List String → List (String × Option String) →
      ServicesState × Except ServiceFailure (List (String × Option String))
  | s, [], held => (s, .ok held)
  | s, name :: rest, held =>
    match cfg.acquire s name key (outside name) with
    | (s, .error failure) => (s, .error failure)
    | (s, .ok address) => cfg.acquireAll key outside s rest (held ++ [(name, address)])

/-- A task comes to hold the services it claims (`held`, up to its block): each name's
address, in the order the task claims them, or why it cannot hold them (the task then ends
with `launch_failed`). A task that claims no service, or that the run plays, holds none.
`outside` is what acquiring each name reads. -/
def hold (cfg : ServicesConfig) (env : ServicesEnv) (s : ServicesState) (task : Task)
    (outside : String → ServiceOutside) :
    ServicesState × Except ServiceFailure (List (String × Option String)) :=
  let names := env.names task
  if names.isEmpty || env.plays task then (s, .ok [])
  else
    match env.clash [] names with
    | some (first, second) => (s, .error (.clash first second))
    | none => cfg.acquireAll task.key outside s names []

end ServicesConfig

namespace ServicesState

/-- One service stops when it is up (`close`'s loop, `_stop`); `error` is what its stop
raised. -/
def stopOne (cause : ServiceStopCause) (stop : String → Option String) (s : ServicesState)
    (name : String) : ServicesState :=
  let state := s.stateOf name
  if state.up then
    { s.setState name { state with up := false, address := none } with
      log := .stop name cause (stop name) :: s.log }
  else s

/-- The names in the order the run's end goes through them: the last started first. -/
def closeOrder (s : ServicesState) : List String :=
  (s.states.mergeSort fun a b => decide (a.2.started ≥ b.2.started)).map (·.1)

/-- The run's end (`close`): every service still up stops, the last started first, and no
service starts after. `stop` is what the stop of each name raises, `none` when it goes
well. -/
def close (s : ServicesState) (cause : ServiceStopCause) (stop : String → Option String) :
    ServicesState :=
  s.closeOrder.foldl (stopOne cause stop) { s with closed := true }

end ServicesState

end Contraagent
