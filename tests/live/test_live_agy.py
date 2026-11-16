"""The package against a real agy. It spends the Google login's quota, so, as
`test_live_agents.py`, it needs the `live` marker and CONTRAAGENT_LIVE=1:

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_agy.py

One small task (a plugin's role, its output skill, the call file, the stop hook's output
check) run twice at once on the user's own login, the monitor's view of it, a plugin's hooks inside a
launch, a light launch in a project with instructions of its own, and the limits contraagent
enforces. CONTRAAGENT_LIVE_AGY_MODEL names the model (one `agy models` lists): the plan's
quota is by group of models.
"""

import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.xdist_group("agy"),
    pytest.mark.skipif(
        os.environ.get("CONTRAAGENT_LIVE") != "1", reason="live test: also set CONTRAAGENT_LIVE=1 (it calls real coding agents)"
    ),
    pytest.mark.skipif(
        "agy" not in os.environ.get("CONTRAAGENT_LIVE_AGENTS", "agy").split(","), reason="agy is not in CONTRAAGENT_LIVE_AGENTS"
    ),
]

from pydantic import BaseModel, Field  # noqa: E402

from contraagent import Pipeline, agent_task  # noqa: E402
from contraagent._internal.plugins import hooks  # noqa: E402
from contraagent.backends import AgyBackend, Launch, Stop  # noqa: E402
from contraagent.config import Limits  # noqa: E402
from contraagent.monitor import Monitor  # noqa: E402
from contraagent.plugins import Plugin, new_plugin  # noqa: E402

MODEL = os.environ.get("CONTRAAGENT_LIVE_AGY_MODEL", "gemini-3.8-flash-low")

