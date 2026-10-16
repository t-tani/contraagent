`contraagent recording import RUN_DIR DIR` (`contraagent.import_recording(run_dir,
directory)`, which returns a `RecordingImport`) writes a recording of each task a run
finished from its run directory, as if the run had been recorded, so a replay plays a past
run's outputs without running it again. A replay plays an imported recording only for a
task of the fingerprint that run recorded; a task changed since ends `error`, or with
`--record-missing` launches and is recorded again. The import lists the tasks it leaves
out: those that did not finish, and those with a missing, rewritten or too large file.
See `contraagent docs testing`.
