"""How well the work queue schedules: makespan, idle slots and deferrals on a simulated coding agent.

    uv run python benchmarks/schedule.py run --out benchmarks/results/main --label main
    uv run python benchmarks/schedule.py compare benchmarks/results/0.6.2.json benchmarks/results/main.json

`run` runs every scenario for each seed, twice in one runs directory: the first run
has no history, and the second reads the first one's journal (each kind's durations,
each tail key's tail). It writes `<out>.json` (every run's figures) and `<out>.md`
(the medians per scenario). `compare` prints, per scenario, how the medians of the
second file differ from those of the first, and the result of the rule for seeding a
first run (below).

The coding agent is `contraagent.testing.StubAgent` under the name `stub`, made slow:
each launch sleeps for a duration drawn from its kind's log-normal distribution
(`KINDS`), from a generator seeded by the seed, the task key and the launch's count.
The same seed draws the same durations, and makes the same decisions (a review that
sends a summary back), under every version of contraagent and in both runs, whatever
order the tasks start in: the second run differs from the first only by its history.
Some kinds have a heavy tail (a sigma of 1: one launch in twenty takes five times
the median or more, up to `CAP` times).

Durations are in minutes of agent work, as a real pipeline sees them, and one minute
runs for `--scale` seconds (default 0.2). Every time the queue is given (`deadline_s`,
`grace_s`, `overdue_s`) is scaled the same way. Two things do not scale: the queue's
default estimate for a kind with no history (300 seconds, an ordering default, so it
ranks an unknown kind far above a known one), and the journal's wall times, rounded
to 0.1 seconds (half a minute at the default scale). The figures carry the noise of
real sleeps and threads: a few percent between two runs of the same seed.

The scenarios are listed in `SCENARIOS`: the demo's flows (`docs`, an async flow with
a review loop per unit, and `docs_one_review`, which does not wait, so the queue knows
each task's successors early; copied here without the demo's command validators,
which start a Python process each and would hold a slot for minutes at this scale),
the analysis example as it is (nested flows, the `heavy` claim), and synthetic flows:
chains of different lengths on two slots, fan-out and join, a claim every second unit
needs, three pipelines sharing the slots, and deadlines with finishing kinds (a
`time_box`, and the demo's flows under a run deadline).

Each run reports, in minutes of agent work: its makespan (from the first agent launch
to the end of the last one), the slot time left idle within it, the deferred tasks,
and under a deadline (counted from the first launch) the agent work finished by it,
the cost of the launches that ended after it (0.05 USD per minute), and how many
deferrals for `cannot_finish` would have fit (the task's own drawn duration was
shorter than the time left).

The rule for seeding a first run (`compare`): it applies when the first run of the
demo's async `docs` has a median makespan 10% or more longer than the first run of
`docs_one_review` in the older file, or does 10% or less work by the deadline, and
the second run brings that gap within 5%.

The tool uses only what 0.6.2 and later versions publish, so the same file measures
a checkout of a release:

    git worktree add /tmp/ca-062 0.6.2 && (cd /tmp/ca-062 && uv sync)
    /tmp/ca-062/.venv/bin/python benchmarks/schedule.py run --out benchmarks/results/0.6.2 --label 0.6.2
    git worktree remove /tmp/ca-062
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import statistics
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from contraagent import Overrides, Pipeline, TaskDeferred, agent_task, python_task, time_box
from contraagent.backends import CallFile, Launch, LaunchResult
from contraagent.testing import StubAgent, StubLaunch, writes_example

#: Real seconds per minute of simulated agent work.
SCALE_S = 0.2
#: USD per minute of agent work.
RATE_USD = 0.05
#: The longest launch, as a multiple of its kind's median.
CAP = 10.0
#: The queue's times, in minutes of agent work (its defaults: 10 and 15 minutes).
OVERDUE_MIN = 10.0
GRACE_MIN = 15.0


@dataclass(frozen=True)
class Kind:
    """A kind's launch durations: log-normal with this median (minutes) and sigma."""

    median: float
    sigma: float


