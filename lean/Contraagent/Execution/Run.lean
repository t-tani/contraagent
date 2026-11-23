import Contraagent.Dispatch.Task

/-!
# What a resume skips

What `resume_skip` and `rerun_reason` of `src/contraagent/_internal/execution/run.py`
decide: whether a resumed run skips a task, given each key's last journal row, and why it
runs again a task that an earlier attempt finished.

Left out: the run itself (its lock, its files, its queue and its records), and the text
of a reason, which `RerunReason` holds as data. The digest of a fingerprint is asked of
`ResumeEnv.fingerprintOf`: the specification does not work out SHA-256.
-/

namespace Contraagent

/-- What a resume reads of a key's last journal row (`JournalRow`). `outputOfAfter`: for a
task that fills in another task's file, the digest of the file as the attempt left it;
`outputOfFile`: that file. Both are empty for any other task. -/
structure JournalRow where
  key : Key
  ok : Bool
  stop : Stop
  fingerprint : String := ""
  fingerprintParts : List (String × String) := []
  outside : String := ""
  outputOfAfter : String := ""
  outputOfFile : String := ""
  deriving Repr

/-- What a resume asks outside the journal. `fingerprintOf kind unit key parts`: the
fingerprint of a task with these parts (`fingerprint_of`). `reads`: whether the task's
output still reads under its output schema. -/
structure ResumeEnv where
  fingerprintOf : Kind → String → Key → List (String × String) → String
  reads : Task → Bool

/-- Why a resume runs a task again whose last journal row is ok (journal `rerun`). -/
inductive RerunReason where
  /-- Its output no longer reads under its output schema. -/
  | unread
  /-- The file it fills in is not as the earlier attempts left it. -/
  | refill
  /-- Its kind is declared `rerun_on_resume`. -/
  | rerunOnResume
  /-- Its last result was `partial`. -/
  | lastPartial
  /-- Its outside state changed, and nothing else of its fingerprint. -/
  | outsideChanged
  /-- Its outside state could not be worked out. -/
  | outsideUnknown
  /-- Its fingerprint changed, and the row or the task holds no parts to name. -/
  | changedUnnamed
  /-- Its fingerprint changed with every part the same: its kind or its unit. -/
  | kindOrUnit
  /-- The flow gave it other params for the same outputs: every task it was given or
  created from was skipped. `parts`: the parts that changed. -/
  | divergence (parts : List String)
  /-- Its fingerprint changed in `parts`. -/
  | changed (parts : List String)
  deriving DecidableEq, Repr

/-- The digest of a part of a fingerprint, by the part's name. -/
def partOf (parts : List (String × String)) (name : String) : Option String :=
  parts.lookup name

/-- A part's place among the parts a reason names: the parts the code knows first, in its
order, then any other, by name. -/
def partRank (name : String) : Nat :=
  (["definition", "params", "input_files", "outside", "output_of"].findIdx? (· == name)).getD 5

/-- Whether part `a` is named before part `b`. -/
def partBefore (a b : String) : Bool :=
  partRank a < partRank b || (partRank a == partRank b && a ≤ b)

/-- The names of the parts whose digest differs between a row and a task, a part either of
them lacks included, in the order a reason names them (`_changed`). -/
def changedParts (row : JournalRow) (task : Task) : List String :=
  let names := (row.fingerprintParts.map (·.1) ++ task.fingerprintParts.map (·.1)).eraseDups
  (names.filter fun name => partOf row.fingerprintParts name != partOf task.fingerprintParts name).mergeSort
    partBefore

/-- Whether a key's last row shows the task finished (`finished_before`): ok and not
`partial`, with the fingerprint `fingerprint`; never for a task that reruns on resume. -/
def finishedBefore (row : JournalRow) (task : Task) (fingerprint : String) : Bool :=
  ! task.rerunOnResume && row.stop != Stop.«partial» && row.ok && row.fingerprint == fingerprint

