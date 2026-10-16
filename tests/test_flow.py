"""The pipeline API end to end: agent_task + plugin + call file, Python tasks, validators, resume."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from contraagent import CommandValidator, ConfigError, Overrides, Pipeline, PipelineConfig, agent_task, python_task
from contraagent._internal.cli import _spent
from contraagent._internal.contracts.calls import validate_call
from contraagent._internal.platform import envvars
from contraagent.backends import CallFile, Stop
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent, fails, writes_nothing


class Doc(BaseModel):
    path: str


class Summary(BaseModel):
    unit: str
    summary: str = Field(description="two or three sentences")
    points: list[str]


class Verdict(BaseModel):
    approved: bool


def good_answer(launch):
    if launch.kind == "summarize":
        return {"unit": launch.unit, "summary": "s", "points": ["a", "b"]}
    if launch.kind == "review":
        return {"approved": len(launch.params["summary"]["points"]) > 1}
    return "# doc\n"


def stub(reply=good_answer) -> StubAgent:
    """The stub agent answering every kind with `reply`."""
    return StubAgent({"summarize": reply, "review": reply, "write_doc": reply})


@pytest.fixture
def plugin_dir(tmp_path):
    new_plugin(tmp_path / "plugins" / "summarize")
    return tmp_path / "plugins" / "summarize"


def declare(plugin_dir, **kw):
    summarize = agent_task("summarize", plugin=plugin_dir, params=Doc, output=Summary, max_turns=5, timeout_s=60, **kw)
    review = agent_task("review", plugin=plugin_dir, output=Verdict, max_turns=5, timeout_s=60)
    return summarize, review


def pipeline(tmp_path, agent, **kw):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def test_a_flow_runs_in_dependency_order_with_typed_outputs(tmp_path, plugin_dir):
    summarize, review = declare(plugin_dir)

    @python_task
    def report(verdicts: list[Verdict]) -> int:
        return sum(v.approved for v in verdicts)

    handles = {}

    def docs(units):
        verdicts = []
        for u in units:
            s = summarize(u, path=f"in/{u}.md")
            verdicts.append(review(u, summary=s))
            handles[u] = s
        handles["report"] = report(verdicts=verdicts)

    agent = stub()
    rep = pipeline(tmp_path, agent).run(docs, units=["a", "b"])
    assert rep.ok, rep.failed
    assert handles["a"].output == Summary(unit="a", summary="s", points=["a", "b"])  # typed, checked
    order = [launch.key for launch in agent.launches]
    assert order.index("summarize-a") < order.index("review-a")
    [first] = agent.launches_of("summarize-a")
    launch, call = first.launch, first.call
    assert call.params == {"path": "in/a.md"} and call.output.format == "json"
    assert call.output.json_schema["properties"]["summary"]["description"] == "two or three sentences"
    assert "in/a.md" not in launch.prompt and "Task call: `summarize`" in launch.prompt  # data stays in the call file
    assert launch.role == "worker" and launch.plugin_dirs == (str(plugin_dir.resolve()),)
    review_call = next(launch.call for launch in agent.launches if launch.kind == "review")
    assert review_call.params["summary"]["points"] == ["a", "b"]  # upstream value, resolved
    assert handles["report"].output == 2


def test_validators_send_the_errors_back_into_the_session(tmp_path, plugin_dir):
    def has_two_points(path, s: Summary):
        if len(s.points) < 2:
            return ["points: give at least two"]

    no_todo = CommandValidator(
        [sys.executable, "-c", "import sys; t = open(sys.argv[1]).read(); sys.exit('found TODO' if 'TODO' in t else 0)", "{path}"],
        name="no-todo",
    )
    summarize = agent_task(
        "summarize", plugin=plugin_dir, params=Doc, output=Summary, validators=[has_two_points, no_todo], max_turns=5, timeout_s=60
    )

    agent = StubAgent(
        {
            "summarize": [
                {"unit": "u", "summary": "TODO", "points": ["a"]},
                {"unit": "u", "summary": "TODO", "points": ["a", "b"]},
                {"unit": "u", "summary": "done", "points": ["a", "b"]},
            ]
        }
    )
    # omp: no stop hook continues its turn, so every check comes back as a correction round
    rep = pipeline(tmp_path, agent, overrides=Overrides(agent="omp")).run(lambda: summarize("u", path="x"), run_id="v")
    [res] = rep.results.values()
    assert res.ok and res.launch_result.rounds == 3
    prompts = [launch.prompt for launch in agent.launches]
    assert "[has_two_points] points: give at least two" in prompts[1]
    assert "[no-todo] found TODO" in prompts[2]
    assert "Required JSON Schema" not in prompts[1]  # the file met its schema; only validators failed
    assert rep.summary["corrections"] == 2 and rep.summary["attempts"] == 1
    assert _spent(rep.summary).endswith(", 2 correction rounds")  # the CLI's closing line
    # the command validator travels in the call file, so the in-session hook runs it too
    assert agent.launches[0].call.output.commands[0]["name"] == "no-todo"


def test_a_text_output_with_a_linter(tmp_path, plugin_dir):
    lint = CommandValidator(
        [sys.executable, "-c", "import sys; sys.exit('no heading' if not open(sys.argv[1]).read().startswith('#') else 0)"], name="heading"
    )
    write_doc = agent_task("write_doc", plugin=plugin_dir, output=str, validators=[lint], max_turns=5, timeout_s=60)
    agent = StubAgent({"write_doc": ["plain", "# ドキュメント\n本文"]})
    holder = {}
    rep = pipeline(tmp_path, agent).run(lambda: holder.setdefault("d", write_doc("u")), run_id="t")
    assert rep.ok and holder["d"].output.startswith("# ドキュメント")
    assert holder["d"].path.suffix == ".md" and agent.launches[0].call.output.format == "text"


def test_a_failed_upstream_refuses_its_consumers_before_launch(tmp_path, plugin_dir):
    summarize, review = declare(plugin_dir, retries=0)
    # The upstream fails outright: the rounds that lead to invalid_output are the contracts' tests.
    agent = StubAgent({"summarize": fails(Stop.INVALID_OUTPUT), "review": good_answer})

    def flow():
        review("u", summary=summarize("u", path="x"))

    rep = pipeline(tmp_path, agent).run(flow)
    stops = {k: r.stop for k, r in rep.results.items()}
    assert stops == {"summarize-u": "invalid_output", "review-u": "invalid_input"}
    assert all(launch.kind == "summarize" for launch in agent.launches)  # review never launched


def test_the_value_of_a_flow_that_does_not_yield_is_what_it_returned(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    rep = pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"))
    assert rep.value.key == "summarize-u"  # the Pending itself
    assert rep.value.output == Summary(unit="u", summary="s", points=["a", "b"])


def _one_point(path, s: Summary):
    return None if len(s.points) > 1 else "points: give at least two"


@pytest.mark.parametrize("yields", [False, True])
def test_an_output_its_validators_rejected_refuses_every_task_that_reads_it(tmp_path, plugin_dir, yields):
    # The file the rounds left behind meets its schema; only a validator rejected it.
    summarize, review = declare(plugin_dir, retries=0, validators=[_one_point])
    ran = []

    @python_task
    def count(summaries: dict[str, Summary]) -> int:
        ran.append(summaries)
        return len(summaries)

    agent = StubAgent({"summarize": {"unit": "u", "summary": "s", "points": ["a"]}, "review": good_answer})

    def flow():
        s = summarize("u", path="x")
        if yields:
            try:
                yield s
            except Exception:
                pass
        review("u", summary=s)
        count(summaries={"u": s})

    rep = pipeline(tmp_path, agent, overrides=Overrides(agent="omp")).run(flow)
    stops = {k: r.stop for k, r in rep.results.items()}
    assert stops == {"summarize-u": "invalid_output", "review-u": "invalid_input", "python:count": "invalid_input"}
    assert ran == [] and all(launch.kind == "summarize" for launch in agent.launches)
    assert rep.results["review-u"].reason.startswith("invalid input: input from summarize-u ended invalid_output: ")
    assert rep.results["python:count"].reason.startswith("invalid input: input from summarize-u ended invalid_output: ")


def test_resume_skips_finished_work_and_still_reads_its_output(tmp_path, plugin_dir):
    summarize, review = declare(plugin_dir)
    handles = {}

    def flow():
        handles["s"] = summarize("u", path="x")
        handles["r"] = review("u", summary=handles["s"])

    agent = stub()
    pipeline(tmp_path, agent).run(flow)
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(flow, resume=True)
    assert agent.launches == [] and {r.stop for r in rep.results.values()} == {"skipped"}
    assert handles["s"].output.points == ["a", "b"] and handles["r"].output.approved


def test_a_task_that_reruns_on_resume_runs_again_and_the_others_are_skipped(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    published: list[str] = []

    @python_task(rerun_on_resume=True)
    def publish(unit: str) -> None:
        published.append(unit)

    publish_agent = agent_task("publish_agent", instructions="Publish.", output=str, rerun_on_resume=True, max_turns=3, timeout_s=60)

    def flow():
        summarize("u", path="x")
        publish("u")
        publish_agent("u")

    agent = StubAgent({"summarize": good_answer, "publish_agent": "published"})
    pipeline(tmp_path, agent).run(flow)
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(flow, resume=True)
    assert published == ["u", "u"] and [launch.key for launch in agent.launches] == ["publish_agent-u"]
    stops = {r.task.key: r.stop for r in rep.results.values()}
    assert stops == {"summarize-u": "skipped", "python:publish-u": "completed", "publish_agent-u": "completed"}
    assert agent_task("x", instructions="x", rerun_on_resume=True).differences(agent_task("x", instructions="x")) == ["rerun_on_resume"]


def test_the_stop_hook_checks_the_call_inside_the_session(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    agent = StubAgent({"summarize": writes_nothing()})  # the runner sees invalid_output
    pipeline(tmp_path, agent, overrides=Overrides(agent="omp")).run(lambda: summarize("u", path="x"), run_id="h")
    call_path = Path(agent.launches[0].launch.env[envvars.CALL])
    env = {envvars.CALL: str(call_path)}
    code, msg = validate_call(env=env)
    assert code == 2 and "file was not written" in msg
    out = Path(CallFile.read(call_path).output.path)
    out.write_text('{"unit": "u", "summary": "s", "points": "not a list"}')
    code, msg = validate_call(env=env)
    assert code == 2 and "points" in msg and "Required JSON Schema" in msg  # pydantic itself, via schema_ref
    assert validate_call(stdin_text='{"stop_hook_active": true}', env=env) == (0, "")  # never loops
    out.write_text('{"unit": "u", "summary": "s", "points": ["a"]}')
    assert validate_call(env=env) == (0, "")


def test_declarations_fail_early(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    with pytest.raises(TypeError, match="missing path"):
        pipeline(tmp_path, stub()).run(lambda: summarize("u"))
    with pytest.raises(TypeError, match="plugin="):
        agent_task("x", output=Summary)
    with pytest.raises(TypeError, match="max_turnz"):
        agent_task("x", plugin=plugin_dir, max_turnz=3)
    with pytest.raises(ConfigError, match=r"agent_task: \[x\]\.max_turns = '3' is not a number"):
        agent_task("x", plugin=plugin_dir, max_turns="3")
    with pytest.raises(RuntimeError, match="inside a flow"):
        summarize("u", path="x")


def test_declared_budgets_are_defaults_and_the_config_outranks_them(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir, model="from-code")
    cfg = tmp_path / "p.toml"
    cfg.write_text("[tasks.summarize]\nmax_turns = 9\n")
    agent = stub()
    Pipeline(PipelineConfig.load(cfg), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None).run(
        lambda: summarize("u", path="x")
    )
    launch = agent.launches[0].launch
    assert launch.model == "from-code" and launch.limits.max_turns == 9 and launch.limits.timeout_s == 60


def test_a_validator_may_take_the_tasks_params_and_call_file(tmp_path, plugin_dir):
    def cites_its_input(path, s: Summary, *, params):
        if s.unit != params["path"]:
            return [f"unit: {params['path']!r} expected"]

    reads_call = CommandValidator(
        [
            sys.executable,
            "-c",
            "import json, sys; c = json.load(open(sys.argv[1])); sys.exit(0 if c['params']['path'] else 'no path')",
            "{call}",
        ],
        name="reads-call",
    )
    summarize = agent_task(
        "summarize", plugin=plugin_dir, params=Doc, output=Summary, validators=[cites_its_input, reads_call], max_turns=5, timeout_s=60
    )
    agent = StubAgent({"summarize": [{"unit": "u", "summary": "s", "points": []}, {"unit": "in/u.md", "summary": "s", "points": []}]})
    handle = {}
    rep = pipeline(tmp_path, agent).run(lambda: handle.setdefault("s", summarize("u", path="in/u.md")))
    assert rep.ok and handle["s"].output.unit == "in/u.md"
    assert "[cites_its_input] unit: 'in/u.md' expected" in agent.launches[1].prompt
    row = json.loads((rep.run_dir / "journal.jsonl").read_text().splitlines()[0])
    assert row["rounds"] == 2 and "[cites_its_input] unit: 'in/u.md' expected" in row["round_errors"][0][0]
    # the in-session hook runs the command validator with the call file too
    call = agent.launches[0].launch.env[envvars.CALL]
    assert validate_call(env={envvars.CALL: call}) == (0, "")


def test_a_python_task_validator_gets_the_resolved_params(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    seen = []

    def same_unit(path, n: int, *, params):
        seen.append(params["summary"].unit)

    @python_task(validators=[same_unit])
    def count(summary: Summary) -> int:
        return len(summary.points)

    def flow():
        return count(summary=summarize("u", path="x"))

    rep = pipeline(tmp_path, stub()).run(flow)
    assert rep.ok and seen == ["u"] and rep.value.output == 2  # the flow's return value, read after the run
    assert rep.value.path.name == "count.json"  # no ':' from the key `python:count`


def test_a_refused_task_names_the_task_that_did_not_write_its_input(tmp_path, plugin_dir):
    summarize, review = declare(plugin_dir, retries=0)
    rep = pipeline(tmp_path, StubAgent({"summarize": fails()})).run(lambda: review("u", summary=summarize("u", path="x")))
    assert rep.results["review-u"].reason.startswith("invalid input: input from summarize-u is missing")


def test_a_run_id_that_holds_a_run_is_refused_unless_resumed(tmp_path, plugin_dir):
    from contraagent import RunExists

    summarize, _ = declare(plugin_dir)
    pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="r")
    with pytest.raises(RunExists, match="continue it with resume=True, or start a new one with another run_id"):
        pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="r")
    assert pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="r", resume=True).ok


def _files(root: Path) -> dict[str, tuple[bytes, int]]:
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_refused_run_writes_nothing(tmp_path, plugin_dir):
    from contraagent import RunExists

    summarize, _ = declare(plugin_dir)
    pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="rj")
    runs = tmp_path / "runs"
    before = _files(runs)
    assert "rj.lock" in before and "rj/run.json" in before
    with pytest.raises(RunExists) as refused:
        pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="rj")
    assert refused.value.rows == 1 and refused.value.run_dir == runs / "rj"
    assert _files(runs) == before  # run.json (argv, pid, started_at) and the lock file as they were


def test_the_cli_refusal_names_its_flags(tmp_path, monkeypatch, capsys):
    from contraagent._internal.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    flow = tmp_path / "flow.py"
    flow.write_text(
        "from contraagent import python_task\n\n@python_task\ndef one() -> str:\n    return 'x'\n\ndef flow():\n    return one()\n"
    )
    args = ["run", f"{flow}:flow", "--stub", "--run-id", "rj", "--runs-dir", str(tmp_path / "runs")]
    assert main(args) == 0, capsys.readouterr().out
    capsys.readouterr()
    assert main(args) == 1
    out = capsys.readouterr().out
    assert "already holds a run (1 journal rows): continue it with --resume, or start a new one with another --run-id" in out
    assert "resume=True" not in out and "run_id" not in out


def test_the_result_carries_the_rounds_of_a_correction(tmp_path, plugin_dir):
    summarize, _ = declare(plugin_dir)
    agent = StubAgent({"summarize": lambda launch: {"unit": "u", "summary": "s", "points": []} if launch.resumed else "{"})
    rep = pipeline(tmp_path, agent).run(lambda: summarize("u", path="x"))
    result = rep.results["summarize-u"]
    assert rep.ok and result.rounds == 2 and result.rounds == result.launch_result.rounds
    [errors] = result.round_errors
    assert isinstance(errors, tuple) and "not valid JSON" in errors[0]
    row = json.loads((rep.run_dir / "journal.jsonl").read_text().splitlines()[0])
    assert row["rounds"] == 2 and row["round_errors"] == [list(errors)]
    plain = pipeline(tmp_path, stub()).run(lambda: summarize("u", path="x"), run_id="plain").results["summarize-u"]
    assert plain.rounds == 1 and plain.round_errors == ()


def test_progress_is_logged_as_it_happens(tmp_path, plugin_dir, caplog):
    import logging

    from contraagent.testing import rate_limited

    summarize, _ = declare(plugin_dir)
    config = {"tasks": {"summarize": {"model": "m1", "fallbacks": [{"agent": "claude", "model": "m2"}]}}}
    agent = StubAgent(
        {
            "summarize": lambda launch: (
                rate_limited() if launch.model == "m1" else ({"unit": "u", "summary": "s", "points": []} if launch.resumed else "{")
            )
        }
    )
    caplog.set_level(logging.INFO, logger="contraagent")
    Pipeline(PipelineConfig(config), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(
        lambda: summarize("u", path="x")
    )
    lines = [r.getMessage() for r in caplog.records]
    assert "[start] summarize-u" in lines
    assert any(line.startswith("[switch] summarize-u: rate limited on hop 1/2 claude/m1") for line in lines)
    assert any(
        line.startswith("[correction] summarize-u: round 1 failed its checks, sent back:") and "not valid JSON" in line for line in lines
    )
    assert any(line.startswith("[end] summarize-u: completed") and "2 rounds" in line for line in lines)


@pytest.mark.parametrize("coding_agent", ["claude", "codex"])
def test_a_stop_hook_sends_a_command_check_back_within_the_turn(tmp_path, plugin_dir, coding_agent):
    """Claude Code and Codex continue the session when a Stop hook objects: each runs its own
    rendered hooks file (`hooks/hooks.json`, `codex/hooks.json`)."""
    lint = CommandValidator(
        [sys.executable, "-c", "import sys; sys.exit('no heading' if not open(sys.argv[1]).read().startswith('#') else 0)"], name="heading"
    )
    write_doc = agent_task("write_doc", plugin=plugin_dir, output=str, validators=[lint], max_turns=5, timeout_s=60)
    agent = StubAgent({"write_doc": ["plain", "# Doc\n"]})
    rep = pipeline(tmp_path, agent, overrides=Overrides(agent=coding_agent)).run(lambda: write_doc("u"))
    assert rep.ok and rep.results["write_doc-u"].launch_result.rounds == 1  # fixed before the turn ended
    first, second = agent.launches
    assert not first.in_turn and second.in_turn and not second.resumed
    assert "[heading] no heading" in second.prompt  # what the plugin's rendered Stop hook said
    assert "JSON output" not in second.prompt  # a text output is not told about JSON
    row = json.loads((rep.run_dir / "journal.jsonl").read_text().splitlines()[0])
    assert row["rounds"] == 1 and row["hook_errors"] == [[second.prompt.split("- ", 1)[1].strip()]]