KINDS: dict[str, Kind] = {
    # The demo's flows.
    "summarize": Kind(4.0, 0.5),
    "review": Kind(2.0, 0.3),
    "revise": Kind(3.0, 0.4),
    "write_note": Kind(3.0, 1.0),
    # The analysis example (contraagent.docs.examples.analysis).
    "classify": Kind(1.5, 0.3),
    "parse_csv": Kind(5.0, 1.0),
    "parse_json": Kind(3.0, 0.5),
    "propose": Kind(2.0, 0.4),
    "refine": Kind(2.0, 0.4),
    # The synthetic flows.
    "draft": Kind(4.0, 0.5),
    "step": Kind(3.0, 0.4),
    "deep": Kind(6.0, 1.0),
    "join": Kind(2.0, 0.3),
    "load": Kind(3.0, 0.3),
    "check": Kind(2.0, 0.3),
    "finish": Kind(1.0, 0.2),
}


def draw(seed: int, kind: str, key: str, n: int) -> float:
    """The minutes launch `n` of task `key` (of `kind`) takes under seed `seed`."""
    k = KINDS[kind]
    rng = random.Random(f"{seed}:{key}:{n}")
    return min(k.median * math.exp(k.sigma * rng.gauss(0.0, 1.0)), CAP * k.median)


def chance(seed: int, key: str, n: int, what: str) -> float:
    """A uniform draw in [0, 1) for the decision `what` of launch `n` of `key`."""
    return random.Random(f"{seed}:{key}:{n}:{what}").random()


# --- the simulated agent --------------------------------------------------------------


@dataclass(frozen=True)
class Launched:
    key: str
    kind: str
    start: float
    end: float
    minutes: float


class SlowStub(StubAgent):
    """A `StubAgent` whose launches take their drawn duration (`draw`), scaled."""

    def __init__(self, seed: int, scale: float, script: dict[str, Any]) -> None:
        super().__init__(script, default=writes_example())
        self.seed, self.scale = seed, scale
        #: Every launch with a call file, in the order they ended.
        self.timed: list[Launched] = []
        self._n: dict[str, int] = {}
        self._timed_lock = threading.Lock()

    def run(self, launch: Launch) -> LaunchResult:
        path = CallFile.path_of(launch)
        if path is None:
            return super().run(launch)
        call = CallFile.read(path)
        with self._timed_lock:
            n = self._n[call.key] = self._n.get(call.key, 0) + 1
        minutes = draw(self.seed, call.kind, call.key, n)
        start = time.monotonic()
        time.sleep(minutes * self.scale)
        result = super().run(launch)
        end = time.monotonic()
        result.wall_s = end - start
        result.cost_usd = round(minutes * RATE_USD, 6)
        with self._timed_lock:
            self.timed.append(Launched(call.key, call.kind, start, end, minutes))
        return result


# --- the demo's flows -----------------------------------------------------------------
#
# The flows of `contraagent.docs.examples.demo.tasks`, with its kinds, and without its
# command validators (see the module docstring).


class Prepared(BaseModel):
    unit: str
    words: int


class Summary(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"unit": "alpha", "points": ["a", "b", "c"]}]})

    unit: str
    points: list[str]


class Score(BaseModel):
    points: int
    words: int


class Verdict(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"approved": True, "note": "Accurate."}]})

    approved: bool
    note: str


def three_points(path: Path, summary: Summary):
    if len(summary.points) != 3:
        return [f"points: exactly three expected, got {len(summary.points)}"]


summarize = agent_task(
    "summarize", instructions="Summarize params.prepared.", output=Summary, validators=[three_points], max_turns=10, timeout_s=3600
)
review = agent_task("review", instructions="Review params.summary.", output=Verdict, max_turns=10, timeout_s=3600)
revise = agent_task(
    "revise", instructions="Revise params.summary.", output=Summary, validators=[three_points], max_turns=10, timeout_s=3600
)
write_note = agent_task("write_note", instructions="Write a note on params.summary.", output=str, max_turns=10, timeout_s=3600)


