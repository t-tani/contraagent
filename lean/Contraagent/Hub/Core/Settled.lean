import Contraagent.Hub.Core.Kept

/-!
# A prune is complete

A second prune at the same time removes nothing (`afterPrune_settled`): no run, no
transcripts, no heartbeat and no blob. What a prune removes changes nothing in what it
decided to keep: a run that was live or unresponsive is so after it, because the heartbeat
of a host that is up stays, and so does a heartbeat that is evidence of an unresponsive
run; a run it keeps has the activity it had, because its transcripts stay; and the blobs
that the runs it keeps name are the same.

It holds of a hub that holds one run under each name (`Named`), as the store does.
-/

namespace Contraagent

namespace Holdings

/-- The hub holds one run under each name. -/
def Named (hs : Holdings) : Prop :=
  hs.runs.Pairwise fun a b => a.name ≠ b.name

/-! ## Lists -/

theorem filter_of_filter {α : Type} (p q : α → Bool) (l : List α) (imp : ∀ x ∈ l, p x = true → q x = true) :
    (l.filter q).filter p = l.filter p := by
  rw [List.filter_filter]
  refine List.filter_congr fun x mem => ?_
  cases holds : p x
  · simp
  · simp [imp x mem holds]

theorem find_of_filter {α : Type} (p q : α → Bool) (l : List α) (imp : ∀ x ∈ l, p x = true → q x = true) :
    (l.filter q).find? p = l.find? p := by
  induction l with
  | nil => rfl
  | cons x rest ih =>
    have later := ih fun y mem => imp y (List.mem_cons_of_mem _ mem)
    by_cases stays : q x = true
    · rw [List.filter_cons_of_pos stays]
      simp only [List.find?_cons, later]
    · have misses : p x = false := by
        cases holds : p x
        · rfl
        · exact absurd (imp x List.mem_cons_self holds) stays
      rw [List.filter_cons_of_neg stays]
      simp only [List.find?_cons, misses, later]

/-- Two runs of one name are one run. -/
theorem same_named {runs : List HeldRun} (distinct : runs.Pairwise fun a b => a.name ≠ b.name) {a b : HeldRun}
    (first : a ∈ runs) (second : b ∈ runs) (name : a.name = b.name) : a = b := by
  induction runs with
  | nil => cases first
  | cons run rest ih =>
    rw [List.pairwise_cons] at distinct
    rcases List.mem_cons.mp first with rfl | firstLater <;> rcases List.mem_cons.mp second with rfl | secondLater
    · rfl
    · exact absurd name (distinct.1 b secondLater)
    · exact absurd name.symm (distinct.1 a firstLater)
    · exact ih distinct.2 firstLater secondLater

theorem find_named {runs : List HeldRun} (distinct : runs.Pairwise fun a b => a.name ≠ b.name) {run : HeldRun}
    (held : run ∈ runs) : runs.find? (·.name == run.name) = some run := by
  induction runs with
  | nil => cases held
  | cons first rest ih =>
    rw [List.pairwise_cons] at distinct
    rcases List.mem_cons.mp held with rfl | later
    · simp
    · have other : (first.name == run.name) = false := by simpa using distinct.1 run later
      simp only [List.find?_cons, other]
      exact ih distinct.2 later

/-! ## What a prune leaves as it was -/

variable (hs : Holdings) (now : Time) (olderThan blobGrace : Duration)

/-- The same runs are live after a prune: the heartbeat of a host that is up stays. -/
theorem afterPrune_live : (hs.afterPrune now olderThan blobGrace).live now = hs.live now := by
  unfold live
  show ((hs.heartbeats.filter (!hs.removesHeartbeat now (now - olderThan) ·)).filter (up now)).flatMap _ = _
  rw [filter_of_filter]
  intro heartbeat _ isUp
  simp [removesHeartbeat, isUp]

theorem afterPrune_named (named : hs.Named) : (hs.afterPrune now olderThan blobGrace).Named :=
  List.Pairwise.sublist List.filter_sublist named

/-- A run a prune keeps is finished after it exactly when it was. -/
theorem afterPrune_finished (named : hs.Named) {run : HeldRun}
    (kept : run ∈ (hs.afterPrune now olderThan blobGrace).runs) :
    (hs.afterPrune now olderThan blobGrace).finished run.name = hs.finished run.name := by
  have held := ((hs.afterPrune_run_iff now olderThan blobGrace run).mp kept).1
  unfold finished
  rw [find_named (hs.afterPrune_named now olderThan blobGrace named) kept, find_named named held]

