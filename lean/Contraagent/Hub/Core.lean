import Contraagent.Hub.Relay

/-!
# The hub's retention

What `Hub` of `src/contraagent/_internal/hub/core.py` decides about what it removes and
what it keeps. `prune` is `Hub.prune`: which runs, transcripts, heartbeats and blobs a
prune removes, and what it reports. `PrunedRun.records` is what `Hub.records` decides for a
request of a run that retention removed (`pruned_answer`): whether the hub answers the
relay without storing the run again, and what it answers, or stores the run again.
`BlobsState` is the blobs and the file refs while a prune runs beside the relays: a relay
asks for a blob, stores one and sends a file ref (`has_blob`, `put_blob`, `records`), and
the prune marks the blobs to remove and removes each (`mark`, `expire`). `NameHeld` is what
the hub holds under one name while a prune runs beside the requests of the name's run: a
request dates the run and then stores its lines, and the prune removes the run only while
it is dated as the prune read it (`HubStore.put_batch`, `HubStore.prune_run`).

Left out: how the hub stores a request (`store`, `streams`) and serves the monitor; the
segment objects a prune removes with a run's transcripts, which `Segments.lean` describes
(`drop`); and a prune that fails between two of its steps, which a second prune completes.
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

/-! ## What a prune removes -/

/-- A run the hub holds, as a prune reads it. `recordsAt`: when a batch last changed its
records (`HubStore.activity`), `none` when the store has no time for it. `finished`: its
`run.json` says it finished. `files`: the SHA-256 of each of its file refs. `logs`: the
lines of each of its logs in the store. -/
structure HeldRun where
  name : String
  runUid : String
  recordsAt : Option Time := none
  finished : Bool := false
  files : List String := []
  logs : List (String × Nat) := []
  deriving DecidableEq, Repr

/-- The transcripts the hub holds of one run uid under one name (`StreamLogs.runs`).
`activity`: when an append last added lines to one of them. `logs`: the lines of each. -/
structure HeldTranscripts where
  name : String
  runUid : String
  activity : Option Time := none
  logs : List (String × Nat) := []
  deriving DecidableEq, Repr

/-- A host's latest heartbeat (`HubStore.heartbeats`): when the hub received it, its TTL,
and the names of the runs it reports alive. -/
structure HeldHeartbeat where
  host : String
  receivedAt : Time
  ttl : Duration
  alive : List String := []
  deriving DecidableEq, Repr

/-- A blob the hub holds (`BlobStore.items`): its SHA-256, when it was stored, and its
size in bytes. -/
structure HeldBlob where
  sha : String
  modified : Time
  size : Nat := 0
  deriving DecidableEq, Repr

/-- What the hub holds, as a prune reads it, each list in the order its store lists it:
runs by name, transcripts by name and run uid, heartbeats by host, blobs by SHA-256.
`pruned`: the runs the hub remembers it pruned, by name; a name holds a run or the memory
of one, not both. -/
structure Holdings where
  runs : List HeldRun := []
  transcripts : List HeldTranscripts := []
  heartbeats : List HeldHeartbeat := []
  blobs : List HeldBlob := []
  pruned : List (String × PrunedRun) := []
  deriving Repr

/-- Why a prune keeps an old run, or that it removes it. -/
inductive RunVerdict where
  /-- It has no activity time at all. -/
  | noActivity
  /-- Its activity is not older than the cutoff. -/
  | recent
  | live
  | unresponsive
  | removed
  deriving DecidableEq, Repr

/-- What a prune removed (`PruneReport`), and the old runs and heartbeats it kept, with
why. -/
structure PruneReport where
  runs : List String := []
  transcripts : List (String × String) := []
  blobs : List String := []
  blobBytes : Nat := 0
  heartbeats : List String := []
  keptRuns : List (String × String) := []
  keptHeartbeats : List (String × String) := []
  deriving DecidableEq, Repr

namespace Holdings

/-- Whether a host is up at `now`: within its heartbeat's TTL after the hub received it
(`_up`). -/
def up (now : Time) (heartbeat : HeldHeartbeat) : Bool :=
  decide (now < heartbeat.receivedAt + heartbeat.ttl)

