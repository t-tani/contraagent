import Contraagent.Hub.Relay

/-!
# The hub's copy of a log is the log's first lines

Of the description of the relay's shipping: every chunk of a request holds lines of its
log from the chunk's offset on (`chunks_of_file`), so a hub that keeps every line once, in
order, and holds the first lines of the log still holds first lines of it after the chunk
(`hubTakes_prefix`): it never holds a line the log does not have in that place. And the
relay takes as its progress exactly what the hub says it holds, when that is no more than
the log has (`acceptChunk_exact`), so its next chunk starts where the hub's copy ends.
-/

namespace Contraagent

/-- A hub that holds the first lines of a log holds first lines of it after a chunk of the
log's lines from the chunk's offset on. -/
theorem hubTakes_prefix (file held : List String) (chunk : LogChunk) (count : Nat)
    (first : held <+: file) (cut : chunk.lines = (file.drop chunk.offset).take count) :
    hubTakes held chunk <+: file := by
  unfold hubTakes
  split
  · rename_i reaches
    obtain ⟨rest, whole⟩ := first
    rw [cut, List.drop_take, List.drop_drop, ← whole]
    have here : chunk.offset + (held.length - chunk.offset) = held.length := by omega
    rw [here, List.drop_left]
    exact (List.prefix_append_right_inj held).mpr (List.take_prefix _ rest)
  · exact first

namespace RunProgress

/-- Every chunk of a request holds lines of its log from the chunk's offset on. -/
theorem chunks_of_file (progress : RunProgress) (probe : Bool) (logs : List (String × List String)) :
    ∀ (budget : Nat) (chunk : LogChunk), chunk ∈ progress.chunks probe budget logs →
      ∃ file count, (chunk.log, file) ∈ logs ∧ chunk.lines = (file.drop chunk.offset).take count := by
  induction logs with
  | nil => intro budget chunk held; simp [chunks] at held
  | cons entry rest ih =>
    intro budget chunk held
    obtain ⟨log, file⟩ := entry
    unfold chunks at held
    dsimp only at held
    rcases List.mem_append.mp held with here | later
    · split at here
      · rw [List.mem_singleton] at here
        subst here
        exact ⟨file, budget, List.mem_cons_self, rfl⟩
      · cases here
    · obtain ⟨found, count, there, cut⟩ := ih _ chunk later
      exact ⟨found, count, List.mem_cons_of_mem _ there, cut⟩

theorem putLines_self (logs : List (String × Nat)) (log : String) (lines : Nat) :
    (putLines logs log lines).lookup log = some lines := by
  unfold putLines
  split
  · rename_i held
    induction logs with
    | nil => simp at held
    | cons entry rest ih =>
      obtain ⟨name, count⟩ := entry
      by_cases same : name = log
      · simp [same]
      · have keep : (name == log) = false := by simpa using same
        have differs : (log == name) = false := by simpa using fun eq : log = name => same eq.symm
        have later : rest.any (·.1 == log) = true := by simpa [keep] using held
        simp only [List.map_cons, keep, Bool.false_eq_true, ↓reduceIte, List.lookup_cons, differs]
        exact ih later
  · rename_i absent
    induction logs with
    | nil => simp
    | cons entry rest ih =>
      obtain ⟨name, count⟩ := entry
      simp only [List.any_cons, Bool.or_eq_true, not_or, beq_iff_eq] at absent
      have differs : (log == name) = false := by simpa using fun eq : log = name => absent.1 eq.symm
      simp only [List.cons_append, List.lookup_cons, differs]
      exact ih (by simpa using absent.2)

/-- The relay takes as a log's progress what the hub says it holds, when that is no more
than the log has. -/
theorem acceptChunk_exact (files : RunFiles) (accepted : List (String × Nat)) (acc : RunProgress × Bool)
    (chunk : LogChunk) (held : Nat) (answered : accepted.lookup chunk.log = some held)
    (within : held ≤ ((files.logs.lookup chunk.log).getD []).length) :
    (acceptChunk files accepted acc chunk).1.logs.lookup chunk.log = some held := by
  unfold acceptChunk
  rw [answered]
  dsimp only
  split
  · exact putLines_self _ _ _
  · rw [Nat.min_eq_left within]
    exact putLines_self _ _ _

end RunProgress

/-- info: 'Contraagent.hubTakes_prefix' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms hubTakes_prefix

end Contraagent
