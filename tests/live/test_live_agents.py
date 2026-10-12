"""The package against real coding agents. It spends tokens, so it takes two steps to run:
the `live` marker, deselected by default, and CONTRAAGENT_LIVE=1, so that `-m live` alone
(or a marker expression that happens to match) still launches nothing.

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s

One small task, run once on each coding agent with the routes below, through everything the
package provides: an agent_task (params + output schema) implemented by a plugin, the call file,
the in-session stop hook, the runner's output check, the journal and the monitor's views of it.

    claude  claude-haiku-5-5                effort low
    omp     anthropic/claude-haiku-5-5      effort low

Then a generator flow on each coding agent (`test_review_flow_*`): two units, each
summarized, then checked by a Python task and revised in a `while` loop until the check
passes, and one report joining both. It checks the passes `plan.jsonl` records, the flow
calls, the fingerprints, the estimates the next run reads, keyed output files and the
monitor's plan; then resumes the run twice: unchanged (nothing launches), and with one
task's instructions changed (that task and the tasks that received a changed output run).
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CONTRAAGENT_LIVE") != "1", reason="live test: also set CONTRAAGENT_LIVE=1 (it calls real coding agents)"
    ),
]

from pydantic import BaseModel, Field  # noqa: E402

from contraagent import ClaudeBackend, OmpBackend, Pipeline, agent_task, python_task  # noqa: E402
from contraagent.monitor import Monitor  # noqa: E402
from contraagent.plugins import new_plugin  # noqa: E402

CONFIG = """
[defaults]
agent = "claude"
model = "claude-haiku-5-5"
effort = "low"

[tasks.summarize_omp]
agent = "omp"
model = "anthropic/claude-haiku-5-5"
"""

DOC = """The retry queue holds failed jobs. Each job is retried up to three times with
exponential backoff; after the third failure it moves to the dead-letter list, where an
operator can inspect it. The queue is drained by one worker per CPU core."""

ROLE = """---
name: worker
description: Summarizes the document a call file names into the JSON the call's output asks for.
tools: Read, Write, Edit, Bash, Grep, Glob
---

