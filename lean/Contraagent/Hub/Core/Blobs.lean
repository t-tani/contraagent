import Contraagent.Hub.Core

/-!
# A file ref names a blob the hub holds

A prune removes the blobs that no file ref names, while relays go on sending file refs. A
relay that finds the hub holds a blob sends a file ref without the blob's content, so the
blob must stay until the file ref arrives. Two things make it stay. Asking for a blob
renews it (`hasBlob`), as storing it does, and a prune removes a blob only when the blob is
still dated, as it is removed, before the grace of the time the prune began (`expire`).

`Reachable.refs_held`: every file ref names a blob the hub holds, after any steps of relays
and prunes in any order, however long a prune takes, when each file ref arrives within
`delay` of its relay's asking for the blob or storing it, and `delay` is within the grace.
-/

namespace Contraagent

namespace BlobsState

/-- The blobs and the file refs, with the times the theorem speaks of. `clock`: the time of
the latest step. `asked`: each blob a relay asked for and was told the hub holds, or
stored, with when. `markedAt`: when the latest prune read the file refs. -/
structure Play where
  state : BlobsState := {}
  clock : Time := 0
  asked : List (String × Time) := []
  markedAt : Time := 0

/-- Every blob of `sha` the hub holds is dated at `since` or later. -/
def DatedFrom (s : BlobsState) (sha : String) (since : Time) : Prop :=
  ∀ blob ∈ s.blobs, blob.1 = sha → since ≤ blob.2

/-- What relays and prunes do, in any order, at times that do not go back. A file ref
arrives within `delay` of its relay's asking for the blob or storing it. A prune removes
the blobs it marked at any later times, each when it is still dated before the grace of the
time the prune read the file refs. -/
inductive Reachable (grace delay : Duration) : Play → Prop
  | start (clock : Time) : Reachable grace delay { clock := clock, markedAt := clock }
  | has {p : Play} (now : Time) (sha : String) : Reachable grace delay p → p.clock ≤ now →
      Reachable grace delay
        { state := (p.state.hasBlob now sha).1, clock := now,
          asked := if p.state.holds sha then (sha, now) :: p.asked else p.asked, markedAt := p.markedAt }
  | put {p : Play} (now : Time) (sha : String) : Reachable grace delay p → p.clock ≤ now →
      Reachable grace delay
        { state := p.state.putBlob now sha, clock := now, asked := (sha, now) :: p.asked, markedAt := p.markedAt }
  | ref {p : Play} (now : Time) (sha : String) (since : Time) : Reachable grace delay p → p.clock ≤ now →
      (sha, since) ∈ p.asked → now ≤ since + delay →
      Reachable grace delay { state := p.state.fileRef sha, clock := now, asked := p.asked, markedAt := p.markedAt }
  | forget {p : Play} (now : Time) (sha : String) : Reachable grace delay p → p.clock ≤ now →
      Reachable grace delay { state := p.state.forget sha, clock := now, asked := p.asked, markedAt := p.markedAt }
  | mark {p : Play} (now : Time) : Reachable grace delay p → p.clock ≤ now →
      Reachable grace delay { state := p.state.mark (now - grace), clock := now, asked := p.asked, markedAt := now }
  | expire {p : Play} (now : Time) (sha : String) : Reachable grace delay p → p.clock ≤ now →
      sha ∈ p.state.marked →
      Reachable grace delay
        { state := (p.state.expire (p.markedAt - grace) sha).1, clock := now, asked := p.asked,
          markedAt := p.markedAt }

/-- What every play keeps. Each file ref names a blob held, and one that a prune marked is
dated late enough for the prune to leave it. Each blob a relay asked for or stored is held,
and dated no earlier than that, while its file ref may still arrive. -/
structure Safe (delay : Duration) (p : Play) : Prop where
  refs : ∀ sha ∈ p.state.refs,
    p.state.holds sha = true ∧ (sha ∈ p.state.marked → p.state.DatedFrom sha (p.markedAt - delay))
  asked : ∀ entry ∈ p.asked,
    entry.2 ≤ p.clock ∧ (p.clock ≤ entry.2 + delay → p.state.holds entry.1 = true ∧ p.state.DatedFrom entry.1 entry.2)
  marked : p.markedAt ≤ p.clock

