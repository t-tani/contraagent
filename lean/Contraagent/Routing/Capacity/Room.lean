import Contraagent.Routing.Capacity

/-!
# A run always goes on

Of the description of `HostCapacity`: while no running task holds memory, a name that no
task holds admits one task, whatever the host reads. So a queue with nothing running always
finds room for a task whose capacities are sized by the host.
-/

namespace Contraagent.HostState

theorem read_tasks (s : HostState) (host : HostReading) : (s.read host).1.tasks = s.tasks := by
  unfold read
  split <;> rfl

theorem more_tasks (s : HostState) (host : HostReading) (memoryMb : Nat) :
    (s.more host memoryMb).1.tasks = s.tasks := by
  unfold more
  dsimp only
  split <;> exact read_tasks s host

theorem more_holdsMemory (s : HostState) (host : HostReading) (memoryMb : Nat) :
    (s.more host memoryMb).1.holdsMemory = s.holdsMemory := by
  unfold holdsMemory
  rw [more_tasks]

theorem tighter_least (a b : Option Nat) (least : Nat) (ha : ∀ x, a = some x → least ≤ x)
    (hb : ∀ x, b = some x → least ≤ x) : ∀ x, tighter a b = some x → least ≤ x := by
  intro x eq
  cases a <;> cases b <;> simp only [tighter] at eq
  · cases eq
  · exact hb x eq
  · exact ha x eq
  · rename_i va vb
    have := ha va rfl
    have := hb vb rfl
    cases eq
    exact Nat.le_min.mpr ⟨by assumption, by assumption⟩

theorem coresLimit_one (s : HostState) (need : PerTask) : ∀ x, s.coresLimit need = some x → 1 ≤ x := by
  intro x eq
  unfold coresLimit at eq
  split at eq
  · split at eq
    · cases eq
    · cases eq
      exact Nat.le_max_right _ _
  · cases eq

/-- While no running task holds memory, the memory lets a name with no holder admit one
task. -/
theorem memoryLimit_one (s : HostState) (host : HostReading) (need : PerTask) (idle : s.holdsMemory = false) :
    ∀ x, (s.memoryLimit host need 0).2 = some x → 1 ≤ x := by
  intro x eq
  unfold memoryLimit at eq
  split at eq
  · rename_i memoryMb _
    split at eq
    · cases eq
    · dsimp only at eq
      have still := more_holdsMemory s host memoryMb
      rw [idle] at still
      cases room : (s.more host memoryMb).2 with
      | none => simp [room] at eq
      | some free =>
        simp only [room, Option.map_some, still] at eq
        cases eq
        simp
        exact Nat.le_max_right _ _
  · cases eq

/-- While no running task holds memory, a name with no holder admits at least one task:
the answer is a number of 1 or more, or no limit. -/
theorem allowed_one (s : HostState) (host : HostReading) (need : PerTask)
    (idle : s.holdsMemory = false) (n : Nat) (answer : (s.allowed host need 0).2 = some n) : 1 ≤ n := by
  unfold allowed at answer
  exact tighter_least _ _ 1 (memoryLimit_one s host need idle) (coresLimit_one _ need) n answer

/-- info: 'Contraagent.HostState.allowed_one' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms allowed_one

end Contraagent.HostState
