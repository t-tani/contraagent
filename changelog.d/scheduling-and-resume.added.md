**Scheduling and resume.** The work queue starts the ready task with the longest
remaining work first, puts tasks that waited too long (`overdue_s`) ahead, and runs as
many tasks at once as each kind's `max_concurrent` allows.

- Claims: `claims=["topic:{unit}"]` names what a task holds while it runs, so tasks that
  share a name never overlap; `claim_capacity` lets more tasks hold a name, as a count or
  sized by the host's free memory and cores (`PerTask`).
- `priority=` on a task call breaks ties among ready tasks.
- A run's deadline (`deadline_s`, `grace_s`, `finishing_kinds`, `slack_s`) and time boxes
  (`yield time_box(flow, deadline_s=...)`), a deadline of a flow call's own: past it only
  the finishing kinds launch, and the rest are deferred, with their cause recorded. A
  deferred task is not a failure.
- `Pipeline(max_passes=)` limits the passes of a `while` loop in flow code
  (`TooManyPasses`).
- Resume (`Pipeline.run(..., resume=True)`, `contraagent run --resume`): a task runs again
  only when its fingerprint (its parameters, its definition and the outputs it received)
  changed; `rerun_on_resume=True` runs a final step every time.