@python_task
def prepare(unit: str) -> Prepared:
    return Prepared(unit=unit, words=12)


@python_task
def score(unit: str, summary: Summary) -> Score:
    return Score(points=len(summary.points), words=sum(len(p.split()) for p in summary.points))


@python_task
def report(summaries: list[Summary]) -> str:
    return "\n".join(f"{s.unit}: {len(s.points)} points" for s in summaries)


def docs_one_review(units: list[str]):
    summaries = []
    for u in units:
        summary = summarize(u, prepared=prepare(u))
        review(u, summary=summary, score=score(u, summary=summary))
        write_note(u, summary=summary)
        summaries.append(summary)
    return report(summaries=summaries)


async def review_loop(unit: str):
    summary = await summarize(unit, prepared=prepare(unit))
    while True:
        figures = await score(unit, summary=summary)
        verdict = await review(unit, summary=summary, score=figures)
        if verdict.approved:
            break
        summary = await revise(unit, summary=summary, verdict=verdict)
    await write_note(unit, summary=summary)
    return summary


async def docs(units: list[str]):
    done = await asyncio.gather(*[review_loop(u) for u in units], return_exceptions=True)
    return await report(summaries=[s for s in done if isinstance(s, Summary)])


def demo_script(seed: int) -> dict[str, Any]:
    """Replies for the demo's flows: every review approves, so `docs` and
    `docs_one_review` create the same tasks."""
    return _demo_replies(seed, 0.0, 0.0)


def demo_loop_script(seed: int) -> dict[str, Any]:
    """Replies for the demo's flows: a review sends the summary back on a seeded draw
    (35% of first reviews, 20% of later ones)."""
    return _demo_replies(seed, 0.35, 0.2)


def _demo_replies(seed: int, first: float, later: float) -> dict[str, Any]:
    points = ["parses a config file", "validates it", "reports errors"]

    def reviewed(launch: StubLaunch):
        revised = launch.params["summary"]["points"][0].endswith("(revised)")
        sent_back = chance(seed, launch.key, launch.n, "review") < (later if revised else first)
        return {"approved": not sent_back, "note": "Name the file format." if sent_back else "Accurate."}

    def revised(launch: StubLaunch):
        summary = dict(launch.params["summary"])
        summary["points"] = [f"{summary['points'][0].removesuffix(' (revised)')} (revised)", *summary["points"][1:]]
        return summary

    return {
        "summarize": lambda launch: {"unit": launch.params["prepared"]["unit"], "points": points},
        "review": reviewed,
        "revise": revised,
        "write_note": lambda launch: f"# {launch.unit}\n\n" + "\n".join(launch.params["summary"]["points"]) + "\n",
    }


def analysis_script(seed: int) -> dict[str, Any]:
    """Replies for the analysis example: a file's format (60% CSV) and a proposal that
    `verify` sends back (40%) are seeded draws."""

    def classified(launch: StubLaunch):
        csv = chance(seed, launch.key, 1, "format") < 0.6
        return {"name": launch.params["file"]["name"], "format": "csv" if csv else "json", "data": True}

    def proposed(launch: StubLaunch):
        col = launch.params["column"]["name"]
        short = chance(seed, launch.key, launch.n, "short") < 0.4
        return {"column": col, "reads": "value" if short else f"The {col} column."}

    def refined(launch: StubLaunch):
        col = launch.params["meaning"]["column"]
        return {"column": col, "reads": f"The {col} column."}

    table = {"columns": [{"name": "id", "nulls": 0}, {"name": "amount", "nulls": 1}, {"name": "note", "nulls": 9}]}
    return {"classify": classified, "parse_csv": table, "parse_json": table, "propose": proposed, "refine": refined}


# --- the synthetic flows --------------------------------------------------------------


class Done(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"ok": True}]})

    ok: bool


