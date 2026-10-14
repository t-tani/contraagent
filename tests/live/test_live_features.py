"""The task features against real coding agents: Claude Code on Haiku and omp on Haiku.
It spends tokens, so, as `test_live_agents.py`, it needs the `live` marker and CONTRAAGENT_LIVE=1:

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_features.py

Each test runs a small flow once per coding agent:

* `skills_from`: a task loads a skill from a skill plugin beside its own plugin;
* `changes`, with `Pipeline(scopes=, enrichers=, row_extras=)`: an attempt's changed files
  are journaled, and the files a timed-out attempt created are removed;
* claims: tasks of two kinds that claim `topic:{unit}` write one topic one after the
  other, a task that claims nothing runs beside them, and a task that claims two topics
  through `{params.topics}` waits while a write of either runs;
* `output_from="message"`: the final message is the output, after a tool call, and a
  message that fails its checks is corrected in the same session;
* quota caps and `quota_rule`: a credential past one rests, its tasks take the next hop,
  and a task with no hop left is deferred (`deferred.jsonl`);
* a light launch (`tools=()`): one call with no tools and the role as the system prompt,
  its input a small part of the same judgement's with the agent's tools.
* a time box: past a flow call's own deadline its writes are deferred, its finishing kind
  still launches, and a task after the box launches.
* the cost of a fix-up round: an attempt costs what its rounds cost, each counted once,
  though Claude Code reports a resumed session's cost so far;
* `unwrap`: a final message that wraps its JSON passes in one round with `unwrap=True`,
  and takes a fix-up round without it.
"""

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CONTRAAGENT_LIVE") != "1", reason="live test: also set CONTRAAGENT_LIVE=1 (it calls real coding agents)"
    ),
]

from pydantic import BaseModel  # noqa: E402

from contraagent import ClaudeBackend, OmpBackend, Pipeline, TaskDeferred, agent_task, time_box  # noqa: E402
from contraagent.plugins import new_plugin  # noqa: E402

ROUTES = {"claude": ("claude", "claude-haiku-5-5"), "omp": ("omp", "anthropic/claude-haiku-5-5")}
AGENTS = list(ROUTES)

#: Where the runs are kept, so the monitor can be pointed at them. Wiped at the start.
LIVE_DIR = Path(os.environ.get("CONTRAAGENT_LIVE_DIR") or Path(__file__).resolve().parents[2] / "live-demo") / "features"


@pytest.fixture(scope="module")
def ws():
    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    LIVE_DIR.mkdir(parents=True)
    (LIVE_DIR / ".gitignore").write_text("*\n!.gitignore\n")
    return LIVE_DIR


def route(agent: str) -> dict:
    name, model = ROUTES[agent]
    return {"agent": name, "model": model, "effort": "low"}


def pipeline(ws: Path, config: str | None = None, **options) -> Pipeline:
    path = None
    if config is not None:
        path = ws / f"pipeline-{len(list(ws.glob('pipeline-*.toml')))}.toml"
        path.write_text(config)
    return Pipeline(
        path,
        runs_dir=ws / "runs",
        cwd=ws,
        backends={"claude": ClaudeBackend(), "omp": OmpBackend()},
        **{"log": print, **options},
    )


