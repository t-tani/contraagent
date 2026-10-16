"""A stub coding agent for tests: a `Backend` that plays scripted replies instead of an LLM.

Only the coding agent is replaced. The runner, the output checks and the
correction rounds, failover, retries, the journal and the monitor all run as
they do in production, so a flow's wiring is tested without spending tokens:

    stub = StubAgent({
        "summarize": lambda launch: {"unit": launch.unit, "points": ["a", "b", "c"]},
        "review": [fails(), {"approved": True, "note": "ok"}],   # one reply per launch
        "summarize-beta": rate_limited(),                          # a task key outranks its kind
    })
    report = Pipeline("pipeline.toml", backends=stub.backends()).run(docs, units=["alpha", "beta"])
    assert [l.key for l in stub.launches if l.resumed] == []

A reply is one of:

* a value: the output to write (a pydantic model or a dict as JSON, a `str` as is), or for
  a task whose output is its final message (`output_from="message"`), the final message;
* `writes(value)`: the same, explicitly (a JSON list output needs it); `writes(value,
  quota=QuotaReading(five_hour_pct=80))` also reports a quota reading, as a coding
  agent does, so quota caps and `quota_rule` rest the credential in a test; `writes(rows,
  stop=Stop.TIMEOUT)` writes and then ends the launch on `stop`, as a launch the runner
  stopped after it wrote what it had (`agent_task(partial_on=)`); rows (`Rows[Row]`) are
  a list, written one JSON object per line;
* `writes_example()`: the output's example: at every part of its JSON Schema, the first
  of its `examples` (a model's own, a field's), else the smallest value that part
  accepts; a text output's from `Annotated[str, Field(examples=[...])]`, else `stub`;
  rows are one row. A
  schema rule it cannot build where there is no example (`pattern`) fails the launch and
  names the rule. As a task's only reply (not in a list, not from a callable), a value its
  validators reject ends the task `invalid_output` after one round: no correction round
  and no retry, which would write the same value;
* `writes_nothing()`: the launch completes and leaves no file;
* `fails(stop, reason)`: the launch ends on `stop` (default `error`);
* `rate_limited(retry_after_s)`: a 429 (a quota refusal, with the cool-off it states), which
  moves the task to its next hop;
* a callable `(StubLaunch) -> reply`: decided per launch;
* a list or tuple of replies: one per reply of that task in a run, the last one repeating.

Script keys are a task key (`summarize-beta`) or a kind (`summarize`); the key
wins. A task with no reply scripted gets `default` (`StubAgent(default=...)`); with
none, its launch ends `error` and says so.

A **stub run** (`Pipeline(stub=StubAgent(...))`, `contraagent run --stub`) plays the
Python tasks too: a Python task's function does not run, and its reply is its
return value (`writes_nothing()`: no output; `fails()`: it raises), from the same
script; a callable reply is given a `StubTask`. The kinds in `execute` run their
functions as in any run. Flow code runs in a stub run as in any run.

A preflight's probe (`Pipeline(preflight=)`) completes on every route the stub plays; a
route the stub's `catalogue()` does not list is dropped as it is for a coding agent.

Under a name whose coding agent continues its turn when a stop hook objects
(Claude Code, Codex: `Backend.stop_hooks_file`), the stub does what that agent
does: once it has written its output it runs the Stop hooks of the launch's
plugins (their rendered `hooks/hooks.json` or `codex/hooks.json`, with the agent's
working directory and environment), and when one exits 2 it is sent the hook's
message and replies again in the same launch (`StubLaunch.in_turn`). Under omp's
names it stops, as omp does.

`contraagent docs testing` shows a flow tested on it.
"""

from contraagent._internal.public import publish
from contraagent._internal.testing import (
    Reply,
    StubAgent,
    StubLaunch,
    StubTask,
    fails,
    rate_limited,
    writes,
    writes_example,
    writes_nothing,
)

__all__ = [
    "Reply",
    "StubAgent",
    "StubLaunch",
    "StubTask",
    "fails",
    "rate_limited",
    "writes",
    "writes_nothing",
    "writes_example",
]

publish(__name__, __all__)
