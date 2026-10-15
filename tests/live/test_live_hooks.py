"""A plugin's post_tool hook against real coding agents: it objects (exit 2) to a note written
without a title line, and the agent fixes the note in the same session. The hook script reads
the tool input in Claude Code's shape (`file_path`) on every agent.

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_hooks.py
    CONTRAAGENT_LIVE=1 CONTRAAGENT_LIVE_AGENTS=omp,pi uv run pytest -m live -s tests/live/test_live_hooks.py

    claude    claude-haiku-5-5                           ambient
    omp       anthropic/claude-haiku-5-5                 ambient
    pi        openai/gpt-5.6-luna                        a ChatGPT login (subscription, provider openai)
    opencode  CONTRAAGENT_LIVE_OPENCODE_MODEL (default: OpenCode Zen's free Muse model)
"""

import json
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

from pydantic import BaseModel  # noqa: E402

from contraagent import Pipeline, agent_task  # noqa: E402
from contraagent._internal.plugins import hooks  # noqa: E402
from contraagent.plugins import Plugin, new_plugin  # noqa: E402

OPENCODE_MODEL = os.environ.get("CONTRAAGENT_LIVE_OPENCODE_MODEL", "opencode/muse-spark-1.3-contributor-free")
ROUTES = {
    "claude": {"agent": "claude", "model": "claude-haiku-5-5", "effort": "low"},
    "omp": {"agent": "omp", "model": "anthropic/claude-haiku-5-5", "effort": "low"},
    "pi": {"agent": "pi", "model": "openai/gpt-5.6-luna", "effort": "low", "credential": "chatgpt"},
    "opencode": {"agent": "opencode", "model": OPENCODE_MODEL},
}
AGENTS = [a for a in os.environ.get("CONTRAAGENT_LIVE_AGENTS", ",".join(ROUTES)).split(",") if a in ROUTES]

CONFIG = """
[credentials.chatgpt]
type = "subscription"
provider = "openai"
"""

ROLE = """---
name: worker
description: Writes a one-sentence note, then the output its call file asks for.
tools: Read, Write, Edit, Bash
---

1. Read the call file the prompt names. `params.topic` is the topic.
2. Write the file `notes/<unit>.md` (the unit is in the call file): one sentence about the topic and nothing else.
3. A hook may answer a write with what is wrong with the file. Fix the file as it says.
4. Write the output file exactly as the call's `output` describes: `{"note": "notes/<unit>.md"}` (skill `write-output`).
5. Stop.
"""

# Objects to a note whose first line is not a `# ` title, once per write; logs what it read.
HOOK = """#!/usr/bin/env bash
input=$(cat)
echo "$input" >> "$CLAUDE_PLUGIN_ROOT/seen.jsonl"
path=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tool_input"].get("file_path",""))')
case "$path" in */notes/*) ;; *) exit 0 ;; esac
head -n1 "$path" | grep -q '^# ' && exit 0
echo "$path" >> "$CLAUDE_PLUGIN_ROOT/objected.txt"
echo "$path: the first line must be a '# ' title line naming the topic; add one at the top" >&2
exit 2
"""


class Written(BaseModel):
    note: str


LIVE_DIR = Path(os.environ.get("CONTRAAGENT_LIVE_DIR") or Path(__file__).resolve().parents[2] / "live-demo") / "hooks"


@pytest.fixture(scope="module")
def ws():
    if LIVE_DIR.exists():
        shutil.rmtree(LIVE_DIR)
    LIVE_DIR.mkdir(parents=True)
    (LIVE_DIR / ".gitignore").write_text("*\n!.gitignore\n")
    plugin = LIVE_DIR / "plugins" / "noter"
    new_plugin(plugin)
    (plugin / "agents" / "worker.md").write_text(ROLE)
    script = plugin / "hooks" / "title.sh"
    script.write_text(HOOK)
    script.chmod(0o755)
    toml = (plugin / "hooks.toml").read_text()
    for tool in ("write", "edit"):
        toml += f'\n[[hooks]]\non = "post_tool"\ntool = "{tool}"\nscript = "hooks/title.sh"\n'
    (plugin / "hooks.toml").write_text(toml)
    hooks.write(Plugin.load(plugin))
    (LIVE_DIR / "pipeline.toml").write_text(CONFIG)
    return LIVE_DIR


@pytest.mark.parametrize("agent", list(ROUTES))
def test_a_post_tool_hook_s_objection_is_fixed_in_the_same_session(ws, agent):
    if agent not in AGENTS:
        pytest.skip(f"{agent} is not in CONTRAAGENT_LIVE_AGENTS")
    plugin = ws / "plugins" / "noter"
    seen = plugin / "seen.jsonl"
    objected = plugin / "objected.txt"
    seen.unlink(missing_ok=True)
    objected.unlink(missing_ok=True)
    note = agent_task(f"note_{agent}", plugin=plugin, output=Written, max_turns=16, timeout_s=300, **ROUTES[agent])

    def flow():
        note(f"n-{agent}", topic="green tea")

    report = Pipeline(ws / "pipeline.toml", runs_dir=ws / "runs", cwd=ws, log=print).run(flow, run_id=f"hooks-{agent}")
    [row] = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    calls = [json.loads(line) for line in seen.read_text().splitlines()] if seen.exists() else []
    text = (ws / "notes" / f"n-{agent}.md").read_text() if (ws / "notes" / f"n-{agent}.md").exists() else ""
    first = text.splitlines()[:1]
    print(f"\n  {agent}: {row['stop']} ok={row['ok']} rounds={row.get('rounds')} hook calls={len(calls)} first line={first}")
    print(f"  tool inputs the hook read: {[sorted(c['tool_input']) for c in calls]}")
    assert report.ok, report.failed
    assert calls and all("file_path" in c["tool_input"] for c in calls)  # Claude Code's shape on every agent
    assert objected.exists(), "the first note had a title line: the hook never objected"
    assert text.startswith("# "), text  # the agent took the hook's words and fixed the note
    assert row["rounds"] == 1  # in the same session, not a correction round
