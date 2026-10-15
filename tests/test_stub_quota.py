"""The stub agent reports a utilization reading, so a run on it rests a credential past its cap."""

import json

from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, QuotaReading, TaskDeferred, agent_task
from contraagent.testing import StubAgent, writes

CONFIG = {
    "credentials": {"capped": {"type": "subscription", "max_five_hour_pct": 50}},
    "tasks": {
        "q": {"credential": "capped", "fallbacks": [{"agent": "omp", "model": "anthropic/m", "credential": "ambient"}]},
        "q_nohop": {"credential": "capped"},
    },
}


class Note(BaseModel):
    note: str


def test_a_stub_run_rests_a_credential_past_its_cap_and_falls_over(tmp_path):
    q = agent_task("q", instructions="x", output=Note, max_turns=1, timeout_s=10, agent="claude", model="m")
    q_nohop = agent_task("q_nohop", instructions="x", output=Note, max_turns=1, timeout_s=10, agent="claude", model="m")
    stub = StubAgent({"q": writes({"note": "n"}, quota=QuotaReading(five_hour_pct=80.0)), "q_nohop": {"note": "n"}})
    deferred: list[str] = []

    def flow():
        yield q("first")  # runs on capped, which reports 80%
        yield q("second")  # capped rests: the omp hop
        try:
            yield q_nohop("third")  # no hop left: deferred
        except TaskDeferred as exc:
            deferred.append(str(exc))

    report = Pipeline(
        PipelineConfig(CONFIG), runs_dir=tmp_path / "runs", cwd=tmp_path, backends=stub.backends(), log=lambda line: None
    ).run(flow)
    rows = {r["key"]: r for r in map(json.loads, (report.run_dir / "journal.jsonl").read_text().splitlines())}
    first, second = rows["q-first"], rows["q-second"]
    assert first["agent"] == "claude" and first["quota"][0]["five_hour_pct"] == 80.0 and first["quota"][0]["credential"] == "capped"
    assert second["agent"] == "omp" and "capped rests: 5-hour usage 80%, max 50%" in second["reason"]
    assert "q_nohop-third" not in rows and deferred
    rests = [json.loads(line) for line in (report.run_dir / "rests.jsonl").read_text().splitlines()]
    assert rests[0]["event"] == "start" and rests[0]["credential"] == "capped" and rests[0]["window"] == "five_hour"
