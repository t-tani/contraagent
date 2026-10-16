**Output checks.** Each output is checked against its schema and its validators; an
output that does not pass goes back to the same agent session with the errors, for a
number of correction rounds. A validator is a Python function that may take the task's
`params`, its call file and the output file as it was before the task (`before`); a
`CommandValidator` runs a program, also from the agent's own stop hook, so the agent fixes
its output before its turn ends. Inputs are checked too: a task whose input is missing or
does not pass its checks does not start, and the cause names the earlier task.
