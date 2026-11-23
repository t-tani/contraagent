import Contraagent.Hub.Segments

/-!
# Every index row has its object

Of the description of the hub's logs: in every state the hub reaches, each index row names
an object that is in the store (`Reachable.whole`). So a read of a sealed segment finds its
object, whichever seal failed and wherever a process died.

It rests on two orders of the code. A seal puts the object before it commits the row, so a
crash between the two leaves an object with no row, never a row with no object. And `sweep`
deletes only objects that no row names.
-/

namespace Contraagent

/-- Every index row names an object that is in the store. -/
def Kept.Whole (kept : Kept) : Prop :=
  ∀ row ∈ kept.rows, ∃ object ∈ kept.objects, object.key = row.key ∧ object.first = row.first

namespace Kept.Whole

/-- What changes neither the rows nor the objects keeps it. -/
theorem congr {kept kept' : Kept} (whole : kept.Whole) (rows : kept'.rows = kept.rows)
    (objects : kept'.objects = kept.objects) : kept'.Whole := by
  intro row held
  rw [rows] at held
  rw [objects]
  exact whole row held

theorem putObject {kept : Kept} (whole : kept.Whole) (key : LogKey) (first : Nat) (lines : List String) :
    (kept.putObject key first lines).Whole := by
  intro row held
  obtain ⟨object, there, sameKey, sameFirst⟩ := whole row held
  by_cases hit : (object.key == key && object.first == first) = true
  · simp only [Bool.and_eq_true, beq_iff_eq] at hit
    refine ⟨{ key := key, first := first, lines := lines }, ?_, ?_, ?_⟩
    · simp [Kept.putObject]
    · rw [← sameKey]; exact hit.1.symm
    · rw [← sameFirst]; exact hit.2.symm
  · refine ⟨object, ?_, sameKey, sameFirst⟩
    simp only [Kept.putObject, List.mem_append, List.mem_filter]
    exact Or.inl ⟨there, by rw [(Bool.not_eq_true _).mp hit]; rfl⟩

/-- Committing a row whose object is in the store keeps it. -/
theorem addRow {kept : Kept} (whole : kept.Whole) (key : LogKey) (first count : Nat)
    (there : ∃ object ∈ kept.objects, object.key = key ∧ object.first = first) :
    (kept.addRow key first count).Whole := by
  intro row held
  simp only [Kept.addRow, List.mem_append, List.mem_filter, List.mem_singleton] at held
  rcases held with ⟨old, _⟩ | new
  · exact whole row old
  · rw [new]; exact there

theorem removeFile {kept : Kept} (whole : kept.Whole) (key : LogKey) (first : Nat) :
    (kept.removeFile key first).Whole :=
  whole.congr rfl rfl

theorem writeFile {kept : Kept} (whole : kept.Whole) (key : LogKey) (first : Nat) (lines : List String) :
    (kept.writeFile key first lines).Whole :=
  whole.congr rfl rfl

end Kept.Whole

theorem Kept.put_there (kept : Kept) (key : LogKey) (first : Nat) (lines : List String) :
    ∃ object ∈ (kept.putObject key first lines).objects, object.key = key ∧ object.first = first :=
  ⟨{ key := key, first := first, lines := lines }, by simp [Kept.putObject], rfl, rfl⟩

/-- A seal keeps it at each of its steps: it puts the object before it commits the row. -/
theorem sealOne_whole (fault : Option Fault) (key : LogKey) (kept : Kept) (st : LogState) (first : Nat)
    (whole : kept.Whole) : (sealOne fault key kept st first).1.Whole := by
  have put := whole.putObject key first (kept.fileLines key first)
  have there := kept.put_there key first (kept.fileLines key first)
  unfold sealOne
  dsimp only
  split
  · exact whole
  · exact put
  · exact put
  · exact put.addRow key first _ there
  · exact (put.addRow key first _ there).removeFile key first

theorem sealAll_whole (fault : Option Fault) (key : LogKey) : ∀ (fuel : Nat) (kept : Kept) (st : LogState),
    kept.Whole → (sealAll fault key fuel kept st).1.Whole := by
  intro fuel
  induction fuel with
  | zero => intro kept st whole; exact whole
  | succ fuel ih =>
    intro kept st whole
    unfold sealAll
    cases waiting : st.sealing with
    | nil => exact whole
    | cons first rest =>
      dsimp only
      have one := sealOne_whole fault key kept st first whole
      split
      · rename_i kept' st' eq
        rw [eq] at one
        exact ih kept' st' one
      · rename_i kept' st' eq
        rw [eq] at one
        exact one
      · rename_i kept' st' eq
        rw [eq] at one
        exact one

namespace HubConfig

theorem writeLines_whole (cfg : HubConfig) (now : Time) (key : LogKey) :
    ∀ (fuel : Nat) (kept : Kept) (st : LogState) (lines : List String), kept.Whole →
      (cfg.writeLines now key fuel kept st lines).1.Whole := by
  intro fuel
  induction fuel with
  | zero => intro kept st lines whole; exact whole
  | succ fuel ih =>
    intro kept st lines whole
    cases lines with
    | nil => exact whole
    | cons line rest =>
      unfold writeLines
      dsimp only
      exact ih _ _ _ (whole.writeFile key _ _)

end HubConfig

namespace HubState

theorem setLog_kept (s : HubState) (key : LogKey) (st : LogState) : (s.setLog key st).kept = s.kept := by
  unfold setLog
  split <;> rfl

theorem load_kept (s : HubState) (key : LogKey) (create : Bool) : (s.load key create).1.kept = s.kept := by
  unfold load
  split
  · rfl
  · dsimp only
    split
    · rfl
    · exact setLog_kept s key _

theorem sealed_whole (s : HubState) (fault : Option Fault) (key : LogKey) (kept : Kept) (st : LogState)
    (whole : kept.Whole) : (s.sealed fault key kept st).1.kept.Whole := by
  have all := sealAll_whole fault key st.sealing.length kept st whole
  unfold sealed
  dsimp only
  rw [setLog_kept]
  exact all

end HubState

namespace HubConfig

theorem appendNew_whole (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (st : LogState) (new : List String) (whole : s.kept.Whole) :
    (cfg.appendNew now fault s key st new).1.kept.Whole := by
  have written := cfg.writeLines_whole now key new.length s.kept { st with lastAppend := now } new whole
  unfold appendNew
  dsimp only
  split
  · exact whole
  · split
    · exact HubState.sealed_whole s fault key _ _ written
    · rw [HubState.setLog_kept]
      exact written

theorem append_whole (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (offset : Nat) (lines : List String) (whole : s.kept.Whole) :
    (cfg.append now fault s key offset lines).1.kept.Whole := by
  have loaded : (s.load key true).1.kept.Whole := by rw [HubState.load_kept]; exact whole
  exact cfg.appendNew_whole now fault _ key _ _ loaded

theorem close_whole (fault : Option Fault) (s : HubState) (key : LogKey) (whole : s.kept.Whole) :
    (HubConfig.close fault s key).1.kept.Whole := by
  have loaded : (s.load key false).1.kept.Whole := by rw [HubState.load_kept]; exact whole
  unfold close
  split
  · rename_i s' eq
    rw [eq] at loaded
    exact loaded
  · rename_i s' st eq
    rw [eq] at loaded
    split
    · exact HubState.sealed_whole s' fault key s'.kept st.rotate loaded
    · exact loaded

theorem tickLog_whole (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (whole : s.kept.Whole) : (cfg.tickLog now fault s key).1.kept.Whole := by
  unfold tickLog
  split
  · exact whole
  · exact HubState.sealed_whole s fault key s.kept _ whole

theorem tick_whole (cfg : HubConfig) (now : Time) (fault : Option Fault) (s : HubState)
    (whole : s.kept.Whole) : (cfg.tick now fault s).1.kept.Whole := by
  unfold tick
  suffices kept : ∀ (keys : List LogKey) (acc : HubState × Bool), acc.1.kept.Whole →
      (keys.foldl (fun (acc : HubState × Bool) key => if acc.2 then acc else cfg.tickLog now fault acc.1 key)
        acc).1.kept.Whole from kept _ (s, false) whole
  intro keys
  induction keys with
  | nil => intro acc held; exact held
  | cons key rest ih =>
    intro acc held
    rw [List.foldl_cons]
    apply ih
    split
    · exact held
    · exact cfg.tickLog_whole now fault acc.1 key held

end HubConfig

namespace HubState

/-- Adopting an object commits a row for an object that is in the store. -/
theorem adopt_whole (fault : Option Fault) (key : LogKey) : ∀ (fuel : Nat) (kept : Kept) (st : LogState),
    kept.Whole → (adopt fault key fuel kept st).1.Whole := by
  intro fuel
  induction fuel with
  | zero => intro kept st whole; exact whole
  | succ fuel ih =>
    intro kept st whole
    unfold adopt
    split
    · exact whole
    · rename_i object found
      have there : ∃ o ∈ kept.objects, o.key = key ∧ o.first = st.count := by
        refine ⟨object, List.mem_of_find?_eq_some found, ?_⟩
        have is := List.find?_some found
        simpa using is
      split
      · exact whole
      · dsimp only
        split
        · exact whole
        · exact whole.addRow key st.count _ there
        · exact ih _ _ (whole.addRow key st.count _ there)

theorem takeFiles_whole (key : LogKey) : ∀ (files : List (Nat × Nat)) (kept : Kept) (st : LogState)
    (taken : List Nat), kept.Whole → (takeFiles key files kept st taken).1.Whole := by
  intro files
  induction files with
  | nil => intro kept st taken whole; exact whole
  | cons file rest ih =>
    intro kept st taken whole
    obtain ⟨first, lines⟩ := file
    unfold takeFiles
    split
    · exact ih _ _ _ whole
    · exact ih _ _ _ (whole.removeFile key first)

theorem adoptPast_whole (fault : Option Fault) (key : LogKey) (files : List (Nat × Nat)) (kept : Kept)
    (st : LogState) (whole : kept.Whole) : (adoptPast fault key files kept st).1.Whole := by
  unfold adoptPast
  split
  · exact adopt_whole fault key _ kept st whole
  · exact whole

theorem resume_whole (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey) (files : List (Nat × Nat))
    (kept : Kept) (st : LogState) (whole : kept.Whole) : (resume now fault s key files kept st).1.kept.Whole := by
  exact sealed_whole s fault key _ _ (takeFiles_whole key files kept st [] whole)

theorem recoverLog_whole (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey)
    (whole : s.kept.Whole) : (recoverLog now fault s key).1.kept.Whole := by
  have loaded : (s.load key true).1.kept.Whole := by rw [load_kept]; exact whole
  unfold recoverLog
  dsimp only
  split
  · exact adoptPast_whole fault key _ _ _ loaded
  · exact resume_whole now fault _ key _ _ _ (adoptPast_whole fault key _ _ _ loaded)

theorem recover_whole (now : Time) (fault : Option Fault) (kept : Kept) (whole : kept.Whole) :
    (recover now fault kept).1.kept.Whole := by
  unfold recover
  suffices held : ∀ (keys : List LogKey) (acc : HubState × Bool), acc.1.kept.Whole →
      (keys.foldl (fun (acc : HubState × Bool) key => if acc.2 then acc else recoverLog now fault acc.1 key)
        acc).1.kept.Whole from held _ ({ kept := kept }, false) whole
  intro keys
  induction keys with
  | nil => intro acc held; exact held
  | cons key rest ih =>
    intro acc held
    rw [List.foldl_cons]
    apply ih
    split
    · exact held
    · exact recoverLog_whole now fault acc.1 key held

/-- `sweep` deletes no object that a row names. -/
theorem sweep_whole (s : HubState) (whole : s.kept.Whole) : s.sweep.1.kept.Whole := by
  intro row held
  obtain ⟨object, there, sameKey, sameFirst⟩ := whole row held
  refine ⟨object, ?_, sameKey, sameFirst⟩
  simp only [sweep, List.mem_filter, Bool.not_not, List.any_eq_true]
  exact ⟨there, row, held, by simp [sameKey, sameFirst]⟩

/-- `drop` deletes the rows of the run whose objects it deletes. -/
theorem drop_whole (s : HubState) (name uid : String) (whole : s.kept.Whole) : (s.drop name uid).1.kept.Whole := by
  intro row held
  simp only [drop, List.mem_filter] at held
  obtain ⟨object, there, sameKey, sameFirst⟩ := whole row held.1
  refine ⟨object, ?_, sameKey, sameFirst⟩
  simp only [drop, List.mem_filter]
  rw [sameKey]
  exact ⟨there, held.2⟩

end HubState

/-- The states the hub reaches: from nothing, by what it is asked to do, at any times,
whichever seal fails or kills the process; by a start on what the last process left; and
by an index that lost its rows. -/
inductive HubConfig.Reachable (cfg : HubConfig) : HubState → Prop
  | nothing : cfg.Reachable {}
  | append (now : Time) (fault : Option Fault) (s : HubState) (key : LogKey) (offset : Nat) (lines : List String) :
    cfg.Reachable s → cfg.Reachable (cfg.append now fault s key offset lines).1
  | close (fault : Option Fault) (s : HubState) (key : LogKey) :
    cfg.Reachable s → cfg.Reachable (HubConfig.close fault s key).1
  | tick (now : Time) (fault : Option Fault) (s : HubState) : cfg.Reachable s → cfg.Reachable (cfg.tick now fault s).1
  | start (now : Time) (fault : Option Fault) (s : HubState) :
    cfg.Reachable s → cfg.Reachable (HubState.recover now fault s.kept).1
  | lostIndex (s : HubState) : cfg.Reachable s → cfg.Reachable { s with kept := { s.kept with rows := [] } }
  | read (s : HubState) (key : LogKey) (since : Nat) (limit : Option Nat) :
    cfg.Reachable s → cfg.Reachable (s.read key since limit).1
  | held (s : HubState) (key : LogKey) : cfg.Reachable s → cfg.Reachable (s.held key).1
  | sweep (s : HubState) : cfg.Reachable s → cfg.Reachable s.sweep.1
  | drop (s : HubState) (name uid : String) : cfg.Reachable s → cfg.Reachable (s.drop name uid).1

/-- In every state the hub reaches, each index row names an object that is in the store:
whichever seal failed, wherever a process died, and after an index that lost its rows. -/
theorem HubConfig.Reachable.whole {cfg : HubConfig} {s : HubState} (reached : cfg.Reachable s) :
    s.kept.Whole := by
  induction reached with
  | nothing => intro row held; cases held
  | append now fault s key offset lines _ ih => exact cfg.append_whole now fault s key offset lines ih
  | close fault s key _ ih => exact HubConfig.close_whole fault s key ih
  | tick now fault s _ ih => exact cfg.tick_whole now fault s ih
  | start now fault s _ ih => exact HubState.recover_whole now fault s.kept ih
  | lostIndex s _ ih => intro row held; cases held
  | read s key since limit _ ih =>
    have same : (s.read key since limit).1.kept = (s.load key false).1.kept := by
      unfold HubState.read
      split <;> (rename_i eq; rw [eq])
    rw [same, HubState.load_kept]
    exact ih
  | held s key _ ih =>
    have same : (s.held key).1.kept = (s.load key false).1.kept := by
      unfold HubState.held
      split <;> (rename_i eq; rw [eq])
    rw [same, HubState.load_kept]
    exact ih
  | sweep s _ ih => exact s.sweep_whole ih
  | drop s name uid _ ih => exact s.drop_whole name uid ih

/-- info: 'Contraagent.HubConfig.Reachable.whole' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms HubConfig.Reachable.whole

end Contraagent
