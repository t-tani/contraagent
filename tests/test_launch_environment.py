"""What a launch hands its agent, and a launch the operating system refuses to start.

The params reach an agent through its call file only: a param in the environment counts
toward the operating system's limit on one launch's arguments and environment, and a long
text there kept the task from launching at all. A command the operating system refuses
(`SpawnRefused`) fails the same way on every launch, so it is launched once per route."""

import errno
import json
import os
import sys

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent.backends import ClaudeBackend, OmpBackend
from contraagent.testing import StubAgent
from fake_cli import write_fake_cli

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="a fake coding agent is a #! script")


class Note(BaseModel):
    text: str


class Seen(BaseModel):
    text: str
    params_in_env: bool


echo = agent_task("echo", params=Note, output=Seen, instructions="Repeat the note.", max_turns=1, timeout_s=60)

#: Reads its call file and writes what it found there to its output file.
ECHO_CLAUDE = r"""
import json, os, pathlib, sys
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)"); sys.exit(0)
sys.stdin.read()
call = json.loads(pathlib.Path(os.environ["CONTRAAGENT_CALL"]).read_text(encoding="utf-8"))
out = pathlib.Path(call["cwd"]) / call["output"]["path"]
out.parent.mkdir(parents=True, exist_ok=True)
seen = {"text": call["params"]["text"], "params_in_env": any(k == "CONTRAAGENT_PARAMS" for k in os.environ)}
out.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"type": "system", "subtype": "init", "model": "fake-model", "tools": ["Write"], "session_id": "s-1"}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done", "session_id": "s-1",
                  "num_turns": 1, "total_cost_usd": 0.001, "usage": {"output_tokens": 2}}))
"""

#: Past what any operating system takes for one launch's arguments and environment.
TOO_LONG = "x" * 4_000_000


def backend(cls, tmp_path, name, **env):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, name, ECHO_CLAUDE)
    return cls(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path), **env})


def run(tmp_path, backends, config=None, note="a note"):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    pipeline = Pipeline(
        PipelineConfig(config or {}),
        runs_dir=tmp_path / "runs",
        backends=backends,
        cwd=work,
        preflight="off",
        retry_wait_s=0,
        log=lambda line: None,
    )
    handle = {}
    report = pipeline.run(lambda: handle.setdefault("echo", echo("u", Note(text=note))))
    return report, handle["echo"]


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def test_a_long_non_ascii_param_reaches_the_agent_in_its_call_file(tmp_path):
    # About 200 KB in UTF-8 and over 400 KB as JSON with \uXXXX escapes: more than
    # Linux takes for one variable of the environment (MAX_ARG_STRLEN, 131072 bytes).
    note = "長い本文の一行です。" * 6_700
    assert len(note.encode("utf-8")) > 200_000
    report, pending = run(tmp_path, {"claude": backend(ClaudeBackend, tmp_path, "claude")}, note=note)
    assert report.ok, report.failed
    assert [row["stop"] for row in journal(report)] == ["completed"]
    assert pending.output.text == note and not pending.output.params_in_env


def test_a_command_the_system_refuses_fails_over_once_and_is_not_retried(tmp_path):
    refused = backend(ClaudeBackend, tmp_path, "claude", TOO_LONG=TOO_LONG)
    stub = StubAgent({"echo": {"text": "from omp", "params_in_env": False}})
    config = {"tasks": {"echo": {"retries": 2, "fallbacks": [{"agent": "omp", "model": "anthropic/m2"}]}}}
    report, _ = run(tmp_path, {"claude": refused, **stub.backends(["omp"])}, config)
    assert report.ok, report.failed
    (row,) = journal(report)
    assert [hop["stop"] for hop in row["hops"]] == ["launch_failed", "completed"]
    assert "refuses to start this command, on every launch" in row["reason"]
    assert "Argument list too long" in row["reason"] or "E2BIG" in row["reason"]


def test_a_refused_command_on_every_route_is_launched_once_per_route(tmp_path):
    config = {"tasks": {"echo": {"retries": 2, "fallbacks": [{"agent": "omp", "model": "anthropic/m2"}]}}}
    backends = {
        "claude": backend(ClaudeBackend, tmp_path, "claude", TOO_LONG=TOO_LONG),
        "omp": backend(OmpBackend, tmp_path, "omp", TOO_LONG=TOO_LONG),
    }
    report, _ = run(tmp_path, backends, config)
    result = report.results["echo-u"]
    assert not result.ok and result.stop == "launch_failed" and not result.retryable
    (row,) = journal(report)  # one attempt: neither the kind's retries nor the queue's retry
    assert [hop["stop"] for hop in row["hops"]] == ["launch_failed", "launch_failed"]
    assert result.launch_result is not None and f"[Errno {errno.E2BIG}]" in result.launch_result.stderr_tail


def test_a_launch_failure_that_may_pass_is_still_retried(tmp_path, monkeypatch):
    """A missing executable (`ENOENT`) may be one that an upgrade is replacing."""
    import subprocess

    from contraagent._internal.backends import process

    real = subprocess.Popen
    calls = []

    def popen(argv, *args, **kwargs):
        if any(str(a).endswith("claude") for a in argv[:1]) and "--version" not in argv:
            calls.append(argv)
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", argv[0])
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(process.subprocess, "Popen", popen)
    report, _ = run(tmp_path, {"claude": backend(ClaudeBackend, tmp_path, "claude")}, {"tasks": {"echo": {"retries": 1}}})
    result = report.results["echo-u"]
    assert not result.ok and result.stop == "launch_failed" and result.retryable
    # Two attempts (the kind's one retry), then the queue's one retry of a launch that never ran: two more.
    assert [row["stop"] for row in journal(report)] == ["launch_failed"] * 4
    assert len(calls) == 4
