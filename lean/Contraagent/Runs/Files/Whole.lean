import Contraagent.Runs.Files

/-!
# A row appended whole is read, and what is read was appended

Of the description of a run's logs, for rows that hold no newline:

- A complete line stays as it is: an append adds lines after those the log has
  (`append_keeps`).
- An append that is not cut adds its rows as lines, each whole, also to a log whose last
  write was cut (`append_whole`): the cut line is ended first. So every row of an append
  that was not cut is read, after any appends that follow, cut or not (`whole_read`).
- Every line read is a row that an append was given, or the first bytes of one whose write
  was cut (`Reachable.read_given`). A cut row does not parse as a row, so the rows a reader
  gets are rows that were given to an append.
- A reader that rests on a log reads no line only of a log with none or of no file: a file
  it cannot read is not read as empty (`Found.read_nil`).
-/

namespace Contraagent

namespace Log

/-! ## Writing bytes -/

theorem write_append (log : Log) (first second : List UInt8) :
    log.write (first ++ second) = (log.write first).write second := by
  simp [write, List.foldl_append]

/-- Bytes that hold no newline go on in the last line. -/
theorem write_plain (log : Log) (bytes : List UInt8) (plain : newline ∉ bytes) :
    log.write bytes = { log with tail := log.tail ++ bytes } := by
  induction bytes generalizing log with
  | nil => simp [write]
  | cons byte rest ih =>
    have other : (byte == newline) = false := by
      simpa using fun eq : byte = newline => plain (eq ▸ List.mem_cons_self)
    have later : newline ∉ rest := fun mem => plain (List.mem_cons_of_mem _ mem)
    show (log.push byte).write rest = _
    rw [ih _ later]
    simp [push, other]

/-- A row and its newline make one more line: the row after what the last line held. -/
theorem write_row (log : Log) (row : Line) (plain : newline ∉ row) :
    log.write (row ++ [newline]) = { lines := log.lines ++ [log.tail ++ row], tail := [] } := by
  rw [write_append, write_plain log row plain]
  simp [write, push]

theorem take_plain {row : Line} (plain : newline ∉ row) (n : Nat) : newline ∉ row.take n :=
  fun mem => plain (List.mem_of_mem_take mem)

/-- What the first `written` bytes of rows with their newlines leave in a log whose last
line is ended: some of the rows as whole lines, the first ones, and then nothing, or the
first bytes of the next row as a line with no end. When no byte is cut, all the rows. -/
theorem write_rows (log : Log) (rows : List Line) (plain : ∀ row ∈ rows, newline ∉ row) (ended : log.tail = [])
    (written : Nat) :
    ∃ whole part, log.write ((rows.flatMap (· ++ [newline])).take written) = { lines := log.lines ++ whole, tail := part }
      ∧ whole <+: rows ∧ (part = [] ∨ ∃ row ∈ rows, part <+: row)
      ∧ ((rows.flatMap (· ++ [newline])).length ≤ written → whole = rows ∧ part = []) := by
  induction rows generalizing log written with
  | nil =>
    refine ⟨[], [], ?_, List.prefix_refl _, Or.inl rfl, fun _ => ⟨rfl, rfl⟩⟩
    cases log
    simp_all [write]
  | cons row rest ih =>
    have clean : newline ∉ row := plain row List.mem_cons_self
    have later : ∀ other ∈ rest, newline ∉ other := fun other mem => plain other (List.mem_cons_of_mem _ mem)
    rw [List.flatMap_cons, List.take_append, write_append]
    by_cases cut : written ≤ row.length
    · -- The write is cut inside the first row, or just before its newline.
      have none_after : (row ++ [newline]).length ≥ written := by simp; omega
      have first : (row ++ [newline]).take written = row.take written := by
        rw [List.take_append_of_le_length cut]
      have nothing : written - (row ++ [newline]).length = 0 := by omega
      rw [first, nothing, List.take_zero, write_plain log _ (take_plain clean written)]
      refine ⟨[], row.take written, ?_, List.nil_prefix, Or.inr ⟨row, List.mem_cons_self, List.take_prefix _ _⟩, ?_⟩
      · simp [write, ended]
      · intro all
        simp only [List.length_append, List.length_cons, List.length_nil] at all
        omega
    · have whole_row : (row ++ [newline]).take written = row ++ [newline] := by
        apply List.take_of_length_le
        simp
        omega
      rw [whole_row, write_row log row clean, ended, List.nil_append]
      obtain ⟨whole, part, eq, isPrefix, fragment, all⟩ :=
        ih { lines := log.lines ++ [row], tail := [] } later rfl (written - (row ++ [newline]).length)
      refine ⟨row :: whole, part, ?_, ?_, ?_, ?_⟩
      · rw [eq]; simp
      · exact List.prefix_cons_inj row |>.mpr isPrefix
      · exact fragment.imp id fun ⟨other, mem, cut⟩ => ⟨other, List.mem_cons_of_mem _ mem, cut⟩
      · intro enough
        have rest_fits : (rest.flatMap (· ++ [newline])).length ≤ written - (row ++ [newline]).length := by
          simp only [List.length_append, List.length_cons, List.length_nil] at enough ⊢
          omega
        obtain ⟨whole_eq, part_eq⟩ := all rest_fits
        exact ⟨by rw [whole_eq], part_eq⟩