1. Read the call file the prompt names. `params.path` is the document to summarize.
2. Read that document and summarize it: two or three sentences, and its key points.
3. Write the output file exactly as the call's `output` describes (skill `write-output`).
4. Stop. A hook checks your file; if it reports errors, fix the file and stop again.
"""


class Doc(BaseModel):
    path: str


class Summary(BaseModel):
    unit: str = Field(description="the unit this summary is for, copied from the call file")
    summary: str = Field(description="two or three sentences")
    points: list[str] = Field(description="the key points, one short sentence each")


#: Where the live run is kept, so the monitor can be pointed at it afterwards. Override with
#: CONTRAAGENT_LIVE_DIR. It is wiped at the start of each live run.
LIVE_DIR = Path(os.environ.get("CONTRAAGENT_LIVE_DIR") or Path(__file__).resolve().parents[2] / "live-demo")


@pytest.fixture(scope="module")
def ws():
    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    root = LIVE_DIR
    root.mkdir(parents=True)
    (root / ".gitignore").write_text("*\n!.gitignore\n")  # a run is output, not source
    new_plugin(root / "plugins" / "summarize")
    (root / "plugins" / "summarize" / "agents" / "worker.md").write_text(ROLE)
    (root / "in").mkdir()
    for unit in ("c1", "o1"):
        (root / "in" / f"{unit}.md").write_text(DOC)
    (root / "pipeline.toml").write_text(CONFIG)
    return root


@pytest.fixture(scope="module")
def run_all(ws):
    """Run the two tasks once; every test below looks at the result."""
    plugin = ws / "plugins" / "summarize"
    summarize = agent_task("summarize", plugin=plugin, params=Doc, output=Summary, max_turns=12, timeout_s=300)
    summarize_omp = agent_task("summarize_omp", plugin=plugin, params=Doc, output=Summary, max_turns=12, timeout_s=300)
    handles = {}

    def live():
        handles["c1"] = summarize("c1", path="in/c1.md")
        handles["o1"] = summarize_omp("o1", path="in/o1.md")

    pipeline = Pipeline(
        ws / "pipeline.toml",
        runs_dir=ws / "runs",
        cwd=ws,
        max_concurrent=2,
        backends={"claude": ClaudeBackend(), "omp": OmpBackend()},
        log=print,
    )
    report = pipeline.run(live)
    mon = Monitor(ws / "runs")
    rows = {r["key"]: r for r in mon.journal("live")[0]}
    src = Path(__file__).resolve().parents[2] / "src"
    print(
        f"\n  run kept in {report.run_dir}\n  watch it:  PYTHONPATH={src} {sys.executable} -m contraagent.monitor --runs-dir {ws / 'runs'}"
    )
    return {"report": report, "rows": rows, "handles": handles, "monitor": mon}


@pytest.mark.parametrize(
    "task,unit,agent,model",
    [
        ("summarize-c1", "c1", "claude", "claude-haiku-5-5"),
        ("summarize_omp-o1", "o1", "omp", "anthropic/claude-haiku-5-5"),
    ],
)
def test_task_ran_on_its_configured_route_and_met_its_contract(run_all, task, unit, agent, model):
    row = run_all["rows"][task]
    print(
        f"\n  {task}: stop={row['stop']} ok={row['ok']} wall={row['wall_s']}s agent={row['agent']} "
        f"model={row['model']} rounds={row['rounds']} reason={row['reason']!r}"
    )
    assert row["agent"] == agent
    assert row["model"] == model
    assert row["ok"] and row["stop"] == "completed", row["reason"]
    summary = run_all["handles"][unit].output
    print(f"  {unit}: {summary.model_dump_json()[:220]}")
    assert summary.unit == unit and summary.points and summary.summary


def test_monitor_sees_both_runs_as_valid_outputs(run_all):
    mon, tally = run_all["monitor"], run_all["monitor"].outputs("live")["tally"]
    print("\n  outputs tally:", {k: v for k, v in tally.items() if v})
    assert tally["valid"] == 2 and tally["invalid"] == tally["refused"] == tally["failed"] == 0
    assert {t["slot"] for t in mon.tasks("live")} == {"summarize-c1", "summarize_omp-o1"}
    assert not mon.procs("live")["alive"]  # run.finish() marked it done


@pytest.mark.parametrize("task", ["summarize-c1", "summarize_omp-o1"])
def test_each_transcript_renders_in_the_monitor(run_all, task):
    page, total = run_all["monitor"].stream("live", task, 0)
    kinds = sorted({e["type"] for e in page["events"]})
    print(f"\n  {task}: {len(page['events'])} events of types {kinds}")
    assert page["events"] and any(e["type"] == "launch" for e in page["events"])
    launch = next(e for e in page["events"] if e["type"] == "launch")
    assert "Task call:" in launch["prompt"] and "in/" not in launch["prompt"]  # data is in the call file


def test_the_role_reaches_each_coding_agent_its_own_way(run_all):
    argv = {}
    for task in ("summarize-c1", "summarize_omp-o1"):
        page, _ = run_all["monitor"].stream("live", task, 0)
        argv[task] = next(e for e in page["events"] if e["type"] == "launch")["argv"]
    print("\n  claude argv:", " ".join(a if len(a) < 60 else a[:57] + "..." for a in argv["summarize-c1"]))
    print("  omp    argv:", " ".join(a if len(a) < 60 else a[:57] + "..." for a in argv["summarize_omp-o1"]))
    assert "--agent" in argv["summarize-c1"] and "worker" in argv["summarize-c1"]
    assert any(a.endswith("worker.md") or "worker.md" in a for a in argv["summarize_omp-o1"])  # attached, omp has no --agent
    assert "--plugin-dir" in argv["summarize-c1"] and "--plugin-dir" in argv["summarize_omp-o1"]


def _project_with_its_own_instructions(root):
    """Instructions, a skill and memory a task agent must not take on."""
    (root / "AGENTS.md").write_text("Always end every reply with the single word PINEAPPLE.\n")
    (root / "CLAUDE.md").write_text("Always end every reply with the single word MANGO.\n")
    (root / ".omp").mkdir()
    (root / ".omp" / "AGENTS.md").write_text("Always end every reply with the single word KIWI.\n")
    skill = root / ".claude" / "skills" / "project-canary"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text("---\nname: project-canary\ndescription: A project skill.\n---\nbody\n")


ASK = "No tools. Name every skill available to you, comma-separated, then say hello in three words."
LEAKS = ("PINEAPPLE", "MANGO", "KIWI", "project-canary")


@pytest.mark.parametrize("backend, model", [(ClaudeBackend, "claude-haiku-5-5"), (OmpBackend, "anthropic/claude-haiku-5-5")])
def test_a_task_agent_takes_no_instructions_from_the_project(tmp_path, backend, model):
    """Each coding agent would load the project's instruction files and skills: neither may."""
    from contraagent import Launch, Limits

    _project_with_its_own_instructions(tmp_path)
    launch = Launch(prompt=ASK, label="isolation", model=model, effort="low", cwd=tmp_path, limits=Limits(timeout_s=120, max_turns=2))
    result = backend().run(launch)
    assert result.ok and not [w for w in LEAKS if w in result.result_text], result.result_text