/-- A run a prune keeps that was unresponsive is unresponsive after it: the heartbeat that
reports it is evidence, and stays. -/
theorem afterPrune_unresponsive (named : hs.Named) {run : HeldRun}
    (kept : run ∈ (hs.afterPrune now olderThan blobGrace).runs) (gone : run.name ∈ hs.unresponsive now) :
    run.name ∈ (hs.afterPrune now olderThan blobGrace).unresponsive now := by
  have held := ((hs.afterPrune_run_iff now olderThan blobGrace run).mp kept).1
  have was := gone
  unfold unresponsive at gone ⊢
  obtain ⟨reported, open_⟩ := List.mem_filter.mp gone
  obtain ⟨heartbeat, down, alive⟩ := List.mem_flatMap.mp reported
  obtain ⟨has, notUp⟩ := List.mem_filter.mp down
  have proof : hs.evidence now heartbeat = true :=
    List.any_eq_true.mpr ⟨run.name, alive, by
      simp only [Bool.and_eq_true, List.contains_iff_mem]
      exact ⟨was, List.any_eq_true.mpr ⟨run, held, by simp⟩⟩⟩
  have stays := hs.afterPrune_keeps_heartbeat now olderThan blobGrace has (Or.inr (Or.inr proof))
  refine List.mem_filter.mpr ⟨List.mem_flatMap.mpr ⟨heartbeat, List.mem_filter.mpr ⟨stays, notUp⟩, alive⟩, ?_⟩
  rw [hs.afterPrune_finished now olderThan blobGrace named kept]
  exact open_

/-- A run a prune keeps has the activity it had: its transcripts stay. -/
theorem afterPrune_activity (named : hs.Named) {run : HeldRun}
    (kept : run ∈ (hs.afterPrune now olderThan blobGrace).runs) :
    (hs.afterPrune now olderThan blobGrace).activity run = hs.activity run := by
  obtain ⟨held, stays⟩ := (hs.afterPrune_run_iff now olderThan blobGrace run).mp kept
  unfold activity transcriptsAt
  show later run.recordsAt (((hs.transcripts.filter (!hs.dropsTranscripts now (now - olderThan) ·)).find? _).bind _) = _
  rw [find_of_filter]
  intro transcripts _ its
  simp only [Bool.and_eq_true, beq_iff_eq] at its
  have holds : hs.holdsRun transcripts.name transcripts.runUid = true :=
    List.any_eq_true.mpr ⟨run, held, by simp [its.1, its.2]⟩
  have none_removed : hs.runs.any (fun other =>
      other.name == transcripts.name && other.runUid == transcripts.runUid && hs.removes now (now - olderThan) other)
      = false := by
    refine List.any_eq_false.mpr fun other mem => ?_
    by_cases same : other.name = transcripts.name
    · have one : other = run := same_named named mem held (same.trans its.1)
      simp [one, stays]
    · simp [same]
  simp [dropsTranscripts, orphaned, holds, none_removed]

/-- A prune removes no run that an earlier prune at the same time kept. -/
theorem afterPrune_removes (named : hs.Named) {run : HeldRun}
    (kept : run ∈ (hs.afterPrune now olderThan blobGrace).runs) :
    (hs.afterPrune now olderThan blobGrace).removes now (now - olderThan) run = false := by
  obtain ⟨_, stays⟩ := (hs.afterPrune_run_iff now olderThan blobGrace run).mp kept
  cases goes : (hs.afterPrune now olderThan blobGrace).removes now (now - olderThan) run with
  | false => rfl
  | true =>
    obtain ⟨last, at_, old, notLive, notGone⟩ := ((hs.afterPrune now olderThan blobGrace).removes_iff _ _ run).mp goes
    rw [hs.afterPrune_activity now olderThan blobGrace named kept] at at_
    rw [hs.afterPrune_live now olderThan blobGrace] at notLive
    have before : hs.removes now (now - olderThan) run = true :=
      (hs.removes_iff now (now - olderThan) run).mpr
        ⟨last, at_, old, notLive, fun gone => notGone (hs.afterPrune_unresponsive now olderThan blobGrace named kept gone)⟩
    rw [stays] at before
    cases before

/-- The file refs of the runs kept name the same blobs after a prune. -/
theorem afterPrune_referenced (named : hs.Named) :
    (hs.afterPrune now olderThan blobGrace).referenced now (now - olderThan) = hs.referenced now (now - olderThan) := by
  unfold referenced
  have all : (hs.afterPrune now olderThan blobGrace).runs.filter
      (!(hs.afterPrune now olderThan blobGrace).removes now (now - olderThan) ·)
      = (hs.afterPrune now olderThan blobGrace).runs :=
    List.filter_eq_self.mpr fun run kept => by simp [hs.afterPrune_removes now olderThan blobGrace named kept]
  rw [all]
  rfl

