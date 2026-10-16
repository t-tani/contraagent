"""The MCP servers a task's coding agent gets (`Pipeline(mcp_servers=)`, `McpServers`):
built per task from its params and its plugin's `.mcp.json`, and given to each coding
agent as it takes a plugin's."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent.backends import ClaudeBackend, CodexBackend, Launch, OmpBackend
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent


class Note(BaseModel):
    title: str


class Topic(BaseModel):
    index: str


@pytest.fixture
def plugin_dir(tmp_path):
    root = tmp_path / "plugins" / "write"
    new_plugin(root)
    (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"docs": {"command": "docs-server"}}}), encoding="utf-8")
    return root


def run(tmp_path, agent, flow, **options):
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, **options)
    return pipeline.run(flow)


def given(launch) -> dict | None:
    """The servers the launch's MCP config file holds, by name; None for no file."""
    path = launch.launch.mcp_config
    return None if path is None else json.loads(Path(path).read_text(encoding="utf-8"))["mcpServers"]


def test_the_function_adds_a_server_built_from_the_task_s_params_to_the_plugin_s(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, params=Topic, output=Note, max_turns=5, timeout_s=60)
    calls = []

    def servers(task, params, plugin_servers):
        calls.append((task.key, params, plugin_servers))
        return {**plugin_servers, "index": {"command": "index-server", "args": ["--root", params["index"], "--unit", task.unit]}}

    agent = StubAgent({"write": {"title": "t"}})
    report = run(tmp_path, agent, lambda: write("alpha", index="indexes/alpha"), mcp_servers=servers)
    assert report.ok, report.failed
    assert calls == [("write-alpha", {"index": "indexes/alpha"}, {"docs": {"command": "docs-server"}})]
    [launch] = agent.launches
    assert given(launch) == {
        "docs": {"command": "docs-server"},
        "index": {"command": "index-server", "args": ["--root", "indexes/alpha", "--unit", "alpha"]},
    }
    path = Path(launch.launch.mcp_config)
    assert not path.is_relative_to(report.run_dir) and not path.is_relative_to(plugin_dir)  # never in the run's records


def test_the_example_gives_each_answer_an_index_over_its_own_collection(tmp_path):
    from contraagent.docs.examples.mcp import flow as example

    agent = StubAgent({"answer": {"text": "a", "sources": []}})
    pipeline = example.pipeline(runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path)
    assert pipeline.check(example.ask_all, questions={"reports": "q"}).ok
    report = pipeline.run(example.ask_all, questions={"reports": "What changed?", "reviews": "Who wrote the most?"})
    assert report.ok, report.failed
    by_unit = {launch.unit: given(launch) for launch in agent.launches}
    assert by_unit == {
        unit: {
            "glossary": {"command": "glossary-server", "args": ["--stdio"]},
            "index": {"command": "index-server", "args": ["--stdio", "--root", f"collections/{unit}"]},
        }
        for unit in ("reports", "reviews")
    }


def test_none_keeps_the_plugin_s_and_an_empty_table_gives_none(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60)
    agent = StubAgent({"write": {"title": "t"}})
    run(
        tmp_path,
        agent,
        lambda: [write("alpha"), write("beta")],
        mcp_servers=lambda task, params, servers: {} if task.unit == "beta" else None,
    )
    by_unit = {launch.unit: launch for launch in agent.launches}
    assert by_unit["alpha"].launch.mcp_config == str(plugin_dir / ".mcp.json")
    assert given(by_unit["beta"]) == {}


