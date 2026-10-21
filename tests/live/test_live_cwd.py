"""A task's own working directory against real coding agents: Claude Code on Haiku and
opencode (CONTRAAGENT_LIVE_OPENCODE_MODEL, default GPT-5.6 Luna through an OpenAI login)
each work in a directory the task call names, a git repository of its own, and write
their output file into the run's `out/`, outside that directory (`Launch.out_dir`). It
spends tokens, so, as `test_live_agents.py`, it needs the `live` marker and
CONTRAAGENT_LIVE=1:

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_cwd.py
"""

import json
import os
import subprocess

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CONTRAAGENT_LIVE") != "1", reason="live test: also set CONTRAAGENT_LIVE=1 (it calls real coding agents)"
    ),
]

from pydantic import BaseModel, Field  # noqa: E402

from contraagent import Pipeline, PipelineConfig, agent_task  # noqa: E402
from contraagent.backends import ClaudeBackend, OpencodeBackend  # noqa: E402

#: The model opencode runs on: any `provider/model` its logins reach.
OPENCODE_MODEL = os.environ.get("CONTRAAGENT_LIVE_OPENCODE_MODEL", "openai/gpt-5.6-luna")
ROUTES = {"claude": "claude-haiku-5-5", "opencode": OPENCODE_MODEL}


class Found(BaseModel):
    word: str = Field(description="the word in word.txt")


@pytest.mark.parametrize("agent", list(ROUTES))
def test_an_agent_in_a_directory_of_its_own_writes_its_output_into_out(tmp_path, agent):
    tree = tmp_path / "trees" / "a"
    tree.mkdir(parents=True)
    (tree / "word.txt").write_text("pelican\n")
    subprocess.run(["git", "init", "-q"], cwd=tree, check=True)  # a repository of its own, as a git worktree is
    (tmp_path / "repo").mkdir()
    find = agent_task(f"find_{agent}", instructions="Read word.txt in your working directory.", output=Found, max_turns=8, timeout_s=300)
    config = PipelineConfig({"tasks": {find.kind: {"agent": agent, "model": ROUTES[agent], "effort": "low", "retries": 0}}})
    report = Pipeline(
        config,
        runs_dir=tmp_path / "runs",  # outside both working directories
        cwd=tmp_path / "repo",
        backends={"claude": ClaudeBackend(), "opencode": OpencodeBackend()},
        log=print,
    ).run(lambda: find.options(cwd=tree)("a"))
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    print(f"  {agent}: {[(r['stop'], r['rounds'], r['reason'][:200]) for r in rows]}")
    assert report.ok, report.failed
    assert json.loads((report.run_dir / "out" / find.kind / "a.json").read_text())["word"] == "pelican"
