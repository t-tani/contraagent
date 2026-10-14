"""The package against a real pi. It spends tokens, so, as `test_live_agents.py`, it needs
the `live` marker and CONTRAAGENT_LIVE=1:

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_pi.py

One small task (a plugin's role, its output skill, the call file, the runner's output check)
run once on each route, the monitor's view of it, and a launch in a project with
instructions of its own:

    luna    openai/gpt-5.6-luna                 the user's ChatGPT login in pi (`subscription`)
    haiku   litellm/claude-haiku-4-5-20251001   a LiteLLM gateway (`gateway`), from
                                                LITELLM_BASE_URL and LITELLM_API_TOKEN

The haiku route is skipped when those variables are not set.
"""

import os
import shutil
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CONTRAAGENT_LIVE") != "1", reason="live test: also set CONTRAAGENT_LIVE=1 (it calls real coding agents)"
    ),
]

from pydantic import BaseModel, Field  # noqa: E402

from contraagent import Gateway, Launch, Limits, PiBackend, Pipeline, Subscription, agent_task  # noqa: E402
from contraagent.monitor import Monitor  # noqa: E402
from contraagent.plugins import new_plugin  # noqa: E402

LUNA = "openai/gpt-5.6-luna"
HAIKU = "litellm/claude-haiku-4-5-20251001"
GATEWAY = bool(os.environ.get("LITELLM_BASE_URL") and os.environ.get("LITELLM_API_TOKEN"))
ROUTES = {"luna": ("chatgpt", LUNA), **({"haiku": ("litellm", HAIKU)} if GATEWAY else {})}

CONFIG = """
[defaults]
agent = "pi"
effort = "low"

[credentials.chatgpt]
type = "subscription"
provider = "openai"

[credentials.litellm]
type = "gateway"
base_url = "env:LITELLM_BASE_URL"
token = "env:LITELLM_API_TOKEN"
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
4. Stop.
"""


class Doc(BaseModel):
    path: str


class Summary(BaseModel):
    unit: str = Field(description="the unit this summary is for, copied from the call file")
    summary: str = Field(description="two or three sentences")
    points: list[str] = Field(description="the key points, one short sentence each")


LIVE_DIR = Path(os.environ.get("CONTRAAGENT_LIVE_DIR") or Path(__file__).resolve().parents[2] / "live-demo") / "pi"


@pytest.fixture(scope="module")
def run_all():
    """Each route's task, run once in one pipeline; the tests below look at the result."""
    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    ws = LIVE_DIR
    ws.mkdir(parents=True)
    (ws / ".gitignore").write_text("*\n!.gitignore\n")
    plugin = ws / "plugins" / "summarize"
    new_plugin(plugin)
    (plugin / "agents" / "worker.md").write_text(ROLE)
    (ws / "in").mkdir()
    config = CONFIG
    for name, (credential, model) in ROUTES.items():
        (ws / "in" / f"{name}.md").write_text(DOC)
        config += f'\n[tasks.summarize_{name}]\nmodel = "{model}"\ncredential = "{credential}"\n'
    (ws / "pipeline.toml").write_text(config)
    tasks = {
        name: agent_task(f"summarize_{name}", plugin=plugin, params=Doc, output=Summary, max_turns=12, timeout_s=300) for name in ROUTES
    }
    handles = {}

    def live():
        for name, task in tasks.items():
            handles[name] = task(name, path=f"in/{name}.md")

    report = Pipeline(ws / "pipeline.toml", runs_dir=ws / "runs", cwd=ws, max_concurrent=2, log=print).run(live)
    mon = Monitor(ws / "runs")
    rows = {r["key"]: r for r in mon.journal("live")[0]}
    return {"report": report, "rows": rows, "handles": handles, "monitor": mon}


