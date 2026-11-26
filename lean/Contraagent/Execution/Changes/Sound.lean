import Contraagent.Execution.Changes

/-!
# The test of two tasks' changes patterns misses no file

When the test finds no pair of patterns that may cover one path (`mayOverlap` answers
`none`), no path is covered by a pattern of each (`mayOverlap_sound`): not one that both
match, and not one under a directory that one of them matches. So two tasks the queue lets
run at once never change one file through their patterns.

What a pattern covers is read as the code reads the pattern (`rawParts`), with a set read
as any one character, which errs toward a cover. Two paths name one file when they are the
same folded (`fold`, each character): the file system is taken to tell names apart by
nothing that folding takes away. The code folds more than the description (case beyond
ASCII letters, `str.casefold`, and Unicode's NFC form), which only makes more names the
same.

The proof: a folded segment matches the folded form of every name the segment it comes
from matches (`widen_matches`); a folded pattern covers the folded form of every path the
pattern covers (`widen_covers`); and two folded segments, or two folded patterns, that match
or cover one name or path are found to meet (`segMeet_sound`, `meet_sound`).
-/

namespace Contraagent

/-! ## What a pattern matches -/

/-- A segment as read matches a name: `?` and a set one character (what a set holds is
left out: any one character), `*` any characters. -/
inductive RawMatch : List RawTok → List Char → Prop where
  | nil : RawMatch [] []
  | lit {c : Char} {p : List RawTok} {n : List Char} : RawMatch p n → RawMatch (.lit c :: p) (c :: n)
  | one {p : List RawTok} {c : Char} {n : List Char} : RawMatch p n → RawMatch (.one :: p) (c :: n)
  | set {body : List Char} {p : List RawTok} {c : Char} {n : List Char} :
      RawMatch p n → RawMatch (.set body :: p) (c :: n)
  | starStop {p : List RawTok} {n : List Char} : RawMatch p n → RawMatch (.star :: p) n
  | starTake {p : List RawTok} {c : Char} {n : List Char} :
      RawMatch (.star :: p) n → RawMatch (.star :: p) (c :: n)

/-- A pattern as read covers a path, its segments from the working directory on: it matches
the path, or a directory the path is under (a pattern that ended covers what is left);
`**` is any number of segments. -/
inductive RawCovers : List RawPart → List (List Char) → Prop where
  | done {x : List (List Char)} : RawCovers [] x
  | name {r : List RawTok} {p : List RawPart} {n : List Char} {x : List (List Char)} :
      RawMatch r n → RawCovers p x → RawCovers (.name r :: p) (n :: x)
  | starStop {p : List RawPart} {x : List (List Char)} : RawCovers p x → RawCovers (.globstar :: p) x
  | starTake {p : List RawPart} {n : List Char} {x : List (List Char)} :
      RawCovers (.globstar :: p) x → RawCovers (.globstar :: p) (n :: x)

/-- A folded segment matches a name. -/
inductive SegMatch : Seg → List Char → Prop where
  | nil : SegMatch [] []
  | lit {c : Char} {p : Seg} {n : List Char} : SegMatch p n → SegMatch (.lit c :: p) (c :: n)
  | starStop {p : Seg} {n : List Char} : SegMatch p n → SegMatch (.star :: p) n
  | starTake {p : Seg} {c : Char} {n : List Char} : SegMatch (.star :: p) n → SegMatch (.star :: p) (c :: n)

/-- A folded pattern covers a path. -/
inductive Covers : Pattern → List (List Char) → Prop where
  | done {x : List (List Char)} : Covers [] x
  | name {s : Seg} {p : Pattern} {n : List Char} {x : List (List Char)} :
      SegMatch s n → Covers p x → Covers (.name s :: p) (n :: x)
  | starStop {p : Pattern} {x : List (List Char)} : Covers p x → Covers (.globstar :: p) x
  | starTake {p : Pattern} {n : List Char} {x : List (List Char)} :
      Covers (.globstar :: p) x → Covers (.globstar :: p) (n :: x)

/-! ## Folding loses no name -/

theorem widen_star (rest : List RawTok) (tok : RawTok) (notLit : ∀ c, tok ≠ .lit c) :
    widen (tok :: rest) = (match widen rest with
      | .star :: more => .star :: more
      | more => .star :: more) := by
  cases tok with
  | lit c => exact absurd rfl (notLit c)
  | one => rfl
  | set body => rfl
  | star => rfl

/-- What `widen` puts before a folded segment for a `?`, a set or a `*`: a `*`, one only. -/
def starred (w : Seg) : Seg :=
  match w with
  | .star :: more => .star :: more
  | more => .star :: more

theorem starred_eq (w : Seg) : ∃ more, starred w = .star :: more := by
  unfold starred
  split
  · exact ⟨_, rfl⟩
  · exact ⟨_, rfl⟩

theorem starred_stop {w : Seg} {n : List Char} (h : SegMatch w n) : SegMatch (starred w) n := by
  unfold starred
  split
  · exact h
  · exact .starStop h

theorem starred_take {w : Seg} {c : Char} {n : List Char} (h : SegMatch (starred w) n) :
    SegMatch (starred w) (c :: n) := by
  obtain ⟨more, eq⟩ := starred_eq w
  rw [eq] at h ⊢
  exact .starTake h

theorem widen_wild (tok : RawTok) (rest : List RawTok) (notLit : ∀ c, tok ≠ .lit c) :
    widen (tok :: rest) = starred (widen rest) := by
  rw [widen_star rest tok notLit]
  rfl

/-- A folded segment matches the folded form of every name its segment matches. -/
theorem widen_matches {r : List RawTok} {n : List Char} (h : RawMatch r n) :
    SegMatch (widen r) (n.map fold) := by
  induction h with
  | nil => exact .nil
  | lit _ ih => exact .lit ih
  | one _ ih =>
    rw [widen_wild _ _ (fun _ h => RawTok.noConfusion h)]
    exact starred_take (starred_stop ih)
  | set _ ih =>
    rw [widen_wild _ _ (fun _ h => RawTok.noConfusion h)]
    exact starred_take (starred_stop ih)
  | starStop _ ih =>
    rw [widen_wild _ _ (fun _ h => RawTok.noConfusion h)]
    exact starred_stop ih
  | starTake _ ih =>
    rw [widen_wild _ _ (fun _ h => RawTok.noConfusion h)] at ih ⊢
    exact starred_take ih

/-- A folded pattern covers the folded form of every path its pattern covers. -/
theorem widen_covers {p : List RawPart} {x : List (List Char)} (h : RawCovers p x) :
    Covers (p.map widenPart) (x.map (·.map fold)) := by
  induction h with
  | done => exact .done
  | name hn _ ih => exact .name (widen_matches hn) ih
  | starStop _ ih => exact .starStop ih
  | starTake _ ih => exact .starTake ih

/-! ## The test finds every meeting -/

theorem segMeet_nil_left : ∀ {q : Seg}, SegMatch q [] → segMeet [] q = true
  | [], _ => by simp [segMeet]
  | .lit _ :: _, h => by cases h
  | .star :: q, h => by
    cases h with
    | starStop h' => simp only [segMeet]; exact segMeet_nil_left h'

theorem segMeet_nil_right : ∀ {p : Seg}, SegMatch p [] → segMeet p [] = true
  | [], _ => by simp [segMeet]
  | .lit _ :: _, h => by cases h
  | .star :: p, h => by
    cases h with
    | starStop h' => simp only [segMeet]; exact segMeet_nil_right h'

/-- Two folded segments that match one name meet. -/
theorem segMeet_sound : ∀ (p q : Seg) (n : List Char), SegMatch p n → SegMatch q n → segMeet p q = true
  | [], _, _, hp, hq => by cases hp; exact segMeet_nil_left hq
  | .lit c :: p, [], _, hp, hq => by cases hq; exact segMeet_nil_right hp
  | .star :: p, [], _, hp, hq => by cases hq; exact segMeet_nil_right hp
  | .lit c :: p, .lit d :: q, n, hp, hq => by
    cases hp with
    | lit hp' =>
      cases hq with
      | lit hq' => simp only [segMeet, beq_self_eq_true, Bool.true_and]; exact segMeet_sound p q _ hp' hq'
  | .lit c :: p, .star :: q, n, hp, hq => by
    simp only [segMeet, Bool.or_eq_true]
    cases hq with
    | starStop hq' => exact Or.inl (segMeet_sound (.lit c :: p) q n hp hq')
    | starTake hq' =>
      cases hp with
      | lit hp' => exact Or.inr (segMeet_sound p (.star :: q) _ hp' hq')
  | .star :: p, .lit d :: q, n, hp, hq => by
    simp only [segMeet, Bool.or_eq_true]
    cases hp with
    | starStop hp' => exact Or.inl (segMeet_sound p (.lit d :: q) n hp' hq)
    | starTake hp' =>
      cases hq with
      | lit hq' => exact Or.inr (segMeet_sound (.star :: p) q _ hp' hq')
  | .star :: p, .star :: q, n, hp, hq => by
    cases hp with
    | starStop hp' =>
      simp only [segMeet, Bool.or_eq_true]
      exact Or.inl (segMeet_sound p (.star :: q) n hp' hq)
    | starTake hp' =>
      cases hq with
      | starStop hq' =>
        simp only [segMeet, Bool.or_eq_true]
        exact Or.inr (segMeet_sound (.star :: p) q _ (.starTake hp') hq')
      | starTake hq' => exact segMeet_sound (.star :: p) (.star :: q) _ hp' hq'
termination_by p q n => p.length + q.length + n.length

/-- Two folded patterns that cover one path meet. -/
theorem meet_sound : ∀ (p q : Pattern) (x : List (List Char)), Covers p x → Covers q x → meet p q = true
  | [], _, _, _, _ => by simp [meet]
  | _ :: _, [], _, _, _ => by simp [meet]
  | .globstar :: p, b :: q, x, hp, hq => by
    cases hp with
    | starStop hp' =>
      simp only [meet, Bool.or_eq_true]
      exact Or.inl (meet_sound p (b :: q) x hp' hq)
    | starTake hp' =>
      cases b with
      | name t =>
        cases hq with
        | name _ hq' =>
          simp only [meet, Bool.or_eq_true]
          exact Or.inr (meet_sound (.globstar :: p) q _ hp' hq')
      | globstar =>
        cases hq with
        | starStop hq' =>
          simp only [meet, Bool.or_eq_true]
          exact Or.inr (meet_sound (.globstar :: p) q _ (.starTake hp') hq')
        | starTake hq' => exact meet_sound (.globstar :: p) (.globstar :: q) _ hp' hq'
  | .name s :: p, .globstar :: q, x, hp, hq => by
    simp only [meet, Bool.or_eq_true]
    cases hq with
    | starStop hq' => exact Or.inl (meet_sound (.name s :: p) q x hp hq')
    | starTake hq' =>
      cases hp with
      | name _ hp' => exact Or.inr (meet_sound p (.globstar :: q) _ hp' hq')
  | .name s :: p, .name t :: q, x, hp, hq => by
    cases hp with
    | name hs hp' =>
      cases hq with
      | name ht hq' =>
        simp only [meet, Bool.and_eq_true]
        exact ⟨segMeet_sound s t _ hs ht, meet_sound p q _ hp' hq'⟩
termination_by p q x => p.length + q.length + x.length

/-! ## The test misses no file -/

/-- When the test finds no pair, no path is covered by a pattern of each: a covering pattern
of `a` covers no path `x` that names the file a covering pattern of `b` covers as `y`. -/
theorem mayOverlap_sound {a b : List String} (none : mayOverlap a b = none) {pa pb : String}
    (inA : pa ∈ covering a) (inB : pb ∈ covering b) {x y : List (List Char)}
    (ha : RawCovers (rawParts pa) x) (hb : RawCovers (rawParts pb) y)
    (same : x.map (·.map fold) = y.map (·.map fold)) : False := by
  have hx := widen_covers ha
  have hy := widen_covers hb
  rw [← same] at hy
  have met : meet (parse pa) (parse pb) = true := meet_sound _ _ _ hx hy
  unfold mayOverlap at none
  rw [List.findSome?_eq_none_iff] at none
  have inner := none pa inA
  rw [List.findSome?_eq_none_iff] at inner
  have found := inner pb inB
  rw [met] at found
  simp at found

/-- info: 'Contraagent.mayOverlap_sound' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms mayOverlap_sound

end Contraagent
