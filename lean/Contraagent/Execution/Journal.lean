import Contraagent.Execution.Run
import Contraagent.Runs.Files

/-!
# The journal a resume reads

What `Journal` of `src/contraagent/_internal/execution/journal.py` gives a resume: the rows
of the journal's log (`rows`), and each key's last row (`last_rows`).

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

end Contraagent
