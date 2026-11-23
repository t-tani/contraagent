import Contraagent.Dispatch.Task

/-!
# The hub's copies of a log

What `SegmentedStreamLogs` of `src/contraagent/_internal/hub/segments.py` decides: which
lines of a log the hub holds and which of them are durable, when an open segment is
sealed, the order of a seal's steps, what a start recovers from the files, the objects and
the index, and what `sweep` and `drop` delete.

The state has two parts. `Kept` is what survives a crash: the index rows, the objects and
the files of the open segments. `logs` is what the process holds in memory, and a start
builds it again (`recover`). A function here is one method of the code, with seals run in
the call that starts them. A seal may fail or the process may die at one of its steps
(`Fault`), so that every order of events a crash leaves is a state of the description.

Left out: the locks and the background threads, the block table and the cache of a read
(a read gives lines, not blocks), a page's limit in bytes, the activity of a run, and a
torn last line, which a start cuts before it reads the file.
-/

namespace Contraagent

/-- A log: the run's name, the run's uid and the log's own name. -/
abbrev LogKey := String × String × String

/-- The index row of a sealed segment (`Segment`): its log, its first line and how many
lines it holds. Its object is the one of the same log and first line (`object_key`). -/
structure SegmentRow where
  key : LogKey
  first : Nat
  count : Nat
  deriving DecidableEq, Repr

/-- A segment in the objects store, with the lines it holds. -/
structure SegmentObject where
  key : LogKey
  first : Nat
  lines : List String
  deriving DecidableEq, Repr

/-- The file of a segment on the hub's disk, with its whole lines. -/
structure SegmentFile where
  key : LogKey
  first : Nat
  lines : List String
  deriving DecidableEq, Repr

/-- What survives a crash of the hub: the index, the objects and the files. -/
structure Kept where
  rows : List SegmentRow := []
  objects : List SegmentObject := []
  files : List SegmentFile := []
  deriving Repr

/-- What the hub holds of one log in memory (`_Log`). `sealed`: its sealed segments, each
its first line and its count. `sealing`: the first lines of the files that wait to be
sealed, in order. `hot`: the first line of the open segment. `durable`, `count`: how many
lines are in sealed segments, and how many the hub holds. `lastAppend`, `openedAt`: when
lines were last added, and when the open segment was opened. -/
structure LogState where
  sealed : List (Nat × Nat) := []
  sealing : List Nat := []
  hot : Option Nat := none
  durable : Nat := 0
  count : Nat := 0
  lastAppend : Time := 0
  openedAt : Time := 0
  deriving Repr

/-- The hub's logs: what survives a crash, and each log the process holds in memory. -/
structure HubState where
  kept : Kept := {}
  logs : List (LogKey × LogState) := []
  deriving Repr

/-- When an open segment is sealed (`segment_bytes`, `idle_s`, `age_s`). -/
structure HubConfig where
  segmentBytes : Nat
  idleS : Duration
  ageS : Duration
  deriving Repr

/-- The step of a seal at which it fails, or at which the process dies. -/
inductive SealFault where
  /-- The put of the object raises: nothing is stored. -/
  | failPut
  /-- The commit of the row raises: the object is stored, the row is not. -/
  | failAdd
  /-- The process dies after the put. -/
  | crashAfterPut
  /-- The process dies after the commit, before the file is deleted. -/
  | crashAfterAdd
  deriving DecidableEq, Repr

/-- The seal that goes wrong during one call: of the segment of a log that starts at
`first`, or of each segment of the log when `first` is none. -/
structure Fault where
  key : LogKey
  first : Option Nat
  how : SealFault
  deriving Repr

/-- How the seal of a log's segment that starts at `first` goes wrong, `none` when it does
not. -/
def Fault.hits (fault : Option Fault) (key : LogKey) (first : Nat) : Option SealFault :=
  fault.bind fun f => if f.key == key && (f.first.isNone || f.first == some first) then some f.how else none

/-- How a seal ended: done, failed and left for the next `tick`, or the process died. -/
inductive SealEnd where
  | done
  | failed
  | crashed
  deriving DecidableEq, Repr

