A recording run leaves out of its comparison of the working directory what
`Pipeline(record_exclude=[...])` or `contraagent run --record-exclude PATTERN` matches:
`Path.glob` patterns relative to the working directory, as in `changes=`, with no `!`.
The comparison does not enter a directory a pattern matches, and
`recordings/undeclared.json` names the patterns (`excluded`).
