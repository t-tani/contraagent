A Python task call refuses `credential=` at the call with a `TypeError` that says a
Python task has no credential, and `contraagent check` reports it, where the run used to
fail with a `TypeError` from the function. A call that names a keyword its function has
no parameter for, or leaves out a required one, is refused at the call the same way. A
task call's `key` that is not a string and an `after` that is not a list of tasks (a
string, a number in the list) are refused at the call too, for agent and Python tasks.
