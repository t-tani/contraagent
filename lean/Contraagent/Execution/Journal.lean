import Contraagent.Execution.Run
import Contraagent.Runs.Files

/-!
# The journal a resume reads

What `Journal` of `src/contraagent/_internal/execution/journal.py` gives a resume: the rows
of the journal's log (`rows`), each key's last row (`last_rows`), and the tasks an attempt
of which the run's end cut (`unfinished_keys`).

Left out: what a row holds beyond what a resume reads; `launches.jsonl`; and the place of
each key in the journal (`places`), which orders the results a resume gives a flow.
-/

namespace Contraagent

/-- How a journal row is written as a line and read back (`JournalRow.model_dump_json`,
`parse_rows`). A row's line holds no newline. A line that is the first bytes of a row's
line, and not all of it, is no row: a JSON object that is cut does not parse. -/
structure RowFormat where
  render : JournalRow → Line
  parse : Line → Option JournalRow
  plain : ∀ row, newline ∉ render row
  whole : ∀ row, parse (render row) = some row
  cut : ∀ row line, line <+: render row → line ≠ render row → parse line = none

/-- The rows of a journal (`Journal.rows`): the complete lines of its log that parse. -/
def journalRows (format : RowFormat) (log : Log) : List JournalRow :=
  log.read.filterMap format.parse

/-- Each key's last row (`Journal.last_rows`): a row that a later row of its key follows is
left out. -/
def lastRows : List JournalRow → List JournalRow
  | [] => []
  | row :: rest => if rest.any (·.key == row.key) then lastRows rest else row :: lastRows rest

/-- The rows a resume reads of the journal as it finds it (`Journal.read`): none when there
is no journal, and nothing when it cannot be read, where the run stops (`Found.read`). -/
def foundRows (format : RowFormat) (found : Found) : Option (List JournalRow) :=
  found.read.map (·.filterMap format.parse)

/-- The keys of the tasks that were in flight when the run's process ended and whose
attempt left no row (`unfinished_keys`). `markers`: the in-flight markers the run left,
each with its task's key and how many rows the journal held when the task started. A marker
is of an attempt that did not finish when the journal holds no row of its key from that
place on. A marker that does not read still names its task by its file, and is given as
one placed after every row (`rows.length`): its attempt may have begun after any of them. -/
def unfinishedKeys (rows : List JournalRow) (markers : List (Key × Nat)) : List Key :=
  (markers.filter fun marker => !(rows.drop marker.2).any (·.key == marker.1)).map (·.1)

end Contraagent
