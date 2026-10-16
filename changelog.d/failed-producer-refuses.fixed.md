**A failed task's output is not read.** A task whose input is the output of a task that did
not succeed (any stop but `completed`, `partial` and `skipped`, `invalid_output` included: its
file meets its schema and its validators rejected it) ends `invalid_input`, its reason
`invalid input: input from <key> ended <stop>: <path>`, as an input that is missing does: in
an agent task and a Python task, in a flow that yields and one that does not, on resume. The
monitor names the cause: "input out/review/a.json is the output of failed task review · a",
"not started (earlier task failed)".
