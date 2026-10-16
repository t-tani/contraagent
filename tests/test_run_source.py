"""The monitor's ports: every `RunSource` keeps the same contract, and `Monitor` makes the
same views from any of them. The demo's runs are read from their directory, copied into
memory record by record, and every view of the copy must equal the original's."""

import json
from pathlib import Path

import pytest

from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import StaticLiveness
from contraagent._internal.runs.names import BadName
from contraagent._internal.runs.procs import ProcLiveness
from contraagent._internal.runs.source import MemorySource
from contraagent.monitor import DirectorySource, Monitor


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
        for text in source.folder(run, layout.CONTRACTS):
            for spec in (lambda r: r.get("outputs", []) + r.get("inputs", []))(json.loads(text)):
                got = source.file(run, spec["path"])
                if got is not None and got.text is not None:
                    files.setdefault(run, {})[spec["path"]] = (got.text, got.mtime)
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
    every, total = source.lines(run, layout.JOURNAL)
    assert total == len(every) > 2
    assert source.lines(run, layout.JOURNAL, 1, 1) == (every[1:2], total)
    assert source.lines(run, layout.JOURNAL, total) == ([], total)
    assert source.lines(run, layout.JOURNAL, 0, 0) == ([], total)


def test_an_absent_log_or_document_is_empty_not_an_error(source):
    run = source.runs()[0]
    assert source.lines(run, layout.stream("no-such-task")) == ([], 0)
    assert source.size(run, layout.stream("no-such-task")) == -1
    assert source.document(run, layout.entry(layout.CALLS, "no-such-task")) is None
    assert source.folder(run, "no-such-folder") == []
    assert not source.exists(run, "no-such-folder")
    assert source.file(run, "/no/such/file.json") is None


def test_size_grows_with_its_log_and_documents_read_whole(source):
    run = source.runs()[0]
    assert source.size(run, layout.JOURNAL) > 0
    assert json.loads(source.document(run, layout.RUN_INFO) or "{}") == source.info(run)
    assert source.exists(run, layout.STREAMS) and source.exists(run, layout.JOURNAL)
    kinds = [json.loads(t)["kind"] for t in source.folder(run, layout.DEFINITIONS)]
    assert kinds and kinds == sorted(kinds)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.info("../x"),
        lambda s: s.lines("../x", layout.JOURNAL),
        lambda s: s.lines(s.runs()[0], "../journal.jsonl"),
        lambda s: s.size(s.runs()[0], "streams/../x.stream.jsonl"),
        lambda s: s.document(s.runs()[0], ".hidden"),
        lambda s: s.folder(s.runs()[0], ".."),
        lambda s: s.exists("..", layout.JOURNAL),
        lambda s: s.activity("a/b"),
        lambda s: s.file("../x", "/etc/hostname"),
    ],
)
def test_a_name_that_is_not_plain_is_refused_by_every_source(source, call):
    with pytest.raises(BadName):
        call(source)


def test_the_listings_name_every_log_and_document_and_stat_each(source):
    run = source.runs()[0]
    logs, docs = source.logs(run), source.documents(run)
    assert layout.JOURNAL in logs and any(layout.stream_name(log) for log in logs)
    assert layout.RUN_INFO in docs and any(d.startswith(layout.CONTRACTS + "/") for d in docs) and layout.TRENDS not in docs
    for name in [*logs, *docs]:
        st = source.stat(run, name)
        assert st is not None and st.size > 0, name
    assert source.stat(run, "no-such.jsonl") is None


def test_a_log_is_read_from_a_kept_position_as_by_its_line_numbers(source):
    run = source.runs()[0]
    every, total = source.lines(run, layout.JOURNAL)
    at = source.position(run, layout.JOURNAL, 0)
    got: list[str] = []
    while True:
        more, at = source.lines_at(run, layout.JOURNAL, at, 2, 1)
        if not more:
            break
        got += more
    assert got == every and at.line == total
    first = source.lines_at(run, layout.JOURNAL, source.position(run, layout.JOURNAL, 0), 1)[1]
    assert source.position(run, layout.JOURNAL, 1) == first
    assert source.position(run, layout.JOURNAL, total + 5).line == total


def test_a_relative_contract_path_is_read_under_the_run_cwd_not_the_monitor_cwd(tmp_path, monkeypatch):
    work, elsewhere = tmp_path / "work", tmp_path / "elsewhere"
    (work / "out").mkdir(parents=True)
    (elsewhere / "out").mkdir(parents=True)
    (work / "out" / "a.json").write_text('{"from": "work"}')
    (elsewhere / "out" / "a.json").write_text('{"from": "elsewhere"}')
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    (run / layout.RUN_INFO).write_text(json.dumps({"run_id": "r1", "cwd": str(work)}))
    monkeypatch.chdir(elsewhere)
    source = DirectorySource(tmp_path / "runs")
    got = source.file("r1", "out/a.json")
    assert got is not None and got.text == '{"from": "work"}'
    st = source.file_stat("r1", "out/a.json")
    assert st is not None and st.size == len('{"from": "work"}')


def test_the_run_info_names_the_run_across_hosts_and_keeps_its_uid_on_resume(demo_runs, tmp_path, monkeypatch):
    from contraagent.engine import Run

    monkeypatch.setenv(layout.HOST_ID_ENV, "build-7")
    first = Run("r1", runs_dir=tmp_path, lock=False)
    info = json.loads((first.dir / layout.RUN_INFO).read_text())
    assert info["host_id"] == "build-7" and len(info["run_uid"]) == 32
    again = Run("r1", runs_dir=tmp_path, lock=False)
    assert json.loads((again.dir / layout.RUN_INFO).read_text())["run_uid"] == info["run_uid"]
    other = Run("r2", runs_dir=tmp_path, lock=False)
    assert json.loads((other.dir / layout.RUN_INFO).read_text())["run_uid"] != info["run_uid"]


def test_a_finished_run_is_live_for_no_liveness(demo_runs):
    memory = copy_to_memory(demo_runs)
    assert ProcLiveness(demo_runs).live() == set() == StaticLiveness(memory).live()
    run = memory.runs()[0]
    assert ProcLiveness(demo_runs).snapshot(run) == StaticLiveness(memory).snapshot(run)
    assert StaticLiveness(memory, live=[run]).snapshot(run)["alive"]
