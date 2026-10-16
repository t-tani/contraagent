The work queue starts the ready task with the longest remaining work first, within each
kind's `max_concurrent`. Claims (`claims=["topic:{unit}"]`) keep tasks that share a name
from running at the same time. A run's deadline, and time boxes over part of a flow,
defer the tasks that cannot finish in time, and a deferred task is not a failure. A
resumed run (`contraagent run --resume`) runs a task again only when its parameters, its
definition or its inputs changed.
