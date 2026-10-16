"""Run records: what a run writes in its directory, and the one way each is written and read.

* `layout`: the name of each record (`journal.jsonl`, `streams/<file>.stream.jsonl`,
  `run.json`, ...), the file name of a task's files, the files a contract names.
* `files`: a document written atomically, lines appended to a log, a log's complete
  lines read by line or by byte offset, its JSON rows.
* `times`: the times records hold, written and parsed one way.
* `names`: the check that keeps a name from outside a plain file name.
* `source`: `RunSource`, where runs' records are read from: `DirectorySource` (one
  host's `runs/`), `MemorySource`; a page of lines.
* `liveness`, `procs`: which runs are live and their processes: `Liveness`,
  `StaticLiveness`, `ProcLiveness` (the OS's processes).

Writers (`execution`, `contracts`, the call files) and readers (`monitor`, `hub`)
import this; it imports only the standard library and the leaf modules `processes`
(over `psutil`), `envvars` and `telemetry`.
"""
