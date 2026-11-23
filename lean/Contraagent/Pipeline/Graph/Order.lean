import Contraagent.Pipeline.Graph

/-!
# The tasks of one file come one after the other

Of the description of `Graph.add`: no two tasks have one key, and a task whose output file
an earlier task already writes or fills in waits for the latest such task
(`GraphOk.chained`). So the tasks of one file form a chain by `after`, and the queue, which
starts no task before the tasks it comes after have finished, never runs two of them at
once.
-/

namespace Contraagent

/-- Each task waits for the latest earlier task of its output file, when there is one.
`nodes`: the latest first. -/
def Chained : List GraphNode → Prop
  | [] => True
  | node :: earlier =>
    (∀ path, node.outputPath = some path →
      ∀ prev, earlier.find? (·.outputPath == some path) = some prev → prev.key ∈ node.after)
      ∧ Chained earlier

/-- What every graph keeps: no two tasks have one key; each task's output file is recorded,
as the file given to a task or among the files that tasks fill in; and each task waits for
the latest earlier task of its file. -/
structure GraphOk (s : GraphState) : Prop where
  keys : (s.nodes.map (·.key)).Nodup
  recorded : ∀ node ∈ s.nodes, ∀ path, node.outputPath = some path →
    (s.writers.lookup path).isSome ∨ (s.fillers.lookup path).isSome
  chained : Chained s.nodes.reverse

theorem lookup_append_isSome {β : Type} (l m : List (String × β)) (key : String)
    (h : (l.lookup key).isSome) : ((l ++ m).lookup key).isSome := by
  induction l with
  | nil => simp at h
  | cons pair l ih =>
    obtain ⟨k, v⟩ := pair
    by_cases same : key == k
    · simp [List.lookup, same]
    · simp only [List.cons_append, List.lookup, same] at h ⊢
      exact ih h

theorem lookup_append_self {β : Type} (l : List (String × β)) (key : String) (value : β) :
    ((l ++ [(key, value)]).lookup key).isSome := by
  induction l with
  | nil => simp
  | cons pair l ih =>
    obtain ⟨k, v⟩ := pair
    by_cases same : key == k
    · simp [List.lookup, same]
    · simp only [List.cons_append, List.lookup, same]
      exact ih

/-- A graph with the same tasks and the same record of their files keeps what it kept. -/
theorem GraphOk.congr {s s' : GraphState} (h : GraphOk s) (nodes : s'.nodes = s.nodes)
    (writers : s'.writers = s.writers) (fillers : s'.fillers = s.fillers) : GraphOk s' := by
  constructor
  · rw [nodes]; exact h.keys
  · rw [nodes, writers, fillers]; exact h.recorded
  · rw [nodes]; exact h.chained

