/-!
# The changes patterns that may cover one file

What `src/contraagent/_internal/execution/changes.py` decides of two tasks' `changes`
patterns: whether a pattern of each may cover one file (`may_overlap`, `overlap`), which
the queue reads to keep two tasks apart (`Graph.conflicts`).

A pattern is a `Path.glob` pattern relative to a working directory. Its segments, between
`/` (or `\`), are read as the code reads them (`rawParts`): `**` is any number of segments,
and in any other segment `*` is any characters, `?` one character, and `[...]` one
character of a set, when a `]` closes it at least two characters on (`_segment`). A
pattern covers the paths it matches and everything under a directory it matches. The test
reads each pattern folded (`parse`, the code's `folded`): `?` and a set made `*`, a run of
`*` one, and each letter folded. The proofs about it are in `Execution/Changes/Sound.lean`.

Left out: what a set holds (any one character, here: the test reads a set as `*`); the
folding of case beyond ASCII letters and Unicode's normal form, which the code adds
(`str.casefold`, NFC); and how the code finds a directory's real path, which `overlap` is
given.
-/

namespace Contraagent

/-- A token of a segment as the code reads it from the pattern: a character, `?`, a set
(its characters between the brackets), or `*`. -/
inductive RawTok where
  | lit (c : Char)
  | one
  | set (body : List Char)
  | star
  deriving Repr, DecidableEq

/-- A segment of a pattern as read, or `**`. -/
inductive RawPart where
  | name (tokens : List RawTok)
  | globstar
  deriving Repr, DecidableEq

/-- A token of a folded segment: a character, or `*`. -/
inductive Tok where
  | lit (c : Char)
  | star
  deriving Repr, DecidableEq

abbrev Seg := List Tok

/-- A segment of a folded pattern, or `**`. -/
inductive Part where
  | name (seg : Seg)
  | globstar
  deriving Repr, DecidableEq

abbrev Pattern := List Part

/-- The tokens of one segment (`_segment`): `[` opens a set when a `]` closes it at least
two characters on; else it is a character. `fuel`: the number of characters is enough. -/
def tokensWithin : Nat → List Char → List RawTok
  | 0, _ => []
  | _, [] => []
  | fuel + 1, c :: rest =>
    if c == '*' then .star :: tokensWithin fuel rest
    else if c == '?' then .one :: tokensWithin fuel rest
    else if c == '[' then
      match rest with
      | first :: more =>
        match more.idxOf? ']' with
        | some i => .set (first :: more.take i) :: tokensWithin fuel (more.drop (i + 1))
        | none => .lit c :: tokensWithin fuel rest
      | [] => .lit c :: tokensWithin fuel rest
    else .lit c :: tokensWithin fuel rest

def tokens (seg : List Char) : List RawTok :=
  tokensWithin seg.length seg

/-- A pattern's segments as read: `\` is `/`, and an empty segment and `.` are left out. -/
def rawParts (pattern : String) : List RawPart :=
  ((pattern.replace "\\" "/").splitOn "/").filterMap fun seg =>
    if seg == "" || seg == "." then none
    else if seg == "**" then some .globstar
    else some (.name (tokens seg.toList))

/-- A character folded: an ASCII letter in lower case. -/
def fold (c : Char) : Char := c.toLower

/-- A segment folded (a part of `folded`): a character folded, `?`, a set and `*` made `*`,
a run of `*` one. -/
def widen : List RawTok → Seg
  | [] => []
  | .lit c :: rest => .lit (fold c) :: widen rest
  | _ :: rest =>
    match widen rest with
    | .star :: more => .star :: more
    | more => .star :: more

def widenPart : RawPart → Part
  | .name tokens => .name (widen tokens)
  | .globstar => .globstar

/-- A pattern as the test reads it (`folded`). -/
def parse (pattern : String) : Pattern :=
  (rawParts pattern).map widenPart

/-- Whether two folded segments match one name (`_names_meet`): a `*` matches nothing more,
or one more character. -/
def segMeet : Seg → Seg → Bool
  | [], [] => true
  | [], .star :: q => segMeet [] q
  | [], .lit _ :: _ => false
  | .star :: p, [] => segMeet p []
  | .lit _ :: _, [] => false
  | .star :: p, b :: q => segMeet p (b :: q) || segMeet (.star :: p) q
  | .lit c :: p, .star :: q => segMeet (.lit c :: p) q || segMeet p (.star :: q)
  | .lit c :: p, .lit d :: q => c == d && segMeet p q
termination_by p q => p.length + q.length

/-- Whether two folded patterns may cover one path (`_paths_meet`): a pattern that ended
matched a directory the other's path is under, and `**` is any number of segments. -/
def meet : Pattern → Pattern → Bool
  | [], _ => true
  | _ :: _, [] => true
  | .globstar :: p, b :: q => meet p (b :: q) || meet (.globstar :: p) q
  | .name s :: p, .globstar :: q => meet (.name s :: p) q || meet p (.globstar :: q)
  | .name s :: p, .name t :: q => segMeet s t && meet p q
termination_by p q => p.length + q.length

/-- The patterns that cover paths: those that do not start with `!` (`split`). -/
def covering (patterns : List String) : List String :=
  patterns.filter fun p => ! p.startsWith "!"

/-- A pattern of `a` and one of `b` that may cover one path (`may_overlap`): the first such
pair, `a`'s order first. -/
def mayOverlap (a b : List String) : Option (String × String) :=
  (covering a).findSome? fun pa =>
    (covering b).findSome? fun pb => if meet (parse pa) (parse pb) then some (pa, pb) else none

/-- A directory folded, as `overlap` compares it. -/
def foldDir (dir : String) : List Char :=
  dir.toList.map fold

/-- When `low` is under `top`: its path below `top` (`sub`). -/
def below (top low : List Char) : Option String :=
  let above := (top.reverse.dropWhile (· == '/')).reverse ++ ['/']
  if above.isPrefixOf low then some (String.ofList (low.drop above.length)) else none

/-- `mayOverlap` of the patterns `a`, relative to `dirA`, and `b`, relative to `dirB`
(`overlap`, given each directory's real path): in one directory, or in two of which one is
under the other, whose patterns are then read from the one above (`sub/<pattern>`). Two
directories apart share no file. A pattern of the one under is given as it was written. -/
def overlap (dirA : String) (a : List String) (dirB : String) (b : List String) : Option (String × String) :=
  let ra := foldDir dirA
  let rb := foldDir dirB
  let fromAbove (sub : String) (high deep : List String) (swapped : Bool) : Option (String × String) :=
    (covering deep).findSome? fun pattern =>
      (mayOverlap high [sub ++ "/" ++ pattern]).map fun found =>
        if swapped then (pattern, found.1) else (found.1, pattern)
  if ra == rb then mayOverlap a b
  else
    match below ra rb with
    | some sub => fromAbove sub a b false
    | none =>
      match below rb ra with
      | some sub => fromAbove sub b a true
      | none => none

end Contraagent
