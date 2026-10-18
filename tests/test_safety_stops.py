"""Safety stops: a safety classifier that stopped part of a launch, which went on. Read from
Claude Code's stream, recorded on the launch and the journal, counted in the trends, and a
reason to fail over for a kind that asks for it."""

import json
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import ConfigError, Pipeline, PipelineConfig, SafetyStop, Task, agent_task
from contraagent._internal.backends.claude.wire import StreamReader, normalize_event
from contraagent._internal.backends.launch import Launch, Limits
from contraagent.backends import Backend, LaunchResult, Stop
from contraagent.config import KindConfig, Route
from contraagent.engine import AgentRunner, Router, TaskAdapter
from contraagent.monitor import Monitor, Period
from contraagent.testing import StubAgent, writes

# --- Claude Code's stream ----------------------------------------------------------


def _tool_use(tid: str, name: str) -> dict:
    return {"type": "assistant", "message": {"id": f"m-{tid}", "content": [{"type": "tool_use", "id": tid, "name": name, "input": {}}]}}


def _tool_error(tid: str, text: str) -> dict:
    content = [{"type": "tool_result", "tool_use_id": tid, "is_error": True, "content": text}]
    return {"type": "user", "timestamp": "2026-10-01T10:00:00.000Z", "message": {"role": "user", "content": content}}


def _read(events: list[dict]) -> LaunchResult:
    reader = StreamReader(Limits())
    for ev in events:
        reader.feed(ev)
    return reader.result(Launch(label="t", prompt="p", cwd=Path(".")), "claude", exit_code=0, killed=None)


RESULT = {"type": "result", "subtype": "success", "is_error": False, "stop_reason": "end_turn", "num_turns": 4, "result": "done"}


def test_a_stopped_response_is_read_with_its_model_its_unfinished_tool_and_its_message():
    o = _read(
        [
            _tool_use("t1", "Write"),
            _tool_error("t1", "Interrupted: the response that made this tool call was stopped by a safety classifier"),
            {"type": "system", "subtype": "informational", "content": "Model X's safeguards stopped the response above · continuing once"},
            {"type": "user", "isSynthetic": True, "refused_message_id": "msg_1", "message": {"role": "user", "content": "stopped"}},
            {**RESULT, "safety_stops": 1},
        ]
    )
    assert o.stop is Stop.COMPLETED and o.ok  # the launch went on and ended well
    (s,) = o.safety_stops
    assert (s.part, s.model, s.tool, s.message_id, s.ts) == ("response", "Model X", "Write", "msg_1", "2026-10-01T10:00:00.000Z")


def test_a_tool_whose_request_was_flagged_is_read_with_its_category_and_ids():
    text = "API Error: Model Y's safeguards flagged this message.\n\nDetails: `[cyber]`\n\nRequest ID: req_1\n\nMessage ID: msg_2"
    o = _read([_tool_use("t1", "WebFetch"), _tool_error("t1", text), {**RESULT, "safety_stops": 1}])
    (s,) = o.safety_stops
    assert (s.part, s.model, s.category, s.tool, s.request_id, s.message_id) == ("tool", "Model Y", "cyber", "WebFetch", "req_1", "msg_2")
    assert normalize_event({"type": "system", "subtype": "informational", "content": "a notice"}) == {"type": "notice", "text": "a notice"}


def test_one_the_result_counts_beyond_those_read_is_unread():
    o = _read([{**RESULT, "safety_stops": 2}])
    assert [s.part for s in o.safety_stops] == ["unread", "unread"]
    assert _read([RESULT]).safety_stops == []  # an older Claude Code counts none
    assert o.as_dict()["safety_stops"] == [{"part": "unread"}, {"part": "unread"}]


# --- failover ------------------------------------------------------------------------


class Agent(Backend):
    """A coding agent that ends well on every model, with the safety stops its script gives the model."""

    drivable_model_chain = False

    def __init__(self, script):
        super().__init__()
        self.name = self.binary = "claude"
        self.script = script
        self.seen: list[str] = []
        self._lock = threading.Lock()

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.seen.append(launch.model)
        stops = [SafetyStop(part=p, model=f"{launch.model} model") for p in self.script(launch.model)]
        return LaunchResult(label=launch.label, agent=self.name, stop=Stop.COMPLETED, ok=True, model=launch.model, safety_stops=stops)


def runner(tmp_path, agent, parts, chain=("m1", "m2")):
    router = Router(Route("claude", chain[0]), tuple(Route("claude", m) for m in chain[1:]), probe_interval_s=900)
    cfg = {"k": KindConfig(agent="claude", model=chain[0], max_turns=3, timeout_s=10, safety_stop_failover=parts)}
    return AgentRunner({"claude": agent}, cfg, run_dir=tmp_path, adapter=TaskAdapter(), routers={"k": router}, cwd=tmp_path)


def test_a_safety_stop_of_a_part_the_kind_names_moves_the_launch_to_the_next_hop(tmp_path):
    agent = Agent(lambda m: ["response"] if m == "m1" else [])
    res = runner(tmp_path, agent, ("response",)).run(Task("k", key="t"))
    assert agent.seen == ["m1", "m2"] and res.ok and res.route.startswith("hop 2/2")
    assert "response safety stop by m1 model on hop 1/2" in res.reason
    assert [s.model for s in res.launch_result.safety_stops] == ["m1 model"]  # the attempt keeps every hop's