def _agent(kind: str, claims: tuple[str, ...] = ()):
    return agent_task(kind, instructions=f"Do the {kind} work for the unit.", output=Done, max_turns=5, timeout_s=3600, claims=claims)


draft = _agent("draft")
step = _agent("step")
deep = _agent("deep")
join = _agent("join")
check = _agent("check")
finish = _agent("finish")
load = _agent("load", claims=("db",))


async def brief(unit: str):
    await draft(unit)


async def standard(unit: str):
    await draft(unit)
    for i in range(2):
        await step(f"{unit}-{i}")


async def extended(unit: str):
    await draft(unit)
    for i in range(6):
        await step(f"{unit}-{i}")


async def chains(n: int):
    """Chains of 1, 3 and 7 tasks, the long ones queued last: the order of arrival is the
    worst one, and only a tail learned from history tells the chains apart."""
    await asyncio.gather(*[f(f"{f.__name__}{i}") for i in range(n) for f in (brief, standard, extended)])


async def narrow_group(unit: str):
    await asyncio.gather(*[draft(f"{unit}-{i}") for i in range(4)])
    await join(unit)


async def deep_group(unit: str):
    await asyncio.gather(*[draft(f"{unit}-{i}") for i in range(2)])
    await join(unit)
    for i in range(4):
        await check(f"{unit}-{i}")


async def fan_in(n: int):
    """Fan-out and join: the narrow groups end at their join, the deep ones go on after it."""
    await asyncio.gather(*[f(f"{f.__name__.split('_')[0]}{i}") for i in range(n) for f in (narrow_group, deep_group)])


async def note_unit(unit: str):
    await draft(unit)
    await check(unit)


async def import_unit(unit: str):
    await load(unit)  # claims `db`: one at a time
    await deep(unit)


async def contention(n: int):
    """Every second unit loads through the `db` claim, one at a time, before its long
    work: the loads are the bottleneck, and they arrive after the free units."""
    await asyncio.gather(*[note_unit(f"note{i}") for i in range(n)], *[import_unit(f"import{i}") for i in range(n)])


async def competing():
    """Three pipelines in one run, sharing its slots."""
    await asyncio.gather(chains(1), fan_in(1), contention(2))


async def short_topic(unit: str):
    try:
        for i in range(2):
            await draft(f"{unit}-{i}")
    except TaskDeferred:
        pass
    await finish(unit)


async def long_topic(unit: str):
    try:
        for i in range(4):
            await deep(f"{unit}-{i}")
    except TaskDeferred:
        pass
    await finish(unit)


async def topics(n: int):
    await asyncio.gather(*[f(f"{f.__name__.split('_')[0]}{i}") for i in range(n) for f in (short_topic, long_topic)])


async def boxed(n: int, deadline_s: float, grace_s: float):
    """Topics in a time box: past its deadline the drafts are deferred and each topic's
    `finish` still launches, for the grace window."""
    await time_box(topics(n), deadline_s=deadline_s, grace_s=grace_s, finishing_kinds=["finish"])


# --- the scenarios --------------------------------------------------------------------


DEMO_UNITS = [f"unit{i}" for i in range(8)]
BUNDLES = ["east", "west", "south", "north", "central"]


def _no_script(seed: int) -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class Scenario:
    """A flow, its arguments, its slots, and a deadline in minutes: the run's
    (`deadline_min`) or the flow's own time box (`boxed_min`, given to `boxed`)."""

    name: str
    description: str
    flow: Callable[[], tuple[Callable[..., Any], dict[str, Any]]]
    slots: int
    script: Callable[[int], dict[str, Any]] = _no_script
    deadline_min: float | None = None
    finishing_kinds: tuple[str, ...] = ()
    boxed_min: float | None = None

    @property
    def deadline(self) -> float | None:
        return self.deadline_min if self.deadline_min is not None else self.boxed_min


def _analysis() -> tuple[Callable[..., Any], dict[str, Any]]:
    from contraagent.docs.examples.analysis.flow import analyse

    return analyse, {"bundles": BUNDLES}


