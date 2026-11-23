import Contraagent.Dispatch.Task

/-!
# Credential rests

What `CredentialRests` of `src/contraagent/_internal/routing/quota.py` decides: which
credentials a run does not launch on now, because of a quota reading (a cap, or the quota
rule) or because a launch as them was refused.

A function here is one method of the code. It takes the two clocks the code reads: the
time of day (`now`), which readings and resets are in, and the clock that only moves
forward (`clock`), which the grace window is measured on. The quota rule and the account a
launch bills are answers of the surroundings (`RestsEnv`). What `on_change` is told is part
of the state (`log`). Left out: the locks, the reading a rule's rest records, and the text
of a rest.
-/

namespace Contraagent

/-- What `CredentialRests` is built with. `windows`: the windows a cap may name, in order,
each with how long a reading of it stands when it names no reset (`WINDOWS`). `caps`: the
cap of a credential or a pool for a window (`max_<window>_pct`). `members`: a pool's
members, `none` for a credential that is no pool. `finishingKinds`, `graceS`: the
queue's. `hasRule`: whether the pipeline has a quota rule. -/
structure RestsConfig where
  windows : List (String × Duration)
  caps : String → String → Option Int
  members : String → Option (List String)
  finishingKinds : List String := []
  graceS : Duration := 0
  hasRule : Bool := false

/-- What `CredentialRests` asks of its surroundings: what the quota rule says of a
credential's reading, `none` when the credential may launch, else the reason and the time
the rule gives for the rest's end; and the account a launch as a credential bills now. -/
structure RestsEnv where
  rule : String → QuotaReading → Option (String × Option Time)
  account : String → String

/-- A credential and an account. -/
abbrev RestKey := String × String

/-- The rests of one run (`CredentialRests`). `latest`: the newest reading of each
credential and account. `since`: when each was first found resting, on the clock that only
moves forward. `resting`: the rest each began with. `ruled`: the rests the rule gave an
end, with that end. `refused`: the rests of refused credentials, by credential, coding
agent and model. `log`: what `on_change` was told, the latest first. -/
structure RestsState where
  latest : List (RestKey × QuotaReading) := []
  since : List (RestKey × Time) := []
  resting : List (RestKey × Rest) := []
  ruled : List (RestKey × (Rest × Time)) := []
  refused : List ((String × String × String) × Rest) := []
  log : List (String × Rest) := []
  deriving Repr

/-- A table with one more entry: in the place of the entry of the same key, or last. -/
def putEntry {κ α : Type} [BEq κ] (entries : List (κ × α)) (key : κ) (value : α) : List (κ × α) :=
  if entries.any (·.1 == key) then entries.map fun entry => if entry.1 == key then (key, value) else entry
  else entries ++ [(key, value)]

namespace QuotaReading

/-- The window of a reading's own fields by its name. -/
def field (reading : QuotaReading) (window : String) : QuotaWindow :=
  if window == "five_hour" then reading.fiveHour
  else if window == "seven_day" then reading.sevenDay
  else {}

/-- Every window the reading gives a utilization or a reset for, by name
(`named_windows`): the two of its fields, then those of `windows`, which win for the same
name. -/
def namedWindows (reading : QuotaReading) : List (String × QuotaWindow) :=
  (reading.windows.foldl (fun named entry => putEntry named entry.1 entry.2)
    [("five_hour", reading.fiveHour), ("seven_day", reading.sevenDay)]).filter
    fun entry => entry.2.pct.isSome || entry.2.resetsAt.isSome

/-- Whether a reading was observed after another; one with no time, before every other. -/
def after (reading other : QuotaReading) : Bool :=
  match reading.observedAt, other.observedAt with
  | some a, some b => decide (a > b)
  | some _, none => true
  | none, _ => false

end QuotaReading

namespace RestsConfig

/-- How long a reading of a window stands when it names no reset: a window of `windows`,
its length; another, the shortest. -/
def length (cfg : RestsConfig) (window : String) : Duration :=
  match cfg.windows.lookup window with
  | some length => length
  | none => (cfg.windows.map (·.2)).foldl min ((cfg.windows.head?.map (·.2)).getD 0)

