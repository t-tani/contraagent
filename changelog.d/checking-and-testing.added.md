**Checking and testing.** `contraagent check flow.py:flow` (`Pipeline.check`) builds and
checks the task graph with nothing launched, and reports every problem at once: the flow,
parameters, output models, command validators, plugins and routing, each error with the
documentation topic that explains it. `contraagent.testing.StubAgent` plays scripted
replies in place of a coding agent in tests, and a stub run (`contraagent run --stub`)
runs the whole flow on the smallest outputs its schemas accept. A run records each attempt
with `--record DIR`, and a later run replays them with nothing spent (`--replay DIR`;
`--record-missing` launches only what has no recording).
