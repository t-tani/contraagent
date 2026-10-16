**A stub run checks the flow's wiring, and says which validators need real content.** When a
task's only reply is `writes_smallest()` (every task of `contraagent run --stub`) and its
validators reject that value, the task ends `invalid_output` after one round, with no
correction round and no retry (it ended `error` after a correction round and every retry).
`contraagent run --stub` then ends with one line that counts those tasks, names the
validators of each kind that rejected the smallest outputs, and points to tests on
`StubAgent` with replies that carry real content (`contraagent docs testing`). A failed
task's line names an output in the run directory as `out/<kind>/<unit>.json`. The exit
status stays 1, as for any failed task. `LaunchResult.retryable` is new: False when another
attempt cannot end otherwise.
