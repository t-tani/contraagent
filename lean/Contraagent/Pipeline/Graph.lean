import Contraagent.Dispatch.Task

/-!
# The task graph: keys, files and order

What `Graph.add` of `src/contraagent/_internal/pipeline/graph.py` decides of a task call:
its key, its output file, and the tasks it waits for, or why the call is refused.

Left out: what a task is given (its params, its claims, its credential and working
directory), its fingerprint and its origin, the passes of the loops around the call, and
two declarations of one kind. A path is a POSIX path relative to `out/`.
-/

namespace Contraagent

/-- What the graph reads of a task's declaration. `outputName`: the template of its output
file (`{unit}`, `{key}`, `{kind}`); `none`: the task writes no output. `outputOf`: the kind
and the template of the declaration whose task's file it fills in, in place of a file of
its own. -/
structure Declaration where
  kind : Kind
  python : Bool := false
  outputName : Option String := none
  outputOf : Option (Kind × String) := none
  deriving Repr

/-- A task the graph holds. `outputPath`: its output file; `fills`: the file is another
task's, which it fills in (`output_of`). -/
structure GraphNode where
  key : Key
  kind : Kind
  after : List Key := []
  outputPath : Option String := none
  fills : Bool := false
  flowCall : FlowCallId := "0"
  deriving Repr

/-- Why a task call is refused (`ValueError`). -/
inductive GraphRefusal where
  /-- Its key is created by another flow call too. -/
  | twoFlowCalls (owner : FlowCallId)
  /-- Its key is used twice. -/
  | keyUsedTwice
  /-- Another kind's output template names the same files. -/
  | sameLayout (owner : Kind)
  /-- Its output file would be outside `out/`. -/
  | outside
  /-- Another task writes its output file. -/
  | oneWriter (writer : Key)
  /-- A task created before it already fills its output file in. -/
  | filledBefore (filler : Key)
  deriving DecidableEq, Repr

/-- The graph's record. `nodes`: the tasks, in the order they were created. `bases`: for
each key as given, the flow call that creates tasks under it and how many it created.
`layouts`: each output template, its kind filled in, with the kind that writes it.
`writers`: each output file with the task it is given to. `fillers`: each file with the
first task that fills it in. -/
structure GraphState where
  nodes : List GraphNode := []
  bases : List (String × (FlowCallId × Nat)) := []
  layouts : List (String × Kind) := []
  writers : List (String × Key) := []
  fillers : List (String × Key) := []
  deriving Repr

/-- A template filled in for one task (`str.format`). -/
def fillTemplate (template unit key kind : String) : String :=
  ((template.replace "{unit}" unit).replace "{key}" key).replace "{kind}" kind

/-- The name a task's file takes (`{unit}` of its template): the key of its call options
when they give one, else its unit, else its key without `python:`; a `/` or a `:` in it is
a `_`. -/
def fileName (asked : Option Key) (unit base : String) : String :=
  let name := match asked with
    | some key => if key.isEmpty then (if unit.isEmpty then (base.dropPrefix "python:").toString else unit) else key
    | none => if unit.isEmpty then (base.dropPrefix "python:").toString else unit
  (name.replace "/" "_").replace ":" "_"

/-- Whether a filled-in template is a path inside `out/` (`_filled`). -/
def insideOut (rel : String) : Bool :=
  ! rel.startsWith "/" && (rel.splitOn "/").all fun segment => segment != "" && segment != "." && segment != ".."

/-- A file name as its stem and its suffix (`Path.stem`, `Path.suffix`). -/
def stemAndSuffix (name : String) : String × String :=
  match (name.splitOn ".").reverse with
  | last :: before =>
    let stem := ".".intercalate before.reverse
    if before.isEmpty || stem.isEmpty || last.isEmpty then (name, "") else (stem, "." ++ last)
  | [] => (name, "")

/-- A path with its file's stem changed. -/
def withStem (path : String) (change : String → String) : String :=
  match (path.splitOn "/").reverse with
  | name :: before =>
    let (stem, suffix) := stemAndSuffix name
    "/".intercalate (before.reverse ++ [change stem ++ suffix])
  | [] => path

/-- A stem without the `~n` of the n-th task under one key (`_NUMBERED`). -/
def unnumbered (stem : String) : String :=
  match (stem.splitOn "~").reverse with
  | last :: before =>
    if ! before.isEmpty && ! last.isEmpty && last.all Char.isDigit then "~".intercalate before.reverse else stem
  | [] => stem

/-- The file of a task that fills in another's (`_output_of`), and the task to wait for.
The file is that of the latest task of the other kind whose file, its `~n` aside, is the
other's template filled in for this name; with none, the template's file itself. The task
to wait for is the latest that writes or fills the file. -/
def outputOf (s : GraphState) (other : Kind) (template name base : String) : String × Option Key :=
  let path := fillTemplate template name base other
  let path := match s.nodes.reverse.find? fun node =>
      node.kind == other && (node.outputPath.map fun p => withStem p unnumbered) == some path with
    | some node => node.outputPath.getD path
    | none => path
  (path, (s.nodes.reverse.find? (·.outputPath == some path)).map (·.key))