/-- The runs that are live (`HeartbeatLiveness.live`): reported alive by the heartbeat of a
host that is up. -/
def live (hs : Holdings) (now : Time) : List String :=
  (hs.heartbeats.filter (up now)).flatMap (·.alive)

/-- Whether `run.json` of the run under `name` says it finished; a run the hub does not
hold has none. -/
def finished (hs : Holdings) (name : String) : Bool :=
  ((hs.runs.find? (·.name == name)).map (·.finished)).getD false

/-- The runs that are unresponsive (`HeartbeatLiveness.unresponsive`): reported alive by
the heartbeat of a host that is no longer up, and not finished by their `run.json`. -/
def unresponsive (hs : Holdings) (now : Time) : List String :=
  ((hs.heartbeats.filter (!up now ·)).flatMap (·.alive)).filter (!hs.finished ·)

/-- The later of two times that may be missing. -/
def later : Option Time → Option Time → Option Time
  | some a, some b => some (max a b)
  | some a, none => some a
  | none, b => b

/-- When the transcripts of a run uid under a name last grew. -/
def transcriptsAt (hs : Holdings) (name runUid : String) : Option Time :=
  (hs.transcripts.find? fun held => held.name == name && held.runUid == runUid).bind (·.activity)

/-- A run's activity (`Hub._activity`): the later of its records' and its transcripts'. -/
def activity (hs : Holdings) (run : HeldRun) : Option Time :=
  later run.recordsAt (hs.transcriptsAt run.name run.runUid)

/-- What a prune decides of a run, with `cutoff` the time before which activity is old: a
run with no activity time stays, as does one whose activity is not old, a live one and an
unresponsive one. -/
def verdict (hs : Holdings) (now cutoff : Time) (run : HeldRun) : RunVerdict :=
  match hs.activity run with
  | none => .noActivity
  | some last =>
    if cutoff ≤ last then .recent
    else if (hs.live now).contains run.name then .live
    else if (hs.unresponsive now).contains run.name then .unresponsive
    else .removed

/-- Whether a prune removes the run. -/
def removes (hs : Holdings) (now cutoff : Time) (run : HeldRun) : Bool :=
  hs.verdict now cutoff run == .removed

/-- Whether the hub holds a run of `runUid` under `name`. -/
def holdsRun (hs : Holdings) (name runUid : String) : Bool :=
  hs.runs.any fun run => run.name == name && run.runUid == runUid

/-- Whether transcripts are old: their activity is before the cutoff. Those with no
activity time are not. -/
def oldTranscripts (cutoff : Time) (held : HeldTranscripts) : Bool :=
  match held.activity with
  | some last => decide (last < cutoff)
  | none => false

/-- Whether a prune reports transcripts as those of a run the hub no longer held: the hub
holds no run of their run uid under their name, and they are old. -/
def orphaned (hs : Holdings) (cutoff : Time) (held : HeldTranscripts) : Bool :=
  !hs.holdsRun held.name held.runUid && oldTranscripts cutoff held

/-- Whether a prune removes transcripts: those of a run it removes, and those of a run the
hub no longer held. -/
def dropsTranscripts (hs : Holdings) (now cutoff : Time) (held : HeldTranscripts) : Bool :=
  hs.runs.any (fun run => run.name == held.name && run.runUid == held.runUid && hs.removes now cutoff run)
    || hs.orphaned cutoff held

/-- Whether an old heartbeat stays: it reports alive a run that is unresponsive and
held. -/
def evidence (hs : Holdings) (now : Time) (heartbeat : HeldHeartbeat) : Bool :=
  heartbeat.alive.any fun name => (hs.unresponsive now).contains name && hs.runs.any (·.name == name)

/-- Whether a prune removes a heartbeat: an old one of a host that is no longer up, and
that is no evidence of an unresponsive run. The runs a host that is up reports are live by
its heartbeat. -/
def removesHeartbeat (hs : Holdings) (now cutoff : Time) (heartbeat : HeldHeartbeat) : Bool :=
  decide (heartbeat.receivedAt < cutoff) && !up now heartbeat && !hs.evidence now heartbeat