def test_a_safety_stop_of_another_part_or_on_the_last_hop_stands(tmp_path):
    agent = Agent(lambda m: ["tool"])
    res = runner(tmp_path, agent, ("response",)).run(Task("k", key="t"))
    assert agent.seen == ["m1"] and res.ok  # a tool's request, which the kind does not fail over on
    agent = Agent(lambda m: ["response"])
    res = runner(tmp_path, agent, ("response", "tool")).run(Task("k", key="t"))
    assert agent.seen == ["m1", "m2"] and res.ok and res.route.startswith("hop 2/2")  # the last hop's result stands
    agent = Agent(lambda m: ["unread"])
    runner(tmp_path, agent, ("tool",)).run(Task("k", key="t"))
    assert agent.seen == ["m1", "m2"]  # of no known part: it moves when any part does
    agent = Agent(lambda m: ["response"])
    runner(tmp_path, agent, ()).run(Task("k", key="t"))
    assert agent.seen == ["m1"]  # none named: a safety stop moves nothing


def test_a_safety_stop_moves_the_launch_to_the_next_hop_for_refusals(tmp_path):
    agent = Agent(lambda m: ["response"] if m == "m1" else [])
    router = Router(Route("claude", "m1"), (Route("claude", "m2", stops=("rate_limited",)), Route("claude", "m3", stops=("refused",))))
    cfg = {"k": KindConfig(agent="claude", model="m1", max_turns=3, timeout_s=10, safety_stop_failover=("response",))}
    res = AgentRunner({"claude": agent}, cfg, run_dir=tmp_path, adapter=TaskAdapter(), routers={"k": router}, cwd=tmp_path).run(
        Task("k", key="t")
    )
    assert agent.seen == ["m1", "m3"] and res.ok and res.route.startswith("hop 3/3")
    router = Router(Route("claude", "m1"), (Route("claude", "m2", stops=("rate_limited",)),))
    agent = Agent(lambda m: ["response"])
    res = AgentRunner({"claude": agent}, cfg, run_dir=tmp_path, adapter=TaskAdapter(), routers={"k": router}, cwd=tmp_path).run(
        Task("k", key="t")
    )
    assert agent.seen == ["m1"] and res.ok  # no hop for refusals: the launch's result stands


# --- a run ------------------------------------------------------------------------


class Note(BaseModel):
    text: str


def test_a_run_records_the_safety_stops_of_each_attempt_and_the_trends_count_them(tmp_path):
    (tmp_path / "pipeline.toml").write_text(
        '[tasks.write]\nmax_turns = 5\ntimeout_s = 60\nsafety_stop_failover = ["tool"]\n'
        '[[tasks.write.fallbacks]]\nagent = "claude"\nmodel = "m2"\n'
    )
    write = agent_task("write", instructions="Write.", output=Note, model="m1")
    stopped = [SafetyStop(part="tool", model="Model Y", category="cyber", tool="WebFetch")]
    agent = StubAgent({"write": lambda launch: writes(Note(text="x"), safety_stops=stopped if launch.model == "m1" else ())})
    report = Pipeline(tmp_path / "pipeline.toml", runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(
        lambda: write("a"), run_id="r"
    )
    assert report.ok, report.failed
    assert [launch.model for launch in agent.launches] == ["m1", "m2"]
    (row,) = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    (stop,) = row["safety_stops"]
    assert (stop["part"], stop["model"], stop["category"], stop["tool"]) == ("tool", "Model Y", "cyber", "WebFetch")
    day = row["ts"][:10]
    trends = Monitor(tmp_path / "runs").trends(Period.parse(day, day, "UTC"))
    assert trends["safety_stops"] == [{"part": "tool", "model": "Model Y", "count": 1, "kinds": {"write": 1}}]
    assert trends["bodies"]["safety_stops"]["blocks"][0]["rows"][0]["count"] == 1


def test_a_kind_names_only_the_parts_a_safety_stop_has():
    with pytest.raises(ConfigError, match=r"safety_stop_failover must be a list of 'response' and 'tool', not 'unread'"):
        PipelineConfig({"tasks": {"write": {"safety_stop_failover": ["unread"]}}}).task_tables()
    with pytest.raises(ConfigError, match="safety_stop_failover"):
        agent_task("x", instructions="x", output=Note, safety_stop_failover=["all"], max_turns=1, timeout_s=1)  # pyright: ignore[reportArgumentType]


def test_check_warns_of_a_kind_that_fails_over_on_a_safety_stop_with_no_chain(tmp_path):
    write = agent_task("write", instructions="Write.", output=Note, max_turns=5, timeout_s=60, safety_stop_failover=["response"])
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", backends=StubAgent().backends(), cwd=tmp_path)
    report = pipeline.check(lambda: write("a"))
    assert any("write: safety_stop_failover = ['response']" in w and "no failover chain" in w for w in report.warnings), report.warnings
