`contraagent.pipeline_table()` works in flow code that `contraagent check`
(`Pipeline.check`) builds: it reads the table of the config the check is given, as a run
does, so a flow may read its pipeline table in its body. `contraagent.log` and
`contraagent.save` write into the check's temporary directory, which it removes.