/-- The blobs that the file refs of the runs a prune keeps name. -/
def referenced (hs : Holdings) (now cutoff : Time) : List String :=
  (hs.runs.filter (!hs.removes now cutoff ·)).flatMap (·.files)

/-- Whether a prune removes a blob: one stored before `oldBlobs` that no file ref of a run
it keeps names. -/
def removesBlob (hs : Holdings) (now cutoff oldBlobs : Time) (blob : HeldBlob) : Bool :=
  decide (blob.modified < oldBlobs) && !(hs.referenced now cutoff).contains blob.sha

/-- The words of a verdict in a report, for an old run that stays. -/
def keptWhy : RunVerdict → Option String
  | .noActivity => some "no activity"
  | .live => some "live"
  | .unresponsive => some "unresponsive"
  | _ => none

/-- What the hub remembers of a run it prunes (`HubStore.prune_run`): its run uid, and the
lines of each of its logs, its records' and its transcripts'. -/
def remembered (hs : Holdings) (run : HeldRun) : PrunedRun :=
  { runUid := run.runUid
    logs := run.logs ++ ((hs.transcripts.find? fun held => held.name == run.name && held.runUid == run.runUid).map
      (·.logs)).getD [] }

/-- What a prune reports (`Hub.prune`), at `now`, for runs whose activity is older than
`olderThan` and blobs older than `blobGrace`. A dry run reports the same. -/
def pruneReport (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) : PruneReport :=
  let cutoff := now - olderThan
  let gone := hs.blobs.filter (hs.removesBlob now cutoff (now - blobGrace))
  { runs := (hs.runs.filter (hs.removes now cutoff)).map (·.name)
    transcripts := (hs.transcripts.filter (hs.orphaned cutoff)).map fun held => (held.name, held.runUid)
    blobs := gone.map (·.sha)
    blobBytes := (gone.map (·.size)).sum
    heartbeats := (hs.heartbeats.filter (hs.removesHeartbeat now cutoff)).map (·.host)
    keptRuns := hs.runs.filterMap fun run => (keptWhy (hs.verdict now cutoff run)).map fun why => (run.name, why)
    keptHeartbeats := (hs.heartbeats.filter fun heartbeat =>
      decide (heartbeat.receivedAt < cutoff) && !up now heartbeat && hs.evidence now heartbeat).map fun heartbeat =>
        (heartbeat.host, "unresponsive run") }

/-- What the hub holds after a prune (`Hub.prune`): every run, transcript, heartbeat and
blob it does not remove, and the memory of each run it removed. -/
def afterPrune (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) : Holdings :=
  let cutoff := now - olderThan
  let removed := hs.runs.filter (hs.removes now cutoff)
  { runs := hs.runs.filter (!hs.removes now cutoff ·)
    transcripts := hs.transcripts.filter (!hs.dropsTranscripts now cutoff ·)
    heartbeats := hs.heartbeats.filter (!hs.removesHeartbeat now cutoff ·)
    blobs := hs.blobs.filter (!hs.removesBlob now cutoff (now - blobGrace) ·)
    pruned := removed.map (fun run => (run.name, hs.remembered run))
      ++ hs.pruned.filter fun entry => !removed.any (·.name == entry.1) }

/-- A prune (`Hub.prune`): what the hub holds after it, and its report. With `dryRun`, it
removes nothing and reports the same. -/
def prune (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) (dryRun : Bool) : Holdings × PruneReport :=
  (if dryRun then hs else hs.afterPrune now olderThan blobGrace, hs.pruneReport now olderThan blobGrace)

end Holdings

/-! ## The blobs, while a prune runs beside the relays -/

/-- The blobs and the file refs. `blobs`: each blob the hub holds, by its SHA-256, with its
date: when it was stored or last renewed. `refs`: the SHA-256 that each file ref of a run
held names. `marked`: the blobs a prune under way is about to remove. -/
structure BlobsState where
  blobs : List (String × Time) := []
  refs : List String := []
  marked : List String := []
  deriving DecidableEq, Repr