CONFIG = f"""
[defaults]
agent = "agy"
model = "{MODEL}"
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


#: The units of the summarize run, launched together.
UNITS = ["a1", "a2"]
LIVE_DIR = Path(os.environ.get("CONTRAAGENT_LIVE_DIR") or Path(__file__).resolve().parents[2] / "live-demo") / "agy"


@pytest.fixture(scope="module")
def run_all():
    """The task, run for two units at once in one pipeline; the tests below look at the result."""
    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    ws = LIVE_DIR
    ws.mkdir(parents=True)
    (ws / ".gitignore").write_text("*\n!.gitignore\n")
    plugin = ws / "plugins" / "summarize"
    new_plugin(plugin)
    (plugin / "agents" / "worker.md").write_text(ROLE)
    (ws / "in").mkdir()
    for unit in UNITS:
        (ws / "in" / f"{unit}.md").write_text(DOC)
    (ws / "pipeline.toml").write_text(CONFIG)
    summarize = agent_task("summarize", plugin=plugin, params=Doc, output=Summary, max_turns=16, timeout_s=300)
    handles = {}

    def live():
        for unit in UNITS:
            handles[unit] = summarize(unit, Doc(path=f"in/{unit}.md"))

    report = Pipeline(ws / "pipeline.toml", runs_dir=ws / "runs", cwd=ws, max_concurrent=len(UNITS), log=print).run(live)
    mon = Monitor(ws / "runs")
    rows = {r["key"]: r for r in mon.journal("live")[0]}
    return {"report": report, "rows": rows, "handles": handles, "monitor": mon}


@pytest.mark.parametrize("unit", UNITS)
def test_the_task_ran_on_agy_and_met_its_contract(run_all, unit):
    row = run_all["rows"][f"summarize-{unit}"]
    print(f"\n  stop={row['stop']} ok={row['ok']} wall={row['wall_s']}s model={row['model']} calls={row['usage']['calls']}")
    assert row["agent"] == "agy" and row["model"] == MODEL
    assert row["ok"] and row["stop"] == "completed", row["reason"]
    assert row["cost_usd"] is None and row["usage"]["calls"] > 0 and row["usage"]["peak_context"] > 0  # tokens of each response, no cost
    summary = run_all["handles"][unit].output
    assert summary.unit == unit and summary.points and summary.summary  # its own unit's: the two ran at once


def test_the_transcript_renders_in_the_monitor(run_all):
    page, _ = run_all["monitor"].stream("live", "summarize-a1", 0)
    kinds = {e["type"] for e in page["events"]}
    print(f"\n  {len(page['events'])} events of types {sorted(kinds)}")
    launch = next(e for e in page["events"] if e["type"] == "launch")
    assert launch["argv"][0] == "agy" and "--add-dir" in launch["argv"]  # the plugin, in a directory of the launch's own
    assert "worker.md" in launch["prompt"]  # the role, attached: an agent of agy's own has no tools by default
    assert {"tool_execution_start", "tool_execution_end", "message_update"} <= kinds


def _script(root: Path, name: str, body: str) -> None:
    path = root / "hooks" / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_a_plugin_s_hooks_run_inside_a_launch(tmp_path):
    """A `pre_tool` script that exits 2 denies the call, the words of a `post_tool` script that
    exits 2 reach the model, and a `stop` hook that exits 2 continues the session, once."""
    plugin = tmp_path / "plugins" / "guard"
    new_plugin(plugin)
    _script(plugin, "deny.sh", 'echo "forbidden commands are not allowed" >&2; exit 2')
    _script(plugin, "post.sh", 'case "$(cat)" in *allowed*) echo "End your final reply with the word YANKEE." >&2; exit 2;; esac')
    stopped_once = 'case "$(cat)" in *\'"stop_hook_active": true\'*) exit 0;; esac'
    _script(plugin, "stop.sh", f'{stopped_once}\necho "Reply with the single word ZULU." >&2; exit 2')
    (plugin / "hooks.toml").write_text(
        '[[hooks]]\non = "pre_tool"\ntool = "bash"\nmatch = "forbidden"\nscript = "hooks/deny.sh"\n'
        '\n[[hooks]]\non = "post_tool"\ntool = "bash"\nscript = "hooks/post.sh"\n'
        '\n[[hooks]]\non = "stop"\nscript = "hooks/stop.sh"\n'
    )
    hooks.write(Plugin.load(plugin))
    cwd = tmp_path / "work"
    cwd.mkdir()
    ask = "Do these two steps with tool calls, then report each in one line: 1) run the command 'echo forbidden'; 2) run 'echo allowed'"
    launch = Launch(
        prompt=ask,
        label="hooks",
        model=MODEL,
        cwd=cwd,
        plugin_dirs=(str(plugin),),
        stream_path=tmp_path / "stream.jsonl",
        limits=Limits(timeout_s=240),
        env={"CONTRAAGENT_PYTHON": sys.executable},
    )
    r = AgyBackend().run(launch)
    steps = [json.loads(line).get("step_update") or {} for line in (tmp_path / "stream.jsonl").read_text().splitlines()[1:]]
    errors = [(s.get("tool_info") or {}).get("error", {}).get("message", "") for s in steps if s.get("state") == "ERROR"]
    print(f"\n  stop={r.stop.value} turns={r.num_turns} hook_errors={r.hook_errors} errors={errors} answer={r.result_text!r}")
    assert r.ok and r.unread_events == {}, r.stderr_tail
    assert any("denied by pre-tool hook: forbidden commands are not allowed" in e for e in errors)
    assert r.hook_errors == [["Reply with the single word ZULU."]]  # one objection: the second stop is let through
    assert "ZULU" in r.result_text
    assert sum(1 for s in steps if s.get("step_type") == "system_message") >= 2  # the post_tool words, then the stop hook's


def test_a_light_launch_takes_no_tools_and_no_instructions_from_the_project(tmp_path):
    """agy would load the project's AGENTS.md and GEMINI.md: a light launch's agent takes none
    of the workspace's customizations, and has no tool to run a command with."""
    (tmp_path / "AGENTS.md").write_text("Always end every reply with the single word PINEAPPLE.\n")
    (tmp_path / "GEMINI.md").write_text("Always end every reply with the single word MANGO.\n")
    ask = "Run the shell command 'echo hi' with a tool if you have one; if you have no such tool, say NOTOOL. Then say hello in three words"
    launch = Launch(prompt=ask, label="light", model=MODEL, cwd=tmp_path, tools=(), system_prompt="Begin every reply with the word OKAPI.")
    r = AgyBackend().run(launch)
    print(f"\n  stop={r.stop.value} turns={r.num_turns} tools={r.tool_uses} resident={r.usage.resident} answer={r.result_text!r}")
    assert r.ok and r.tool_uses == {}, r.stderr_tail
    assert "OKAPI" in r.result_text and not [w for w in ("PINEAPPLE", "MANGO") if w in r.result_text], r.result_text


