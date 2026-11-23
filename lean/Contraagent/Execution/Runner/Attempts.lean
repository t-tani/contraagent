import Contraagent.Execution.Runner

/-!
# The attempts of a task

Of the description of `RetryingRunner.run`: a task gets one attempt and `retries` more at
most (`attempts_journaled`), it always ends with a result (`attempts_result`), and the
journal gets no deferred attempt, which launched nothing (`attempts_launched`).
-/

namespace Contraagent.RetryConfig

theorem attemptsFrom_journaled {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult) :
    ∀ (left attempt : Nat) (surroundings : σ),
      (cfg.attemptsFrom run left attempt surroundings).2.1.length ≤ left ∧
        ∀ result ∈ (cfg.attemptsFrom run left attempt surroundings).2.1, result.stop ≠ Stop.deferred := by
  intro left
  induction left with
  | zero => intro attempt surroundings; simp [attemptsFrom]
  | succ left ih =>
    intro attempt surroundings
    unfold attemptsFrom
    dsimp only
    split
    · simp
    · rename_i launched
      have stop : (run attempt surroundings).2.stop ≠ Stop.deferred := by simpa using launched
      split
      · obtain ⟨few, stops⟩ := ih (attempt + 1) (run attempt surroundings).1
        refine ⟨by simpa using few, ?_⟩
        intro result held
        rcases List.mem_cons.mp held with first | later
        · rw [first]; exact stop
        · exact stops result later
      · refine ⟨by simp, ?_⟩
        intro result held
        rw [List.mem_singleton.mp held]
        exact stop

/-- The journal gets one attempt of a task and `retries` more at most. -/
theorem attempts_journaled {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult)
    (surroundings : σ) : (cfg.attempts run surroundings).2.1.length ≤ 1 + cfg.retries.toNat :=
  (cfg.attemptsFrom_journaled run _ 0 surroundings).1

/-- The journal gets no deferred attempt. -/
theorem attempts_launched {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult)
    (surroundings : σ) : ∀ result ∈ (cfg.attempts run surroundings).2.1, result.stop ≠ Stop.deferred :=
  (cfg.attemptsFrom_journaled run _ 0 surroundings).2

theorem attemptsFrom_result {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult) :
    ∀ (left attempt : Nat) (surroundings : σ),
      ∃ result, (cfg.attemptsFrom run (left + 1) attempt surroundings).2.2 = some result := by
  intro left
  induction left with
  | zero =>
    intro attempt surroundings
    unfold attemptsFrom
    dsimp only
    split
    · exact ⟨_, rfl⟩
    · simp
  | succ left ih =>
    intro attempt surroundings
    unfold attemptsFrom
    dsimp only
    split
    · exact ⟨_, rfl⟩
    · split
      · exact ih (attempt + 1) (run attempt surroundings).1
      · exact ⟨_, rfl⟩

/-- A task ends with a result: that of its last attempt. -/
theorem attempts_result {σ : Type} (cfg : RetryConfig) (run : Nat → σ → σ × AttemptResult)
    (surroundings : σ) : ∃ result, (cfg.attempts run surroundings).2.2 = some result := by
  unfold attempts
  rw [Nat.add_comm]
  exact cfg.attemptsFrom_result run _ 0 surroundings

/-- info: 'Contraagent.RetryConfig.attempts_journaled' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms attempts_journaled

end Contraagent.RetryConfig