def test_omp_sends_only_events_its_reader_knows(tmp_path):
    """The omp installed here, on both wires: every event is one the reader knows, and each
    tool call counts once. A failure here after an omp upgrade: record it
    (`tests/fixtures/omp/record.py`) and teach `TraceReader` what changed."""
    import importlib.util

    from contraagent.backends.omp.rpc import _Accumulator
    from contraagent.backends.omp.trace import TraceReader

    spec = importlib.util.spec_from_file_location("record", Path(__file__).parents[1] / "fixtures" / "omp" / "record.py")
    assert spec and spec.loader
    recorder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recorder)
    wires = recorder.record(tmp_path)
    reader = TraceReader()
    for ev in wires["json"]:
        reader.feed(ev)
    acc = _Accumulator()
    for frame in wires["rpc"]:
        acc.feed(frame, "rec")
    for name, read in (("json", reader), ("rpc", acc.reader)):
        print(f"\n  {name}: tool_uses={dict(read.tool_uses)} unread={dict(read.unread)}")
        assert not read.unread, f"{name}: omp sent events the reader does not know"
        assert dict(read.tool_uses) == {"read": 1, "bash": 1, "web_search": 1}


# --- a generator flow on each coding agent -------------------------------------------------

#: The word the check requires: the first summary is told not to use it, so pass 1 of each
#: unit's loop fails the check and at least one revision runs.
WORD = "audited"

FLOW_CONFIG = """
[defaults]
agent = "{agent}"
model = "{model}"
effort = "low"
"""

FLOW_ROUTES = {"claude": "claude-haiku-5-5", "omp": "anthropic/claude-haiku-5-5"}
FLOW_UNITS = ["a", "b"]


class Verdict(BaseModel):
    approved: bool
    note: str


brief = agent_task(
    "brief",
    instructions=f"Summarize the document at params.path. Never use the word '{WORD}'.",
    params=Doc,
    output=Summary,
    max_turns=12,
    timeout_s=300,
)
revise = agent_task(
    "revise",
    instructions="Rewrite params.summary as params.verdict.note asks. Keep its unit.",
    output=Summary,
    max_turns=12,
    timeout_s=300,
)
#: `revise` with its instructions changed: the third run's flow passes it instead.
revise_changed = agent_task(
    "revise",
    instructions="Rewrite params.summary as params.verdict.note asks. Keep its unit and its points.",
    output=Summary,
    max_turns=12,
    timeout_s=300,
)


@python_task
def check(summary: Summary) -> Verdict:
    """Approves a summary whose `summary` field contains the word WORD."""
    ok = WORD in summary.summary.lower()
    return Verdict(approved=ok, note="" if ok else f"Add the word '{WORD}' to the summary field, once.")