/-! ## Each step on the blobs -/

theorem holds_renew (s : BlobsState) (now : Time) (sha other : String) :
    (s.renew now sha).holds other = s.holds other := by
  simp only [holds, renew, List.any_map]
  congr 1
  funext blob
  by_cases its : blob.1 = sha <;> simp [its]

/-- A renewed blob is dated now, and every other blob as it was. -/
theorem datedFrom_renew {s : BlobsState} {other : String} {since : Time} (now : Time) (sha : String)
    (dated : s.DatedFrom other since ∨ other = sha) (early : since ≤ now) : (s.renew now sha).DatedFrom other since := by
  intro blob mem its
  obtain ⟨was, wasMem, rfl⟩ := List.mem_map.mp mem
  by_cases renewed : (was.1 == sha) = true
  · simpa [renewed] using early
  · simp only [renewed, Bool.false_eq_true, ↓reduceIte] at its ⊢
    rcases dated with dated | same
    · exact dated was wasMem its
    · exact absurd (its.trans same) (by simpa using renewed)

theorem holds_putBlob (s : BlobsState) (now : Time) (sha : String) :
    (s.putBlob now sha).holds sha = true ∧ ∀ other, s.holds other = true → (s.putBlob now sha).holds other = true := by
  unfold putBlob
  by_cases held : s.holds sha = true
  · simp only [held, ↓reduceIte, holds_renew]
    exact ⟨trivial, fun _ was => was⟩
  · simp only [held, Bool.false_eq_true, ↓reduceIte]
    refine ⟨by simp [holds], fun other was => ?_⟩
    simp only [holds, List.any_append, Bool.or_eq_true]
    exact Or.inl was

theorem datedFrom_putBlob {s : BlobsState} {other : String} {since : Time} (now : Time) (sha : String)
    (dated : s.DatedFrom other since ∨ other = sha) (early : since ≤ now) :
    (s.putBlob now sha).DatedFrom other since := by
  unfold putBlob
  by_cases held : s.holds sha = true
  · simp only [held, ↓reduceIte]
    exact datedFrom_renew now sha dated early
  · simp only [held, Bool.false_eq_true, ↓reduceIte]
    intro blob mem its
    rcases List.mem_append.mp mem with old | new
    · rcases dated with dated | same
      · exact dated blob old its
      · refine absurd (List.any_eq_true.mpr ⟨blob, old, ?_⟩) held
        simpa using its.trans same
    · simp only [List.mem_singleton] at new
      rw [new]
      exact early

/-- A blob that `expire` does not remove is held as it was, and dated as it was. -/
theorem expire_other (s : BlobsState) (old : Time) (sha other : String) (differs : other ≠ sha) :
    (s.holds other = true → (s.expire old sha).1.holds other = true)
      ∧ ∀ since, s.DatedFrom other since → (s.expire old sha).1.DatedFrom other since := by
  unfold expire
  split
  · refine ⟨fun was => ?_, fun since dated blob mem its => dated blob (List.mem_filter.mp mem).1 its⟩
    obtain ⟨blob, mem, its⟩ := List.any_eq_true.mp was
    refine List.any_eq_true.mpr ⟨blob, List.mem_filter.mpr ⟨mem, ?_⟩, its⟩
    have name : blob.1 = other := by simpa using its
    simpa [name] using differs
  · exact ⟨fun was => was, fun since dated => dated⟩

/-- `expire` removes only a blob dated before `old`, and leaves any blob dated later as it
was. -/
theorem expire_dated (s : BlobsState) (old : Time) (sha : String) {since : Time} (held : s.holds sha = true)
    (dated : s.DatedFrom sha since) (late : old ≤ since) :
    (s.expire old sha).1.holds sha = true ∧ (s.expire old sha).1.DatedFrom sha since := by
  unfold expire
  split
  · rename_i removes
    obtain ⟨blob, mem, its⟩ := List.any_eq_true.mp removes
    simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at its
    exact absurd (Int.lt_of_lt_of_le its.2 (Int.le_trans late (dated blob mem its.1))) (Int.lt_irrefl _)
  · exact ⟨held, dated⟩

theorem expire_refs (s : BlobsState) (old : Time) (sha : String) : (s.expire old sha).1.refs = s.refs := by
  unfold expire
  split <;> rfl