/-- When a reading stops standing (`stale_at`): the earliest reset among its windows, a
window that names no reset standing for its length after the reading was observed; `none`
when it says neither. -/
def staleAt (cfg : RestsConfig) (reading : QuotaReading) : Option Time :=
  let ends := reading.namedWindows.filterMap fun entry =>
    match entry.2.resetsAt with
    | some resets => some resets
    | none => reading.observedAt.map (· + cfg.length entry.1)
  match ends with
  | [] => none
  | first :: rest => some (rest.foldl min first)

/-- The cap that holds for a credential on a window: its own, else its pool's. -/
def capOf (cfg : RestsConfig) (name : String) (pool : Option String) (window : String) : Option Int :=
  match cfg.caps name window with
  | some cap => some cap
  | none => pool.bind fun p => cfg.caps p window

/-- The rest of a credential whose reading is past a cap (`_capped`): the first window, in
order, whose utilization is at its cap or past it, unless the window the reading describes
is over. -/
def capped (cfg : RestsConfig) (now : Time) (name : String) (pool : Option String) (reading : QuotaReading) :
    Option Rest :=
  cfg.windows.findSome? fun (window, length) =>
    match cfg.capOf name pool window, (reading.field window).pct with
    | some cap, some pct =>
      if pct < cap then none
      else
        match (reading.field window).resetsAt, reading.observedAt with
        | some resets, _ =>
          if resets ≤ now then none
          else some { credential := name, window := window, pct := some pct, cap := some cap, «until» := some resets,
                      account := reading.account }
        | none, some observed =>
          if now - observed > length then none
          else some { credential := name, window := window, pct := some pct, cap := some cap,
                      «until» := some (observed + length), account := reading.account }
        | none, none =>
          some { credential := name, window := window, pct := some pct, cap := some cap, account := reading.account }
    | _, _ => none

end RestsConfig

namespace RestsState

/-- A launch as a credential was refused on a coding agent and a model (`refuse`): the
credential rests there for the rest of the run, and `on_change` is told when that begins. -/
def refuse (s : RestsState) (name agent model : String) : RestsState :=
  if s.refused.any (·.1 == (name, agent, model)) then s
  else
    let rest : Rest := { credential := name, stop := "auth_failed", agent := agent, model := model }
    { s with refused := s.refused ++ [((name, agent, model), rest)], log := ("start", rest) :: s.log }

/-- A reading a coding agent reported (`observe`): the newest of each credential and
account counts, and one with no time counts as the newest; one that names no credential
counts for none. -/
def observe (s : RestsState) (reading : QuotaReading) : RestsState :=
  if reading.credential.isEmpty then s
  else
    let key := (reading.credential, reading.account)
    let newest := match s.latest.lookup key with
      | none => true
      | some old =>
        match reading.observedAt, old.observedAt with
        | some new, some had => decide (new ≥ had)
        | _, _ => true
    if newest then { s with latest := putEntry s.latest key reading } else s

/-- The newest reading of a credential for an account (`latest`): of that account, or of
none named; for no account, of any. Of two as new, the one that was first read. -/
def latestOf (s : RestsState) (name account : String) : Option QuotaReading :=
  let found := (s.latest.filter fun entry =>
    entry.1.1 == name && (account.isEmpty || entry.1.2 == account || entry.1.2.isEmpty)).map (·.2)
  found.foldl (fun best reading =>
    match best with
    | none => some reading
    | some newest => if reading.after newest then some reading else some newest) none

end RestsState

namespace RestsConfig

/-- What the quota rule's answer rests a credential by (`_judge`): nothing when the rule
gives no reason, or gives an end that has passed; else the rest, to the end the rule gives,
or with none to when the reading stops standing. With the end the rule gave, when it gave
one. -/
def ruledRest (now : Time) (name : String) (reading : QuotaReading) (ends : Option Time) :
    Option (String × Option Time) → Option (Rest × Option Time)
  | none => none
  | some (said, given) =>
    if said.isEmpty then none
    else
      match given with
      | some «end» =>
        if now < «end» then
          some ({ credential := name, rule := said, «until» := some «end», account := reading.account }, given)
        else none
      | none => some ({ credential := name, rule := said, «until» := ends, account := reading.account }, none)

