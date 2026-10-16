A flow can be checked and tested with nothing spent. `contraagent check` builds the task
graph and reports every problem in the flow, the output models, the validators, the
plugins and the routing at once, each with the documentation topic that explains it.
`contraagent.testing.StubAgent` plays scripted replies in tests, and a stub run
(`contraagent run --stub`) runs the whole flow on each output's example. A run records
each attempt with `--record DIR`, and a later run replays the recordings with
`--replay DIR`.