theorem expire_marked (s : BlobsState) (old : Time) (sha other : String)
    (marked : other ∈ (s.expire old sha).1.marked) : other ∈ s.marked := by
  unfold expire at marked
  split at marked <;> exact (List.mem_filter.mp marked).1

theorem DatedFrom.mono {s : BlobsState} {sha : String} {since earlier : Time} (dated : s.DatedFrom sha since)
    (le : earlier ≤ since) : s.DatedFrom sha earlier :=
  fun blob mem its => Int.le_trans le (dated blob mem its)

theorem putBlob_same (s : BlobsState) (now : Time) (sha : String) :
    (s.putBlob now sha).refs = s.refs ∧ (s.putBlob now sha).marked = s.marked := by
  unfold putBlob
  split <;> exact ⟨rfl, rfl⟩

/-! ## Times -/

theorem before_now {marked clock now delay : Int} (first : marked ≤ clock) (later : clock ≤ now) (waits : 0 ≤ delay) :
    marked - delay ≤ now := by
  omega

theorem before_asked {marked clock now since delay : Int} (first : marked ≤ clock) (later : clock ≤ now)
    (soon : now ≤ since + delay) : marked - delay ≤ since := by
  omega

theorem late_for_marked {marked grace delay : Int} (fits : delay ≤ grace) : marked - grace ≤ marked - delay := by
  omega

theorem late_for_asked {marked clock now since grace delay : Int} (first : marked ≤ clock) (later : clock ≤ now)
    (soon : now ≤ since + delay) (fits : delay ≤ grace) : marked - grace ≤ since := by
  omega

/-! ## Every play -/