/-- The digests a file may hold when it is as `row`'s attempt left it, or as a task after
it that fills the same file in left it: those reached from what the attempt left, each
task taking the file from the digest it found to the one it left (`_as_left`). `rounds`
bounds the search: the number of rows is enough. -/
def leftDigests (rows : List JournalRow) (file : String) : Nat → List String → List String
  | 0, reached => reached
  | rounds + 1, reached =>
    let next := rows.filterMap fun r =>
      match partOf r.fingerprintParts "output_of" with
      | some found =>
        if r.outputOfFile == file && r.outputOfAfter != "" && reached.contains found
            && ! reached.contains r.outputOfAfter then some r.outputOfAfter
        else none
      | none => none
    leftDigests rows file rounds (reached ++ next.eraseDups)

/-- Whether a file whose digest is `now` is as `row`'s attempt left it, or as a task after
it that fills the same file in left it (`_as_left`). -/
def asLeft (rows : List JournalRow) (row : JournalRow) (now : String) : Bool :=
  if row.outputOfAfter == "" then false
  else (leftDigests rows row.outputOfFile rows.length [row.outputOfAfter]).contains now

/-- Why a resume runs `task` again although its last row is ok (`rerun_reason`), given the
keys the resume has skipped so far. -/
def rerunReason (row : JournalRow) (task : Task) (skipped : List Key) : RerunReason :=
  let changed := changedParts row task
  if task.rerunOnResume then .rerunOnResume
  else if row.stop == Stop.«partial» then .lastPartial
  else if task.outside != "" && row.outside != "" && task.outside != row.outside
      && (changed == [] || changed == ["outside"]) then .outsideChanged
  else if task.fingerprintAtStart && task.outside == "" && row.outside != "" then .outsideUnknown
  else if row.fingerprintParts.isEmpty || task.fingerprintParts.isEmpty then .changedUnnamed
  else if changed.isEmpty then .kindOrUnit
  else
    let origin := task.origin.getD {}
    if changed.contains "params" && ! changed.contains "input_files"
        && (origin.givenFrom ++ origin.createdFrom).all (skipped.contains ·) then .divergence changed
    else .changed changed

/-- What a resume has decided so far: the keys it skipped, and why it runs again each
task that an earlier attempt finished, the latest first. -/
structure ResumeState where
  skipped : List Key := []
  reruns : List (Key × RerunReason) := []
  deriving Repr

/-- The task a row is compared with, and the fingerprint the row must hold for a skip
(`resume_skip`). A task that fills in another task's file holds the file's digest in its
fingerprint. When the file is as the earlier attempts left it, the row's own digest of that
part takes its place; when it is not, `none`: the task fills the file in again. -/
def judged (env : ResumeEnv) (rows : List JournalRow) (row : JournalRow) (task : Task) :
    Option (Task × String) :=
  match partOf task.fingerprintParts "output_of" with
  | none => some (task, task.fingerprint)
  | some now =>
    match partOf row.fingerprintParts "output_of" with
    | none => none
    | some recorded =>
      if asLeft rows row now then
        let parts := task.fingerprintParts.map fun part =>
          if part.1 == "output_of" then (part.1, recorded) else part
        some ({ task with fingerprintParts := parts }, env.fingerprintOf task.kind task.unit task.key parts)
      else none

/-- Whether a resume skips `task` (`resume_skip`), given each key's last row (`rows`, one
for each key): its row shows it finished, and its output still reads. A task that an
earlier attempt finished and that is not skipped is noted with why it runs again. -/
def resumeSkip (env : ResumeEnv) (rows : List JournalRow) (s : ResumeState) (task : Task) :
    ResumeState × Bool :=
  match rows.find? (·.key == task.key) with
  | none => (s, false)
  | some row =>
    let same := judged env rows row task
    let finished := match same with
      | some (_, fingerprint) => finishedBefore row task fingerprint
      | none => false
    let unread := finished && ! env.reads task
    if finished && ! unread then ({ s with skipped := task.key :: s.skipped }, true)
    else if ! row.ok then (s, false)
    else
      let why :=
        if unread then .unread
        else if same.isNone && ! task.rerunOnResume && row.stop != Stop.«partial» then .refill
        else rerunReason row ((same.map (·.1)).getD task) s.skipped
      ({ s with reruns := (task.key, why) :: s.reruns.filter (·.1 != task.key) }, false)

end Contraagent