/-- Whether a credential rests for an account now (`_judge`), recorded and told when that
begins or ends: the state after, the rest, and when the account was first found resting.
A rest the rule gave an end holds to that end, and the rule is not asked before it. Else
the newest reading decides: past a cap, or by the rule while the reading stands. -/
def judge (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState) (name : String)
    (pool : Option String) (key : RestKey) : RestsState × Option Rest × Time :=
  let reading := s.latestOf name key.2
  let held := (s.ruled.lookup key).filter fun entry => decide (now < entry.2)
  let s := if held.isSome then s else { s with ruled := s.ruled.filter (·.1 != key) }
  let (s, rest) : RestsState × Option Rest :=
    match held, reading with
    | some entry, _ => (s, some entry.1)
    | none, none => (s, none)
    | none, some reading =>
      match cfg.capped now name pool reading with
      | some rest => (s, some rest)
      | none =>
        let ends := cfg.staleAt reading
        let stands := match ends with
          | some «end» => decide (now < «end»)
          | none => true
        if cfg.hasRule && stands then
          match ruledRest now name reading ends (env.rule name reading) with
          | some (rest, some «end») => ({ s with ruled := putEntry s.ruled key (rest, «end») }, some rest)
          | some (rest, none) => (s, some rest)
          | none => (s, none)
        else (s, none)
  match rest with
  | none =>
    let s := { s with since := s.since.filter (·.1 != key) }
    match s.resting.lookup key with
    | some ended => ({ s with resting := s.resting.filter (·.1 != key), log := ("end", ended) :: s.log }, none, 0)
    | none => (s, none, 0)
  | some rest =>
    let first := (s.since.lookup key).getD clock
    let s := { s with since := putEntry s.since key first }
    if s.resting.any (·.1 == key) then (s, some rest, first)
    else ({ s with resting := putEntry s.resting key rest, log := ("start", rest) :: s.log }, some rest, first)

/-- Why one credential rests for a task of `kind` on a coding agent and a model now
(`_member_rest`), `none` when it does not. A refused credential rests at once. A task of a
finishing kind still launches for the grace window after the credential was first found
resting on its quota. The account is asked only of a credential that has a reading. -/
def memberRest (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState) (name : String)
    (pool : Option String) (kind agent model : String) : RestsState × Option Rest :=
  match s.refused.lookup (name, agent, model) with
  | some refused => (s, some refused)
  | none =>
    let account := if s.latest.any (·.1.1 == name) then env.account name else ""
    let (s, rest, first) := cfg.judge env now clock s name pool (name, account)
    match rest with
    | none => (s, none)
    | some rest =>
      if cfg.finishingKinds.contains kind && clock - first < cfg.graceS then (s, none) else (s, some rest)

/-- Each of some members of a pool, in order, with why it rests. -/
def memberRests (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (pool kind agent model : String) :
    RestsState → List String → RestsState × List (Option Rest)
  | s, [] => (s, [])
  | s, member :: others =>
    let (s, rest) := cfg.memberRest env now clock s member (some pool) kind agent model
    let (s, rests) := cfg.memberRests env now clock pool kind agent model s others
    (s, rest :: rests)

/-- Why a credential rests for a task of `kind` on a coding agent and a model now
(`rests`): one rest, or for a pool one for each member when every member rests; none when
it does not rest. -/
def rests (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (name kind agent model : String) : RestsState × List Rest :=
  match cfg.members name with
  | some members =>
    let (s, why) := cfg.memberRests env now clock name kind agent model s members
    (s, if !why.isEmpty && why.all (·.isSome) then why.filterMap id else [])
  | none =>
    let (s, rest) := cfg.memberRest env now clock s name none kind agent model
    (s, rest.toList)

/-- The members of a pool that rest for a task of `kind` on a coding agent and a model now
(`resting_members`). -/
def restingMembers (cfg : RestsConfig) (env : RestsEnv) (now clock : Time) (s : RestsState)
    (pool kind agent model : String) : RestsState × List String :=
  match cfg.members pool with
  | some members =>
    let (s, why) := cfg.memberRests env now clock pool kind agent model s members
    (s, (members.zip why).filterMap fun (member, rest) => if rest.isSome then some member else none)
  | none => (s, [])

end RestsConfig

end Contraagent