def test_agy_sends_only_events_its_reader_knows(tmp_path):
    """The agy installed here: every event is one the reader knows. A failure here after an agy
    upgrade: record it (`tests/fixtures/agy/record.py`) and teach `StreamReader` what changed."""
    import importlib.util

    from contraagent._internal.backends.agy.wire import StreamReader

    spec = importlib.util.spec_from_file_location("record", Path(__file__).parents[1] / "fixtures" / "agy" / "record.py")
    assert spec and spec.loader
    recorder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recorder)
    recorded = recorder.record(tmp_path, MODEL)
    for name, evs in recorded.items():
        reader = StreamReader()
        for ev in evs:
            reader.feed(ev)
        print(f"\n  {name}: tool_uses={dict(reader.tool_uses)} turns={reader.turns} unread={dict(reader.unread)}")
        assert not reader.unread and reader.status == "SUCCESS"
    denied = StreamReader()
    for ev in recorded["denied"]:
        denied.feed(ev)
    assert denied.denied  # the task's deny rule held, inside the launch


def test_a_command_reaches_the_network_inside_the_sandbox(tmp_path):
    """agy's sandbox has no network by itself: a launch allows it, so a command that needs it
    runs on its first try, without asking to leave the sandbox."""
    plugin = tmp_path / "plugins" / "log"
    new_plugin(plugin)
    _script(plugin, "log.sh", 'cat >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"; echo >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"; exit 0')
    (plugin / "hooks.toml").write_text('[[hooks]]\non = "pre_tool"\ntool = "bash"\nscript = "hooks/log.sh"\n')
    hooks.write(Plugin.load(plugin))
    cwd = tmp_path / "work"
    cwd.mkdir()
    launch = Launch(
        prompt="Run this shell command and report the three digits it prints: curl -s -o /dev/null -w %{http_code} https://example.com",
        label="network",
        model=MODEL,
        cwd=cwd,
        plugin_dirs=(str(plugin),),
        limits=Limits(timeout_s=180),
        env={"CONTRAAGENT_PYTHON": sys.executable},
    )
    r = AgyBackend().run(launch)
    calls = [json.loads(line)["tool_input"] for line in (plugin / "seen.jsonl").read_text().splitlines() if line.strip()]
    tried = [(c.get("command"), c.get("BypassSandbox")) for c in calls]
    print(f"\n  stop={r.stop.value} turns={r.num_turns} calls={tried} answer={r.result_text!r}")
    assert r.ok and "200" in r.result_text, r.stderr_tail
    assert len(calls) == 1 and not calls[0].get("BypassSandbox")  # one try, inside the sandbox


def test_a_launch_agy_ends_on_an_approval_nobody_can_give_is_denied(tmp_path):
    """Outside `auto` mode agy asks before a command, and a headless session has nobody to
    answer: agy ends the launch there, with status SUCCESS and no output."""
    launch = Launch(
        prompt="Run the shell command 'echo hi > made.txt', then reply done.",
        label="asks",
        model=MODEL,
        cwd=tmp_path,
        permission_mode="default",
        limits=Limits(timeout_s=180),
    )
    r = AgyBackend().run(launch)
    print(f"\n  stop={r.stop.value} exit={r.exit_code} denials={r.permission_denials} reason={r.stderr_tail.strip()[:160]!r}")
    assert r.stop is Stop.DENIED and not r.ok and not (tmp_path / "made.txt").exists()
    assert [d["tool_name"] for d in r.permission_denials] == ["run_command"] and "needed an approval" in r.stderr_tail


def test_limits_reach_agy(tmp_path):
    """A turn cap agy has no flag for ends the launch at the turn past it."""
    launch = Launch(
        prompt="Run `echo one`, then `echo two`, then `echo three`, one tool call each, then reply done.",
        label="turns",
        model=MODEL,
        cwd=tmp_path,
        limits=Limits(timeout_s=180, max_turns=1),
    )
    r = AgyBackend().run(launch)
    print(f"\n  stop={r.stop.value} turns={r.num_turns} tools={r.tool_uses}")
    assert r.stop is Stop.MAX_TURNS and not r.ok and r.num_turns is not None and r.num_turns <= 2