/-- A task's key as given: the key of its call options, else `<kind>-<unit>`, `<kind>`
with no unit, after `python:` for a Python task. -/
def baseKey (decl : Declaration) (unit : String) (asked : Option Key) : String :=
  let stem := if unit.isEmpty then decl.kind else decl.kind ++ "-" ++ unit
  let own := if decl.python then "python:" ++ stem else stem
  match asked with
  | some key => if key.isEmpty then own else key
  | none => own

/-- How many tasks the flow call has created under this key, this one counted, or why the
call is refused: another flow call creates tasks under it. -/
def countUnder (s : GraphState) (base : String) (call : FlowCallId) : Except GraphRefusal Nat :=
  let (owner, count) := (s.bases.lookup base).getD (call, 0)
  if owner != call then .error (.twoFlowCalls owner) else .ok (count + 1)

/-- The n-th task under one key: the key itself, then `<key>~n`. -/
def numberedKey (base : String) (n : Nat) : Key :=
  if n == 1 then base else base ++ "~" ++ toString n

/-- The template that a kind with a file of its own takes (`layout`), its kind filled in. -/
def layoutOf (decl : Declaration) : Option String :=
  match decl.outputName, decl.outputOf with
  | some template, none => some (template.replace "{kind}" decl.kind)
  | _, _ => none

/-- A kind takes its template (`layout`), or the call is refused: another kind's template
names the same files. -/
def takeLayout (s : GraphState) (decl : Declaration) : Except GraphRefusal GraphState :=
  match layoutOf decl with
  | none => .ok s
  | some template =>
    match s.layouts.lookup template with
    | none => .ok { s with layouts := s.layouts ++ [(template, decl.kind)] }
    | some owner => if owner != decl.kind then .error (.sameLayout owner) else .ok s

/-- A task's output file and the task it waits for on its account, or why the call is
refused. A task with a file of its own is given a file that no task writes or fills in. A
task that fills in another's file waits for the latest task that writes or fills it. -/
def taskFile (s : GraphState) (decl : Declaration) (name base : String) (n : Nat) :
    Except GraphRefusal (Option String × Option Key) :=
  match decl.outputName, decl.outputOf with
  | none, _ => .ok (none, none)
  | some _, some (other, template) =>
    if insideOut (fillTemplate template name base other) then
      let (path, writer) := outputOf s other template name base
      .ok (some path, writer)
    else .error .outside
  | some template, none =>
    let rel := fillTemplate template name base decl.kind
    if ! insideOut rel then .error .outside
    else
      let path := if n > 1 then withStem rel (· ++ "~" ++ toString n) else rel
      match s.writers.lookup path, s.fillers.lookup path with
      | some writer, _ => .error (.oneWriter writer)
      | none, some filler => .error (.filledBefore filler)
      | none, none => .ok (some path, none)

/-- The graph with one more task, which its file's record names: as the task the file is
given to, or among those that fill it in. -/
def insertNode (s : GraphState) (node : GraphNode) (base : String) (n : Nat) : GraphState :=
  let s := { s with
    nodes := s.nodes ++ [node]
    bases := (base, (node.flowCall, n)) :: s.bases.filter (·.1 != base) }
  match node.outputPath with
  | some path =>
    if node.fills then
      (if (s.fillers.lookup path).isSome then s else { s with fillers := s.fillers ++ [(path, node.key)] })
    else { s with writers := s.writers ++ [(path, node.key)] }
  | none => s

/-- A task call (`add`): the graph after it, and the task or why the call is refused.
`asked`: the key of its call options. `after`: the keys of the tasks its call options name.
`call`: the flow call whose code calls it. -/
def addTask (s : GraphState) (decl : Declaration) (unit : String) (asked : Option Key)
    (after : List Key) (call : FlowCallId) : GraphState × Except GraphRefusal GraphNode :=
  let base := baseKey decl unit asked
  match countUnder s base call with
  | .error why => (s, .error why)
  | .ok n =>
    let key := numberedKey base n
    if s.nodes.any (·.key == key) then (s, .error .keyUsedTwice)
    else
      match takeLayout s decl with
      | .error why => (s, .error why)
      | .ok s =>
        match taskFile s decl (fileName asked unit base) base n with
        | .error why => (s, .error why)
        | .ok (path, writer) =>
          let deps := match writer with
            | some w => if after.contains w then after else after ++ [w]
            | none => after
          let node : GraphNode :=
            { key := key, kind := decl.kind, after := deps.eraseDups, outputPath := path,
              fills := decl.outputOf.isSome && path.isSome, flowCall := call }
          (insertNode s node base n, .ok node)

end Contraagent
