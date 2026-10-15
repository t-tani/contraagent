"""An output taken from the agent's final message (`agent_task(output_from="message")`)."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.contracts.calls import validate_call
from contraagent.backends import CallFile, Launch, LaunchResult, Stop
from contraagent.engine import OutputContract, run_until_valid
from contraagent.testing import StubAgent, writes_nothing


class Verdict(BaseModel):
    approved: bool


def classify(**config):
    return agent_task(
        "classify", instructions="Classify the item.", output=Verdict, output_from="message", max_turns=1, timeout_s=60, **config
    )


def run(tmp_path, agent, flow, config=None):
    return Pipeline(PipelineConfig(config or {}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(flow)


def test_the_final_message_is_written_to_the_output_file_and_checked(tmp_path):
    task = classify()
    handle = {}
    agent = StubAgent({"classify": {"approved": True}})
    report = run(tmp_path, agent, lambda: handle.setdefault("a", task("a")))
    assert report.ok, report.failed
    assert handle["a"].output.approved is True
    assert json.loads(handle["a"].path.read_text()) == {"approved": True}
    (launch,) = agent.launches
    assert launch.call.output is not None and launch.call.output.from_ == "message"
    assert '"from": "message"' in Path(launch.launch.env["CONTRAAGENT_CALL"]).read_text()
    assert "Your final message is the output" in launch.prompt and "write no file" in launch.prompt
    assert json.loads((report.run_dir / "definitions" / "classify.json").read_text())["output_from"] == "message"


def test_a_message_off_contract_goes_back_to_the_same_session(tmp_path):
    task = classify()
    agent = StubAgent({"classify": ["Approved, I think.", {"approved": False}]})
    report = run(tmp_path, agent, lambda: task("a"), config={"defaults": {"agent": "omp"}})
    assert report.ok, report.failed
    first, second = agent.launches
    assert second.resumed and "Your final message is the output, and it does not pass its checks" in second.prompt
    assert "## Your final message" in second.prompt
    assert report.results["classify-a"].launch_result.rounds == 2


def test_an_empty_final_message_is_named(tmp_path):
    task = classify(retries=0)
    report = run(tmp_path, StubAgent({"classify": writes_nothing()}), lambda: task("a"), config={"defaults": {"agent": "omp"}})
    result = report.results["classify-a"]
    assert result.stop == "invalid_output"
    assert result.launch_result.round_errors[0] == ["the final message is empty"]


def test_output_from_is_part_of_the_definition():
    in_file = agent_task("classify", instructions="Classify the item.", output=Verdict, max_turns=1, timeout_s=60)
    assert classify().digest() != in_file.digest()
    with pytest.raises(TypeError, match="needs an output"):
        agent_task("x", instructions="x", output_from="message", max_turns=1, timeout_s=60)
    with pytest.raises(TypeError, match="output_from must be"):
        agent_task("x", instructions="x", output=str, output_from="reply", max_turns=1, timeout_s=60)  # type: ignore[arg-type]


class _Hollow:
    """A backend whose one-turn answer reads like a tool call written out as text."""

    name = "fake"

    def resumable(self, launch):
        return launch

    def run(self, launch):
        text = json.dumps({"approved": True, "note": "Read(the file) first"})
        return LaunchResult(label="t", stop=Stop.COMPLETED, ok=False, hollow=True, result_text=text)

    def resumed(self, launch, result, prompt):
        return None

    def discard_session(self, launch, sid):
        pass


class Noted(BaseModel):
    approved: bool
    note: str


def test_a_message_that_passes_its_checks_is_not_hollow(tmp_path):
    contract = OutputContract(tmp_path / "out.json", Noted, from_message=True)
    result = run_until_valid(_Hollow(), Launch(prompt="p", label="t", cwd=tmp_path), [contract])  # type: ignore[arg-type]
    assert result.ok and not result.hollow
    assert json.loads((tmp_path / "out.json").read_text())["note"] == "Read(the file) first"


def test_the_stop_hook_leaves_a_message_output_to_the_runner(tmp_path):
    call = CallFile.model_validate(
        {"run": "r", "key": "classify-a", "kind": "classify", "output": {"path": str(tmp_path / "none.json"), "from": "message"}}
    )
    path = call.write(tmp_path / "call.json")
    assert validate_call(path) == (0, "")
