**An input's record names its producer.** In `/api/runs/{run}/outputs`, each input of a task
(`ContractSpec`, `io: "input"`) has `producer`, the key of the task whose output it is; a
task's `params` there are its strings, numbers and booleans, so a Python task given only other
tasks' outputs (`reviews=`) shows `params: {}` and those outputs as its `inputs`.