SCENARIOS: list[Scenario] = [
    Scenario(
        "demo",
        "`docs`: async, a review loop per unit, every review approving; 8 units, 3 slots",
        lambda: (docs, {"units": DEMO_UNITS}),
        3,
        demo_script,
    ),
    Scenario(
        "demo-one-review",
        "`docs_one_review`: the same tasks as `demo`, created without waiting, so each task's successors are known early; "
        "the note does not wait for the review",
        lambda: (docs_one_review, {"units": DEMO_UNITS}),
        3,
        demo_script,
    ),
    Scenario(
        "demo-loop",
        "`demo` with reviews that send the summary back (35% of first reviews, 20% of later ones)",
        lambda: (docs, {"units": DEMO_UNITS}),
        3,
        demo_loop_script,
    ),
    Scenario(
        "demo-deadline",
        "`demo` under a run deadline of 15 minutes (60% of its median work over the slots), `write_note` and `report` finishing kinds",
        lambda: (docs, {"units": DEMO_UNITS}),
        3,
        demo_script,
        deadline_min=15.0,
        finishing_kinds=("write_note", "report"),
    ),
    Scenario(
        "demo-one-review-deadline",
        "`demo-one-review` under the same deadline",
        lambda: (docs_one_review, {"units": DEMO_UNITS}),
        3,
        demo_script,
        deadline_min=15.0,
        finishing_kinds=("write_note", "report"),
    ),
    Scenario(
        "analysis",
        "the analysis example: nested flows, the parsers claim `heavy` (one at a time); 5 bundles, 3 slots",
        _analysis,
        3,
        analysis_script,
    ),
    Scenario("chains", "chains of 1, 3 and 7 tasks, the long ones queued last; 3 of each, 2 slots", lambda: (chains, {"n": 3}), 2),
    Scenario("fan-in", "3 fan-outs of 4 then a join, 3 of 2 then a join and 4 checks; 3 slots", lambda: (fan_in, {"n": 3}), 3),
    Scenario("claims", "6 units through a `db` claim (capacity 1) beside 6 free ones; 3 slots", lambda: (contention, {"n": 6}), 3),
    Scenario("competing", "chains, fan-in and claims as three pipelines in one run; 3 slots", lambda: (competing, {}), 3),
    Scenario(
        "time-box",
        "8 topics (2 drafts, or 4 deep tasks, then `finish`) in a time box of 27 minutes (60% of the median work over the slots), "
        "`finish` a finishing kind; 3 slots",
        lambda: (boxed, {"n": 4}),
        3,
        boxed_min=27.0,
    ),
]


def _figures(scenario: Scenario, stub: SlowStub, report: Any, scale: float) -> dict[str, Any]:
    timed = sorted(stub.timed, key=lambda launch: launch.start)
    if not timed:
        return {"makespan": 0.0, "launches": 0}
    first, last = timed[0].start, max(launch.end for launch in timed)
    makespan = (last - first) / scale
    busy = sum((launch.end - launch.start) / scale for launch in timed)
    out: dict[str, Any] = {
        "makespan": round(makespan, 2),
        "idle": round(scenario.slots * makespan - busy, 2),
        "launches": len(timed),
        "work": round(sum(launch.minutes for launch in timed), 2),
        "deferred": len(report.deferred),
        "failed": len(report.failed),
        "flow_errors": len(report.flow_errors),
    }
    if scenario.deadline is not None:
        at = first + scenario.deadline * scale
        out["done_by_deadline"] = round(sum(launch.minutes for launch in timed if launch.end <= at), 2)
        out["cost_after_deadline"] = round(sum(launch.minutes * RATE_USD for launch in timed if launch.end > at), 4)
        fit = 0
        for result in report.deferred:
            cause = result.cause
            if cause is not None and cause.cause == "cannot_finish" and cause.left_s is not None:
                # A Python task takes no time here: any time left would have done.
                own = draw(stub.seed, result.task.kind, result.task.key, 1) if result.task.kind in KINDS else 0.0
                fit += own * scale <= cause.left_s
        out["deferred_would_fit"] = fit
    return out