theorem graphOk_takeLayout (s s' : GraphState) (decl : Declaration) (h : GraphOk s)
    (taken : takeLayout s decl = .ok s') : GraphOk s' := by
  unfold takeLayout at taken
  split at taken
  · cases taken; exact h
  · split at taken
    · cases taken; exact h.congr rfl rfl rfl
    · split at taken
      · cases taken
      · cases taken; exact h

/-- A task joins the graph: its key is new, and it waits for the latest earlier task of
its file. -/
theorem graphOk_insertNode (s : GraphState) (node : GraphNode) (base : String) (n : Nat) (h : GraphOk s)
    (fresh : ∀ old ∈ s.nodes, old.key ≠ node.key)
    (waits : ∀ path, node.outputPath = some path →
      ∀ prev, s.nodes.reverse.find? (·.outputPath == some path) = some prev → prev.key ∈ node.after) :
    GraphOk (insertNode s node base n) := by
  have nodes : (insertNode s node base n).nodes = s.nodes ++ [node] := by
    unfold insertNode
    dsimp only
    repeat' split
    all_goals rfl
  constructor
  · rw [nodes, List.map_append, List.nodup_append]
    refine ⟨h.keys, by simp, ?_⟩
    intro a ha b hb
    simp only [List.map_cons, List.map_nil, List.mem_singleton] at hb
    obtain ⟨old, mem, rfl⟩ := List.mem_map.mp ha
    rw [hb]
    exact fresh old mem
  · intro member mem path at_
    rw [nodes] at mem
    unfold insertNode
    dsimp only
    rcases List.mem_append.mp mem with old | new
    · have before := h.recorded member old path at_
      repeat' split
      all_goals first
        | exact before
        | (rcases before with w | f
           · exact Or.inl (lookup_append_isSome _ _ _ w)
           · exact Or.inr f)
        | (rcases before with w | f
           · exact Or.inl w
           · exact Or.inr (lookup_append_isSome _ _ _ f))
    · have same : member = node := by simpa using new
      subst same
      rw [at_]
      dsimp only
      split
      · split
        · rename_i held
          exact Or.inr held
        · exact Or.inr (lookup_append_self _ _ _)
      · exact Or.inl (lookup_append_self _ _ _)
  · rw [nodes, List.reverse_append]
    exact ⟨waits, h.chained⟩

/-- The file a task is given and the task it waits for on its account: whenever an earlier
task has that file, the task waits for the latest of them. A task with a file of its own is
given one that no earlier task has. -/
theorem taskFile_waits (s : GraphState) (decl : Declaration) (name base : String) (n : Nat)
    (h : GraphOk s) (path : Option String) (writer : Option Key)
    (file : taskFile s decl name base n = .ok (path, writer)) :
    ∀ p, path = some p → ∀ prev, s.nodes.reverse.find? (·.outputPath == some p) = some prev →
      writer = some prev.key := by
  intro p at_ prev found
  unfold taskFile at file
  split at file
  · cases file
    cases at_
  · split at file
    · unfold outputOf at file
      dsimp only at file
      cases file
      cases at_
      rw [found]
      rfl
    · cases file
  · dsimp only at file
    split at file
    · cases file
    · split at file
      · cases file
      · cases file
      · rename_i noWriter noFiller
        cases file
        cases at_
        have mem : prev ∈ s.nodes := by
          have := List.mem_of_find?_eq_some found
          simpa using this
        have has := List.find?_some found
        simp only [beq_iff_eq] at has
        rcases h.recorded prev mem _ has with w | f
        · rw [noWriter] at w
          simp at w
        · rw [noFiller] at f
          simp at f

/-- A task call keeps what every graph keeps, whether the call is refused or not. -/
theorem graphOk_addTask (s : GraphState) (decl : Declaration) (unit : String) (asked : Option Key)
    (after : List Key) (call : FlowCallId) (h : GraphOk s) :
    GraphOk (addTask s decl unit asked after call).1 := by
  unfold addTask
  dsimp only
  split
  · exact h
  · split
    · exact h
    · rename_i fresh
      split
      · exact h
      · rename_i laid taken
        have ok := graphOk_takeLayout s laid decl h taken
        have nodes : laid.nodes = s.nodes := by
          unfold takeLayout at taken
          repeat' split at taken
          all_goals first | (cases taken; rfl) | cases taken
        split
        · exact ok
        · rename_i path writer file
          apply graphOk_insertNode laid _ _ _ ok
          · intro old mem eq
            rw [nodes] at mem
            apply fresh
            simp only [List.any_eq_true]
            exact ⟨old, mem, by simpa using eq⟩
          · intro p at_ prev found
            have waits := taskFile_waits laid decl _ _ _ ok path writer file p at_ prev found
            dsimp only
            rw [waits]
            dsimp only
            split
            · rename_i has
              exact List.mem_eraseDups.mpr (by simpa using has)
            · exact List.mem_eraseDups.mpr (by simp)

/-- The graphs a flow builds: from the empty one, by task calls. -/
inductive Built : GraphState → Prop where
  | empty : Built {}
  | called (s : GraphState) (decl : Declaration) (unit : String) (asked : Option Key) (after : List Key)
      (call : FlowCallId) : Built s → Built (addTask s decl unit asked after call).1

theorem Built.ok {s : GraphState} (built : Built s) : GraphOk s := by
  induction built with
  | empty => exact ⟨by simp, by intro node mem; simp at mem, trivial⟩
  | called s decl unit asked after call _ ih => exact graphOk_addTask s decl unit asked after call ih

/-- No two tasks of a graph have one key. -/
theorem Built.keys_distinct {s : GraphState} (built : Built s) : (s.nodes.map (·.key)).Nodup :=
  built.ok.keys

/-- Each task of a graph waits for the latest earlier task of its output file, when there
is one: the tasks of one file come one after the other. -/
theorem Built.chained {s : GraphState} (built : Built s) : Chained s.nodes.reverse :=
  built.ok.chained

/-- info: 'Contraagent.Built.chained' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms Built.chained

end Contraagent
