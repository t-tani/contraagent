import Contraagent.Dispatch.Flow

/-!
# The order in which the flow code gets results

On a resume, the queue skips the tasks that finished in the first run, and their results
come in an order of its own. The driver gives them to the flow code by the place of each
key in the first run: the result given next is, of those kept, the one with the least
place, and of two with one place the one that came first (`next_least`). So the flow code
gets the skipped results in the order of the first run, whatever order they come in. With
no skipped result kept, the result given next is the one that came first (`next_oldest`).
-/

namespace Contraagent

namespace FlowDriverState

/-- A kept result of a skipped task: its key's place on a resume, the order it came in, and
the result. -/
abbrev Replayed := Nat × Nat × FlowResult

/-- `a` is given no later than `b`: a lower place, or one place and it came no later. -/
def Replayed.before (a b : Replayed) : Prop :=
  a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2.1 ≤ b.2.1)

theorem Replayed.before_trans {a b c : Replayed} (first : Replayed.before a b) (second : Replayed.before b c) :
    Replayed.before a c := by
  unfold Replayed.before at *
  omega

theorem earlier_cases (best entry : Replayed) :
    (earlier best entry = best ∨ earlier best entry = entry)
      ∧ Replayed.before (earlier best entry) best ∧ Replayed.before (earlier best entry) entry := by
  by_cases takes : (entry.1 < best.1 || (entry.1 == best.1 && entry.2.1 < best.2.1)) = true
  · have chosen : earlier best entry = entry := by simp only [earlier, takes, ↓reduceIte]
    rw [chosen]
    simp only [Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true, beq_iff_eq] at takes
    unfold Replayed.before
    exact ⟨Or.inr rfl, by omega, by omega⟩
  · have chosen : earlier best entry = best := by simp only [earlier, takes, Bool.false_eq_true, ↓reduceIte]
    rw [chosen]
    simp only [Bool.or_eq_true, decide_eq_true_eq, Bool.and_eq_true, beq_iff_eq, not_or, not_and] at takes
    unfold Replayed.before
    exact ⟨Or.inl rfl, by omega, by omega⟩

/-- The choice over a list is one of its entries, and is given no later than any. -/
theorem foldl_earlier (first : Replayed) (rest : List Replayed) :
    rest.foldl earlier first ∈ first :: rest
      ∧ ∀ entry ∈ first :: rest, Replayed.before (rest.foldl earlier first) entry := by
  induction rest generalizing first with
  | nil => exact ⟨List.mem_cons_self, fun entry mem => by
      simp only [List.mem_singleton] at mem
      subst mem
      exact Or.inr ⟨rfl, Nat.le_refl _⟩⟩
  | cons second rest ih =>
    rw [List.foldl_cons]
    obtain ⟨which, beforeFirst, beforeSecond⟩ := earlier_cases first second
    obtain ⟨held, least⟩ := ih (earlier first second)
    refine ⟨?_, ?_⟩
    · rcases List.mem_cons.mp held with here | later
      · rw [here]
        rcases which with same | same <;> rw [same] <;> simp
      · exact List.mem_cons_of_mem _ (List.mem_cons_of_mem _ later)
    · intro entry mem
      have chosen := least (earlier first second) List.mem_cons_self
      rcases List.mem_cons.mp mem with here | later
      · rw [here]; exact Replayed.before_trans chosen beforeFirst
      · rcases List.mem_cons.mp later with here | later
        · rw [here]; exact Replayed.before_trans chosen beforeSecond
        · exact least entry (List.mem_cons_of_mem _ later)

/-- While results of skipped tasks are kept, the result given next is one of them, with the
least place on a resume, and of those with that place the one that came first. -/
theorem next_least (s : FlowDriverState) (kept : s.replayed ≠ []) :
    ∃ best ∈ s.replayed, s.next = some best.2.2 ∧ ∀ entry ∈ s.replayed, Replayed.before best entry := by
  unfold FlowDriverState.next
  cases replayed : s.replayed with
  | nil => exact absurd replayed kept
  | cons first rest =>
    have chosen := foldl_earlier first rest
    exact ⟨rest.foldl earlier first, chosen.1, rfl, chosen.2⟩

/-- With no result of a skipped task kept, the result given next is the one that came
first. -/
theorem next_oldest (s : FlowDriverState) (none : s.replayed = []) : s.next = s.results.head? := by
  unfold FlowDriverState.next
  rw [none]

end FlowDriverState

/-- info: 'Contraagent.FlowDriverState.next_least' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms FlowDriverState.next_least

end Contraagent