def run_seed(scenario_name: str, seed: int, scale: float) -> dict[str, Any]:
    """Both runs of one scenario and seed, in a directory of their own (this process's
    working directory while they run)."""
    scenario = next(s for s in SCENARIOS if s.name == scenario_name)
    with tempfile.TemporaryDirectory(prefix=f"bench-{scenario_name}-{seed}-") as tmp:
        here = Path(tmp)
        os.chdir(here)
        figures: dict[str, Any] = {}
        for run in ("first", "second"):
            stub = SlowStub(seed, scale, scenario.script(seed))
            flow, kwargs = scenario.flow()
            if scenario.boxed_min is not None:
                kwargs = {**kwargs, "deadline_s": scenario.boxed_min * scale, "grace_s": GRACE_MIN * scale}
            pipeline = Pipeline(
                None,
                runs_dir=here / "runs",
                cwd=here,
                backends=stub.backends(),
                overrides=Overrides(agent="stub"),
                max_concurrent=scenario.slots,
                keep_transcripts=False,
                log=lambda line: None,
                deadline_s=scenario.deadline_min * scale if scenario.deadline_min is not None else None,
                grace_s=GRACE_MIN * scale,
                finishing_kinds=scenario.finishing_kinds,
                overdue_s=OVERDUE_MIN * scale,
            )
            report = pipeline.run(flow, run_id=run, **kwargs)
            figures[run] = _figures(scenario, stub, report, scale)
        os.chdir(tempfile.gettempdir())
        return figures


# --- the report -----------------------------------------------------------------------

RUNS = ("first", "second")
#: The figures a summary gives the median of; it also gives the largest makespan.
MEDIAN = ("makespan", "idle", "deferred", "done_by_deadline", "cost_after_deadline", "deferred_would_fit")


