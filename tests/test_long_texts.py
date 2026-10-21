"""A long text of a task reaches each coding agent through a file or stdin, never its
command line or its environment.

Linux takes at most 131072 bytes for one argument or one variable of the environment
(`MAX_ARG_STRLEN`), and a launch past it is never started (`E2BIG`). A light launch's
system prompt holds its instructions with the params filled in, and a `preamble` param
goes into the launch's prompt, so either can be as long as a param. Each agent here is a
fake one, a real process that records what it was given."""

import json
import os
import stat
import sys

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.backends.process import command_line_size, via_stdin
from contraagent.backends import ClaudeBackend, CodexBackend, Launch, OmpBackend, OmpRpcBackend, OpencodeBackend, PiBackend
from contraagent.config import Limits
from fake_cli import write_fake_cli

#: About 300 KB in UTF-8: more than twice what Linux takes for one argument.
LONG = "長い本文の一行です。" * 10_000
#: Another one, to tell the two texts of one launch apart.
OTHER = "前置きの文です。" * 12_500
#: Linux's limit on one argument or one variable (`MAX_ARG_STRLEN`).
ARG_LIMIT = 131_072

#: Records its arguments, its environment, its stdin and the text of each file an argument
#: names (`--flag=<file>`, `<file>`, codex's `key="<file>"`, opencode's `{file:<file>}` and the
#: paths in its config).
RECORDER = r"""
import json, os, re, sys
if "--version" in sys.argv:
    print("0.0.1"); sys.exit(0)

def text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None

def files_of(values):
    found = {}
    for value in values:
        for cand in (value, value.partition("=")[2], value.partition("=")[2].strip('"')):
            if cand and os.path.isfile(cand):
                found[cand] = text(cand)
        for ref in [*re.findall(r"\{file:([^}]+)\}", value), *re.findall(r'"(/[^"]+)"', value)]:
            if os.path.isfile(ref):
                found[ref] = text(ref)
    return found

def dump(stdin, more=()):
    record = {"argv": sys.argv, "env": dict(os.environ), "stdin": stdin,
              "files": files_of([*sys.argv[1:], *os.environ.values(), *more])}
    with open(os.environ["FAKE_DUMP"], "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)

if "rpc" in sys.argv:
    print(json.dumps({"type": "ready", "supportedProtocolVersions": [1]}), flush=True)
    for line in sys.stdin:
        req = json.loads(line)
        if req["type"] == "prompt":
            dump(req["message"])
            print(json.dumps({"type": "agent_end", "isTerminal": True}), flush=True)
        elif req["type"] == "get_state":
            print(json.dumps({"type": "response", "id": req["id"], "success": True, "data": {}}), flush=True)
else:
    dump(sys.stdin.read())
"""


@pytest.fixture
def agent(tmp_path):
    """`agent(cls, **launch)`: what the fake agent `cls` runs as recorded for a launch, with the
    `LaunchResult`."""
    bindir = tmp_path / "bin"
    work = tmp_path / "work"
    work.mkdir()
    dump = tmp_path / "dump.json"
    base = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path / "home"), "XDG_CACHE_HOME": str(tmp_path / "cache")}

    def run(cls, **kw):
        write_fake_cli(bindir, cls.binary, RECORDER)
        backend = cls(base_env=base, agent_dirs=tmp_path / "pi") if cls is PiBackend else cls(base_env=base)
        launch = Launch(**{"prompt": "p", "label": "t", "model": "p/m", "cwd": work, "limits": Limits(timeout_s=30), **kw})
        dump.unlink(missing_ok=True)
        result = backend.run(launch.__class__(**{**launch.__dict__, "env": {"FAKE_DUMP": str(dump)}}))
        assert dump.is_file(), result.stderr_tail  # the process started: no E2BIG
        seen = json.loads(dump.read_text(encoding="utf-8"))
        assert_small(seen["argv"], seen["env"])
        return seen, result

    return run


def assert_small(argv: list[str], env: dict[str, str]) -> None:
    """Each argument and each variable well under `ARG_LIMIT`, whatever the texts."""
    longest = max([*(len(a.encode()) for a in argv), *(len(f"{k}={v}".encode()) for k, v in env.items())])
    assert longest < ARG_LIMIT // 8, longest
    assert not any(LONG[:50] in a or OTHER[:50] in a for a in [*argv, *env.values()])


def owner_only(seen: dict, text: str) -> None:
    """The text is in one of the files the agent was given, which this user alone may read."""
    [path] = [p for p, t in seen["files"].items() if t is not None and t.strip() == text]
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_claude_code_reads_its_system_prompts_from_files(agent):
    seen, _ = agent(ClaudeBackend, system_prompt=LONG, append_system_prompt=OTHER, tools=())
    argv = seen["argv"]
    assert seen["files"][argv[argv.index("--system-prompt-file") + 1]] == LONG
    assert seen["files"][argv[argv.index("--append-system-prompt-file") + 1]] == OTHER
    owner_only(seen, LONG)


#: 50,000 characters, 150,000 bytes in UTF-8: under `STDIN_THRESHOLD` counted in characters,
#: past what Linux takes for one argument.
JAPANESE_PROMPT = "日本語の短い指示です" * 5_000


@pytest.mark.parametrize("cls", [ClaudeBackend, OmpBackend, OmpRpcBackend, PiBackend, OpencodeBackend, CodexBackend])
def test_a_prompt_long_in_bytes_goes_over_stdin(agent, cls):
    assert len(JAPANESE_PROMPT) == 50_000 and len(JAPANESE_PROMPT.encode()) == 150_000
    seen, _ = agent(cls, prompt=JAPANESE_PROMPT)  # every argument under 16 KB (`assert_small`)
    assert seen["stdin"] == JAPANESE_PROMPT
    assert not any("日本語の短い指示" in a for a in seen["argv"])