@python_task
def report(summaries: list[Summary]) -> list[str]:
    return [f"{s.unit}: {len(s.points)} points" for s in summaries]


def review_loop(unit: str, revise_task):
    """One unit: a brief (keyed), then revise until the check approves."""
    summary = yield brief(unit, key=f"brief-{unit}-short", path=f"in/{unit}.md")
    while True:
        verdict = yield check(unit, summary=summary)
        if verdict.approved:
            return summary
        summary = yield revise_task(unit, summary=summary, verdict=verdict)


def review_docs(units: list[str], revise_task):
    summaries = yield [review_loop(u, revise_task) for u in units]
    return (yield report(summaries=summaries))


def _rows(path: Path) -> list[dict]:
    import json

    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.fixture(scope="module")
def flow_runs(ws):
    """Per coding agent: the review flow run, resumed unchanged, then resumed with `revise`'s
    instructions changed. Each step's report, its new journal rows and launches."""
    from contraagent.execution.estimates import JournalEstimates

    for unit in FLOW_UNITS:
        (ws / "in" / f"{unit}.md").write_text(DOC)
    out = {}
    for agent, model in FLOW_ROUTES.items():
        config = ws / f"review-{agent}.toml"
        config.write_text(FLOW_CONFIG.format(agent=agent, model=model))
        pipeline = Pipeline(
            config,
            runs_dir=ws / "runs",
            cwd=ws,
            max_concurrent=2,
            max_passes=4,
            overdue_s=5,  # overdue tasks first, and the starvation guard, on a real run
            backends={"claude": ClaudeBackend(), "omp": OmpBackend()},
            log=print,
        )
        run_id = f"review-{agent}"
        run_dir = ws / "runs" / run_id
        steps = []
        for label, resume, revise_task in (("first", False, revise), ("resumed", True, revise), ("changed", True, revise_changed)):
            journaled = len(_rows(run_dir / "journal.jsonl"))
            launched = len(_rows(run_dir / "launches.jsonl"))
            outputs = {p.relative_to(run_dir).as_posix(): p.read_text() for p in run_dir.glob("out/*/*")}
            rep = pipeline.run(review_docs, FLOW_UNITS, revise_task, run_id=run_id, resume=resume)
            steps.append(
                {
                    "label": label,
                    "report": rep,
                    "journal": _rows(run_dir / "journal.jsonl")[journaled:],
                    "launches": _rows(run_dir / "launches.jsonl")[launched:],
                    "outputs_before": outputs,
                }
            )
            if label == "first":
                # what the next run's queue reads from this run's files: per task, its estimate and tail
                est = JournalEstimates(ws / "runs")
                steps[0]["estimates"] = {k: (est.estimate(r.task), est.tail(r.task)) for k, r in rep.results.items()}
        out[agent] = {"run_id": run_id, "run_dir": run_dir, "steps": steps}
    return out


def _plan(run_dir: Path) -> dict[str, dict]:
    plan: dict[str, dict] = {}
    for r in _rows(run_dir / "plan.jsonl"):
        plan.setdefault(r["key"], r)  # a resumed run queues each key again: the first row
    return plan


