import Contraagent.Hub.Core

/-!
# A prune does not take a line that arrives while it runs

A prune reads when a run was last dated, finds it old, counts its lines, and removes the
run, remembering the count. A request of the run's relay may come between any two of those
steps. It dates the run and then stores its lines, and the prune removes the run only while
the run is dated as the prune read it.

`Reachable.accounted`: whenever no request is under way, the lines the relay was last told
the hub holds are at most those the hub holds, or held when it pruned the run. So the hub
never lets the relay take a line for held that a prune removed uncounted: such a line
would not be sent again. It holds after any steps of requests and prunes in any order, when
a request stores its lines within `span` of dating the run, and `span` is within the
retention.
-/

namespace Contraagent

namespace NameHeld

/-- One name's play: what the hub holds under it, the time of the latest step, and what the
steps under way know. `request`: when the request under way dated the run. `seen`,
`readAt`, `counted`: what the prune under way read, when a batch last dated the run and
when the prune read it, and then how many lines the run holds. `told`: the lines the relay
was last told the hub holds. -/
structure Play where
  held : NameHeld := .nothing
  clock : Time := 0
  request : Option Time := none
  seen : Option Time := none
  readAt : Time := 0
  counted : Option Nat := none
  told : Nat := 0

/-- When the run was last dated; none when the name holds no run. -/
def dated : NameHeld → Option Time
  | .run _ at_ => some at_
  | _ => none

/-- The steps of requests and of prunes, in any order, at times that do not go back. A
request dates the run (`date`), stores lines within `span` of that (`store`), and tells the
relay what the hub accounts for (`answer`). A prune reads when the run was dated (`read`),
counts its lines (`count`), and removes the run when what it read is older than the
retention (`prune`). -/
inductive Reachable (retention span : Duration) : Play → Prop
  | start (clock : Time) : Reachable retention span { clock := clock, readAt := clock }
  | date {p : Play} (now : Time) : Reachable retention span p → p.clock ≤ now →
      Reachable retention span { p with held := p.held.dateRun now, clock := now, request := some now }
  | store {p : Play} (now since : Time) : Reachable retention span p → p.clock ≤ now → p.request = some since →
      now ≤ since + span → Reachable retention span { p with held := p.held.storeLine, clock := now }
  | answer {p : Play} (now : Time) : Reachable retention span p → p.clock ≤ now →
      Reachable retention span { p with clock := now, request := none, told := p.held.lines }
  | read {p : Play} (now : Time) : Reachable retention span p → p.clock ≤ now →
      Reachable retention span { p with clock := now, seen := p.held.dated, readAt := now, counted := none }
  | count {p : Play} (now : Time) : Reachable retention span p → p.clock ≤ now →
      Reachable retention span { p with clock := now, counted := some p.held.lines }
  | prune {p : Play} (now seen : Time) (counted : Nat) : Reachable retention span p → p.clock ≤ now →
      p.seen = some seen → seen < p.readAt - retention → p.counted = some counted →
      Reachable retention span
        { p with held := (p.held.pruneRun seen counted).1, clock := now, seen := none, counted := none }

/-- What every play keeps. The relay was told no more lines than the hub accounts for,
unless a request is under way. A run is dated by the request under way. The prune under
way read no later than now, and counted the lines of the run it read as old. -/
structure Safe (retention : Duration) (p : Play) : Prop where
  told : p.request = none → p.told ≤ p.held.lines
  dates : ∀ since, p.request = some since → ∀ held at_, p.held = .run held at_ → at_ = since
  read : p.readAt ≤ p.clock
  counts : ∀ seen counted, p.seen = some seen → p.counted = some counted → seen < p.readAt - retention →
    ∀ held, p.held = .run held seen → counted = held

/-! ## Times -/

theorem later_than_read {seen readAt clock now retention : Int} (old : seen < readAt - retention) (read : readAt ≤ clock)
    (later : clock ≤ now) (keeps : 0 ≤ retention) : seen ≠ now := by
  omega

theorem stores_before_read {seen readAt clock now retention span : Int} (old : seen < readAt - retention)
    (read : readAt ≤ clock) (later : clock ≤ now) (soon : now ≤ seen + span) (fits : span ≤ retention) : False := by
  omega

/-! ## Every play -/