def summary(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in MEDIAN:
        values = [f[name] for f in per_seed if name in f]
        if values:
            out[name] = round(statistics.median(values), 2)
    out["makespan_worst"] = round(max(f["makespan"] for f in per_seed), 2)
    out["failed"] = sum(f.get("failed", 0) + f.get("flow_errors", 0) for f in per_seed)
    return out


def markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Scheduling benchmark: {result['label']}",
        "",
        f"contraagent {result['version']} on Python {result['python']}, {result['seeds']} seeds, "
        f"one minute of agent work run in {result['scale_s']} s. Written by `benchmarks/schedule.py`, whose "
        "docstring says what each figure means. Minutes of agent work, the median over the seeds; "
        "`worst` is the largest makespan.",
        "",
        "| scenario | run | makespan | worst | idle slot time | deferred | done by deadline | cost after deadline (USD) | would fit |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, scenario in result["scenarios"].items():
        for run in RUNS:
            s = scenario["summary"][run]
            cells = [
                s["makespan"],
                s["makespan_worst"],
                s["idle"],
                s["deferred"],
                s.get("done_by_deadline", "-"),
                s.get("cost_after_deadline", "-"),
                s.get("deferred_would_fit", "-"),
            ]
            lines.append(f"| {name} | {run} | " + " | ".join(str(c) for c in cells) + " |")
    lines += ["", "## Scenarios", ""]
    lines += [f"- `{s.name}`: {s.description}." for s in SCENARIOS if s.name in result["scenarios"]]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> None:
    names = args.scenarios or [s.name for s in SCENARIOS]
    unknown = sorted(set(names) - {s.name for s in SCENARIOS})
    if unknown:
        sys.exit(f"unknown scenarios: {', '.join(unknown)}")
    jobs = [(name, seed) for name in names for seed in range(args.seeds)]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        done = list(pool.map(run_seed, [n for n, _ in jobs], [s for _, s in jobs], [args.scale] * len(jobs)))
    scenarios: dict[str, Any] = {}
    for (name, _), figures in zip(jobs, done, strict=True):
        entry = scenarios.setdefault(name, {"runs": {r: [] for r in RUNS}})
        for r in RUNS:
            entry["runs"][r].append(figures[r])
    for entry in scenarios.values():
        entry["summary"] = {r: summary(entry["runs"][r]) for r in RUNS}
    result = {
        "label": args.label or version("contraagent"),
        "version": version("contraagent"),
        "python": sys.version.split()[0],
        "seeds": args.seeds,
        "scale_s": args.scale,
        "scenarios": scenarios,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Not `with_suffix`: a name such as `0.6.2` has dots of its own.
    out.with_name(f"{out.name}.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    out.with_name(f"{out.name}.md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))


def _change(old: float | None, new: float | None) -> str:
    if old is None or new is None:
        return "-"
    if old == 0:
        return "0" if new == 0 else f"0 → {new}"
    return f"{(new - old) / old * 100:+.1f}%"


def _gap(new: dict[str, Any], old: dict[str, Any], run: str, name: str) -> float | None:
    """How much worse the async `docs` (`new`) is than `docs_one_review` (`old`) in
    `run`: makespan longer, or work by the deadline smaller, as a fraction; None when
    either file lacks the scenario."""
    late = "-deadline" if name == "done_by_deadline" else ""
    if f"demo-one-review{late}" not in old["scenarios"] or f"demo{late}" not in new["scenarios"]:
        return None
    a = old["scenarios"][f"demo-one-review{late}"]["summary"][run][name]
    b = new["scenarios"][f"demo{late}"]["summary"][run][name]
    if not a:
        return None
    return (b - a) / a if name == "makespan" else (a - b) / a


def compare(args: argparse.Namespace) -> None:
    old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (args.old, args.new))
    lines = [
        f"{new['label']} against {old['label']}: the change in each median, and in the largest makespan (`worst`).",
        "",
        "| scenario | run | makespan | worst | idle slot time | done by deadline | deferred |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, entry in new["scenarios"].items():
        if name not in old["scenarios"]:
            continue
        for r in RUNS:
            a, b = old["scenarios"][name]["summary"][r], entry["summary"][r]
            lines.append(
                f"| {name} | {r} | {_change(a['makespan'], b['makespan'])} | {_change(a['makespan_worst'], b['makespan_worst'])} | "
                f"{_change(a['idle'], b['idle'])} | {_change(a.get('done_by_deadline'), b.get('done_by_deadline'))} | "
                f"{a['deferred']} → {b['deferred']} |"
            )
    lines += ["", f"Seeding a first run: `demo` of {new['label']} against `demo-one-review` of {old['label']}.", ""]
    applies = False
    for name in ("makespan", "done_by_deadline"):
        first, second = _gap(new, old, "first", name), _gap(new, old, "second", name)
        if first is None or second is None:
            continue
        holds = first >= 0.10 and second <= 0.05
        applies = applies or holds
        verdict = "holds" if holds else "does not hold"
        lines.append(f"- {name}: {first * 100:+.1f}% worse in the first run, {second * 100:+.1f}% in the second: {verdict}.")
    lines += ["", f"The rule {'applies' if applies else 'does not apply'}."]
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the scenarios and write <out>.json and <out>.md")
    r.add_argument("--out", required=True, help="the path of the results, without a suffix")
    r.add_argument("--label", help="what the results are of (default: the installed version)")
    r.add_argument("--seeds", type=int, default=20)
    r.add_argument("--scale", type=float, default=SCALE_S, help="real seconds per minute of agent work")
    r.add_argument("--jobs", type=int, default=6, help="seeds run at once, each in a process of its own")
    r.add_argument("--scenarios", nargs="*", help="the scenarios to run (default: every one)")
    c = sub.add_parser("compare", help="print how the medians of one results file differ from another's")
    c.add_argument("old")
    c.add_argument("new")
    args = ap.parse_args(argv)
    if args.command == "run":
        run(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()
