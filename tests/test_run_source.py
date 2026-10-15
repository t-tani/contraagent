"""The monitor's ports: every `RunSource` keeps the same contract, and `Monitor` makes the
same views from any of them. The demo's runs are read from their directory, copied into
memory record by record, and every view of the copy must equal the original's."""

import json
from pathlib import Path

import pytest

from contraagent import rundir
from contraagent.monitor import Monitor
from contraagent.monitor.paths import BadName
from contraagent.monitor.source import DirectorySource, MemorySource, ProcLiveness, StaticLiveness


def copy_to_memory(root: Path) -> MemorySource:
    """Every record of every run under `root`, and every file a contract names, held in memory."""
    source = DirectorySource(root)
    records: dict[str, dict] = {}
    files: dict[str, dict[str, tuple[str, str]]] = {}
    times: dict[str, str] = {}
    for run in source.runs():
        held: dict = {}
        for path in sorted((root / run).rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(root / run).as_posix()
            text = path.read_text(errors="replace")
            held[name] = text.splitlines() if name.endswith(".jsonl") else text
        records[run] = held
        times[run] = source.activity(run) or ""
        for text in source.folder(run, rundir.CONTRACTS):
            for spec in (lambda r: r.get("outputs", []) + r.get("inputs", []))(json.loads(text)):
                got = source.file(run, spec["path"])
                if got is not None and got[0] is not None:
                    files.setdefault(run, {})[spec["path"]] = (got[0], got[2])
    return MemorySource(records, files=files, times=times)


def views(mon: Monitor) -> dict:
    out: dict = {"runs": mon.runs()}
    for run in [r["run"] for r in out["runs"]]:
        plan = mon.plan(run)
        keys = [n["key"] for n in plan["nodes"]]
        out[run] = {
            "journal": mon.journal(run, 0),
            "journal_from_3": mon.journal(run, 3),
            "plan": plan,
            "outputs": mon.outputs(run),
            "definitions": mon.definitions(run),
            "cursor": mon.cursor(run),
            "procs": mon.procs(run),
            "task": {k: mon.task_detail(run, k) for k in keys},
            "stream": {k: mon.stream(run, k, 0, limit=5) for k in keys},
            "stream_from_2": {k: mon.stream(run, k, 2, limit=5) for k in keys},
        }
    return json.loads(json.dumps(out, default=str, sort_keys=True))


def test_a_run_copied_into_memory_has_every_view_of_its_directory(demo_runs):
    memory = copy_to_memory(demo_runs)
    on_disk = views(Monitor(demo_runs))
    assert on_disk["runs"], "the demo wrote no run"
    assert views(Monitor(source=memory, liveness=StaticLiveness(memory))) == on_disk


@pytest.fixture(params=["directory", "memory"])
def source(request, demo_runs):
    return DirectorySource(demo_runs) if request.param == "directory" else copy_to_memory(demo_runs)


def test_lines_page_a_log_by_offset_and_count_it(source):
    run = source.runs()[0]
    every, total = source.lines(run, rundir.JOURNAL)
    assert total == len(every) > 2
    assert source.lines(run, rundir.JOURNAL, 1, 1) == (every[1:2], total)
    assert source.lines(run, rundir.JOURNAL, total) == ([], total)
    assert source.lines(run, rundir.JOURNAL, 0, 0) == ([], total)


def test_an_absent_log_or_document_is_empty_not_an_error(source):
    run = source.runs()[0]
    assert source.lines(run, rundir.stream("no-such-task")) == ([], 0)
    assert source.size(run, rundir.stream("no-such-task")) == -1
    assert source.document(run, rundir.entry(rundir.CALLS, "no-such-task")) is None
    assert source.folder(run, "no-such-folder") == []
    assert not source.exists(run, "no-such-folder")
    assert source.file(run, "/no/such/file.json") is None


def test_size_grows_with_its_log_and_documents_read_whole(source):
    run = source.runs()[0]
    assert source.size(run, rundir.JOURNAL) > 0
    assert json.loads(source.document(run, rundir.RUN_INFO) or "{}") == source.info(run)
    assert source.exists(run, rundir.STREAMS) and source.exists(run, rundir.JOURNAL)
    kinds = [json.loads(t)["kind"] for t in source.folder(run, rundir.DEFINITIONS)]
    assert kinds and kinds == sorted(kinds)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.info("../x"),
        lambda s: s.lines("../x", rundir.JOURNAL),
        lambda s: s.lines(s.runs()[0], "../journal.jsonl"),
        lambda s: s.size(s.runs()[0], rundir.stream("../x")),
        lambda s: s.document(s.runs()[0], ".hidden"),
        lambda s: s.folder(s.runs()[0], ".."),
        lambda s: s.exists("..", rundir.JOURNAL),
        lambda s: s.activity("a/b"),
        lambda s: s.file("../x", "/etc/hostname"),
    ],
)
def test_a_name_that_is_not_plain_is_refused_by_every_source(source, call):
    with pytest.raises(BadName):
        call(source)


def test_the_run_info_names_the_run_across_hosts_and_keeps_its_uid_on_resume(demo_runs, tmp_path, monkeypatch):
    from contraagent.execution.run import Run

    monkeypatch.setenv(rundir.HOST_ID_ENV, "build-7")
    first = Run("r1", runs_dir=tmp_path, lock=False)
    info = json.loads((first.dir / rundir.RUN_INFO).read_text())
    assert info["host_id"] == "build-7" and len(info["run_uid"]) == 32
    again = Run("r1", runs_dir=tmp_path, lock=False)
    assert json.loads((again.dir / rundir.RUN_INFO).read_text())["run_uid"] == info["run_uid"]
    other = Run("r2", runs_dir=tmp_path, lock=False)
    assert json.loads((other.dir / rundir.RUN_INFO).read_text())["run_uid"] != info["run_uid"]


def test_a_finished_run_is_live_for_no_liveness(demo_runs):
    memory = copy_to_memory(demo_runs)
    assert ProcLiveness(demo_runs).live() == set() == StaticLiveness(memory).live()
    run = memory.runs()[0]
    assert ProcLiveness(demo_runs).snapshot(run) == StaticLiveness(memory).snapshot(run)
    assert StaticLiveness(memory, live=[run]).snapshot(run)["alive"]
