A task call takes the task's params only. Its key, its order without data, its priority and an agent task's credential are its call options, given by the new `AgentTask.options(key=, after=, priority=, credential=, cancellable=)` and `PythonTask.options(key=, after=, priority=, cancellable=)`. `options` returns the same task with them, typed as the task is, and an option it is not given keeps the value it had (old → new):

- `task(u, key="k", priority=2, credential="c", a=1)` → `task.options(key="k", priority=2, credential="c")(u, a=1)`.
- `task(u, after=[p])` → `task.options(after=[p])(u)`.
- A call that still gives `key=`, `after=`, `priority=`, `credential=` or `cancellable=` to a task with no param of that name raises `TypeError`, which names `.options()`; a Python task given `credential=` raises as before.
- A params field or a Python task's parameter named `key`, `after`, `priority` or `credential` was refused where the task was declared → it is a param like any other, and the call gives it.
- `key=None` and `credential=None` on a call meant "none" → `options` takes a string for each, and None keeps the value the task had.