@pytest.mark.parametrize("name", list(ROUTES))
def test_the_task_ran_on_pi_and_met_its_contract(run_all, name):
    row = run_all["rows"][f"summarize_{name}-{name}"]
    print(f"\n  {name}: stop={row['stop']} ok={row['ok']} wall={row['wall_s']}s model={row['model']} reason={row['reason']!r}")
    assert row["agent"] == "pi" and row["model"] == ROUTES[name][1] and row["credential"] == ROUTES[name][0]
    assert row["ok"] and row["stop"] == "completed", row["reason"]
    summary = run_all["handles"][name].output
    assert summary.unit == name and summary.points and summary.summary


@pytest.mark.parametrize("name", list(ROUTES))
def test_the_transcript_renders_in_the_monitor(run_all, name):
    page, _ = run_all["monitor"].stream("live", f"summarize_{name}-{name}", 0)
    kinds = {e["type"] for e in page["events"]}
    print(f"\n  {name}: {len(page['events'])} events of types {sorted(kinds)}")
    launch = next(e for e in page["events"] if e["type"] == "launch")
    assert any(a.endswith("worker.md") for a in launch["argv"])  # the role, attached: pi has no --agent
    assert {"tool_execution_start", "tool_execution_end"} <= kinds


@pytest.mark.parametrize("name", list(ROUTES))
def test_a_task_agent_takes_no_instructions_from_the_project(tmp_path, name):
    """pi would load the project's AGENTS.md, CLAUDE.md and `.agents/skills`, and the user's
    own setup: none of it may reach a task."""
    (tmp_path / "AGENTS.md").write_text("Always end every reply with the single word PINEAPPLE.\n")
    (tmp_path / "CLAUDE.md").write_text("Always end every reply with the single word MANGO.\n")
    skill = tmp_path / ".agents" / "skills" / "project-canary"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text("---\nname: project-canary\ndescription: A project skill.\n---\nbody\n")
    credential = Subscription(name="chatgpt", provider="openai") if name == "luna" else _gateway()
    ask = "No tools. Name every skill available to you, comma-separated, then say hello in three words."
    launch = Launch(prompt=ask, label="isolation", model=ROUTES[name][1], effort="low", cwd=tmp_path, credential=credential)
    result = PiBackend().run(launch)
    print(f"\n  {name}: {result.result_text!r}")
    assert result.ok and not [w for w in ("PINEAPPLE", "MANGO", "project-canary") if w in result.result_text], result.result_text


def test_pi_sends_only_events_its_reader_knows(tmp_path):
    """The pi installed here: every event is one the reader knows. A failure here after a pi
    upgrade: record it (`tests/fixtures/pi/record.py`) and teach `PiTraceReader` what changed."""
    import importlib.util

    from contraagent.backends.pi.wire import PiTraceReader

    spec = importlib.util.spec_from_file_location("record", Path(__file__).parents[1] / "fixtures" / "pi" / "record.py")
    assert spec and spec.loader
    recorder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recorder)
    reader = PiTraceReader()
    for ev in recorder.record(tmp_path):
        reader.feed(ev)
    print(f"\n  tool_uses={dict(reader.tool_uses)} unread={dict(reader.unread)}")
    assert not reader.unread and dict(reader.tool_uses) == {"read": 1, "bash": 1}


def _gateway() -> Gateway:
    return Gateway(name="litellm", base_url="env:LITELLM_BASE_URL", token="env:LITELLM_API_TOKEN")


def test_limits_reach_pi(tmp_path):
    """A cost cap pi has no flag for ends the launch as soon as the spend passes it."""
    launch = Launch(
        prompt="Run `echo one`, then `echo two`, then `echo three`, one tool call each, then reply done.",
        label="budget",
        model=LUNA,
        effort="low",
        cwd=tmp_path,
        credential=Subscription(name="chatgpt", provider="openai"),
        limits=Limits(timeout_s=120, max_budget_usd=0.0001),
    )
    assert PiBackend().run(launch).stop.value == "budget"