def rows(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def show(report) -> None:
    for r in rows(report):
        print(
            f"  {r['key']}: {r['stop']} ok={r['ok']} agent={r['agent']} model={r['model']} credential={r['credential']} "
            f"rounds={r.get('rounds')} wall={r['wall_s']}s reason={r['reason'][:200]!r}"
        )


# --- skills_from -------------------------------------------------------------


class CodeWord(BaseModel):
    codeword: str


ROLE = """---
name: worker
description: Looks up the code word with a skill and writes it to the call's output.
tools: Read, Write, Edit, Grep, Glob, Skill
---

1. Read the call file the prompt names.
2. Find the code word: it is in your skill named `codeword` (it may be listed as `common:codeword`).
   Load that skill and read the code word from it. Do not guess it.
3. Write the output file the call names: `{"codeword": "<the code word>"}` (skill `write-output`).
4. Stop.
"""

SKILL = """---
name: codeword
description: The code word a task asks for.
---

The code word is PERIWINKLE-42.
"""


def skill_plugins(ws: Path) -> tuple[Path, Path]:
    own, common = ws / "plugins" / "own", ws / "plugins" / "common"
    if not own.exists():
        new_plugin(own)
        (own / "agents" / "worker.md").write_text(ROLE)
        (common / ".claude-plugin").mkdir(parents=True)
        (common / ".claude-plugin" / "plugin.json").write_text('{"name": "common"}\n')
        (common / "skills" / "codeword").mkdir(parents=True)
        (common / "skills" / "codeword" / "SKILL.md").write_text(SKILL)
    return own, common


@pytest.mark.parametrize("agent", AGENTS)
def test_skills_from_a_skill_plugin(ws, agent):
    own, common = skill_plugins(ws)
    lookup = agent_task(f"lookup_{agent}", plugin=own, skills_from=[common], output=CodeWord, max_turns=12, timeout_s=300, **route(agent))
    got = {}

    def flow():
        got["p"] = lookup("x")

    report = pipeline(ws).run(flow, run_id=f"skills-{agent}")
    show(report)
    assert report.ok, report.failed
    assert got["p"].output.codeword == "PERIWINKLE-42"


# --- changes, scopes, enrichers, row_extras -----------------------------------


class Written(BaseModel):
    topic: str


class Effect:
    def snapshot(self, task):
        return None

    def enrich(self, task, before, result):
        c = result.changes
        if result.ok and c is not None:
            result.payload = {"effect": "new" if c.created else "updated" if c.modified else "unchanged"}


STALL_ROLE = """---
name: worker
description: Creates a partial file, then waits.
tools: Read, Write, Bash
---

1. Create the file `topics/<unit>/partial.md` (the unit is in the call file the prompt names)
   with the single line `draft`.
2. Then run the shell command `sleep 600` and wait for it to finish. Do nothing else.
"""


def never(path, value) -> list[str]:
    """The attempt fails however it ends: a timeout, or its checks."""
    return ["this task never passes"]


def stall_plugin(ws: Path) -> Path:
    root = ws / "plugins" / "stall"
    if not root.exists():
        new_plugin(root)
        (root / "agents" / "worker.md").write_text(STALL_ROLE)
        settings = json.loads((root / "settings.json").read_text())
        settings["permissions"]["allow"].append("Bash(sleep:*)")
        (root / "settings.json").write_text(json.dumps(settings, indent=2))
    return root


@pytest.mark.parametrize("agent", AGENTS)
def test_changes_are_journaled_and_a_failed_attempt_leaves_none(ws, agent):
    entered: list[str] = []

    @contextmanager
    def scope(task):
        entered.append(f"enter {task.key}")
        yield
        entered.append(f"exit {task.key}")

    write = agent_task(
        f"write_{agent}",
        instructions="Create the file topics/${unit}/note.md with one sentence about ${subject}. "
        "Then write the output: the path of that file as `topic`.",
        output=Written,
        changes=["topics/{unit}/**"],
        max_turns=10,
        timeout_s=300,
        **route(agent),
    )
    stall = agent_task(
        f"stall_{agent}",
        plugin=stall_plugin(ws),
        output=Written,
        changes=["topics/{unit}/**"],
        validators=[never],
        max_turns=10,
        timeout_s=60,
        retries=1,
        **route(agent),
    )

    def flow():
        write(f"w-{agent}", subject="tea")
        stall(f"s-{agent}")

    report = pipeline(ws, scopes=[scope], enrichers=[Effect()], row_extras=lambda r: r.payload if isinstance(r.payload, dict) else {}).run(
        flow, run_id=f"changes-{agent}"
    )
    show(report)
    by_key = {r["key"]: r for r in rows(report)}
    w, s = by_key[f"write_{agent}-w-{agent}"], by_key[f"stall_{agent}-s-{agent}"]
    print(f"  write changes: {w['changes']}\n  stall changes: {s['changes']}\n  scope: {entered}")
    assert w["ok"] and any(p.endswith(f"topics/w-{agent}/note.md") for p in w["changes"]["created"])
    assert w.get("effect") == "new"
    assert (ws / "topics" / f"w-{agent}" / "note.md").exists()
    assert not s["ok"] and s["stop"] in ("timeout", "invalid_output")
    assert s["changes"]["created"], "the agent created no file: nothing to remove"
    assert any(p.endswith(f"topics/s-{agent}/partial.md") for p in s["changes"]["removed"]), s["changes"]
    assert not (ws / "topics" / f"s-{agent}" / "partial.md").exists()
    keys = [f"write_{agent}-w-{agent}", f"stall_{agent}-s-{agent}"]
    assert sorted(entered) == sorted(f"{e} {k}" for k in keys for e in ("enter", "exit"))


# --- claims -----------------------------------------------------------------


class Verdict(BaseModel):
    relevant: bool


def spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Each task's (start, end) as positions in the progress lines, which are in the order
    the queue started and ended the tasks."""
    order = [line.split(":")[0] for line in lines if line.startswith(("[start]", "[end]"))]
    keys = {o.split(" ", 1)[1] for o in order}
    return {k: (order.index(f"[start] {k}"), order.index(f"[end] {k}")) for k in keys}


def overlap(s: dict[str, tuple[int, int]], a: str, b: str) -> bool:
    (a0, a1), (b0, b1) = s[a], s[b]
    return a0 < b1 and b0 < a1


@pytest.mark.parametrize("agent", AGENTS)
def test_claims_keep_writes_to_one_topic_apart_and_leave_the_rest_parallel(ws, agent):
    rewrite = "Rewrite the file ${path} so that it ${rule}. Then write the output: that path as `topic`."
    style = agent_task(
        f"style_{agent}", instructions=rewrite, output=Written, claims=["topic:{unit}"], max_turns=10, timeout_s=300, **route(agent)
    )
    terms = agent_task(
        f"terms_{agent}", instructions=rewrite, output=Written, claims=["topic:{unit}"], max_turns=10, timeout_s=300, **route(agent)
    )
    merge = agent_task(
        f"merge_{agent}",
        instructions="Append the text of the files ${second} to the file ${first}. Then write the output: ${first} as `topic`.",
        output=Written,
        claims=["topic:{params.topics}"],
        max_turns=10,
        timeout_s=300,
        **route(agent),
    )
    triage = agent_task(
        f"triage_{agent}",
        instructions="Read the file ${path}. Is it about tea? Write the output.",
        output=Verdict,
        max_turns=6,
        timeout_s=300,
        **route(agent),
    )
    d = f"claims-{agent}"

    def flow():
        style("alpha", path=f"{d}/alpha.md", rule="uses short sentences")
        terms("alpha", path=f"{d}/alpha.md", rule="says 'green tea' for every tea")
        style("beta", path=f"{d}/beta.md", rule="uses short sentences")
        triage("alpha", path=f"{d}/alpha.md")
        merge("alpha", key=f"merge-{agent}", topics=["alpha", "beta"], first=f"{d}/alpha.md", second=f"{d}/beta.md")

    (ws / d).mkdir(exist_ok=True)
    for name in ("alpha", "beta"):
        (ws / d / f"{name}.md").write_text(f"Notes on {name}. It is about tea, which people drink.\n")
    lines: list[str] = []

    def log(line: str) -> None:
        print(line)
        lines.append(line)

    report = pipeline(ws, max_concurrent=5, log=log).run(flow, run_id=f"claims-{agent}")
    show(report)
    assert report.ok, report.failed
    s = spans(lines)
    print(f"  spans: {s}")
    alpha = [f"style_{agent}-alpha", f"terms_{agent}-alpha", f"merge-{agent}"]
    assert not any(overlap(s, a, b) for a in alpha for b in alpha if a < b)  # one topic: one write at a time
    assert not overlap(s, f"merge-{agent}", f"style_{agent}-beta")  # merge claims beta too
    assert any(overlap(s, f"triage_{agent}-alpha", w) for w in alpha)  # claims nothing: beside the writes
    assert overlap(s, f"style_{agent}-alpha", f"style_{agent}-beta") or overlap(s, f"terms_{agent}-alpha", f"style_{agent}-beta")
    plan = {p["key"]: p for p in map(json.loads, (report.run_dir / "plan.jsonl").read_text().splitlines())}
    assert plan[f"merge-{agent}"]["claims"] == ["topic:alpha", "topic:beta"]
    assert plan[f"triage_{agent}-alpha"]["claims"] == []


# --- output_from="message" ----------------------------------------------------


class Answer(BaseModel):
    lines: int
    word: str


def upper_word(path, value: Answer) -> list[str]:
    return [] if value.word.isupper() else [f"word: {value.word!r} must be written in upper case"]


@pytest.mark.parametrize("agent", AGENTS)
def test_output_from_the_final_message(ws, agent):
    ask = agent_task(
        f"ask_{agent}",
        instructions="Read the file data/${unit}.txt with your file reading tool. Count its lines and take its first word.",
        output=Answer,
        output_from="message",
        validators=[upper_word],
        max_turns=6,
        timeout_s=300,
        **route(agent),
    )
    (ws / "data").mkdir(exist_ok=True)
    (ws / "data" / f"fruit-{agent}.txt").write_text("apple pie\nbanana\ncherry\n")
    got = {}

    def flow():
        got["p"] = ask(f"fruit-{agent}")

    report = pipeline(ws).run(flow, run_id=f"message-{agent}")
    show(report)
    row = rows(report)[-1]
    out = got["p"].path.read_text()
    print(f"  output file: {out!r}\n  round errors: {row['round_errors']}")
    assert report.ok, report.failed
    assert got["p"].output == Answer(lines=3, word="APPLE")
    json.loads(out)  # only the document: no prose around it
    assert row["rounds"] >= 1


# --- the cost of fix-up rounds, and unwrap -------------------------------------------


def once(message: str):
    """A validator that refuses the first output it sees: the task takes one fix-up round."""
    seen: list[int] = []

    def refuse_once(path, value) -> list[str]:
        seen.append(1)
        return [message] if len(seen) == 1 else []

    return refuse_once


def result_costs(report, key: str) -> list[float]:
    """The cost each launch's result event reported (Claude Code's stream)."""
    path = report.run_dir / "streams" / f"{key}.stream.jsonl"
    out = []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result" and event.get("total_cost_usd") is not None:
            out.append(event["total_cost_usd"])
    return out


@pytest.mark.parametrize("agent", AGENTS)
def test_a_fix_up_round_is_charged_once(ws, agent):
    note = agent_task(
        f"note_{agent}",
        instructions="Write the output: one short sentence about ${unit} as `note`.",
        output=Note,
        validators=[once("note: write it again, in other words")],
        max_turns=6,
        timeout_s=300,
        **route(agent),
    )
    report = pipeline(ws).run(lambda: note("tea"), run_id=f"cost-{agent}")
    show(report)
    [row] = rows(report)
    [launch] = [json.loads(line) for line in (report.run_dir / "launches.jsonl").read_text().splitlines()]
    print(f"  cost {row['cost_usd']} rounds {row['rounds']} round costs {launch['round_costs']}")
    assert report.ok, report.failed
    assert row["rounds"] == 2 and len(launch["round_costs"]) == 2
    assert row["cost_usd"] == pytest.approx(sum(launch["round_costs"]), abs=1e-6)
    assert row["hops"][0]["cost_usd"] == pytest.approx(row["cost_usd"], abs=1e-6)
    if agent == "claude":
        reported = result_costs(report, f"note_{agent}-tea")
        print(f"  result events: {reported}")
        # the second round reports the session's cost so far: that is the attempt's cost
        assert reported[-1] > reported[0] and row["cost_usd"] == pytest.approx(reported[-1], abs=1e-6)


WRAP = (
    "Decide whether ${unit} is a fruit. Your final message must be exactly this: first the "
    "line `Here is the verdict.`, then the JSON document in a ```json fenced block, then the "
    "line `Done.`"
)


class Fruit(BaseModel):
    fruit: bool


@pytest.mark.parametrize("agent", AGENTS)
def test_unwrap_takes_a_wrapped_message_in_one_round(ws, agent):
    def judge(unwrap: bool):
        return agent_task(
            f"judge_{agent}_{'unwrap' if unwrap else 'strict'}",
            instructions=WRAP,
            output=Fruit,
            output_from="message",
            unwrap=unwrap,
            max_turns=4,
            timeout_s=300,
            **route(agent),
        )

    got = {}

    def flow():
        got["u"] = judge(True)("banana")
        got["s"] = judge(False)("banana")

    report = pipeline(ws).run(flow, run_id=f"unwrap-{agent}")
    show(report)
    by_kind = {r["kind"]: r for r in rows(report)}
    unwrapped, strict = by_kind[f"judge_{agent}_unwrap"], by_kind[f"judge_{agent}_strict"]
    message = got["u"].path.with_name(got["u"].path.name + ".message.txt").read_text()
    print(f"  message: {message!r}\n  strict round errors: {strict['round_errors']}")
    launched = {json.loads(line)["label"]: json.loads(line) for line in (report.run_dir / "launches.jsonl").read_text().splitlines()}
    # Whether the model wraps its message as told varies from run to run (the call protocol
    # asks for the document alone): each check below holds for what it did.
    wrapped = message.strip() != got["u"].path.read_text().strip()
    assert unwrapped["ok"] and unwrapped["rounds"] == 1 and got["u"].output == Fruit(fruit=True)
    assert launched[unwrapped["key"]]["unwrapped"] is wrapped
    assert strict["ok"]
    if strict["rounds"] > 1:
        assert "not valid JSON" in strict["round_errors"][0][0]  # the wrapped message went back
    if not wrapped and strict["rounds"] == 1:
        pytest.skip(f"{agent} wrote the document alone both times: nothing to unwrap in this run")


# --- quota caps and quota_rule ------------------------------------------------


class Note(BaseModel):
    note: str


QUOTA = """
[credentials.capped_{a}]
type = "subscription"
max_five_hour_pct = 0.01
max_seven_day_pct = 0.01

