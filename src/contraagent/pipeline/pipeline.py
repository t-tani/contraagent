"""`Pipeline`: run a flow function — the tasks it calls, in the order their outputs allow.

    pipeline = Pipeline("pipeline.toml")
    report = pipeline.run(docs, units=["alpha", "beta"])

A flow that never yields builds the whole task graph before anything runs. A
flow that is a generator (or returns one) is driven by a `FlowDriver`: each
`yield` waits for the tasks or flow calls it names, and the flow creates
further tasks from their outputs. Its reachable kinds (`reach.py`) are routed,
and probed by the preflight, before the first launch, with the kinds of its
first step; a kind its code does not reach (declared while the flow runs) is
routed when it is created, so a config problem raises at that task call. Its
code may reach two declarations of one kind (a default argument the caller
replaces): the first one reached is routed, the one whose tasks are created is
the kind's, and when its `config` or `requires` differ it is routed again as
its first task is created (`Graph.declare`).

Under it is the engine (`execution`, `routing`, `dispatch`): a `Run` directory
with its journal and lock, a `RoutingPlan` from the config file and each
task's declared defaults, an `AgentRunner` with failover and retry, and a
`WorkQueue`. Use those directly for anything this does not cover.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import GeneratorType
from typing import Any

from contraagent.backends import Backend, create_backend, known_agents
from contraagent.dispatch.flow import FlowCall, FlowDriver
from contraagent.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent.dispatch.queue import GRACE_S
from contraagent.dispatch.task import Task, TaskResult
from contraagent.execution.run import Run, RunExists
from contraagent.execution.runner import AgentRunner, RetryingRunner
from contraagent.pipeline.adapter import SpecAdapter
from contraagent.pipeline.check import CheckReport, check_flow
from contraagent.pipeline.graph import MAX_PASSES, Graph
from contraagent.pipeline.reach import reachable
from contraagent.routing.config import PipelineConfig
from contraagent.routing.plan import Overrides, RoutingPlan, check_task_tables
from contraagent.routing.quota import QuotaRule


@dataclass
class RunReport:
    """What a `Pipeline.run` did. The flow's `Pending` values read their outputs from it too.

    `summary` is the queue's (`wall_s`, `finished`, `ok`, `by_stop`, `by_kind`,
    `deferred`) plus the attempts this call journaled (`attempt_totals`)."""

    run_id: str
    run_dir: Path
    results: dict[str, TaskResult]
    summary: dict = field(default_factory=dict)
    #: What the flow returned: a `Pending` in it reads its task's checked output (`.output`).
    value: Any = None
    #: The top flow calls that raised after their first task was queued; `.error` is the
    #: exception (recorded in `flow_calls.jsonl` too).
    flow_errors: list[FlowCall] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results.values()) and not self.summary.get("deferred") and not self.flow_errors

    @property
    def failed(self) -> list[TaskResult]:
        return [r for r in self.results.values() if not r.ok]


def attempt_totals(rows: list[dict]) -> dict:
    """Over journal rows: `attempts`, `cost_usd` (None when no row reports a cost) and
    `fixups` (rounds after the first, plus each objection of a stop hook)."""
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    return {
        "attempts": len(rows),
        "cost_usd": round(sum(costs), 6) if costs else None,
        "fixups": sum(max((r.get("rounds") or 1) - 1, 0) + len(r.get("hook_errors") or []) for r in rows),
    }


class Pipeline:
    """Runs flow functions: plain Python that calls `agent_task`s and `python_task`s."""

    def __init__(
        self,
        config: PipelineConfig | str | Path | None = None,
        *,
        runs_dir: str | Path = "runs",
        backends: Mapping[str, Backend] | None = None,
        overrides: Overrides = Overrides(),
        cwd: str | Path | None = None,
        max_concurrent: int = 4,
        preflight: bool = False,
        keep_transcripts: bool = True,
        env: Mapping[str, str] | None = None,
        log: Callable[[str], None] | None = None,
        max_passes: int | None = None,
        quota_rule: QuotaRule | None = None,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
        row_extras: Callable[[TaskResult], dict] | None = None,
        stub: Any = None,
        **queue_options: Any,
    ) -> None:
        """`config`: the TOML file (`[defaults]`, `[tasks.<kind>]`, `[[defaults.fallbacks]]`,
        `[credentials.<name>]`); None runs on each task's declared defaults.
        `runs_dir`: where each run's directory (`<runs_dir>/<run_id>/`) is written.
        `backends`: coding agent name -> `Backend`; default, every registered one
        (`contraagent.testing.StubAgent().backends()` in a test).
        `overrides`: choices that outrank the config (agent, model, effort, credential).
        `cwd`: where the agents run (default: this process's directory).
        `max_concurrent`: tasks running at once, across kinds (a kind's own
        `max_concurrent` caps it further).
        `preflight`: probe every route once before the first task and drop the
        ones that cannot answer (it launches each, so it spends a little).
        `keep_transcripts`: write each launch's stream file (`streams/<key>.stream.jsonl`).
        `env`: extra variables for every launch (a tool's own API key: a chosen
        credential removes every other secret-looking variable from the child).
        `log`: a function given each progress line instead of the `logging` module.
        `max_passes`: how many passes a `while` loop of flow code may make: a task call, or a
        `yield` of a child flow call, in a later pass raises `TooManyPasses`; default
        `[defaults] max_passes`, else 10.
        `quota_rule(credential, reading)`: a reason the credential rests now, or None, given its
        latest utilization reading (`RateLimit`); beside the config's own caps
        (`max_five_hour_pct`, `max_seven_day_pct`). A resting credential is not launched
        on: its tasks take the next hop of their failover chain, or are deferred.
        `scopes`: context managers around each agent task's dispatch (`TaskScope`: entered
        before its first hop, exited after its last, a timeout included); `enrichers`
        see the task before and its result after (`ResultEnricher`, which may set
        `TaskResult.payload`, `.ok` and `.stop`). Both run once per attempt.
        `row_extras(result)` adds a domain's own columns to each journal row (`Run`).
        `stub`: a stub agent (`contraagent.testing.StubAgent`) makes each run a stub run: it
        plays every agent task, under every coding agent's name, and every Python task but
        the kinds it executes (`StubAgent(execute=)`), so no model is called and no
        function runs that was not named. The run id defaults to `<flow>-stub`, and
        `run.json` says `stub: true`. Flow code runs as in any run. Not with `backends`.
        `queue_options` go to the `WorkQueue` (`deadline_s`, `slack_s`, `finishing_kinds`,
        `overdue_s`, `claim_capacity`, ...); its docstring has the scheduling rules.
        `claim_capacity` outranks the config's `[defaults.claim_capacity]` key by key."""
        if config is None:
            config = PipelineConfig()
        elif not isinstance(config, PipelineConfig):
            config = PipelineConfig.load(config)
        self.config = config
        self.runs_dir = Path(runs_dir)
        if stub is not None and backends is not None:
            raise TypeError("Pipeline: give stub= or backends=, not both (a stub run's coding agents are the stub's)")
        self.stub = stub
        if stub is not None:
            backends = stub.backends()
        self.backends = dict(backends) if backends is not None else {n: create_backend(n) for n in known_agents()}
        self.overrides = overrides
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.max_concurrent = max_concurrent
        self.preflight = preflight
        self.keep_transcripts = keep_transcripts
        self.log = log
        self.env = dict(env or {})
        # A malformed [defaults] is reported with every other routing problem, by the routing plan.
        self.max_passes = max_passes if max_passes is not None else int(config.defaults([]).get("max_passes", MAX_PASSES))
        self.quota_rule = quota_rule
        self.scopes = tuple(scopes)
        self.enrichers = tuple(enrichers)
        self.row_extras = row_extras
        # A malformed [defaults.claim_capacity] is reported by the routing plan too.
        claim_capacity = {**config.claim_capacity([]), **dict(queue_options.pop("claim_capacity", None) or {})}
        self.queue_options = {**queue_options, **({"claim_capacity": claim_capacity} if claim_capacity else {})}

    def check(self, flow: Callable[..., Any], /, *args: Any, **kwargs: Any) -> CheckReport:
        """Build the task graph `run` would, and check everything that needs no launch:
        the flow, parameters, output schemas (importable by the in-session hook), command
        validators, plugins and routing. Writes no run directory and spends nothing."""
        return check_flow(self, flow, args, kwargs)

    def run(self, flow: Callable[..., Any], /, *args: Any, run_id: str | None = None, resume: bool = False, **kwargs: Any) -> RunReport:
        """Call `flow(*args, **kwargs)` and run the tasks it creates to the end.

        A flow that never yields builds the whole task graph first. A flow that is,
        or returns, a generator is driven: each `yield` receives the outputs it
        waited for, and what it creates next runs as it is created. An exception
        in a flow before its first task is queued is raised; after, it is recorded
        in `RunReport.flow_errors` (and `flow_calls.jsonl`) and the run goes on with
        the tasks already queued.

        `run_id` defaults to the flow's name (`<flow>-stub` in a stub run). A run id that already holds a run is
        refused (`RunExists`) unless `resume=True`, which runs the flow again from the
        start and skips every task whose key's last journal row is ok with the same
        fingerprint, reading its output from the run directory.
        """
        run_id = run_id or (f"{flow.__name__}-stub" if self.stub is not None else flow.__name__)
        with Run(run_id, self.runs_dir, log=self.log, cwd=self.cwd, row_extras=self.row_extras) as run:
            if self.stub is not None:
                run.update_info(stub=True)
            if not resume and run.rows():
                raise RunExists(
                    f"{run.dir} already holds a run ({len(run.rows())} journal rows): "
                    "continue it with resume=True (`contraagent run --resume`), or start a new one with another run_id"
                )
            run_dir = run.dir.resolve()  # call files and outputs are read from the agent's cwd
            graph = Graph(run_dir / "out", max_passes=self.max_passes)
            graph.tail = run.estimator().tail
            graph.stub, graph.run_id = self.stub, run.run_id

            def on_flow_call(event: str, call: FlowCall) -> None:
                if event == "start":
                    flow = graph.flow_call_started(call)
                    parent = call.parent.id if call.parent is not None else None
                    box = {"time_box": call.time_box, "started_at": call.started_at}
                    run.record_flow_call("start", call.id, parent=parent, function=call.function, flow=flow, **box)
                    graph.check_passes(flow, f"flow call {call.id} ({call.function})", call.id)
                else:
                    graph.flow_call_ended(call)
                    run.record_flow_call("end", call.id, state=call.state, error=call.error)

            driver = FlowDriver(waits_for=graph.waits_for, answer=graph.answer, created=graph.take_new, on_flow_call=on_flow_call)
            graph.driver = driver

            def follow_up(result: TaskResult) -> list[Task]:
                graph.record(result)
                return driver.follow_up(result)

            with graph.building():
                try:
                    value, tasks, driven = _start(flow, args, kwargs, graph, driver, run)
                    if driven:  # route every kind its code can reach before the first launch
                        for spec in reachable(flow, *args, *kwargs.values()):
                            graph.reached(spec)
                    specs = graph.agent_specs()
                    plan = RoutingPlan.build(
                        self.config,
                        list(specs),
                        self.backends,
                        self.overrides,
                        declared={kind: spec.config for kind, spec in specs.items()},
                        requirements={kind: spec.requires for kind, spec in specs.items()},
                        all_kinds=not driven,
                    )
                    if self.preflight:
                        plan.preflight()
                    plan.log()
                    rests = run.quota_rests(
                        plan.credentials,
                        self.quota_rule,
                        finishing_kinds=self.queue_options.get("finishing_kinds", ()),
                        grace_s=self.queue_options.get("grace_s", GRACE_S),
                    )
                    runner = run.agent_runner(
                        self.backends,
                        plan.configs,
                        routers=plan.routers,
                        credentials=plan.credentials,
                        adapter=SpecAdapter(run.run_id, run_dir, self.cwd),
                        keep_transcripts=self.keep_transcripts,
                        cwd=self.cwd,
                        env=self.env,
                        rests=rests,
                        scopes=self.scopes,
                        enrichers=self.enrichers,
                    )
                    graph.new_kind = lambda spec: self._route(spec, runner)
                    queue = run.queue(
                        run.python_runner(RetryingRunner(runner, on_attempt=run.record_attempt), cwd=self.cwd),
                        follow_up=follow_up,
                        resume=resume,
                        max_concurrent=self.max_concurrent,
                        **self.queue_options,
                    )
                    driver.past_grace = queue.past_hard_stop
                    journaled = len(run.rows())
                    queue.extend(tasks)
                    summary = queue.run()
                finally:
                    driver.finish()
            if driven:
                check_task_tables(self.config.task_tables([]), graph.agent_specs())
                top = driver.calls.get("0")
                value = top.value if top is not None and top.state == "returned" else None
            summary.update(attempt_totals(run.rows()[journaled:]))
            run.finish()
            errors = [c for c in driver.calls.values() if c.parent is None and c.state == "raised"]
            return RunReport(
                run_id=run.run_id, run_dir=run.dir, results=dict(graph.results), summary=summary, value=value, flow_errors=errors
            )

    def _route(self, spec: Any, runner: AgentRunner) -> None:
        """Route a kind while the run runs: one first created then, or one created by another
        declaration than the reachable one routed before the first launch. A config problem
        raises at its task call."""
        plan = RoutingPlan.build(
            self.config,
            [spec.kind],
            self.backends,
            self.overrides,
            declared={spec.kind: spec.config},
            requirements={spec.kind: spec.requires},
            all_kinds=False,
        )
        plan.log()
        runner.configs = {**runner.configs, **plan.configs}
        runner.routers.update(plan.routers)


def _start(flow: Callable[..., Any], args: tuple, kwargs: dict, graph: Graph, driver: FlowDriver, run: Run) -> tuple[Any, list[Task], bool]:
    """Call the flow: (its value, the tasks to queue first, whether it is driven).

    A flow that raises before a task is queued raises here: the static part of
    any flow, or the first step of a generator flow that created no task."""
    function = f"{getattr(flow, '__module__', '')}.{getattr(flow, '__qualname__', repr(flow))}"
    try:
        value = flow(*args, **kwargs)
    except Exception as exc:
        run.record_flow_call("start", "0", function=function)
        run.record_flow_call("end", "0", state="raised", error=exc)
        raise
    if not isinstance(value, GeneratorType):
        run.record_flow_call("start", "0", function=function)
        run.record_flow_call("end", "0", state="returned")
        return value, graph.take_new(), False
    tasks = driver.start(value)
    top = driver.calls["0"]
    if top.state == "raised" and not graph.nodes and top.error is not None:
        raise top.error
    return None, tasks, True