/-- The bytes a line takes in a segment: its text and a newline. -/
def lineBytes (line : String) : Nat :=
  line.utf8ByteSize + 1

def bytesOf (lines : List String) : Nat :=
  (lines.map lineBytes).sum

/-- How many of some lines an open segment that holds `size` bytes takes (`_Hot.append`):
lines until it holds `segmentBytes`, and one at least. -/
def takeCount (segmentBytes : Nat) : Nat → List String → Nat
  | _, [] => 0
  | size, line :: rest =>
    if size + lineBytes line ≥ segmentBytes then 1 else 1 + takeCount segmentBytes (size + lineBytes line) rest

/-- The rows that follow one another from line 0, of rows in the order of their first
lines (`_contiguous`). -/
def contiguous (rows : List (Nat × Nat)) : List (Nat × Nat) :=
  rows.foldl (fun out row =>
    if row.1 == (out.map fun r => r.1 + r.2).getLast?.getD 0 && row.2 > 0 then out ++ [row] else out) []

namespace Kept

/-- The rows of a log in the order of their first lines (`SegmentIndex.segments`). -/
def rowsOf (kept : Kept) (key : LogKey) : List (Nat × Nat) :=
  ((kept.rows.filter (·.key == key)).map fun row => (row.first, row.count)).mergeSort fun a b => a.1 ≤ b.1

/-- Commit a row (`SegmentIndex.add`): in the place of the row of the same log and first
line, when there is one. -/
def addRow (kept : Kept) (key : LogKey) (first count : Nat) : Kept :=
  { kept with rows := kept.rows.filter (fun row => !(row.key == key && row.first == first)) ++
      [{ key := key, first := first, count := count }] }

def objectOf (kept : Kept) (key : LogKey) (first : Nat) : Option SegmentObject :=
  kept.objects.find? fun object => object.key == key && object.first == first

/-- Put an object (`SegmentObjects.put`): in the place of the object of the same key. -/
def putObject (kept : Kept) (key : LogKey) (first : Nat) (lines : List String) : Kept :=
  { kept with objects := kept.objects.filter (fun object => !(object.key == key && object.first == first)) ++
      [{ key := key, first := first, lines := lines }] }

/-- The lines of a file; none for a file that is not there. -/
def fileLines (kept : Kept) (key : LogKey) (first : Nat) : List String :=
  ((kept.files.find? fun file => file.key == key && file.first == first).map (·.lines)).getD []

def removeFile (kept : Kept) (key : LogKey) (first : Nat) : Kept :=
  { kept with files := kept.files.filter fun file => !(file.key == key && file.first == first) }

/-- Write a file's lines: a new file, or the file with more lines. -/
def writeFile (kept : Kept) (key : LogKey) (first : Nat) (lines : List String) : Kept :=
  { kept.removeFile key first with
    files := (kept.removeFile key first).files ++ [{ key := key, first := first, lines := lines }] }

end Kept

namespace LogState

/-- A log as the index holds it (`_Log`): its sealed segments, every line durable. -/
def ofSealed (sealed : List (Nat × Nat)) : LogState :=
  let durable := (sealed.map fun r => r.1 + r.2).getLast?.getD 0
  { sealed := sealed, durable := durable, count := durable }

/-- Stop the open segment and queue it to be sealed (`rotate`). -/
def rotate (st : LogState) : LogState :=
  match st.hot with
  | some first => { st with sealing := st.sealing ++ [first], hot := none }
  | none => st

end LogState

namespace HubState

def logOf (s : HubState) (key : LogKey) : Option LogState :=
  s.logs.lookup key

/-- Hold a log's state in memory: in its place, or after the logs held. -/
def setLog (s : HubState) (key : LogKey) (st : LogState) : HubState :=
  if s.logs.any (·.1 == key) then
    { s with logs := s.logs.map fun entry => if entry.1 == key then (key, st) else entry }
  else { s with logs := s.logs ++ [(key, st)] }

/-- A log's state, loaded from the index when it is not in memory (`_get`). Without
`create`, a log the index does not hold has none. -/
def load (s : HubState) (key : LogKey) (create : Bool) : HubState × Option LogState :=
  match s.logOf key with
  | some st => (s, some st)
  | none =>
    let sealed := contiguous (s.kept.rowsOf key)
    if sealed.isEmpty && !create then (s, none)
    else (s.setLog key (LogState.ofSealed sealed), some (LogState.ofSealed sealed))

