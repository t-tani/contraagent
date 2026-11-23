import Contraagent.Execution.Journal
import Contraagent.Execution.Run.Skip
import Contraagent.Runs.Files.Whole

/-!
# A resume goes by rows that were recorded

A resume reads the journal's log, which a run only appends to, and which a write that was
cut may have left with a line that is no row.

- Every row a resume reads is one the run recorded: a row handed to the journal, whole
  (`journalRows_recorded`). A line that a cut write left is the first bytes of a row, and
  parses as none.
- So a resume skips a task only on a row the run recorded for the task's key, ok and not
  `partial`, for a task that does not rerun on resume and whose output reads
  (`resume_skips_recorded`): never on what a crash left in the file.
- A row that was appended whole is read after any appends that follow, cut or not, and
  whatever a cut write left before it (`recorded_read`): the task is judged by that row or
  by a later one of its key, and is not run again for a line that a crash left.
- A task whose attempt the run's end cut is not skipped (`unfinished_not_skipped`). The
  attempt left its in-flight marker, which holds how many rows the journal held when the
  task started, and no row of the task's key from that place on. The task's last row is
  then of an earlier attempt, and its output file may hold what the cut attempt wrote. A
  marker whose attempt left a row says nothing (`unfinishedKeys_row`): the run ended
  between the row and the marker's removal, and the task is judged by the row.
-/

namespace Contraagent

theorem lastRows_subset (rows : List JournalRow) : ∀ row ∈ lastRows rows, row ∈ rows := by
  induction rows with
  | nil => intro row mem; cases mem
  | cons first rest ih =>
    intro row mem
    unfold lastRows at mem
    split at mem
    · exact List.mem_cons_of_mem _ (ih row mem)
    · rcases List.mem_cons.mp mem with rfl | later
      · exact List.mem_cons_self
      · exact List.mem_cons_of_mem _ (ih row later)

/-- Every row a resume reads of a journal is one the run recorded, when the journal's log
was only appended rows the run recorded. -/
theorem journalRows_recorded (format : RowFormat) {log : Log} {recorded : List JournalRow}
    (reached : Log.Reachable log (recorded.map format.render)) :
    ∀ row ∈ journalRows format log, row ∈ recorded := by
  intro row mem
  obtain ⟨line, isRead, parses⟩ := List.mem_filterMap.mp mem
  obtain ⟨handed, has, starts⟩ := reached.read_given.1 line isRead
  obtain ⟨was, wasRecorded, rfl⟩ := List.mem_map.mp has
  by_cases all : line = format.render was
  · rw [all, format.whole] at parses
    cases parses
    exact wasRecorded
  · rw [format.cut was line starts all] at parses
    cases parses

/-- A resume skips a task only on a row the run recorded for the task's key: ok, not
`partial`, for a task that does not rerun on resume and whose output reads. -/
theorem resume_skips_recorded (format : RowFormat) (env : ResumeEnv) {log : Log} {recorded : List JournalRow}
    (reached : Log.Reachable log (recorded.map format.render)) (s : ResumeState) (task : Task)
    (skipped : (resumeSkip env (lastRows (journalRows format log)) s task).2 = true) :
    ∃ row ∈ recorded, row.key = task.key ∧ row.ok = true ∧ row.stop ≠ Stop.«partial»
      ∧ task.rerunOnResume = false ∧ env.reads task = true := by
  obtain ⟨row, _, _, found, _, ok, whole, _, runsOnce, reads, _⟩ := resumeSkip_sound env _ s task skipped
  have key : row.key = task.key := by simpa using List.find?_some found
  have isLast := List.mem_of_find?_eq_some found
  exact ⟨row, journalRows_recorded format reached row (lastRows_subset _ row isLast), key, ok, whole, runsOnce, reads⟩

/-- A row appended whole is among the rows a resume reads, after any appends that follow,
cut or not, and whatever the log held before, a line that a cut write left too. -/
theorem recorded_read (format : RowFormat) (log : Log) (row : JournalRow) (written : Nat)
    (all : (log.data [format.render row]).length ≤ written) (steps : List (List Line × Nat))
    (later : ∀ step ∈ steps, ∀ line ∈ step.1, newline ∉ line) :
    row ∈ journalRows format ((log.append [format.render row] written).appends steps) := by
  have plain : ∀ line ∈ [format.render row], newline ∉ line := fun line mem => by
    simp only [List.mem_singleton] at mem
    rw [mem]
    exact format.plain row
  have isRead := Log.whole_read log [format.render row] plain written all steps later (format.render row)
    List.mem_cons_self
  exact List.mem_filterMap.mpr ⟨format.render row, isRead, format.whole row⟩

/-- A resume does not skip a task whose attempt the run's end cut: one with an in-flight
marker and no row of its key from the place the marker names on. `rows`: the journal's
rows; `last`: each key's last row. -/
theorem unfinished_not_skipped (env : ResumeEnv) (rows last : List JournalRow) (markers : List (Key × Nat))
    (s : ResumeState) (task : Task) (place : Nat) (marked : (task.key, place) ∈ markers)
    (none_since : ∀ row ∈ rows.drop place, row.key ≠ task.key) :
    (resumeSkip { env with unfinished := (unfinishedKeys rows markers).contains } last s task).2 = false := by
  cases skips : (resumeSkip { env with unfinished := (unfinishedKeys rows markers).contains } last s task).2 with
  | false => rfl
  | true =>
    obtain ⟨_, _, _, _, _, _, _, _, _, _, finished⟩ := resumeSkip_sound _ last s task skips
    have listed : task.key ∈ unfinishedKeys rows markers := by
      refine List.mem_map.mpr ⟨(task.key, place), List.mem_filter.mpr ⟨marked, ?_⟩, rfl⟩
      simp only [Bool.not_eq_true', List.any_eq_false, beq_iff_eq]
      exact fun row mem => none_since row mem
    have contained : (unfinishedKeys rows markers).contains task.key = true := List.contains_iff_mem.mpr listed
    have none : (unfinishedKeys rows markers).contains task.key = false := finished
    rw [contained] at none
    cases none

/-- A marker whose attempt left a row, at the place the marker names or after it, does not
make its task unfinished: only a marker with no such row does. -/
theorem unfinishedKeys_row (rows : List JournalRow) (markers : List (Key × Nat)) (key : Key)
    (listed : key ∈ unfinishedKeys rows markers) :
    ∃ place, (key, place) ∈ markers ∧ ∀ row ∈ rows.drop place, row.key ≠ key := by
  obtain ⟨marker, kept, rfl⟩ := List.mem_map.mp listed
  obtain ⟨mem, none⟩ := List.mem_filter.mp kept
  refine ⟨marker.2, mem, fun row at_ => ?_⟩
  simp only [Bool.not_eq_true', List.any_eq_false, beq_iff_eq] at none
  exact none row at_

/-- info: 'Contraagent.unfinished_not_skipped' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms unfinished_not_skipped

/-- info: 'Contraagent.resume_skips_recorded' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms resume_skips_recorded

/-- info: 'Contraagent.recorded_read' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms recorded_read

end Contraagent