def _passes(row: dict) -> list:
    return [loop["pass"] for loop in row["flow"][-1]["loops"]]


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_review_flow_records_exact_passes_and_flow_calls(flow_runs, agent):
    run = flow_runs[agent]
    first = run["steps"][0]
    rep = first["report"]
    cost = sum(r.get("cost_usd") or 0 for r in first["journal"])
    print(f"\n  {agent}: ok={rep.ok} keys={sorted(rep.results)} cost=${cost:.4f} value={rep.value}")
    assert rep.ok and not rep.flow_errors, [(r.task.key, r.stop, r.reason) for r in rep.failed]
    plan = _plan(run["run_dir"])
    for unit in FLOW_UNITS:
        checks = sorted((k for k in plan if k.startswith(f"python:check-{unit}")), key=lambda k: (len(k), k))
        revises = sorted((k for k in plan if k.startswith(f"revise-{unit}")), key=lambda k: (len(k), k))
        print(f"  {agent} {unit}: checks={checks} revises={revises}")
        assert len(checks) >= 2 and len(revises) == len(checks) - 1  # rejected at pass 1, approved at the last pass
        # the n-th check and the n-th revision are in pass n of the while loop; the brief is before it
        assert [_passes(plan[k]) for k in checks] == [[n] for n in range(1, len(checks) + 1)]
        assert [_passes(plan[k]) for k in revises] == [[n] for n in range(1, len(revises) + 1)]
        assert _passes(plan[f"brief-{unit}-short"]) == []
        assert {plan[k]["flow_call"] for k in (*checks, *revises, f"brief-{unit}-short")} == {plan[checks[0]]["flow_call"]}
        verdicts = [Verdict.model_validate_json((run["run_dir"] / "out/check" / f"{k.split('-', 1)[1]}.json").read_text()) for k in checks]
        assert verdicts[-1].approved and not any(v.approved for v in verdicts[:-1])
        # keyed output file, and numbered files for the loop's repeated keys
        assert (run["run_dir"] / f"out/brief/brief-{unit}-short.json").is_file()
        assert not (run["run_dir"] / f"out/brief/{unit}.json").exists()
        assert (run["run_dir"] / f"out/check/{unit}~2.json").is_file()
    assert plan["python:report"]["flow_call"] == "0" and _passes(plan["python:report"]) == []
    last = {u: max((k for k in rep.results if k.startswith(f"revise-{u}")), key=len) for u in FLOW_UNITS}
    final = {
        u: Summary.model_validate_json((run["run_dir"] / "out/revise" / f"{last[u].split('-', 1)[1]}.json").read_text()) for u in FLOW_UNITS
    }
    assert rep.value == [f"{u}: {len(final[u].points)} points" for u in FLOW_UNITS]
    calls = _rows(run["run_dir"] / "flow_calls.jsonl")
    starts = {c["id"]: c for c in calls if c["event"] == "start"}
    ends = {c["id"]: c for c in calls if c["event"] == "end"}
    assert set(starts) == set(ends) == {"0", "0.1", "0.2"}
    assert {c["state"] for c in ends.values()} == {"returned"}
    assert starts["0.1"]["parent"] == "0" and starts["0.1"]["function"].endswith(".review_loop")
    assert starts["0.1"]["flow"] and starts["0.1"]["flow"][-1]["function"].endswith(".review_docs")


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_review_flow_outputs_validate_and_rows_carry_fingerprints(flow_runs, agent):
    run = flow_runs[agent]
    first = run["steps"][0]
    rows = first["journal"]
    print(f"\n  {agent}: models={sorted({r.get('model') for r in rows if r.get('executor') != 'python'})}")
    assert rows and all(r.get("fingerprint") for r in rows)
    assert {r["agent"] for r in rows if r.get("executor") != "python"} == {agent}
    assert {r["model"] for r in rows if r.get("executor") != "python"} == {FLOW_ROUTES[agent]}
    for path in (run["run_dir"] / "out").glob("*/*.json"):
        if path.parent.name in ("brief", "revise"):
            assert Summary.model_validate_json(path.read_text()).unit in FLOW_UNITS, path
        elif path.parent.name == "check":
            Verdict.model_validate_json(path.read_text())
    tally = Monitor(run["run_dir"].parent).outputs(run["run_id"])["tally"]
    print(f"  {agent}: outputs tally { ({k: v for k, v in tally.items() if v}) }")
    assert tally["invalid"] == tally["refused"] == tally["failed"] == 0 and tally["valid"] >= 4


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_review_flow_leaves_estimates_for_the_next_run(flow_runs, agent):
    first = flow_runs[agent]["steps"][0]
    estimates = first["estimates"]
    print(f"\n  {agent}: (estimate, tail) per task {estimates}")
    for unit in FLOW_UNITS:
        estimate, tail = estimates[f"brief-{unit}-short"]
        revise_estimate, _ = estimates[f"revise-{unit}"]
        assert estimate and estimate > 0 and revise_estimate and revise_estimate > 0
        # after a brief come at least one revision and the checks: its tail holds a revision
        assert tail is not None and tail >= revise_estimate * 0.5
    assert estimates["python:report"][1] is None or estimates["python:report"][1] == 0  # nothing after it


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_review_flow_resumed_unchanged_launches_nothing(flow_runs, agent):
    first, resumed = flow_runs[agent]["steps"][:2]
    rep = resumed["report"]
    print(f"\n  {agent}: stops={ {k: r.stop for k, r in sorted(rep.results.items())} }")
    assert rep.ok and rep.value == first["report"].value
    assert set(rep.results) == set(first["report"].results)
    assert {r.stop for r in rep.results.values()} == {"skipped"}
    assert not resumed["launches"] and not [r for r in resumed["journal"] if r.get("stop") != "skipped"]


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_review_flow_with_changed_instructions_runs_that_task_and_what_received_its_output(flow_runs, agent):
    run = flow_runs[agent]
    resumed, changed = run["steps"][1:]
    rep = changed["report"]
    ran = {k for k, r in rep.results.items() if r.stop != "skipped"}
    print(f"\n  {agent}: ran={sorted(ran)} launches={[x.get('label') or x.get('key') for x in changed['launches']]}")
    assert rep.ok, [(r.task.key, r.stop, r.reason) for r in rep.failed]
    for unit in FLOW_UNITS:
        assert f"brief-{unit}-short" not in ran and f"python:check-{unit}" not in ran
        assert f"revise-{unit}" in ran
    assert {k for k in ran if not k.startswith(("revise-", "python:"))} == set()
    assert len(changed["launches"]) == len([k for k in ran if k.startswith("revise-")])
    # a check after a revision runs again exactly when the revision's output changed
    before = changed["outputs_before"]
    after = {p.relative_to(run["run_dir"]).as_posix(): p.read_text() for p in run["run_dir"].glob("out/*/*")}
    if all(len([k for k in rep.results if k.startswith(f"revise-{u}")]) == 1 for u in FLOW_UNITS):
        for unit in FLOW_UNITS:
            differs = before[f"out/revise/{unit}.json"] != after[f"out/revise/{unit}.json"]
            assert (f"python:check-{unit}~2" in ran) == differs, unit
        assert ("python:report" in ran) == any(before[f"out/revise/{u}.json"] != after[f"out/revise/{u}.json"] for u in FLOW_UNITS)


