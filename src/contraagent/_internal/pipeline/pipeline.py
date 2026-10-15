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

from contraagent._internal.backends import Backend, create_backend, known_agents
from contraagent._internal.dispatch.flow import FlowCall, FlowDriver
from contraagent._internal.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent._internal.dispatch.queue import GRACE_S
from contraagent._internal.dispatch.task import STOP_PARTIAL, Task, TaskResult
from contraagent._internal.execution.recording import MAX_FILE_MB, Recorder, Replay
from contraagent._internal.execution.run import Run, RunExists
from contraagent._internal.execution.runner import AgentRunner, RetryingRunner
from contraagent._internal.pipeline.adapter import SpecAdapter
from contraagent._internal.pipeline.check import CheckReport, check_flow
from contraagent._internal.pipeline.graph import MAX_PASSES, Graph
from contraagent._internal.pipeline.reach import reachable
from contraagent._internal.routing.config import ConfigError, PerTask, PipelineConfig
from contraagent._internal.routing.plan import Overrides, RoutingPlan, check_task_tables
from contraagent._internal.routing.preflight import PreflightPolicy, PreflightStopped, check_policy
from contraagent._internal.routing.quota import QuotaRule


@dataclass
class RunReport:
    """What a `Pipeline.run` did. The flow's `Pending` values read their outputs from it too.

    `summary` is the queue's (`wall_s`, `finished`, `ok`, `by_stop`, `by_kind`,
    `deferred`) plus the attempts this call journaled (`attempt_totals`). A `partial`
    result is ok, so `ok` holds with one; `partial` lists them (`by_stop` counts them)."""

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

    @property
    def partial(self) -> list[TaskResult]:
        """The results with stop `partial`: ok, their outputs placeholders a resume makes again."""
        return [r for r in self.results.values() if r.stop == STOP_PARTIAL]


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
        preflight: PreflightPolicy | None = None,
        keep_transcripts: bool = True,
        env: Mapping[str, str] | None = None,
        log: Callable[[str], None] | None = None,
        max_passes: int | None = None,
        quota_rule: QuotaRule | None = None,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
        row_extras: Callable[[TaskResult], dict] | None = None,
        stub: Any = None,
        record: str | Path | None = None,
        replay: str | Path | None = None,
        execute: Sequence[str] = (),
        record_missing: bool = False,
        record_max_file_mb: float | None = None,
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
        `preflight`: before the first task, probe every route once (a launch each, so it
        spends a little), drop the ones that cannot answer, and for a kind left with no
        route `"substitute"` (run it on the first route that answered, of its own
        credential), `"stop"` (raise `PreflightStopped`; nothing launches), or `"off"`
        (no probe); default `[defaults] preflight`, else `"off"`. `run.json` records what
        it did (`preflight`, a `PreflightRecord`).
        `keep_transcripts`: write each launch's stream file (`streams/<key>.stream.jsonl`).
        `env`: extra variables for every launch (a tool's own API key: a chosen
        credential removes every other secret-looking variable from the child).
        `log`: a function given each progress line instead of the `logging` module.
        `max_passes`: how many passes a `while` loop of flow code may make: a task call, or a
        `yield` of a child flow call, in a later pass raises `TooManyPasses`; default
        `[defaults] max_passes`, else 10.
        `quota_rule(credential, reading)`: a reason the credential rests now, or None, given its
        latest quota reading (`QuotaReading`), or the reason and when the rest ends
        (`(reason, datetime)`); beside the config's own caps
        (`max_five_hour_pct`, `max_seven_day_pct`). A resting credential is not launched
        on: its tasks take the next hop of their failover chain, or are deferred.
        `scopes`: context managers around each attempt of a task, agent or Python
        (`TaskScope`: entered before an agent task's first hop, exited after its last, a
        timeout included; around a Python task's call and its contract checks); `enrichers`
        see the task before and its result after (`ResultEnricher`, which may set
        `TaskResult.payload`, `.ok` and `.stop`). Both run once per attempt; one that cares
        about some tasks only tests `task.kind` or `task.executor`.
        `row_extras(result)` adds a domain's own columns to each journal row (`Run`).
        `stub`: a stub agent (`contraagent.testing.StubAgent`) makes each run a stub run: it
        plays every agent task, under every coding agent's name, and every Python task but
        the kinds it executes (`StubAgent(execute=)`), so no model is called and no
        function runs that was not named. The run id defaults to `<flow>-stub`, and
        `run.json` says `stub: true`. Flow code runs as in any run. Not with `backends`.
        `record`: a directory each task attempt's recording is written to
        (`<record>/<kind>/<key>.json` and its files: `execution/recording.py`): its outputs,
        the files its `changes=` patterns saw change, its transcript and its result; for a
        Python task, how its call ended and its output.
        `replay`: a directory of recordings, played in place of every agent task's launch and
        every Python task's function, attempt by attempt; nothing is spent. A task with no
        recording ends `error`. A replay is a stub run (`run.json` `stub: true`, and `replay`,
        the directory); its run id defaults to `<flow>-replay`. Not with `record`, `stub`,
        `backends` or `preflight`.
        `execute`: with `replay`, the Python task kinds whose functions run instead of being
        played (as `StubAgent(execute=)` in a stub run).
        `record_missing`: with `replay`, a task with no recording launches on the coding agents
        (`backends`, default every registered one) through the config's routing, or runs its
        function, and its recording is written into the `replay` directory (which may be empty);
        the tasks with one are played. It can spend tokens, so the run is no stub run
        (`run.json` `stub: false`, `replay` the directory); each played attempt's journal row
        says `replayed`. With it, `backends` and `preflight` are allowed; `record` and `stub`
        are not.
        `record_max_file_mb`: with `record` or `record_missing`, the size in MB (MiB) above
        which a recorded output or changed file is kept by its SHA-256 and size only, and a
        warning names it (default 4); such a recording cannot be played. The run ends with
        one line on what it recorded (files, size, files kept by hash, tasks that cannot be
        replayed). A recording run also compares the working directory at its start and its
        end (but `.git`, `__pycache__`, the recordings and the run's own files): each path
        created, modified or deleted that no task's outputs or `changes=` cover is an
        undeclared change, written to `<recordings>/undeclared.json` and named in a warning.
        `queue_options` go to the `WorkQueue` (`deadline_s`, `slack_s`, `finishing_kinds`,
        `overdue_s`, `claim_capacity`, ...); its docstring has the scheduling rules.
        `claim_capacity` outranks the config's `[defaults.claim_capacity]` key by key; a
        value is a number or a `PerTask` (what one task that claims the name needs of the
        host); another value raises `ConfigError`."""
        if config is None:
            config = PipelineConfig()
        elif not isinstance(config, PipelineConfig):
            config = PipelineConfig.load(config)
        self.config = config
        self.runs_dir = Path(runs_dir)
        if stub is not None and backends is not None:
            raise TypeError("Pipeline: give stub= or backends=, not both (a stub run's coding agents are the stub's)")
        if record_max_file_mb is not None and record is None and not record_missing:
            raise TypeError("Pipeline: record_max_file_mb= caps a recording's files; give record= (or replay= with record_missing=True)")
        if record_max_file_mb is not None and not record_max_file_mb > 0:
            raise ValueError(f"Pipeline: record_max_file_mb={record_max_file_mb!r} is not a positive number of MB")
        self.record_max_file_mb = record_max_file_mb if record_max_file_mb is not None else MAX_FILE_MB
        if record_missing and replay is None:
            raise TypeError("Pipeline: record_missing= fills in a replay's recordings; give replay= the recordings directory")
        if replay is not None:
            given = [name for name, value in (("record", record), ("stub", stub)) if value is not None]
            if not record_missing:  # with nothing to launch, a coding agent or a probe has no use
                given += ["backends"] if backends is not None else []
                given += ["preflight"] if preflight else []
            if given:
                fills = " (record_missing records into the replay directory)" if record_missing else ""
                raise TypeError(f"Pipeline: replay= plays recordings in place of the coding agents; not with {', '.join(given)}={fills}")
        if execute and replay is None:
            where = "give it to the stub agent: StubAgent(execute=)" if stub is not None else "it names what a replay does not play"
            raise TypeError(f"Pipeline: execute= is for a replay ({where})")
        self.stub = stub
        self.record = Path(record) if record is not None else None
        #: The recordings a replay plays (`execution.recording.Replay`); None when this is no replay.
        self.replay = Replay(replay, execute=execute, record_missing=record_missing) if replay is not None else None
        if stub is not None:
            backends = stub.backends()
        elif self.replay is not None and record_missing:
            real = dict(backends) if backends is not None else {n: create_backend(n) for n in known_agents()}
            backends = self.replay.backends(real=real)
        elif self.replay is not None:
            backends = self.replay.backends()
        self.backends = dict(backends) if backends is not None else {n: create_backend(n) for n in known_agents()}
        self.overrides = overrides
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.max_concurrent = max_concurrent
        # A malformed [defaults] preflight is reported by the routing plan, with the rest.
        self.preflight: PreflightPolicy = check_policy(
            preflight if preflight is not None else config.defaults([]).get("preflight", "off"), "Pipeline: preflight"
        )
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
        given = dict(queue_options.pop("claim_capacity", None) or {})
        for name, value in given.items():
            if not isinstance(value, PerTask) and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ConfigError(f"Pipeline(claim_capacity=) {name!r} = {value!r} is not a non-negative integer or a PerTask")
        claim_capacity = {**config.claim_capacity([]), **given}
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
        fingerprint, reading its output from the run directory (a task declared
        `rerun_on_resume` runs again, and so does a task whose last result was `partial`,
        with the tasks that wait for it).

        On the main thread, SIGTERM and SIGINT (Ctrl-C) stop the run's agents while it
        runs, then end the process as they would have; the handlers in place before are
        put back when it returns. An agent of a process killed outright (SIGKILL) is
        stopped by a watchdog (`backends/live_processes.py`): no agent outlives its run.
        """
        suffix = "-stub" if self.stub is not None else "-replay" if self.replay is not None else ""
        run_id = run_id or f"{flow.__name__}{suffix}"
        with Run(run_id, self.runs_dir, log=self.log, cwd=self.cwd, row_extras=self.row_extras, config=self.config) as run:
            run.stop_on_signals()  # SIGTERM or Ctrl-C stops the agents too (on the main thread)
            if self.stub is not None:
                run.update_info(stub=True)
            if self.replay is not None:
                run.update_info(stub=not self.replay.record_missing, replay=str(self.replay.directory.resolve()))
            if not resume and run.rows():
                raise RunExists(
                    f"{run.dir} already holds a run ({len(run.rows())} journal rows): "
                    "continue it with resume=True (`contraagent run --resume`), or start a new one with another run_id"
                )
            run_dir = run.dir.resolve()  # call files and outputs are read from the agent's cwd
            graph = Graph(run_dir / "out", max_passes=self.max_passes)
            graph.tail = run.estimator().tail
            graph.stub, graph.run_id = self.stub, run.run_id
            adapter = SpecAdapter(run.run_id, run_dir, self.cwd)
            recorder = None
            into = self.record or (self.replay.directory if self.replay is not None and self.replay.record_missing else None)
            if into is not None:
                recorder = Recorder(
                    into,
                    adapter.output_contracts,
                    cwd=self.cwd,
                    run_dir=run_dir,
                    run_id=run.run_id,
                    max_file_mb=self.record_max_file_mb,
                    log=lambda line: run.progress(line, warning=True),
                    patterns=adapter.changes,
                )
                recorder.start()  # before the flow runs: its own side effects count too

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
                        bases={kind: spec.base_kind for kind, spec in specs.items() if spec.base_kind},
                        requirements={kind: spec.requires for kind, spec in specs.items()},
                        light=[kind for kind, spec in specs.items() if spec.light],
                        all_kinds=not driven,
                    )
                    try:
                        preflight = plan.preflight(self.preflight)
                    except PreflightStopped as exc:
                        run.update_info(preflight=exc.record.model_dump(mode="json"))
                        raise
                    run.update_info(preflight=preflight.model_dump(mode="json"))
                    plan.log()
                    rests = run.quota_rests(
                        plan.credentials,
                        self.quota_rule,
                        finishing_kinds=self.queue_options.get("finishing_kinds", ()),
                        grace_s=self.queue_options.get("grace_s", GRACE_S),
                    )
                    enrichers = list(self.enrichers)
                    if self.replay is not None:
                        self.replay.start(adapter.output_contracts, self.cwd)
                        enrichers.insert(0, self.replay)
                    if recorder is not None:  # last: it records the result the enrichers leave
                        enrichers.append(recorder)
                    # A pure replay plays each attempt's last launch: it walks no failover hop.
                    pure = self.replay is not None and not self.replay.record_missing
                    runner = run.agent_runner(
                        self.backends,
                        plan.configs,
                        routers=plan.routers if not pure else {},
                        credentials=plan.credentials,
                        adapter=adapter,
                        keep_transcripts=self.keep_transcripts,
                        cwd=self.cwd,
                        env=self.env,
                        rests=rests,
                        scopes=self.scopes,
                        enrichers=enrichers,
                    )
                    graph.new_kind = lambda spec: self._route(spec, runner)
                    queue = run.queue(
                        run.python_runner(
                            RetryingRunner(runner, on_attempt=run.record_attempt),
                            cwd=self.cwd,
                            scopes=self.scopes,
                            enrichers=self.enrichers,
                            recorder=recorder,
                            replay=self.replay,
                        ),
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
                specs = graph.agent_specs()
                check_task_tables(self.config.task_tables([]), specs, {kind: spec.base_kind for kind, spec in specs.items()})
                top = driver.calls.get("0")
                value = top.value if top is not None and top.state == "returned" else None
            summary.update(attempt_totals(run.rows()[journaled:]))
            if recorder is not None:
                for path in recorder.finish():
                    run.progress(f"[record] undeclared change: {path}", warning=True)
                run.progress(recorder.summary())
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
            bases={spec.kind: spec.base_kind} if spec.base_kind else {},
            requirements={spec.kind: spec.requires},
            light=[spec.kind] if spec.light else [],
            all_kinds=False,
        )
        plan.log()
        runner.configs = {**runner.configs, **plan.configs}
        if self.replay is None or self.replay.record_missing:
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
