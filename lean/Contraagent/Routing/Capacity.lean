import Contraagent.Dispatch.Task

/-!
# Claim capacities sized by the host

What `HostCapacity` and its `PerTask` capacities of
`src/contraagent/_internal/routing/capacity.py` decide: how many running tasks may hold a
claimed name, given what one task needs of the host's memory and cores, what the running
tasks hold, and what the host reads as free.

A function here is one method of the code. What the method reads of the host is an
argument: the free memory, and what the processes of each running task take
(`HostReading`). Left out: how the host is read (`/proc`, process groups).
-/

namespace Contraagent

/-- What one running task that claims a name needs of the host (`PerTask`): memory in MB,
cores, or both. -/
structure PerTask where
  memoryMb : Option Nat := none
  cores : Option Nat := none
  deriving Repr

/-- What the host answers when it is read: the free memory in MB, `none` where the host
does not report it, and the memory the processes of each task take, by key; a task with no
live process has none. -/
structure HostReading where
  freeMb : Option Nat
  usageMb : List (Key × Nat)

/-- A reading kept for the questions of one pass: the free memory, what each task takes,
and whether no task with a `PerTask` claim ran when it was read. -/
structure KeptReading where
  freeMb : Option Nat
  usageMb : List (Key × Nat)
  idle : Bool
  deriving Repr

/-- The host's room (`HostCapacity`). `tasks`: each running task with a `PerTask` claim,
with the memory it declared (the `memoryMb` of its `PerTask` names, added up) and how many
such names it holds. `baselineMb`: the free memory read while no such task ran. `reading`:
the reading kept since the queue last began to start tasks. -/
structure HostState where
  cores : Nat
  tasks : List (Key × Nat × Nat) := []
  baselineMb : Option Nat := none
  reading : Option KeptReading := none
  deriving Repr

namespace HostState

/-- Read the host again at the next question (`refresh`). -/
def refresh (s : HostState) : HostState :=
  { s with reading := none }

/-- The reading for this pass (`_read`): the kept one, else a new one. A reading taken
while no task with a `PerTask` claim runs sets the baseline. -/
def read (s : HostState) (host : HostReading) : HostState × KeptReading :=
  match s.reading with
  | some kept => (s, kept)
  | none =>
    let idle := s.tasks.isEmpty
    let baseline := if idle then (host.freeMb.orElse fun _ => s.baselineMb) else s.baselineMb
    let usage := if ! idle && host.freeMb.isSome then
        host.usageMb.filter fun pair => s.tasks.any (·.1 == pair.1)
      else []
    let kept : KeptReading := { freeMb := host.freeMb, usageMb := usage, idle := idle }
    ({ s with baselineMb := baseline, reading := some kept }, kept)

/-- How many more tasks that each declare `memoryMb` may start on this reading (`more`);
`none`: memory does not limit, the host reports none. A running task holds what it
declared, or what its processes take when that is more. The holds, the new task and the
memory other work took must fit in the baseline, and the free memory must hold the new task
and what the running tasks hold but have not taken yet. -/
def more (s : HostState) (host : HostReading) (memoryMb : Nat) : HostState × Option Nat :=
  let (s, kept) := s.read host
  match kept.freeMb, s.baselineMb with
  | some free, some baseline =>
    let used := fun (key : Key) => (kept.usageMb.lookup key).getD 0
    let held : Nat := (s.tasks.map fun task => max task.2.1 (used task.1)).foldl (· + ·) 0
    let taken : Nat := (s.tasks.map fun task => used task.1).foldl (· + ·) 0
    let other : Nat := baseline - free - taken
    let room : Int :=
      min ((baseline : Int) - (other : Int) - (held : Int)) ((free : Int) - ((held : Int) - (taken : Int)))
    (s, some (room.toNat / memoryMb))
  | _, _ => (s, none)

/-- Whether a running task holds memory (`holds_memory`): one with a `PerTask` name that
gives `memoryMb`. -/
def holdsMemory (s : HostState) : Bool :=
  s.tasks.any fun task => task.2.1 != 0

/-- A task that claims a name with `need` has started (`started`). The baseline is read
right before the first one starts. -/
def started (s : HostState) (host : HostReading) (key : Key) (need : PerTask) : HostState :=
  let fresh := match s.reading with
    | some kept => ! kept.idle
    | none => true
  let s := if s.tasks.isEmpty && fresh then (s.refresh.read host).1 else s
  let memory := need.memoryMb.getD 0
  match s.tasks.lookup key with
  | some (declared, names) =>
    { s with tasks := s.tasks.map fun task =>
        if task.1 == key then (key, declared + memory, names + 1) else task }
  | none => { s with tasks := s.tasks ++ [(key, memory, 1)] }

/-- A task that claims a name with `need` has ended (`ended`): one call for each
`started`. -/
def ended (s : HostState) (key : Key) (need : PerTask) : HostState :=
  match s.tasks.lookup key with
  | none => s
  | some (declared, names) =>
    if names ≤ 1 then { s with tasks := s.tasks.filter (·.1 != key) }
    else
      { s with tasks := s.tasks.map fun task =>
          if task.1 == key then (key, declared - need.memoryMb.getD 0, names - 1) else task }

/-- How many running tasks the memory lets hold a name with `need`, when `held` hold it;
`none`: the memory does not limit. The memory is the host's: one task starts over it only
while no running task holds memory. -/
def memoryLimit (s : HostState) (host : HostReading) (need : PerTask) (held : Nat) : HostState × Option Nat :=
  match need.memoryMb with
  | some memoryMb =>
    if memoryMb = 0 then (s, none)
    else
      let (s, room) := s.more host memoryMb
      (s, room.map fun room => held + (if s.holdsMemory then room else max room 1))
  | none => (s, none)

/-- How many running tasks the cores let hold a name with `need`; `none`: the cores do not
limit. As many as the usable cores divided by `need.cores`, and one where that is none. -/
def coresLimit (s : HostState) (need : PerTask) : Option Nat :=
  match need.cores with
  | some each => if each = 0 then none else some (max (s.cores / each) 1)
  | none => none

/-- The smaller of two limits; one that does not limit leaves the other. -/
def tighter : Option Nat → Option Nat → Option Nat
  | some a, some b => some (min a b)
  | some a, none => some a
  | none, some b => some b
  | none, none => none

/-- How many running tasks may hold a name with `need`, given that `held` hold it now
(`allowed`); `none`: no limit. The tighter of what the memory and the cores let. -/
def allowed (s : HostState) (host : HostReading) (need : PerTask) (held : Nat) : HostState × Option Nat :=
  let (s, memory) := s.memoryLimit host need held
  (s, tighter memory (s.coresLimit need))

end HostState

end Contraagent