theorem Reachable.safe {grace delay : Duration} (fits : delay ≤ grace) (waits : 0 ≤ delay) {p : Play}
    (reached : Reachable grace delay p) : Safe delay p := by
  induction reached with
  | start clock => refine ⟨?_, ?_, Int.le_refl _⟩ <;> intro _ mem <;> cases mem
  | @has p now sha _ later ih =>
    by_cases held : p.state.holds sha = true
    · simp only [hasBlob, held, ↓reduceIte]
      refine ⟨?_, ?_, Int.le_trans ih.marked later⟩
      · intro other mem
        obtain ⟨was, dated⟩ := ih.refs other mem
        have early : p.markedAt - delay ≤ now := before_now ih.marked later waits
        exact ⟨by rw [holds_renew]; exact was, fun marked => datedFrom_renew now sha (Or.inl (dated marked)) early⟩
      · intro entry mem
        rcases List.mem_cons.mp mem with rfl | old
        · exact ⟨Int.le_refl _, fun _ => ⟨by rw [holds_renew]; exact held,
            datedFrom_renew now sha (Or.inr rfl) (Int.le_refl _)⟩⟩
        · obtain ⟨before, pending⟩ := ih.asked entry old
          refine ⟨Int.le_trans before later, fun soon => ?_⟩
          obtain ⟨was, dated⟩ := pending (Int.le_trans later soon)
          exact ⟨by rw [holds_renew]; exact was, datedFrom_renew now sha (Or.inl dated) (Int.le_trans before later)⟩
    · simp only [hasBlob, held, Bool.false_eq_true, ↓reduceIte]
      refine ⟨ih.refs, ?_, Int.le_trans ih.marked later⟩
      intro entry mem
      obtain ⟨before, pending⟩ := ih.asked entry mem
      exact ⟨Int.le_trans before later, fun soon => pending (Int.le_trans later soon)⟩
  | @put p now sha _ later ih =>
    have same := putBlob_same p.state now sha
    have holds := holds_putBlob p.state now sha
    refine ⟨?_, ?_, Int.le_trans ih.marked later⟩
    · intro other mem
      rw [same.1] at mem
      obtain ⟨was, dated⟩ := ih.refs other mem
      have early : p.markedAt - delay ≤ now := before_now ih.marked later waits
      refine ⟨holds.2 other was, fun marked => ?_⟩
      rw [same.2] at marked
      exact datedFrom_putBlob now sha (Or.inl (dated marked)) early
    · intro entry mem
      rcases List.mem_cons.mp mem with rfl | old
      · exact ⟨Int.le_refl _, fun _ => ⟨holds.1, datedFrom_putBlob now sha (Or.inr rfl) (Int.le_refl _)⟩⟩
      · obtain ⟨before, pending⟩ := ih.asked entry old
        refine ⟨Int.le_trans before later, fun soon => ?_⟩
        obtain ⟨was, dated⟩ := pending (Int.le_trans later soon)
        exact ⟨holds.2 entry.1 was, datedFrom_putBlob now sha (Or.inl dated) (Int.le_trans before later)⟩
  | @ref p now sha since _ later asked soon ih =>
    refine ⟨?_, ?_, Int.le_trans ih.marked later⟩
    · intro other mem
      rcases List.mem_append.mp mem with old | new
      · exact ih.refs other old
      · simp only [List.mem_singleton] at new
        subst new
        obtain ⟨_, pending⟩ := ih.asked (other, since) asked
        obtain ⟨was, dated⟩ := pending (Int.le_trans later soon)
        exact ⟨was, fun _ => dated.mono (before_asked ih.marked later soon)⟩
    · intro entry mem
      obtain ⟨before, pending⟩ := ih.asked entry mem
      exact ⟨Int.le_trans before later, fun soon => pending (Int.le_trans later soon)⟩
  | @forget p now sha _ later ih =>
    refine ⟨fun other mem => ih.refs other (List.mem_filter.mp mem).1, ?_, Int.le_trans ih.marked later⟩
    intro entry mem
    obtain ⟨before, pending⟩ := ih.asked entry mem
    exact ⟨Int.le_trans before later, fun soon => pending (Int.le_trans later soon)⟩
  | @mark p now _ later ih =>
    refine ⟨?_, ?_, Int.le_refl _⟩
    · intro other mem
      refine ⟨(ih.refs other mem).1, fun marked => ?_⟩
      obtain ⟨blob, chosen, its⟩ := List.mem_map.mp marked
      have unnamed : (decide (blob.2 < now - grace) && !p.state.refs.contains blob.1) = true :=
        (List.mem_filter.mp chosen).2
      have named : p.state.refs.contains blob.1 = true := List.contains_iff_mem.mpr (its ▸ mem)
      rw [named] at unnamed
      simp at unnamed
    · intro entry mem
      obtain ⟨before, pending⟩ := ih.asked entry mem
      exact ⟨Int.le_trans before later, fun soon => pending (Int.le_trans later soon)⟩
  | @expire p now sha _ later marked ih =>
    refine ⟨?_, ?_, Int.le_trans ih.marked later⟩
    · intro other mem
      rw [expire_refs] at mem
      obtain ⟨was, dated⟩ := ih.refs other mem
      by_cases same : other = sha
      · subst same
        have kept := expire_dated p.state (p.markedAt - grace) other was (dated marked) (late_for_marked fits)
        exact ⟨kept.1, fun _ => kept.2⟩
      · have kept := expire_other p.state (p.markedAt - grace) sha other same
        exact ⟨kept.1 was, fun still => kept.2 _ (dated (expire_marked p.state _ sha other still))⟩
    · intro entry mem
      obtain ⟨before, pending⟩ := ih.asked entry mem
      refine ⟨Int.le_trans before later, fun soon => ?_⟩
      obtain ⟨was, dated⟩ := pending (Int.le_trans later soon)
      by_cases same : entry.1 = sha
      · have kept := expire_dated p.state (p.markedAt - grace) entry.1 was dated (late_for_asked ih.marked later soon fits)
        rw [same] at kept ⊢
        exact kept
      · have kept := expire_other p.state (p.markedAt - grace) sha entry.1 same
        exact ⟨kept.1 was, kept.2 _ dated⟩

/-- Every file ref names a blob the hub holds, when each file ref arrives within `delay` of
its relay's asking for the blob or storing it, and `delay` is within the grace. -/
theorem Reachable.refs_held {grace delay : Duration} (fits : delay ≤ grace) (waits : 0 ≤ delay) {p : Play}
    (reached : Reachable grace delay p) : ∀ sha ∈ p.state.refs, p.state.holds sha = true :=
  fun sha mem => ((reached.safe fits waits).refs sha mem).1

end BlobsState

/-- info: 'Contraagent.BlobsState.Reachable.refs_held' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms BlobsState.Reachable.refs_held

end Contraagent
