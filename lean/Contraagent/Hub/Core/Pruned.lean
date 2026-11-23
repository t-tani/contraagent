import Contraagent.Hub.Core

/-!
# A pruned run stays pruned until it grows

Of the description of the hub's answer for a run it pruned: a request that brings no line
is always answered, and stores nothing (`answer_of_probe`); every answer names at least
the lines of the chunk's offset, so the relay finds no line lost and does not send the run
again (`answer_no_loss`, with `acceptChunk_kept` of the relay); and the hub stores the run
again exactly when a chunk brings a line past those it held (`answer_none_iff`).
-/

namespace Contraagent

namespace PrunedRun

/-- The hub stores a pruned run again exactly when a chunk brings a line past those the
hub held of its log. -/
theorem answer_none_iff (pruned : PrunedRun) (chunks : List LogChunk) :
    pruned.answer chunks = none ↔
      ∃ chunk ∈ chunks, chunk.lines ≠ [] ∧ chunk.offset + chunk.lines.length > pruned.held chunk.log := by
  unfold answer
  constructor
  · intro stored
    split at stored
    · rename_i some
      obtain ⟨chunk, held, grows⟩ := List.any_eq_true.mp some
      simp only [PrunedRun.grows, Bool.and_eq_true, Bool.not_eq_true', List.isEmpty_eq_false_iff, decide_eq_true_eq] at grows
      exact ⟨chunk, held, grows.1, grows.2⟩
    · cases stored
  · rintro ⟨chunk, held, lines, past⟩
    have some : chunks.any pruned.grows = true := by
      rw [List.any_eq_true]
      refine ⟨chunk, held, ?_⟩
      simp only [PrunedRun.grows, Bool.and_eq_true, Bool.not_eq_true', List.isEmpty_eq_false_iff, decide_eq_true_eq]
      exact ⟨lines, past⟩
    simp [some]

/-- A request that brings no line, as the one by which a relay asks what the hub holds, is
answered: the hub stores nothing of a pruned run for it. -/
theorem answer_of_probe (pruned : PrunedRun) (chunks : List LogChunk) (asks : ∀ chunk ∈ chunks, chunk.lines = []) :
    ∃ held, pruned.answer chunks = some held := by
  cases answered : pruned.answer chunks with
  | some held => exact ⟨held, rfl⟩
  | none =>
    obtain ⟨chunk, there, lines, _⟩ := (pruned.answer_none_iff chunks).mp answered
    exact absurd (asks chunk there) lines

/-- An answer names, for each chunk, at least the lines of the chunk's offset: in the
place of the chunk in the request. -/
theorem answer_no_loss (pruned : PrunedRun) (chunks : List LogChunk) (held : List (String × Nat))
    (answered : pruned.answer chunks = some held) :
    held = chunks.map (fun chunk => (chunk.log, max (pruned.held chunk.log) chunk.offset)) ∧
      ∀ chunk ∈ chunks, chunk.offset ≤ max (pruned.held chunk.log) chunk.offset := by
  unfold answer at answered
  split at answered
  · cases answered
  · simp only [Option.some.injEq] at answered
    exact ⟨answered.symm, fun chunk _ => Nat.le_max_right _ _⟩

end PrunedRun

namespace RunProgress

/-- A relay that is told the hub holds at least the lines of a chunk's offset finds no
line lost by that chunk. -/
theorem acceptChunk_kept (files : RunFiles) (accepted : List (String × Nat)) (acc : RunProgress × Bool)
    (chunk : LogChunk) (held : Nat) (answered : accepted.lookup chunk.log = some held) (enough : chunk.offset ≤ held) :
    (acceptChunk files accepted acc chunk).2 = acc.2 := by
  unfold acceptChunk
  rw [answered]
  dsimp only
  split
  · rfl
  · have none : decide (held < chunk.offset) = false := by simpa using enough
    rw [none, Bool.or_false]

end RunProgress

/-- info: 'Contraagent.PrunedRun.answer_none_iff' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms PrunedRun.answer_none_iff

end Contraagent
