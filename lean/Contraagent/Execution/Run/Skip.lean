import Contraagent.Execution.Run

/-!
# What a skip rests on

Of the description of `resume_skip`: a task is skipped only when its key's last row is ok
and not `partial`, the task does not rerun on resume, its output reads, and the row holds
the fingerprint the task is judged by; and the history of a file that tasks fill in is
that file's own.
-/

namespace Contraagent

/-- A resume skips a task only on its key's last row: ok, not `partial`, with the
fingerprint the task is judged by (`judged`), for a task that does not rerun on resume and
whose output reads. -/
theorem resumeSkip_sound (env : ResumeEnv) (rows : List JournalRow) (s : ResumeState) (task : Task)
    (skipped : (resumeSkip env rows s task).2 = true) :
    ∃ row as fingerprint,
      rows.find? (·.key == task.key) = some row ∧ judged env rows row task = some (as, fingerprint)
        ∧ row.ok = true ∧ row.stop ≠ Stop.«partial» ∧ row.fingerprint = fingerprint
        ∧ task.rerunOnResume = false ∧ env.reads task = true := by
  unfold resumeSkip at skipped
  split at skipped
  · simp at skipped
  · rename_i row found
    cases same : judged env rows row task with
    | none =>
      simp [same] at skipped
      split at skipped <;> simp at skipped
    | some pair =>
      obtain ⟨as, fingerprint⟩ := pair
      refine ⟨row, as, fingerprint, found, same, ?_⟩
      simp only [same] at skipped
      by_cases finished : finishedBefore row task fingerprint = true
      · by_cases reads : env.reads task = true
        · simp [finishedBefore] at finished
          exact ⟨finished.1.2, by simpa using finished.1.1.2, finished.2, finished.1.1.1, reads⟩
        · simp [finished, reads] at skipped
          split at skipped <;> simp at skipped
      · simp [finished] at skipped
        split at skipped <;> simp at skipped

/-- A task that fills in no file is judged as it is, by its own fingerprint. -/
theorem judged_plain (env : ResumeEnv) (rows : List JournalRow) (row : JournalRow) (task : Task)
    (plain : partOf task.fingerprintParts "output_of" = none) :
    judged env rows row task = some (task, task.fingerprint) := by
  simp [judged, plain]

/-- A skipped task that fills in no file has the fingerprint of its key's last row. -/
theorem resumeSkip_same_fingerprint (env : ResumeEnv) (rows : List JournalRow) (s : ResumeState)
    (task : Task) (plain : partOf task.fingerprintParts "output_of" = none)
    (skipped : (resumeSkip env rows s task).2 = true) :
    ∃ row, rows.find? (·.key == task.key) = some row ∧ row.fingerprint = task.fingerprint := by
  obtain ⟨row, as, fingerprint, found, same, _, _, eq, _, _⟩ := resumeSkip_sound env rows s task skipped
  rw [judged_plain env rows row task plain] at same
  cases same
  exact ⟨row, found, eq⟩

/-- The history of a file is its own: the rows of tasks that fill in another file add
nothing to the digests it may hold. -/
theorem leftDigests_own_file (rows : List JournalRow) (file : String) :
    ∀ (rounds : Nat) (reached : List String),
      leftDigests rows file rounds reached
        = leftDigests (rows.filter (·.outputOfFile == file)) file rounds reached := by
  intro rounds
  induction rounds with
  | zero => intro reached; rfl
  | succ rounds ih =>
    intro reached
    simp only [leftDigests]
    rw [ih]
    congr 2
    rw [List.filterMap_filter]
    refine congrArg (fun select => (List.filterMap select rows).eraseDups) ?_
    funext r
    by_cases own : (r.outputOfFile == file) = true
    · simp [own]
    · simp [own]
      split <;> rfl

/-- info: 'Contraagent.resumeSkip_sound' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms resumeSkip_sound

end Contraagent
