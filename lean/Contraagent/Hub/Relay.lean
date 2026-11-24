import Contraagent.Dispatch.Task

/-!
# The relay's shipping of a run's logs

What `Relay` of `src/contraagent/_internal/hub/relay.py` decides when it ships one run's
logs to a hub: the lines of each request (`_logs`), what it takes from the hub's answer as
its progress (`_accept`), and when it sends the run again or stops (`_ship`).

The hub is the surroundings: `answer` gives, for each request, what the hub is after it
and how many lines of each log the request names it holds then. Left out: the documents and the files a contract names
but for whether a request carries any, the limit of a request in bytes, byte offsets, a
log that became shorter than the part sent, the heartbeat, the fast path's choice of the
active transcripts, the waits after a hub that takes no request, a run or a log whose name
is not UTF-8, which the relay does not send, and the text of a line as a hub holds it
(`text`), which keeps the count of a log's lines.
-/

namespace Contraagent

/-- Where the hub is up to in one run, as far as the relay knows (`RunProgress`): the
lines of each log the hub holds, and whether it holds the run's documents and files. -/
structure RunProgress where
  logs : List (String × Nat) := []
  documents : Bool := false
  deriving DecidableEq, Repr

/-- Lines of one log in a request (`LogChunk`): the first of them is line `offset`. -/
structure LogChunk where
  log : String
  offset : Nat
  lines : List String
  deriving DecidableEq, Repr

/-- One request for a run (`RecordBatch`): its chunks, and whether it carries documents or
files. -/
structure RelayRequest where
  chunks : List LogChunk
  documents : Bool
  deriving DecidableEq, Repr

/-- A run on the relay's host: the complete lines of each of its logs, in the order the
source lists the logs, and whether it has documents or files. -/
structure RunFiles where
  logs : List (String × List String)
  documents : Bool := false
  deriving Repr

/-- A table with one more entry: in the place of the entry of the same name, or last. -/
def putLines (logs : List (String × Nat)) (log : String) (lines : Nat) : List (String × Nat) :=
  if logs.any (·.1 == log) then logs.map fun entry => if entry.1 == log then (log, lines) else entry
  else logs ++ [(log, lines)]

namespace RunProgress

/-- The chunks of one request (`_logs`): for each log in turn, the lines after those the
hub holds, `budget` lines at most in the whole request. A log with no new line is named,
with no line, when the relay never sent it or when the request asks what the hub holds
(`probe`). -/
def chunks (progress : RunProgress) (probe : Bool) : Nat → List (String × List String) → List LogChunk
  | _, [] => []
  | budget, (log, file) :: rest =>
    let held := progress.logs.lookup log
    let lines := (file.drop (held.getD 0)).take budget
    (if !lines.isEmpty || held.isNone || probe then [{ log := log, offset := held.getD 0, lines := lines }] else []) ++
      progress.chunks probe (budget - lines.length) rest

/-- Take the hub's answer to one chunk as the log's progress (`_accept`): the lines the
hub says it holds, and no more than the log has. With whether the hub holds fewer lines
than the chunk's first: it lost lines. A log the answer does not name stays as it is. -/
def acceptChunk (files : RunFiles) (accepted : List (String × Nat)) (acc : RunProgress × Bool) (chunk : LogChunk) :
    RunProgress × Bool :=
  match accepted.lookup chunk.log with
  | none => acc
  | some held =>
    if held == chunk.offset + chunk.lines.length then
      ({ acc.1 with logs := putLines acc.1.logs chunk.log held }, acc.2)
    else
      ({ acc.1 with logs := putLines acc.1.logs chunk.log (min held ((files.logs.lookup chunk.log).getD []).length) },
        acc.2 || decide (held < chunk.offset))

/-- Take the hub's answer to a request (`_accept`); with whether the hub lost lines. -/
def accept (progress : RunProgress) (files : RunFiles) (chunks : List LogChunk) (accepted : List (String × Nat)) :
    RunProgress × Bool :=
  chunks.foldl (acceptChunk files accepted) (progress, false)

end RunProgress

/-- The walk of `_ship`'s loop, between two requests: whether the next one carries the
documents (`whole`), whether it asks what the hub holds (`probe`), and whether the run was
sent again already (`resent`). -/
structure ShipWalk where
  whole : Bool := true
  probe : Bool := false
  resent : Bool := false
  deriving Repr

/-- Ship one run (`_ship`): requests until there is nothing to send or the hub took no
line of the last one, with the hub and the progress after, and the requests made, in
order. When the hub holds fewer lines than the relay sent before, the run is sent again
from what the hub holds, its documents and files too, once, and the next request asks
what the hub holds of every log. A hub that holds fewer lines again after that ends the
walk: the next pass goes on. `answer` gives what the hub
is after a request and how many lines of each log the request names it holds then;
`fuel`: the requests at most. -/
def ship {σ : Type} (batchLines : Nat) (files : RunFiles) (answer : σ → RelayRequest → σ × List (String × Nat)) :
    Nat → ShipWalk → σ → RunProgress → List RelayRequest → σ × RunProgress × List RelayRequest
  | 0, _, hub, progress, sent => (hub, progress, sent)
  | fuel + 1, walk, hub, progress, sent =>
    let documents := walk.whole && files.documents && !progress.documents
    let chunks := progress.chunks walk.probe batchLines files.logs
    if chunks.isEmpty && !documents then (hub, progress, sent)
    else
      let request : RelayRequest := { chunks := chunks, documents := documents }
      let answered := answer hub request
      let held : RunProgress := if documents then { progress with documents := true } else progress
      let taken := held.accept files chunks answered.2
      if taken.2 && !walk.resent then
        ship batchLines files answer fuel { whole := true, probe := true, resent := true } answered.1
          { taken.1 with documents := false } (sent ++ [request])
      else if taken.2 && !walk.probe then (answered.1, taken.1, sent ++ [request])
      else if !documents && taken.1.logs == held.logs then (answered.1, taken.1, sent ++ [request])
      else
        ship batchLines files answer fuel { whole := false, probe := false, resent := walk.resent } answered.1
          taken.1 (sent ++ [request])

/-- What a hub that keeps every line once, in order, holds of a log after a chunk
(`StreamLogs.append`): the lines it held, and those of the chunk after them; a chunk that
leaves a gap adds nothing. -/
def hubTakes (held : List String) (chunk : LogChunk) : List String :=
  if chunk.offset ≤ held.length then held ++ chunk.lines.drop (held.length - chunk.offset) else held

end Contraagent