[credentials.ruled_{a}]
type = "subscription"

[tasks.q_capped]
credential = "capped_{a}"
[[tasks.q_capped.fallbacks]]
agent = "{fallback_agent}"
model = "{fallback_model}"
effort = "low"
credential = "ambient"

[tasks.q_ruled]
credential = "ruled_{a}"
[[tasks.q_ruled.fallbacks]]
agent = "{fallback_agent}"
model = "{fallback_model}"
effort = "low"
credential = "ambient"

[tasks.q_nohop]
credential = "capped_{a}"
"""


@pytest.mark.parametrize("agent", AGENTS)
def test_a_credential_past_its_quota_rests_and_its_tasks_fall_over(ws, agent):
    other = "omp" if agent == "claude" else "claude"
    config = QUOTA.format(a=agent, fallback_agent=ROUTES[other][0], fallback_model=ROUTES[other][1])
    say = "Write the output: one short sentence about ${unit} as `note`."
    kinds = {
        name: agent_task(name, instructions=say, output=Note, max_turns=6, timeout_s=300, **route(agent))
        for name in ("q_capped", "q_ruled", "q_nohop")
    }
    deferred = []

    def flow():
        yield kinds["q_capped"]("first")  # no reading yet: runs on the capped credential, which reports one
        yield kinds["q_ruled"]("first")
        yield kinds["q_capped"]("second")  # past its cap now: the fallback hop
        yield kinds["q_ruled"]("second")  # the rule rests it: the fallback hop
        try:
            yield kinds["q_nohop"]("third")  # no hop left: deferred
        except TaskDeferred as exc:
            deferred.append(str(exc))

    def rule(credential, reading):
        return "ruled by the test" if credential == f"ruled_{agent}" else None

    report = pipeline(ws, config, quota_rule=rule).run(flow, run_id=f"quota-{agent}")
    show(report)
    by_key = {r["key"]: r for r in rows(report)}
    first = by_key["q_capped-first"]
    print(f"  readings of the first task: {first['quota']}")
    if not any(q.get("five_hour_pct") is not None or q.get("seven_day_pct") is not None for q in first["quota"]):
        pytest.skip(f"{agent} reported no utilization reading for a subscription: nothing can rest on a cap")
    assert first["ok"] and first["agent"] == agent and first["credential"] == f"capped_{agent}"
    second = by_key["q_capped-second"]
    assert second["ok"] and second["agent"] == other and f"capped_{agent} rests" in second["reason"], second
    assert [h["route"] for h in second["hops"]] and len(second["hops"]) == 1  # the resting hop never launched
    ruled = by_key["q_ruled-second"]
    assert ruled["ok"] and ruled["agent"] == other and "ruled by the test" in ruled["reason"], ruled
    assert "q_nohop-third" not in by_key and deferred, deferred
    lines = [json.loads(line) for line in (report.run_dir / "deferred.jsonl").read_text().splitlines()]
    print(f"  deferred.jsonl: {lines}")
    assert any(d["key"] == "q_nohop-third" and f"capped_{agent} rests" in d["reason"] for d in lines)


# --- a light launch -------------------------------------------------------------


class Classified(BaseModel):
    category: str
    promo: bool


CLASSIFIER = """---
name: classifier
description: Classifies one news item.
tools: Read
---