namespace BlobsState

/-- Whether the hub holds the blob (`BlobStore.has`). -/
def holds (s : BlobsState) (sha : String) : Bool :=
  s.blobs.any (·.1 == sha)

/-- Date a blob now (`BlobStore.renew`). -/
def renew (s : BlobsState) (now : Time) (sha : String) : BlobsState :=
  { s with blobs := s.blobs.map fun blob => if blob.1 == sha then (blob.1, now) else blob }

/-- A relay asks whether the hub holds a blob (`Hub.has_blob`), to send a file ref of it
without its content: a held blob is renewed. With the answer. -/
def hasBlob (s : BlobsState) (now : Time) (sha : String) : BlobsState × Bool :=
  if s.holds sha then (s.renew now sha, true) else (s, false)

/-- A relay stores a blob (`Hub.put_blob`): a blob already held is renewed. -/
def putBlob (s : BlobsState) (now : Time) (sha : String) : BlobsState :=
  if s.holds sha then s.renew now sha else { s with blobs := s.blobs ++ [(sha, now)] }

/-- A file ref arrives (`Hub.records`). -/
def fileRef (s : BlobsState) (sha : String) : BlobsState :=
  { s with refs := s.refs ++ [sha] }

/-- The file refs that name a blob go: their run was removed, or its file changed. -/
def forget (s : BlobsState) (sha : String) : BlobsState :=
  { s with refs := s.refs.filter (· != sha) }

/-- A prune lists the blobs and reads the file refs (`Hub.prune`): it marks each blob dated
before `old` that no file ref names. -/
def mark (s : BlobsState) (old : Time) : BlobsState :=
  { s with marked := (s.blobs.filter fun blob => decide (blob.2 < old) && !s.refs.contains blob.1).map (·.1) }

/-- A prune removes a blob when it is still dated before `old` (`BlobStore.expire`): one
renewed since the prune listed it stays. With whether it was removed. -/
def expire (s : BlobsState) (old : Time) (sha : String) : BlobsState × Bool :=
  if s.blobs.any fun blob => blob.1 == sha && decide (blob.2 < old) then
    ({ s with blobs := s.blobs.filter (·.1 != sha), marked := s.marked.filter (· != sha) }, true)
  else ({ s with marked := s.marked.filter (· != sha) }, false)

end BlobsState

/-! ## One name, while a prune runs beside the requests of its run -/

/-- What the hub holds under one name, of one log: nothing; a run, with the lines it holds
and when a batch last dated it (`HubStore.activity`); or the memory of a run it pruned,
with the lines it held then (`HubStore.pruned`). A name holds a run or the memory of one,
not both. -/
inductive NameHeld where
  | nothing
  | run (lines : Nat) (dated : Time)
  | pruned (lines : Nat)
  deriving DecidableEq, Repr

namespace NameHeld

/-- The lines the hub accounts for: those it holds, or those it held when it pruned the
run. -/
def lines : NameHeld → Nat
  | .nothing => 0
  | .run held _ => held
  | .pruned held => held

/-- A batch that brings lines is stored (`HubStore.put_batch`): its run is dated, before any
of its lines is stored. A name that holds no run, or the memory of a pruned one, holds a
run with no line from then on. -/
def dateRun (now : Time) : NameHeld → NameHeld
  | .run held _ => .run held now
  | _ => .run 0 now

/-- One line of the batch is stored. -/
def storeLine : NameHeld → NameHeld
  | .run held dated => .run (held + 1) dated
  | other => other

/-- A prune removes the run (`HubStore.prune_run`), only while the run is dated as the prune
read it (`seen`), and remembers it with the lines the prune counted. A run that a batch
dated since stays. With whether the run was removed. -/
def pruneRun (seen : Time) (counted : Nat) : NameHeld → NameHeld × Bool
  | .run held dated => if dated == seen then (.pruned counted, true) else (.run held dated, false)
  | other => (other, false)

end NameHeld

end Contraagent