/-! ## One append -/

/-- What an append leaves, cut or not: the lines the log had, the line that had no end when
there was one and a byte was written, some of the rows as whole lines, the first ones, and
then nothing or the first bytes of the next row. -/
theorem append_cases (log : Log) (rows : List Line) (plain : ∀ row ∈ rows, newline ∉ row) (written : Nat) :
    ∃ ended whole part, log.append rows written = { lines := log.lines ++ ended ++ whole, tail := part }
      ∧ (ended = [] ∨ (ended = [log.tail] ∧ log.tail ≠ [])) ∧ whole <+: rows
      ∧ (part = [] ∨ (∃ row ∈ rows, part <+: row) ∨ part = log.tail)
      ∧ ((log.data rows).length ≤ written → rows ≠ [] →
          ended = (if log.tail.isEmpty then [] else [log.tail]) ∧ whole = rows ∧ part = []) := by
  unfold append
  by_cases none : rows.isEmpty = true
  · have empty : rows = [] := List.isEmpty_iff.mp none
    simp only [none, ↓reduceIte]
    exact ⟨[], [], log.tail, by simp, Or.inl rfl, List.nil_prefix, Or.inr (Or.inr rfl), fun _ some => absurd empty some⟩
  · simp only [none, Bool.false_eq_true, ↓reduceIte]
    unfold data
    by_cases open_ : log.tail.isEmpty = true
    · have ended : log.tail = [] := List.isEmpty_iff.mp open_
      simp only [open_, ↓reduceIte, List.nil_append]
      obtain ⟨whole, part, eq, isPrefix, fragment, all⟩ := write_rows log rows plain ended written
      refine ⟨[], whole, part, by rw [eq]; simp, Or.inl rfl, isPrefix, fragment.imp id Or.inl, fun enough _ => ?_⟩
      exact ⟨rfl, all enough⟩
    · simp only [open_, Bool.false_eq_true, ↓reduceIte]
      by_cases nothing : written = 0
      · subst nothing
        refine ⟨[], [], log.tail, by simp [write], Or.inl rfl, List.nil_prefix, Or.inr (Or.inr rfl), fun enough _ => ?_⟩
        simp at enough
      · obtain ⟨less, rfl⟩ : ∃ less, written = less + 1 := ⟨written - 1, by omega⟩
        have ends : log.write [newline] = { lines := log.lines ++ [log.tail], tail := [] } := by simp [write, push]
        rw [List.singleton_append, List.take_succ_cons, ← List.singleton_append, write_append, ends]
        obtain ⟨whole, part, eq, isPrefix, fragment, all⟩ :=
          write_rows { lines := log.lines ++ [log.tail], tail := [] } rows plain rfl less
        have unended : log.tail ≠ [] := fun empty => open_ (List.isEmpty_iff.mpr empty)
        refine ⟨[log.tail], whole, part, eq, Or.inr ⟨rfl, unended⟩, isPrefix, fragment.imp id Or.inl, fun enough _ => ?_⟩
        simp only [List.length_cons] at enough
        exact ⟨rfl, all (by omega)⟩

/-- A complete line stays as it is: an append adds lines after those the log has. -/
theorem append_keeps (log : Log) (rows : List Line) (plain : ∀ row ∈ rows, newline ∉ row) (written : Nat) :
    log.lines <+: (log.append rows written).lines := by
  obtain ⟨ended, whole, part, eq, _⟩ := append_cases log rows plain written
  rw [eq, List.append_assoc]
  exact List.prefix_append _ _

/-- An append that is not cut adds its rows as lines, each whole, after the line that had
no end, when there was one. -/
theorem append_whole (log : Log) (rows : List Line) (plain : ∀ row ∈ rows, newline ∉ row) (some : rows ≠ [])
    (written : Nat) (all : (log.data rows).length ≤ written) :
    log.append rows written
      = { lines := log.lines ++ (if log.tail.isEmpty then [] else [log.tail]) ++ rows, tail := [] } := by
  obtain ⟨ended, whole, part, eq, _, _, _, complete⟩ := append_cases log rows plain written
  obtain ⟨ended_eq, whole_eq, part_eq⟩ := complete all some
  rw [eq, ended_eq, whole_eq, part_eq]