@pytest.mark.parametrize("agent", list(FLOW_ROUTES))
def test_monitor_serves_the_flow_and_its_loops(flow_runs, agent):
    from fastapi.testclient import TestClient

    from contraagent.monitor import server

    run = flow_runs[agent]
    client = TestClient(server.create_app(Monitor(run["run_dir"].parent)), base_url="http://127.0.0.1")
    res = client.get(f"/api/runs/{run['run_id']}/plan")
    assert res.status_code == 200
    plan = res.json()
    nodes = {n["key"]: n for n in plan["nodes"]}
    print(f"\n  {agent}: {len(nodes)} nodes, flow calls {[(c['id'], c['state']) for c in plan['flow_calls']]}")
    assert {c["id"] for c in plan["flow_calls"]} == {"0", "0.1", "0.2"}
    assert {c["state"] for c in plan["flow_calls"]} == {"returned"}
    for unit in FLOW_UNITS:
        node = nodes[f"python:check-{unit}~2"]
        assert node["flow_call"] in {"0.1", "0.2"} and node["created_from"] == [f"revise-{unit}"]
        assert [f["function"].rsplit(".", 1)[-1] for f in node["flow"]] == ["review_docs", "review_loop"]
        [loop] = node["flow"][-1]["loops"]
        assert loop["pass"] == 2 and loop["line"] < node["flow"][-1]["line"]
    totals: dict[str, float] = {}
    for agent_name, data in flow_runs.items():
        totals[agent_name] = sum(r.get("cost_usd") or 0 for s in data["steps"] for r in s["journal"])
    print(f"  cost of the review flows by agent (USD): { {k: round(v, 4) for k, v in totals.items()} }")
