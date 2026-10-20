A task is given values: a task call copies its params as JSON at the call, and a `Pending` is never a param (old → new):

- `b(u, x=a(u))`, a task call's `Pending` among another task call's params (also in a list, a dict or a model) → `b(u, x=await a(u))` in an `async def` flow; for an order with no output passed on, `b.options(after=[a(u)])(u)`. The old form raises `TypeError` at the call, which says how to write it.
- A plain `def` flow that gives one task another's output → an `async def` flow that awaits the output and passes it on, best one flow call per unit under `asyncio.gather(..., return_exceptions=True)`. A plain `def` flow creates tasks that are independent or ordered with `after=` only.
- A task whose input's writer failed was refused (`invalid_input`), and one whose input's writer was deferred was deferred (`dependency_deferred`) → the writer's `await` raises `TaskFailed` or `TaskDeferred`, and the task is not created: `deferred.jsonl` no longer gets `dependency_deferred`, and `RunReport.failed` and `deferred` count fewer.
- The call file's `params` and a Python task's arguments were read from the upstream output files as the task started → they are the values the flow passed, copied when it called the task. A Python task's unannotated parameter is given that JSON (a model as a dict, a tuple as a list); an annotated one is converted to its annotation as before.
- An agent task's params were validated under its params model as the task started → at the call, where params that do not validate raise `TypeError`.
- A param that is not JSON was written as its `repr` → `TypeError` at the call. So is a Python task's default that is not JSON.
- An `outside_state` function was given the outputs read from their files → the params as JSON, the call file's `params`.
- `TextOutput`, the `str` a flow received for a text output → `str`.