def test_a_task_with_no_plugin_gets_servers_too_and_a_light_launch_none(tmp_path):
    note = agent_task("note", instructions="Write a note.", output=Note, max_turns=5, timeout_s=60)
    judge = agent_task("judge", instructions="Judge.", output=Note, output_from="message", tools=(), max_turns=1, timeout_s=60)
    agent = StubAgent({"note": {"title": "t"}, "judge": {"title": "j"}})
    report = run(
        tmp_path, agent, lambda: [note("a"), judge("a")], mcp_servers=lambda task, params, servers: {"x": {"url": "http://127.0.0.1:9/mcp"}}
    )
    assert report.ok, report.failed
    by_kind = {launch.kind: launch for launch in agent.launches}
    assert given(by_kind["note"]) == {"x": {"url": "http://127.0.0.1:9/mcp"}}
    assert by_kind["judge"].launch.mcp_config is None


@pytest.mark.parametrize(
    ("returned", "said"),
    [
        (["docs"], "returned list"),
        ({"docs": {"args": ["x"]}}, "give it a command"),
        ({"docs": {"command": "x", "env": {"K": object()}}}, "JSON cannot hold"),
    ],
)
def test_check_reports_what_the_function_returns_that_is_no_table_of_servers(tmp_path, plugin_dir, returned, said):
    write = agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60)
    pipeline = Pipeline(None, backends=StubAgent({}).backends(), cwd=tmp_path, mcp_servers=lambda task, params, servers: returned)
    report = pipeline.check(lambda: write("alpha"))
    assert any(e.startswith("write-alpha: mcp_servers:") and said in e for e in report.errors), report.errors
    assert "plugins" in report.topics


def _servers_file(tmp_path: Path, servers: dict) -> str:
    path = tmp_path / "task.mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return str(path)


def _plugin_dirs(argv: list[str]) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == "--plugin-dir"]


def test_omp_gets_a_copy_of_the_plugin_whose_mcp_json_is_the_task_s(tmp_path, plugin_dir):
    omp = OmpBackend()
    own = Launch(prompt="p", label="write-alpha", plugin_dirs=(str(plugin_dir),), mcp_config=str(plugin_dir / ".mcp.json"))
    assert _plugin_dirs(omp.argv(own)) == [str(plugin_dir)]
    servers = _servers_file(tmp_path, {"index": {"command": "i"}})
    [mirror] = _plugin_dirs(omp.argv(Launch(prompt="p", label="write-alpha", plugin_dirs=(str(plugin_dir),), mcp_config=servers)))
    assert mirror != str(plugin_dir)
    assert json.loads((Path(mirror) / ".mcp.json").read_text(encoding="utf-8")) == {"mcpServers": {"index": {"command": "i"}}}
    assert (Path(mirror) / "agents").resolve() == (plugin_dir / "agents").resolve()
    assert json.loads((plugin_dir / ".mcp.json").read_text(encoding="utf-8")) == {"mcpServers": {"docs": {"command": "docs-server"}}}
    [only] = _plugin_dirs(omp.argv(Launch(prompt="p", label="note-a", mcp_config=_servers_file(tmp_path, {"x": {"command": "x"}}))))
    assert sorted(p.name for p in Path(only).iterdir()) == [".claude-plugin", ".mcp.json"]


def test_claude_and_codex_take_the_task_s_file_as_they_take_a_plugin_s(tmp_path):
    path = _servers_file(tmp_path, {"index": {"command": "index-server", "args": ["--root", "r"]}})
    argv = ClaudeBackend().argv(Launch(prompt="p", mcp_config=path))
    assert argv[argv.index("--mcp-config") + 1] == path and "--strict-mcp-config" in argv
    codex = CodexBackend().argv(Launch(prompt="p", mcp_config=path))
    assert any(a.startswith("mcp_servers.") and "index" in a and "index-server" in a for a in codex)


def test_a_function_that_raises_fails_the_launch_and_launches_nothing(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60, retries=0)

    def servers(task, params, plugin_servers):
        raise RuntimeError("no index for this unit")

    agent = StubAgent({"write": {"title": "t"}})
    report = run(tmp_path, agent, lambda: write("alpha"), mcp_servers=servers, retry_wait_s=0)
    assert not report.ok and not agent.launches
    result = report.results["write-alpha"]
    assert "no index for this unit" in (result.reason or ""), result
