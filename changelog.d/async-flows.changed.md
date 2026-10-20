A flow that waits for outputs is an `async def` function that waits with `await` on the run's asyncio event loop, and the outputs it receives have the types of their tasks. Generator flows are refused with a `TypeError` that shows the rewrite. A flow that does not wait stays a plain `def`.

| Old | New |
|---|---|
| `def flow(...):` with `yield` | `async def flow(...):` |
| `x = yield task(...)` | `x = await task(...)` |
| `xs = yield [a(...), b(...)]` | `xs = await asyncio.gather(a(...), b(...))`; with `return_exceptions=True` to keep each failure by position |
| `yield [sub(u) for u in us]` (child flow calls) | `await asyncio.gather(*[sub(u) for u in us])`, `asyncio.TaskGroup`, or `asyncio.create_task` |
| `yield from helper(...)` (the same flow call) | `await helper(...)` |
| `yield time_box(gen, deadline_s=...)` | `await time_box(coro, deadline_s=...)`; `time_box` takes a coroutine |
| `@max_passes(n)` on a generator function | `@max_passes(n)` on an `async def` function |

A flow call is an asyncio Task whose coroutine is flow code, numbered `<parent>.<n>` in the order the parent creates it; `FlowCall.site` and the flow path name where the parent created it. Cancelling a flow call (a `TaskGroup` whose sibling failed, a deferral past the grace window, the end of the run) records it `closed` and leaves the tasks it created running. A coroutine that was never awaited is a warning line in a run and an error in `contraagent check`. One event loop runs one run at a time: a second `Pipeline.run_async` on it raises `RuntimeError`.

In `contraagent.engine`, `FlowDriver` drives async flows on the running event loop: `FlowDriver.wait(item)` is what a flow awaits, `FlowDriver.add(task)` queues a task without waiting, `run_async` joins `run`, and `start` returns the `FlowCall`. `FlowDriver(created=)` and `Created` → `FlowDriver.add`; `FlowDriver.waiting` → `FlowDriver.alive()`; `FlowDriver.finish()` is a coroutine; `FlowCall.gen` → `FlowCall.task` and `FlowCall.coro`. `WorkQueue(between_passes=)` (a `BetweenPasses`) keeps the queue running while work outside it may still add tasks, and `WorkQueue.wake()` ends its wait.
