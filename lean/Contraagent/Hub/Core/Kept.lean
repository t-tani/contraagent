import Contraagent.Hub.Core

/-!
# What a prune keeps

A prune removes a run only when its activity is older than the cutoff and it is neither
live nor unresponsive (`removes_iff`). So a live run stays, as do an unresponsive one, one
whose activity is not old and one with no activity time (`afterPrune_keeps_run`). A blob
that a file ref of a run kept names stays (`afterPrune_keeps_referenced`), and so does one
stored within the grace (`afterPrune_keeps_young`). A heartbeat stays while it is not old,
while its host is up, and while it is evidence of an unresponsive run
(`afterPrune_keeps_heartbeat`). A dry run changes nothing and reports the same
(`prune_dry`).
-/

namespace Contraagent

namespace Holdings

/-- A prune removes a run only when its activity is older than the cutoff and it is neither
live nor unresponsive. -/
theorem removes_iff (hs : Holdings) (now cutoff : Time) (run : HeldRun) :
    hs.removes now cutoff run = true ↔
      ∃ last, hs.activity run = some last ∧ last < cutoff ∧ run.name ∉ hs.live now ∧ run.name ∉ hs.unresponsive now := by
  unfold removes verdict
  cases hs.activity run with
  | none => simp
  | some last =>
    by_cases recent : cutoff ≤ last
    · have young : ¬last < cutoff := Int.not_lt.mpr recent
      simp [recent, young]
    · have old : last < cutoff := Int.not_le.mp recent
      by_cases isLive : (hs.live now).contains run.name = true
      · have mem : run.name ∈ hs.live now := List.contains_iff_mem.mp isLive
        simp [recent, mem]
      · have out : run.name ∉ hs.live now := fun mem => isLive (List.contains_iff_mem.mpr mem)
        by_cases gone : (hs.unresponsive now).contains run.name = true
        · have mem : run.name ∈ hs.unresponsive now := List.contains_iff_mem.mp gone
          simp [recent, out, mem]
        · have away : run.name ∉ hs.unresponsive now := fun mem => gone (List.contains_iff_mem.mpr mem)
          simp [recent, old, out, away]

theorem afterPrune_run_iff (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) (run : HeldRun) :
    run ∈ (hs.afterPrune now olderThan blobGrace).runs ↔ run ∈ hs.runs ∧ hs.removes now (now - olderThan) run = false := by
  simp [afterPrune, List.mem_filter]

/-- A prune keeps a run that is live, one that is unresponsive, one with no activity time
and one whose activity is not older than the cutoff. -/
theorem afterPrune_keeps_run (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) {run : HeldRun}
    (held : run ∈ hs.runs)
    (why : run.name ∈ hs.live now ∨ run.name ∈ hs.unresponsive now ∨ hs.activity run = none
      ∨ ∃ last, hs.activity run = some last ∧ now - olderThan ≤ last) :
    run ∈ (hs.afterPrune now olderThan blobGrace).runs := by
  refine (hs.afterPrune_run_iff now olderThan blobGrace run).mpr ⟨held, ?_⟩
  cases goes : hs.removes now (now - olderThan) run with
  | false => rfl
  | true =>
    obtain ⟨last, at_, old, notLive, notGone⟩ := (hs.removes_iff now (now - olderThan) run).mp goes
    rcases why with isLive | gone | none | ⟨other, eq, recent⟩
    · exact absurd isLive notLive
    · exact absurd gone notGone
    · rw [none] at at_; cases at_
    · rw [eq] at at_
      cases at_
      exact absurd old (Int.not_lt.mpr recent)

/-- A prune keeps every blob that a file ref of a run it keeps names. -/
theorem afterPrune_keeps_referenced (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) {run : HeldRun}
    {blob : HeldBlob} (kept : run ∈ (hs.afterPrune now olderThan blobGrace).runs) (named : blob.sha ∈ run.files)
    (held : blob ∈ hs.blobs) : blob ∈ (hs.afterPrune now olderThan blobGrace).blobs := by
  obtain ⟨mem, stays⟩ := (hs.afterPrune_run_iff now olderThan blobGrace run).mp kept
  have referenced : blob.sha ∈ hs.referenced now (now - olderThan) :=
    List.mem_flatMap.mpr ⟨run, List.mem_filter.mpr ⟨mem, by simp [stays]⟩, named⟩
  simp only [afterPrune, List.mem_filter]
  refine ⟨held, ?_⟩
  simp [removesBlob, referenced]

/-- A prune keeps a blob stored within the grace. -/
theorem afterPrune_keeps_young (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) {blob : HeldBlob}
    (held : blob ∈ hs.blobs) (young : now - blobGrace ≤ blob.modified) :
    blob ∈ (hs.afterPrune now olderThan blobGrace).blobs := by
  simp only [afterPrune, List.mem_filter]
  refine ⟨held, ?_⟩
  have fresh : ¬blob.modified < now - blobGrace := Int.not_lt.mpr young
  simp [removesBlob, fresh]

/-- A prune keeps a heartbeat that is not old, that of a host that is up, and one that is
evidence of an unresponsive run. -/
theorem afterPrune_keeps_heartbeat (hs : Holdings) (now : Time) (olderThan blobGrace : Duration)
    {heartbeat : HeldHeartbeat} (held : heartbeat ∈ hs.heartbeats)
    (why : now - olderThan ≤ heartbeat.receivedAt ∨ up now heartbeat = true ∨ hs.evidence now heartbeat = true) :
    heartbeat ∈ (hs.afterPrune now olderThan blobGrace).heartbeats := by
  simp only [afterPrune, List.mem_filter]
  refine ⟨held, ?_⟩
  rcases why with recent | isUp | proof
  · have fresh : ¬heartbeat.receivedAt < now - olderThan := Int.not_lt.mpr recent
    simp [removesHeartbeat, fresh]
  · simp [removesHeartbeat, isUp]
  · simp [removesHeartbeat, proof]

/-- A dry run changes nothing, and reports what the prune would. -/
theorem prune_dry (hs : Holdings) (now : Time) (olderThan blobGrace : Duration) :
    hs.prune now olderThan blobGrace true = (hs, (hs.prune now olderThan blobGrace false).2) := rfl

end Holdings

/-- info: 'Contraagent.Holdings.afterPrune_keeps_run' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Holdings.afterPrune_keeps_run

/-- info: 'Contraagent.Holdings.afterPrune_keeps_referenced' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Holdings.afterPrune_keeps_referenced

end Contraagent
