/-!
# A run's logs

What `append_lines` of `src/contraagent/_internal/runs/files.py` writes to a log, and
which lines its readers read (`read_lines`, `read_rows`). A log is a file of lines, each
ended by a newline. A write may be cut: a full disk or a host that lost power leaves the
first bytes of what was written, and a last line with no newline.

Left out: documents (`write_document`), which are replaced whole; reading by byte offset
and by blocks; the text of a line (a line here is its bytes); and the lock that keeps the
lines of one call together.
-/

namespace Contraagent

/-- The newline byte. -/
def newline : UInt8 := 10

/-- A line of a log, without its newline: its bytes. -/
abbrev Line := List UInt8

/-- A log file. `lines`: its complete lines, each without its newline, the first first.
`tail`: what follows the last newline, a line with no end yet. -/
structure Log where
  lines : List Line := []
  tail : Line := []
  deriving DecidableEq, Repr

namespace Log

/-- The file with one more byte at its end. -/
def push (log : Log) (byte : UInt8) : Log :=
  if byte == newline then { lines := log.lines ++ [log.tail], tail := [] } else { log with tail := log.tail ++ [byte] }

/-- The file with bytes written at its end. -/
def write (log : Log) (bytes : List UInt8) : Log :=
  bytes.foldl push log

/-- The bytes one call of `append_lines` writes for `rows`, lines without a newline: a
newline first when the file's last line has no end, so that the rows are whole lines, then
each row with its newline. -/
def data (log : Log) (rows : List Line) : List UInt8 :=
  (if log.tail.isEmpty then [] else [newline]) ++ rows.flatMap (· ++ [newline])

/-- `append_lines`: the rows appended to the log, of which `written` bytes reach the file:
all of them, or fewer when the write is cut. A call with no row writes nothing. -/
def append (log : Log) (rows : List Line) (written : Nat) : Log :=
  if rows.isEmpty then log else log.write ((log.data rows).take written)

/-- The complete lines of the log (`read_lines`): a last line with no newline is not read. -/
def read (log : Log) : List Line :=
  log.lines

end Log

end Contraagent