end HubState

namespace HubConfig

/-- Add lines to a log's open segment (the loop of `append`): a segment that reaches
`segmentBytes` is stopped and queued to be sealed, and the lines after go to a new one.
With whether a segment was queued. `fuel`: the number of lines. -/
def writeLines (cfg : HubConfig) (now : Time) (key : LogKey) :
    Nat → Kept → LogState → List String → Kept × LogState × Bool
  | 0, kept, st, _ => (kept, st, false)
  | _ + 1, kept, st, [] => (kept, st, false)
  | fuel + 1, kept, st, line :: rest =>
    let first := st.hot.getD st.count
    let held := if st.hot.isSome then kept.fileLines key first else []
    let st := if st.hot.isSome then st else { st with hot := some first, openedAt := now }
    let taken := takeCount cfg.segmentBytes (bytesOf held) (line :: rest)
    let lines := held ++ (line :: rest).take taken
    let kept := kept.writeFile key first lines
    let st := { st with count := st.count + taken }
    let full := decide (bytesOf lines ≥ cfg.segmentBytes)
    let st := if full then st.rotate else st
    let (kept, st, queued) := cfg.writeLines now key fuel kept st ((line :: rest).drop taken)
    (kept, st, full || queued)

end HubConfig

/-- Seal one segment of a log (`_seal`): put its object, commit its row, then count its
lines durable and delete its file. A fault stops it at one of those steps. -/
def sealOne (fault : Option Fault) (key : LogKey) (kept : Kept) (st : LogState) (first : Nat) :
    Kept × LogState × SealEnd :=
  let lines := kept.fileLines key first
  match Fault.hits fault key first with
  | some .failPut => (kept, st, .failed)
  | some .failAdd => (kept.putObject key first lines, st, .failed)
  | some .crashAfterPut => (kept.putObject key first lines, st, .crashed)
  | some .crashAfterAdd => ((kept.putObject key first lines).addRow key first lines.length, st, .crashed)
  | none =>
    (((kept.putObject key first lines).addRow key first lines.length).removeFile key first,
      { st with
        sealing := st.sealing.filter (· != first)
        sealed := st.sealed ++ [(first, lines.length)]
        durable := first + lines.length },
      .done)

/-- Seal the segments of a log that wait, in order (`_seal_all`): a seal that fails stops
the others, which wait for the next `tick`. With whether the process died. `fuel`: the
segments that wait. -/
def sealAll (fault : Option Fault) (key : LogKey) : Nat → Kept → LogState → Kept × LogState × Bool
  | 0, kept, st => (kept, st, false)
  | fuel + 1, kept, st =>
    match st.sealing with
    | [] => (kept, st, false)
    | first :: _ =>
      match sealOne fault key kept st first with
      | (kept, st, .done) => sealAll fault key fuel kept st
      | (kept, st, .failed) => (kept, st, false)
      | (kept, st, .crashed) => (kept, st, true)

namespace HubState

/-- Hold a log's state and seal what waits of it: the state after, and whether the
process died. -/
def sealed (s : HubState) (fault : Option Fault) (key : LogKey) (kept : Kept) (st : LogState) :
    HubState × Bool :=
  let (kept, st, crashed) := sealAll fault key st.sealing.length kept st
  ({ s with kept := kept }.setLog key st, crashed)

end HubState

namespace HubConfig