/-! ## Any appends -/

/-- The log after appends, each with its rows and how many bytes of it reach the file. -/
def appends (log : Log) (steps : List (List Line × Nat)) : Log :=
  steps.foldl (fun log step => log.append step.1 step.2) log

/-- A line that is read is read after any appends that follow. -/
theorem appends_keep (log : Log) (steps : List (List Line × Nat))
    (plain : ∀ step ∈ steps, ∀ row ∈ step.1, newline ∉ row) : ∀ line ∈ log.read, line ∈ (log.appends steps).read := by
  induction steps generalizing log with
  | nil => exact fun _ mem => mem
  | cons step rest ih =>
    intro line mem
    refine ih (log.append step.1 step.2) (fun other at_ => plain other (List.mem_cons_of_mem _ at_)) line ?_
    exact (append_keeps log step.1 (plain step List.mem_cons_self) step.2).subset mem

/-- Every row of an append that was not cut is read, after any appends that follow, cut or
not, and whatever the log held before, a line with no end too. -/
theorem whole_read (log : Log) (rows : List Line) (plain : ∀ row ∈ rows, newline ∉ row) (written : Nat)
    (all : (log.data rows).length ≤ written) (steps : List (List Line × Nat))
    (later : ∀ step ∈ steps, ∀ row ∈ step.1, newline ∉ row) :
    ∀ row ∈ rows, row ∈ ((log.append rows written).appends steps).read := by
  intro row mem
  refine appends_keep _ steps later row ?_
  have some : rows ≠ [] := fun empty => by rw [empty] at mem; cases mem
  rw [append_whole log rows plain some written all]
  exact List.mem_append_right _ mem

/-- A log after appends to an empty file, some of them cut, of rows that hold no newline,
with every row an append was given. -/
inductive Reachable : Log → List Line → Prop
  | start : Reachable {} []
  | append {log : Log} {handed : List Line} (rows : List Line) (written : Nat) : Reachable log handed →
      (∀ row ∈ rows, newline ∉ row) → Reachable (log.append rows written) (handed ++ rows)

/-- Every line read is a row an append was given, or the first bytes of one whose write was
cut; and so is the line with no end. -/
theorem Reachable.read_given {log : Log} {handed : List Line} (reached : Reachable log handed) :
    (∀ line ∈ log.read, ∃ row ∈ handed, line <+: row) ∧ (log.tail = [] ∨ ∃ row ∈ handed, log.tail <+: row) := by
  induction reached with
  | start =>
    refine ⟨?_, Or.inl rfl⟩
    intro _ mem
    cases mem
  | @append log handed rows written _ plain ih =>
    obtain ⟨ended, whole, part, eq, wasOpen, isPrefix, fragment, _⟩ := append_cases log rows plain written
    rw [eq]
    refine ⟨?_, ?_⟩
    · intro line mem
      rcases List.mem_append.mp mem with before | new
      · rcases List.mem_append.mp before with old | cut
        · obtain ⟨row, has, starts⟩ := ih.1 line old
          exact ⟨row, List.mem_append_left _ has, starts⟩
        · rcases wasOpen with none | ⟨one, unended⟩
          · rw [none] at cut; cases cut
          · rw [one] at cut
            simp only [List.mem_singleton] at cut
            rcases ih.2 with empty | ⟨row, has, starts⟩
            · exact absurd empty unended
            · exact ⟨row, List.mem_append_left _ has, cut ▸ starts⟩
      · exact ⟨line, List.mem_append_right _ (isPrefix.subset new), List.prefix_refl _⟩
    · rcases fragment with none | ⟨row, has, starts⟩ | same
      · exact Or.inl none
      · exact Or.inr ⟨row, List.mem_append_right _ has, starts⟩
      · show part = [] ∨ _
        rw [same]
        exact ih.2.imp id fun ⟨row, has, starts⟩ => ⟨row, List.mem_append_left _ has, starts⟩

end Log

/-- info: 'Contraagent.Log.whole_read' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Log.whole_read

/-- info: 'Contraagent.Log.Reachable.read_given' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Log.Reachable.read_given

/-! ## Reading what is found -/

theorem Found.read_nil (found : Found) (none_read : found.read = some []) :
    found = .absent ∨ ∃ log, found = .present log ∧ log.read = [] := by
  cases found with
  | absent => exact .inl rfl
  | unreadable => simp [Found.read] at none_read
  | present log =>
    simp only [Found.read, Option.some.injEq] at none_read
    exact .inr ⟨log, rfl, none_read⟩

end Contraagent