/-- A second prune at the same time removes nothing: its report names no run, no
transcripts, no heartbeat and no blob. -/
theorem afterPrune_settled (named : hs.Named) :
    ((hs.afterPrune now olderThan blobGrace).pruneReport now olderThan blobGrace).runs = []
      ∧ ((hs.afterPrune now olderThan blobGrace).pruneReport now olderThan blobGrace).transcripts = []
      ∧ ((hs.afterPrune now olderThan blobGrace).pruneReport now olderThan blobGrace).heartbeats = []
      ∧ ((hs.afterPrune now olderThan blobGrace).pruneReport now olderThan blobGrace).blobs = [] := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · show ((hs.afterPrune now olderThan blobGrace).runs.filter _).map _ = []
    rw [List.filter_eq_nil_iff.mpr fun run kept => by simp [hs.afterPrune_removes now olderThan blobGrace named kept]]
    rfl
  · show ((hs.afterPrune now olderThan blobGrace).transcripts.filter _).map _ = []
    rw [List.filter_eq_nil_iff.mpr ?_]
    · rfl
    intro transcripts kept
    obtain ⟨_, stays⟩ := List.mem_filter.mp kept
    simp only [dropsTranscripts, Bool.not_eq_true', Bool.or_eq_false_iff] at stays
    obtain ⟨none_removed, notOrphaned⟩ := stays
    unfold orphaned at notOrphaned ⊢
    cases holds : hs.holdsRun transcripts.name transcripts.runUid with
    | false =>
      have young : oldTranscripts (now - olderThan) transcripts = false := by simpa [holds] using notOrphaned
      simp [young]
    | true =>
      obtain ⟨run, held, its⟩ := List.any_eq_true.mp holds
      have stays : hs.removes now (now - olderThan) run = false := by
        have each := List.any_eq_false.mp none_removed run held
        simpa [its] using each
      have after : (hs.afterPrune now olderThan blobGrace).holdsRun transcripts.name transcripts.runUid = true :=
        List.any_eq_true.mpr ⟨run, (hs.afterPrune_run_iff now olderThan blobGrace run).mpr ⟨held, stays⟩, its⟩
      simp [after]
  · show ((hs.afterPrune now olderThan blobGrace).heartbeats.filter _).map _ = []
    rw [List.filter_eq_nil_iff.mpr ?_]
    · rfl
    intro heartbeat kept
    obtain ⟨_, stays⟩ := List.mem_filter.mp kept
    have before : hs.removesHeartbeat now (now - olderThan) heartbeat = false := by simpa using stays
    unfold removesHeartbeat at before ⊢
    cases old : decide (heartbeat.receivedAt < now - olderThan) with
    | false => simp
    | true =>
      cases isUp : up now heartbeat with
      | true => simp
      | false =>
        have proof : hs.evidence now heartbeat = true := by simpa [old, isUp] using before
        obtain ⟨name, alive, both⟩ := List.any_eq_true.mp proof
        simp only [Bool.and_eq_true, List.contains_iff_mem] at both
        obtain ⟨run, held, its⟩ := List.any_eq_true.mp both.2
        have name_eq : run.name = name := by simpa using its
        have gone : run.name ∈ hs.unresponsive now := name_eq ▸ both.1
        have runStays := hs.afterPrune_keeps_run now olderThan blobGrace held (Or.inr (Or.inl gone))
        have after : (hs.afterPrune now olderThan blobGrace).evidence now heartbeat = true := by
          refine List.any_eq_true.mpr ⟨name, alive, ?_⟩
          simp only [Bool.and_eq_true, List.contains_iff_mem]
          exact ⟨name_eq ▸ hs.afterPrune_unresponsive now olderThan blobGrace named runStays gone,
            List.any_eq_true.mpr ⟨run, runStays, its⟩⟩
        simp [after]
  · show ((hs.afterPrune now olderThan blobGrace).blobs.filter _).map _ = []
    rw [List.filter_eq_nil_iff.mpr ?_]
    · rfl
    intro blob kept
    obtain ⟨_, stays⟩ := List.mem_filter.mp kept
    have before : hs.removesBlob now (now - olderThan) (now - blobGrace) blob = false := by simpa using stays
    unfold removesBlob at before ⊢
    rw [hs.afterPrune_referenced now olderThan blobGrace named, before]
    simp

end Holdings

/--
info: 'Contraagent.Holdings.afterPrune_settled' depends on axioms: [propext, Classical.choice, Quot.sound]
-/
#guard_msgs in
#print axioms Holdings.afterPrune_settled

end Contraagent