/-- Add the lines of a chunk that the hub does not hold yet to a log (the rest of
`append`): the answer is how many lines the hub holds and how many are durable, as they
are before the seals this call starts. With whether the process died. -/
def appendNew (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (st : LogState) (new : List String) : HubState × (Nat × Nat) × Bool :=
  if new.isEmpty then (s, (st.count, st.durable), false)
  else
    let written := cfg.writeLines now key new.length s.kept { st with lastAppend := now } new
    let held := (written.2.1.count, written.2.1.durable)
    if written.2.2 then
      let after := s.sealed fault key written.1 written.2.1
      (after.1, held, after.2)
    else ({ s with kept := written.1 }.setLog key written.2.1, held, false)

/-- Append lines to a log, the first of them line `offset` (`append`): the lines the hub
already holds are dropped, and a chunk that leaves a gap stores nothing. -/
def append (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (offset : Nat) (lines : List String) : HubState × (Nat × Nat) × Bool :=
  let loaded := s.load key true
  let st := loaded.2.getD {}
  cfg.appendNew now fault loaded.1 key st (if offset ≤ st.count then lines.drop (st.count - offset) else [])

/-- Close a log (`close`): its open segment is sealed. A log the hub does not hold stays
as it is. -/
def close (fault : Option Fault) (s : HubState) (key : LogKey) : HubState × Bool :=
  match s.load key false with
  | (s, none) => (s, false)
  | (s, some st) =>
    if st.hot.isSome then s.sealed fault key s.kept st.rotate else (s, false)

/-- One log's part of a `tick`: its open segment is queued when no line was added for
`idleS` or it has been open for `ageS`, and what waits is sealed. -/
def tickLog (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey) :
    HubState × Bool :=
  match s.logOf key with
  | none => (s, false)
  | some st =>
    let due := st.hot.isSome && (decide (now - st.lastAppend ≥ cfg.idleS) || decide (now - st.openedAt ≥ cfg.ageS))
    s.sealed fault key s.kept (if due then st.rotate else st)

/-- `tick`: each log in turn, until the process dies. -/
def tick (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) : HubState × Bool :=
  (s.logs.map (·.1)).foldl
    (fun (acc : HubState × Bool) key => if acc.2 then acc else cfg.tickLog now fault acc.1 key)
    (s, false)

end HubConfig

namespace HubState

/-- Add to the index the objects of a log that continue what the hub holds of it
(`_adopt`), for a log whose rows were lost. A commit that fails ends the start, and so the
process; with whether it died. `fuel`: the objects. -/
def adopt (fault : Option Fault) (key : LogKey) : Nat → Kept → LogState → Kept × LogState × Bool
  | 0, kept, st => (kept, st, false)
  | fuel + 1, kept, st =>
    match kept.objectOf key st.count with
    | none => (kept, st, false)
    | some object =>
      if object.lines.isEmpty then (kept, st, false)
      else
        let «end» := st.count + object.lines.length
        match Fault.hits fault key st.count with
        | some .failAdd => (kept, st, true)
        | some .crashAfterAdd => (kept.addRow key st.count object.lines.length, st, true)
        | _ =>
          adopt fault key fuel (kept.addRow key st.count object.lines.length)
            { st with sealed := st.sealed ++ [(st.count, object.lines.length)], durable := «end», count := «end» }

/-- Go through the files of a log in the order of their first lines (the loop of
`_recover`): a file that continues what the hub holds of the log is taken, any other is
deleted. With the first lines of the files taken. -/
def takeFiles (key : LogKey) : List (Nat × Nat) → Kept → LogState → List Nat → Kept × LogState × List Nat
  | [], kept, st, taken => (kept, st, taken)
  | (first, lines) :: rest, kept, st, taken =>
    if first == st.count && lines > 0 then
      takeFiles key rest kept { st with count := st.count + lines } (taken ++ [first])
    else takeFiles key rest (kept.removeFile key first) st taken

/-- The objects of a log adopted when its last file starts past what the hub holds of it
(`_recover`). `files`: the log's files, each its first line and its count, in order. -/
def adoptPast (fault : Option Fault) (key : LogKey) (files : List (Nat × Nat)) (kept : Kept) (st : LogState) :
    Kept × LogState × Bool :=
  if (files.getLast?.map (·.1)).getD 0 > st.count then adopt fault key kept.objects.length kept st
  else (kept, st, false)

/-- Take up the files of a log at a start (the end of `_recover`): the last file taken is
the open segment, and the others are sealed. -/
def resume (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey) (files : List (Nat × Nat))
    (kept : Kept) (st : LogState) : HubState × Bool :=
  let took := takeFiles key files kept st []
  s.sealed fault key took.1
    (match took.2.2.getLast? with
    | some last => { took.2.1 with sealing := took.2.2.dropLast, hot := some last, lastAppend := now, openedAt := now }
    | none => took.2.1)

/-- Recover one log from its files at a start (`_recover`): its state from the index,
then the objects that continue it when its last file starts past it, then the files that
continue it. -/
def recoverLog (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey) : HubState × Bool :=
  let loaded := s.load key true
  let files := ((loaded.1.kept.files.filter (·.key == key)).map fun file => (file.first, file.lines.length)).mergeSort
    fun a b => a.1 ≤ b.1
  let adopted := adoptPast fault key files loaded.1.kept (loaded.2.getD {})
  if adopted.2.2 then ({ loaded.1 with kept := adopted.1 }, true)
  else resume now fault loaded.1 key files adopted.1 adopted.2.1

/-- Whether a log comes before another in the order of their names. -/
def namedBefore (a b : LogKey) : Bool :=
  a.1 < b.1 || (a.1 == b.1 && (a.2.1 < b.2.1 || (a.2.1 == b.2.1 && a.2.2 ≤ b.2.2)))

/-- A start of the hub on what a crash left (`_recover`): nothing in memory, then each
log that has a file, in the order of their names, until the process dies. -/
def recover (now : Time) (fault : Option Fault) (kept : Kept) : HubState × Bool :=
  (((kept.files.map (·.key)).eraseDups).mergeSort namedBefore).foldl
    (fun (acc : HubState × Bool) key => if acc.2 then acc else recoverLog now fault acc.1 key)
    ({ kept := kept }, false)

/-- Lines of a log from line `since`, `limit` of them at most (`read`), with how many
lines the hub holds: the sealed segments' lines from their objects, then those of the
files. A log the hub does not hold has none. -/
def read (s : HubState) (key : LogKey) (since : Nat) (limit : Option Nat) : HubState × List String × Nat :=
  match s.load key false with
  | (s, none) => (s, [], 0)
  | (s, some st) =>
    let sealedLines := st.sealed.flatMap fun row => ((s.kept.objectOf key row.1).map (·.lines)).getD []
    let fileLines := (st.sealing ++ st.hot.toList).flatMap fun first => s.kept.fileLines key first
    let from_ := (sealedLines ++ fileLines).drop since
    (s, match limit with | some n => from_.take n | none => from_, st.count)

/-- How many lines of a log the hub holds, and how many of them are durable (`held`). -/
def held (s : HubState) (key : LogKey) : HubState × (Nat × Nat) :=
  match s.load key false with
  | (s, none) => (s, (0, 0))
  | (s, some st) => (s, (st.count, st.durable))

/-- Delete every object that no index row names (`sweep`); the objects deleted. -/
def sweep (s : HubState) : HubState × List (LogKey × Nat) :=
  let orphan := fun (object : SegmentObject) =>
    !s.kept.rows.any fun row => row.key == object.key && row.first == object.first
  ({ s with kept := { s.kept with objects := s.kept.objects.filter fun object => !orphan object } },
    (s.kept.objects.filter orphan).map fun object => (object.key, object.first))

/-- The objects of a run's segments (`_run_keys`): the run's objects, and those its index
rows name. -/
def runKeys (s : HubState) (name uid : String) : List (LogKey × Nat) :=
  let ofRun := fun (key : LogKey) => key.1 == name && key.2.1 == uid
  (((s.kept.objects.filter fun object => ofRun object.key).map fun object => (object.key, object.first)) ++
    ((s.kept.rows.filter fun row => ofRun row.key).map fun row => (row.key, row.first))).eraseDups

/-- Remove a run's logs (`drop`): from memory, then their files, their index rows and
their objects. With the objects it deletes: the run's, and those its index rows name. -/
def drop (s : HubState) (name uid : String) : HubState × List (LogKey × Nat) :=
  let ofRun := fun (key : LogKey) => key.1 == name && key.2.1 == uid
  ({ logs := s.logs.filter fun entry => !ofRun entry.1
     kept :=
      { rows := s.kept.rows.filter fun row => !ofRun row.key
        objects := s.kept.objects.filter fun object => !ofRun object.key
        files := s.kept.files.filter fun file => !ofRun file.key } },
    s.runKeys name uid)

end HubState

end Contraagent
