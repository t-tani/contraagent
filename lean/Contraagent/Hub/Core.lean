import Contraagent.Hub.Relay

/-!
# A run the hub pruned, and its relay

What `Hub.records` of `src/contraagent/_internal/hub/core.py` decides for a request of a
run that the hub's retention removed (`pruned_answer`): whether the hub answers the relay
without storing the run again, and what it answers, or stores the run again.

Left out: everything else of the hub, which stores a request (`store`, `streams`) and
serves the monitor, and the choice of the runs a prune removes.
-/

namespace Contraagent

/-- A run that retention removed, as the hub remembers it (`PrunedRun`): its run uid, and
how many lines of each of its logs the hub held then. -/
structure PrunedRun where
  runUid : String
  logs : List (String × Nat)
  deriving DecidableEq, Repr

namespace PrunedRun

/-- How many lines of a log the hub held when it pruned the run. -/
def held (pruned : PrunedRun) (log : String) : Nat :=
  (pruned.logs.lookup log).getD 0

/-- Whether a chunk brings a line past those the hub held of its log. -/
def grows (pruned : PrunedRun) (chunk : LogChunk) : Bool :=
  !chunk.lines.isEmpty && decide (chunk.offset + chunk.lines.length > pruned.held chunk.log)

/-- What the hub answers a request for a run it pruned, without storing it
(`pruned_answer`): for each log the request names, the lines the hub held when it pruned
the run, or the chunk's offset when that is more, so that the relay finds no line lost.
`none` when a chunk brings a line past those the hub held: the run is active again, and is
stored. -/
def answer (pruned : PrunedRun) (chunks : List LogChunk) : Option (List (String × Nat)) :=
  if chunks.any pruned.grows then none
  else some (chunks.map fun chunk => (chunk.log, max (pruned.held chunk.log) chunk.offset))

/-- What the hub does with a request of the run `runUid` under a name it remembers a
pruned run of (`Hub.records`): the answer when it stores nothing; `none` when it forgets
the prune and stores the request, because the run is active again or the name holds
another run. -/
def records (pruned : PrunedRun) (runUid : String) (chunks : List LogChunk) : Option (List (String × Nat)) :=
  if pruned.runUid == runUid then pruned.answer chunks else none

end PrunedRun

end Contraagent
