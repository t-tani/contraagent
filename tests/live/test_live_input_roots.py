"""An input root against real coding agents: Claude Code on Haiku and opencode
(CONTRAAGENT_LIVE_OPENCODE_MODEL, default GPT-5.6 Luna through an OpenAI login) each read a
file of an input root outside their working directory, a git repository of its own, and put
a word from it into their output (Claude Code's `--add-dir`, opencode's `external_directory`
rule). It spends tokens, so, as `test_live_agents.py`, it needs the `live` marker and
CONTRAAGENT_LIVE=1:

    CONTRAAGENT_LIVE=1 uv run pytest -m live -s tests/live/test_live_input_roots.py
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

from contraagent import InputFile, Pipeline, PipelineConfig, agent_task  # noqa: E402
from contraagent.backends import ClaudeBackend, OpencodeBackend  # noqa: E402

#: The model opencode runs on: any `provider/model` its logins reach.
OPENCODE_MODEL = os.environ.get("CONTRAAGENT_LIVE_OPENCODE_MODEL", "openai/gpt-5.6-luna")
ROUTES = {"claude": "claude-haiku-5-5", "opencode": OPENCODE_MODEL}


class Note(BaseModel):
    note: InputFile = Field(description="a note; its first line is one word")


class Found(BaseModel):
    word: str = Field(description="the word on the first line of the note")


@pytest.mark.parametrize("agent", list(ROUTES))
def test_an_agent_reads_a_file_of_an_input_root_outside_its_working_directory(tmp_path, agent):
    corpus = tmp_path / "corpus"
    (corpus / "2026").mkdir(parents=True)
    (corpus / "2026" / "note.txt").write_text("heron\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)  # opencode matches its paths from the repository
    find = agent_task(f"read_{agent}", params=Note, instructions="Read the note.", output=Found, max_turns=8, timeout_s=300)
    config = PipelineConfig({"tasks": {find.kind: {"agent": agent, "model": ROUTES[agent], "effort": "low", "retries": 0}}})
    report = Pipeline(
        config,
        runs_dir=tmp_path / "runs",
        cwd=repo,
        input_roots={"data": corpus},
        backends={"claude": ClaudeBackend(), "opencode": OpencodeBackend()},
        log=print,
    ).run(lambda: find("a", Note(note=InputFile("2026/note.txt", root="data"))))
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    print(f"  {agent}: {[(r['stop'], r['rounds'], r['reason'][:200]) for r in rows]}")
    assert report.ok, report.failed
    assert json.loads((report.run_dir / "out" / find.kind / "a.json").read_text())["word"] == "heron"
