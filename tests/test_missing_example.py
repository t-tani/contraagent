"""The example of a task that finds something missing (`docs/examples/missing/flow.py`):
the flow reads the output's `missing`, fetches what the archive holds, reviews again,
and logs what stays missing, which its run panel shows."""

from __future__ import annotations

from contraagent import Pipeline
from contraagent.docs.examples.missing.flow import PANELS, reviews
from contraagent.monitor import Monitor, TableBody
from contraagent.testing import StubAgent, StubLaunch


def answer(launch: StubLaunch) -> dict:
    """A review that asks for `terms` and `minutes` until it has the file of each."""
    have = {path.rsplit("/", 1)[-1].removesuffix(".md") for path in launch.params["documents"]}
    wanted = {"north": ["terms", "minutes"], "south": []}[launch.unit]
    return {"verdict": "Reviewed.", "missing": [name for name in wanted if name not in have]}


def test_the_flow_fetches_what_a_review_misses_reviews_again_and_shows_what_stays_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # fetch writes documents/ under the process's directory
    agent = StubAgent({"review": answer})
    runs = tmp_path / "runs"
    report = Pipeline(None, runs_dir=runs, cwd=tmp_path, backends=agent.backends(), log=lambda line: None).run(
        reviews, units={"north": ["notes.md"], "south": ["notes.md"]}, run_id="reviews"
    )
    assert report.ok, report.failed
    assert sorted(launch.key for launch in agent.launches) == ["review-north", "review-north~2", "review-south"]
    assert (tmp_path / "documents/terms.md").exists()  # the archive holds it; it holds no minutes
    north, south = report.value
    assert north.missing == ["minutes"] and south.missing == []
    body = TableBody.model_validate(Monitor(runs, panels=PANELS).panel("missing", "reviews"))
    assert body.rows == [{"unit": "north", "document": "minutes"}]