You classify one news item: its category (`security`, `product` or `other`) and whether it
advertises a product or a service (`promo`).
"""

ITEM = "Acme patches a critical remote code execution flaw in its VPN appliance (CVE-2026-1234)."


def classifier_plugin(ws: Path) -> Path:
    root = ws / "plugins" / "classifier"
    if not root.exists():
        new_plugin(root)
        (root / "agents" / "worker.md").unlink()
        (root / "agents" / "classifier.md").write_text(CLASSIFIER)
    return root


@pytest.mark.parametrize("agent", AGENTS)
def test_a_light_launch_is_one_call_with_no_tools(ws, agent):
    plugin = classifier_plugin(ws)
    common = dict(plugin=plugin, output=Classified, output_from="message", max_turns=6, timeout_s=300, **route(agent))
    light = agent_task(f"classify_light_{agent}", tools=(), **common)
    full = agent_task(f"classify_full_{agent}", **common)  # the same judgement with the agent's tools

    def flow():
        light("item", title=ITEM)
        full("item", title=ITEM)

    report = pipeline(ws, max_concurrent=1).run(flow, run_id=f"light-{agent}")
    show(report)
    assert report.ok, report.failed
    by_key = {r["key"]: r for r in rows(report)}
    lit, heavy = by_key[f"classify_light_{agent}-item"], by_key[f"classify_full_{agent}-item"]
    launches = {r["label"]: r for r in map(json.loads, (report.run_dir / "launches.jsonl").read_text().splitlines())}
    argv = launches[f"classify_light_{agent}-item"]["argv"]
    print(f"  light: resident={lit['usage']['resident']} calls={lit['usage']['calls']} rounds={lit['rounds']}")
    print(f"  full:  resident={heavy['usage']['resident']} calls={heavy['usage']['calls']} rounds={heavy['rounds']}")
    print(f"  light argv: {argv}")
    assert lit["rounds"] == 1 and lit["usage"]["calls"] == 1  # one turn: no tool to call
    assert heavy["usage"]["calls"] >= 2  # with tools, the call file is read first
    # Less input on its one call than the same role with tools. On Claude Code the role already
    # replaces the default system prompt (`--agent`, `tools: Read`), so the gap is narrower there.
    assert lit["usage"]["resident"] < heavy["usage"]["resident"]
    assert any(a.startswith("--system-prompt=You classify one news item") for a in argv)
    assert "--plugin-dir" not in argv and "--agent" not in argv
    if agent == "claude":
        assert "--tools" in argv and "--strict-mcp-config" in argv and "--setting-sources" in argv
    else:
        assert "--no-tools" in argv and "--no-lsp" in argv


# --- a time box ---------------------------------------------------------------------


@pytest.mark.parametrize("agent", AGENTS)
def test_a_time_box_cuts_its_own_work_and_the_flow_goes_on_after_it(ws, agent):
    say = "Write the output: one short sentence about ${unit} as `note`."
    jot = agent_task(f"jot_{agent}", instructions=say, output=Note, max_turns=6, timeout_s=300, **route(agent))
    wrap = agent_task(f"wrap_{agent}", instructions=say, output=Note, max_turns=6, timeout_s=300, **route(agent))
    after = agent_task(f"after_{agent}", instructions=say, output=Note, max_turns=6, timeout_s=300, **route(agent))

    def work(topics):
        done = []
        for topic in topics:
            try:
                yield jot(topic)
            except TaskDeferred:
                break
            done.append(topic)
        yield wrap("all")  # a finishing kind: launches past the deadline, in the grace window
        return done

    def flow():
        box = time_box(work([f"t{i}" for i in range(6)]), deadline_s=12, grace_s=120, finishing_kinds=[f"wrap_{agent}"])
        done = yield box
        yield after("next")  # outside the box: its deadline does not hold here
        return done

    report = pipeline(ws).run(flow, run_id=f"time-box-{agent}")
    show(report)
    by_key = {r["key"]: r for r in rows(report)}
    deferred = [json.loads(line) for line in (report.run_dir / "deferred.jsonl").read_text().splitlines()]
    print(f"  done in the box: {report.value}\n  deferred.jsonl: {deferred}")
    assert report.value and len(report.value) < 6  # some writes ran, the rest were cut
    assert [d["cause"] for d in deferred] == [{"cause": "deadline", "flow_call": "0.1"}]
    assert by_key[f"wrap_{agent}-all"]["ok"] and by_key[f"after_{agent}-next"]["ok"]
    calls = [json.loads(line) for line in (report.run_dir / "flow_calls.jsonl").read_text().splitlines()]
    [boxed] = [c for c in calls if "time_box" in c]
    assert boxed["id"] == "0.1" and boxed["time_box"]["deadline_s"] == 12