theorem Reachable.safe {retention span : Duration} (fits : span ≤ retention) (keeps : 0 ≤ retention) {p : Play}
    (reached : Reachable retention span p) : Safe retention p := by
  induction reached with
  | start clock =>
    refine ⟨fun _ => Nat.zero_le _, ?_, Int.le_refl _, ?_⟩
    · intro _ none; cases none
    · intro _ _ none; cases none
  | @date p now _ later ih =>
    refine ⟨?_, ?_, Int.le_trans ih.read later, ?_⟩
    · intro none; cases none
    · intro since eq held at_ is
      cases eq
      cases state : p.held <;> simp only [state, NameHeld.dateRun] at is <;> cases is <;> rfl
    · intro seen counted wasSeen wasCounted old held is
      cases state : p.held <;> simp only [state, NameHeld.dateRun] at is <;> cases is <;>
        exact absurd rfl (later_than_read old ih.read later keeps)
  | @store p now since _ later open_ soon ih =>
    refine ⟨?_, ?_, Int.le_trans ih.read later, ?_⟩
    · intro none; rw [open_] at none; cases none
    · intro other eq held at_ is
      cases state : p.held with
      | nothing => simp only [state, NameHeld.storeLine] at is; cases is
      | pruned n => simp only [state, NameHeld.storeLine] at is; cases is
      | run n at' =>
        simp only [state, NameHeld.storeLine] at is
        cases is
        exact ih.dates other eq n at_ state
    · intro seen counted wasSeen wasCounted old held is
      cases state : p.held with
      | nothing => simp only [state, NameHeld.storeLine] at is; cases is
      | pruned n => simp only [state, NameHeld.storeLine] at is; cases is
      | run n at' =>
        simp only [state, NameHeld.storeLine] at is
        cases is
        have same : seen = since := ih.dates since open_ n seen state
        exact (stores_before_read old ih.read later (same ▸ soon) fits).elim
  | @answer p now _ later ih =>
    refine ⟨fun _ => Nat.le_refl _, ?_, Int.le_trans ih.read later, ih.counts⟩
    intro _ none; cases none
  | @read p now _ later ih =>
    refine ⟨ih.told, ih.dates, Int.le_refl _, ?_⟩
    intro _ _ _ none; cases none
  | @count p now _ later ih =>
    refine ⟨ih.told, ih.dates, Int.le_trans ih.read later, ?_⟩
    intro seen counted _ wasCounted _ held is
    cases wasCounted
    rw [is]
    rfl
  | @prune p now seen counted _ later wasSeen old wasCounted ih =>
    refine ⟨?_, ?_, Int.le_trans ih.read later, ?_⟩
    rotate_left 2
    · intro _ _ none; cases none
    · intro none
      cases state : p.held with
      | nothing => simpa [state, NameHeld.pruneRun] using ih.told none
      | pruned n => simpa [state, NameHeld.pruneRun] using ih.told none
      | run n at' =>
        have before := ih.told none
        rw [state] at before
        by_cases same : (at' == seen) = true
        · have eq : at' = seen := by simpa using same
          have exact := ih.counts seen counted wasSeen wasCounted old n (eq ▸ state)
          simp only [NameHeld.pruneRun, same, ↓reduceIte, NameHeld.lines]
          rw [exact]
          exact before
        · simpa [NameHeld.pruneRun, same] using before
    · intro since eq held at_ is
      cases state : p.held with
      | nothing => simp only [state, NameHeld.pruneRun] at is; cases is
      | pruned n => simp only [state, NameHeld.pruneRun] at is; cases is
      | run n at' =>
        by_cases same : (at' == seen) = true
        · simp only [state, NameHeld.pruneRun, same, ↓reduceIte] at is; cases is
        · simp only [state, NameHeld.pruneRun, same, Bool.false_eq_true, ↓reduceIte] at is
          have both := NameHeld.run.inj is
          rw [← both.2]
          exact ih.dates since eq n at' state

/-- Whenever no request is under way, the lines the relay was last told the hub holds are at
most those the hub holds, or held when it pruned the run: a prune takes no line uncounted,
whatever request arrives while it runs. A request stores its lines within `span` of dating
the run, and `span` is within the retention. -/
theorem Reachable.accounted {retention span : Duration} (fits : span ≤ retention) (keeps : 0 ≤ retention) {p : Play}
    (reached : Reachable retention span p) (idle : p.request = none) : p.told ≤ p.held.lines :=
  (reached.safe fits keeps).told idle

end NameHeld

/-- info: 'Contraagent.NameHeld.Reachable.accounted' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms NameHeld.Reachable.accounted

end Contraagent