def test_the_size_of_a_prompt_is_counted_as_the_system_counts_it():
    windows = sys.platform == "win32"
    assert command_line_size("é" * 10) == (10 if windows else 20)  # UTF-16 code units, else UTF-8 bytes
    assert command_line_size("𝄞") == (2 if windows else 4)  # a surrogate pair on Windows
    assert via_stdin(Launch(prompt=JAPANESE_PROMPT)) and not via_stdin(Launch(prompt="x" * 1_000))


@pytest.mark.parametrize("cls", [OmpBackend, PiBackend])
def test_omp_and_pi_read_the_system_prompt_from_a_file_and_the_preamble_with_the_prompt(agent, cls):
    seen, _ = agent(cls, system_prompt=LONG, append_system_prompt="Answer briefly.", preamble=OTHER, tools=())
    [flag] = [a for a in seen["argv"] if a.startswith("--system-prompt")]
    path = flag.partition("=")[2] or seen["argv"][seen["argv"].index(flag) + 1]
    assert seen["files"][path] == LONG and "Answer briefly." in seen["files"].values()
    owner_only(seen, LONG)
    # One first message: the preamble at its head, then the prompt.
    assert seen["stdin"] == f"{OTHER}\n\np"


@pytest.mark.parametrize("cls", [OmpBackend, PiBackend])
def test_a_short_preamble_and_prompt_are_one_message(agent, cls):
    seen, _ = agent(cls, preamble="Read the role.")
    assert seen["argv"][-1] == "Read the role.\n\np" and "Read the role." not in seen["argv"][:-1]
    assert seen["stdin"] == ""


def test_omp_over_rpc_reads_the_system_prompt_from_a_file_and_the_preamble_from_its_message(agent):
    seen, _ = agent(OmpRpcBackend, system_prompt=LONG, preamble=OTHER, tools=())
    [flag] = [a for a in seen["argv"] if a.startswith("--system-prompt=")]
    assert seen["files"][flag.removeprefix("--system-prompt=")] == LONG
    assert seen["stdin"] == f"{OTHER}\n\np"  # the prompt frame's message


def test_opencode_reads_a_light_launch_s_prompt_from_a_file_its_config_names(agent):
    seen, _ = agent(OpencodeBackend, system_prompt=LONG, tools=(), preamble=OTHER)
    config = json.loads(seen["env"]["OPENCODE_CONFIG_CONTENT"])
    prompt = config["agent"]["contraagent-light"]["prompt"]
    assert seen["files"][prompt.removeprefix("{file:").removesuffix("}")] == LONG
    owner_only(seen, LONG)
    assert seen["stdin"] == f"{OTHER}\n\np" and seen["argv"][-1] != "p"


def test_opencode_reads_another_launch_s_system_prompt_from_its_instructions(agent):
    seen, _ = agent(OpencodeBackend, system_prompt=LONG)
    [path] = json.loads(seen["env"]["OPENCODE_CONFIG_CONTENT"])["instructions"]
    assert seen["files"][path] == LONG


def test_codex_reads_its_instructions_from_a_file_and_the_rest_from_stdin(agent):
    seen, _ = agent(CodexBackend, system_prompt=LONG, append_system_prompt=OTHER, preamble="Read the role.")
    [setting] = [a for a in seen["argv"] if a.startswith("model_instructions_file=")]
    assert seen["files"][json.loads(setting.partition("=")[2])] == LONG
    owner_only(seen, LONG)
    assert not any(a.startswith("developer_instructions") for a in seen["argv"])
    assert seen["argv"][-1] == "-" and seen["stdin"] == f"{OTHER}\n\nRead the role.\n\np"


class Note(BaseModel):
    text: str


class Length(BaseModel):
    chars: int


#: A Claude Code that answers with the length of the system prompt its file holds.
MEASURER = r"""
import json, sys
if "--version" in sys.argv:
    print("2.1.306 (Claude Code)"); sys.exit(0)
sys.stdin.read()  # the prompt, with the note as JSON, is past the size that goes over stdin
system = open(sys.argv[sys.argv.index("--system-prompt-file") + 1], encoding="utf-8").read()
print(json.dumps({"type": "system", "subtype": "init", "model": "fake-model", "tools": [], "session_id": "s-1"}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": "s-1", "num_turns": 1,
                  "result": json.dumps({"chars": len(system)}), "total_cost_usd": 0.001, "usage": {"output_tokens": 2}}))
"""


def test_a_light_launch_whose_instructions_hold_a_long_param_is_launched(tmp_path):
    """The case that kept a task from launching: `$text` in a light launch's instructions."""
    measure = agent_task(
        "measure",
        instructions="Count the characters of this note:\n$text",
        params=Note,
        output=Length,
        output_from="message",
        tools=(),
        max_turns=1,
        timeout_s=60,
    )
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "claude", MEASURER)
    claude = ClaudeBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path)})
    work = tmp_path / "work"
    work.mkdir()
    pipeline = Pipeline(
        PipelineConfig({}), runs_dir=tmp_path / "runs", backends={"claude": claude}, cwd=work, preflight="off", log=lambda line: None
    )
    handle = {}
    report = pipeline.run(lambda: handle.setdefault("m", measure("u", Note(text=LONG))))
    assert report.ok, report.failed
    assert handle["m"].output.chars == len("Count the characters of this note:\n" + LONG)
