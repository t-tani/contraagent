"""Faults of the disk under a run: a record that does not read, a write cut short, a record
that cannot be written, and what a power loss must not leave.

What a resume reads (the journal, `run.json`, the cursor) is never taken for empty when it
does not read; what only the monitor reads never fails a task or a run."""

from __future__ import annotations

import contextlib
import errno
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, RunExists, agent_task, import_recording, python_task
from contraagent._internal.backends.omp.rpc import OmpRpcBackend
from contraagent._internal.backends.process import run_process
from contraagent._internal.backends.transcript import Transcript
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.errors import ContraagentError
from contraagent._internal.execution.journal import Journal
from contraagent._internal.execution.recording import RecordingError
from contraagent._internal.execution.resume_from import EarlierRunError
from contraagent._internal.platform import sharing
from contraagent._internal.runs import failures, files, layout
from contraagent.backends import Launch
from contraagent.config import Limits
from contraagent.engine import CursorStore, Run
from contraagent.testing import StubAgent, writes_example


class Count(BaseModel):
    n: int


class Note(BaseModel):
    note: str


calls: list[str] = []


@python_task(kind="count")
def count(unit: str) -> Count:
    calls.append(unit)
    return Count(n=1)


note = agent_task("note", instructions="Write a note.", output=Note, max_turns=5, timeout_s=60, retries=0)


@pytest.fixture(autouse=True)
def no_calls():
    calls.clear()


def three():
    return [count("a"), count("b"), count("c")]


def run(root: Path, flow=three, *, lines: list[str] | None = None, stub: StubAgent | None = None, run_id: str = "r", **kw):
    log = lines.append if lines is not None else (lambda line: None)
    config = PipelineConfig({}) if stub is not None else None
    return Pipeline(config, runs_dir=root / "runs", cwd=root, stub=stub, log=log).run(flow, run_id=run_id, **kw)


def unreadable(monkeypatch, name: str) -> None:
    """Reading a file called `name` fails as a failing disk does (EIO)."""
    real = sharing.open_shared

    def fail(path):
        if Path(path).name == name:
            raise OSError(errno.EIO, "Input/output error", os.fspath(path))
        return real(path)

    monkeypatch.setattr(sharing, "open_shared", fail)


def keys(run_dir: Path) -> list[str]:
    return sorted(row["key"] for row in files.read_rows(run_dir / layout.JOURNAL))


# --- the journal is empty only when it is absent -----------------------------------------


def test_a_resume_that_cannot_read_the_journal_runs_nothing(tmp_path, monkeypatch):
    run_dir = run(tmp_path).run_dir
    before = (run_dir / layout.RUN_INFO).read_bytes()
    calls.clear()
    unreadable(monkeypatch, layout.JOURNAL)
    with pytest.raises(ContraagentError, match=r"cannot read .*journal\.jsonl") as raised:
        run(tmp_path, resume=True)
    assert isinstance(raised.value.__cause__, OSError)
    assert calls == [] and (run_dir / layout.RUN_INFO).read_bytes() == before


def test_a_run_id_whose_journal_cannot_be_read_is_not_started_again(tmp_path, monkeypatch):
    run(tmp_path)
    calls.clear()
    unreadable(monkeypatch, layout.JOURNAL)
    with pytest.raises(ContraagentError, match=r"cannot read .*journal\.jsonl"):
        run(tmp_path)
    assert calls == []


def test_a_journal_read_that_fails_as_the_resume_decides_runs_nothing(tmp_path, monkeypatch):
    run(tmp_path)
    calls.clear()
    last_rows = Journal.last_rows

    def fails_once(self):
        with monkeypatch.context() as m:
            unreadable(m, layout.JOURNAL)
            return last_rows(self)

    monkeypatch.setattr(Journal, "last_rows", fails_once)
    with pytest.raises(ContraagentError, match=r"cannot read .*journal\.jsonl"):
        run(tmp_path, resume=True)
    assert calls == []


@pytest.mark.parametrize("name", [layout.JOURNAL, layout.RUN_INFO])
def test_a_run_is_not_resumed_from_records_that_cannot_be_read(tmp_path, monkeypatch, name):
    run(tmp_path, run_id="first")
    calls.clear()
    unreadable(monkeypatch, name)
    with pytest.raises(EarlierRunError, match="cannot read"):
        run(tmp_path, run_id="second", resume_from="first")
    assert calls == []


def test_an_import_of_a_journal_that_cannot_be_read_says_so(tmp_path, monkeypatch):
    run_dir = run(tmp_path).run_dir
    unreadable(monkeypatch, layout.JOURNAL)
    with pytest.raises(RecordingError, match="cannot read"):
        import_recording(run_dir, tmp_path / "recordings")


def test_a_journal_that_cannot_be_read_at_the_end_leaves_the_run_unfinished(tmp_path, monkeypatch):
    @python_task(kind="last")
    def last(unit: str) -> Count:
        unreadable(monkeypatch, layout.JOURNAL)
        return Count(n=1)

    with pytest.raises(ContraagentError, match=r"cannot read .*journal\.jsonl"):
        run(tmp_path, lambda: last("a"))
    assert "finished_at" not in json.loads((tmp_path / "runs" / "r" / layout.RUN_INFO).read_text())


def test_a_journal_line_that_does_not_read_is_warned_of(tmp_path):
    run_dir = run(tmp_path).run_dir
    journal = run_dir / layout.JOURNAL
    first, second, third = journal.read_bytes().splitlines(keepends=True)
    journal.write_bytes(first + second[:30] + b"\n" + third)
    calls.clear()
    lines: list[str] = []
    assert run(tmp_path, lines=lines, resume=True).ok
    assert len(calls) == 1
    [warning] = [line for line in lines if "does not read" in line]
    assert warning.startswith("[error]") and "journal.jsonl line 2" in warning


def test_a_resume_from_warns_of_a_line_that_does_not_read(tmp_path):
    run_dir = run(tmp_path, run_id="first").run_dir
    with open(run_dir / layout.JOURNAL, "ab") as f:
        f.write(b"{broken\n")
    lines: list[str] = []
    assert run(tmp_path, lines=lines, run_id="second", resume_from="first").ok
    assert any("journal.jsonl line 4 does not read" in line for line in lines)


def test_a_journal_of_only_unreadable_lines_still_holds_a_run(tmp_path):
    run_dir = run(tmp_path).run_dir
    (run_dir / layout.JOURNAL).write_bytes(b"{broken\n{broken\n")
    calls.clear()
    with pytest.raises(RunExists):
        run(tmp_path)
    assert calls == []


# --- a write cut short costs its own line only -------------------------------------------


def test_the_row_after_a_torn_last_line_is_kept(tmp_path):
    run_dir = run(tmp_path).run_dir
    journal = run_dir / layout.JOURNAL
    os.truncate(journal, journal.stat().st_size - 20)
    calls.clear()
    lines: list[str] = []
    assert run(tmp_path, lines=lines, resume=True).ok
    assert len(calls) == 1 and len(keys(run_dir)) == 3
    assert any("journal.jsonl" in line and "cut short" in line for line in lines)
    calls.clear()
    assert run(tmp_path, resume=True).ok
    assert calls == []


def test_an_append_after_a_line_cut_short_starts_a_line_of_its_own(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_bytes(b'{"n": 1}\n{"n": ')
    lines, at = files.lines_at(log)  # a reader that keeps its place, as a relay does
    files.append_lines(log, ['{"n": 3}'])
    assert lines == ['{"n": 1}'] and files.lines_at(log, at)[0] == ['{"n": ', '{"n": 3}']
    files.append_lines(log, ['{"n": 4}'])
    assert log.read_bytes() == b'{"n": 1}\n{"n": \n{"n": 3}\n{"n": 4}\n'


@pytest.mark.skipif(sys.platform == "win32", reason="needs a file size limit (RLIMIT_FSIZE)")
def test_the_row_after_a_real_short_write_is_kept(tmp_path):
    # In a process of its own: the limit is the whole process's.
    script = """if True:
        import resource, sys
        from contraagent._internal.runs import files
        log = sys.argv[1]
        files.append_lines(log, ['{"n": 1}'])
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        resource.setrlimit(resource.RLIMIT_FSIZE, (14, hard))
        try:
            files.append_lines(log, ['{"n": 2}'])
        except OSError:
            pass
        else:
            sys.exit("the write was not cut short")
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
        files.append_lines(log, ['{"n": 3}'])
    """
    log = tmp_path / "log.jsonl"
    subprocess.run([sys.executable, "-c", script, str(log)], check=True)
    assert files.read_rows(log) == [{"n": 1}, {"n": 3}]


def test_a_launch_marker_after_a_transcript_cut_short_starts_a_line_of_its_own(tmp_path):
    stream = tmp_path / "s.jsonl"
    stream.write_bytes(b'{"type": "assist')
    launch = Launch(prompt="", cwd=tmp_path, limits=Limits(timeout_s=20), stream_path=stream)
    run_process([sys.executable, "-c", "print('hello')"], dict(os.environ), launch)
    assert json.loads(stream.read_bytes().splitlines()[1])["type"] == "launch"


# --- a record only the monitor reads never fails a task or a run -------------------------


@pytest.mark.parametrize(
    ("name", "folder", "times"),
    [
        (layout.PLAN, False, 3),
        (layout.FLOW_CALLS, False, 2),
        (layout.INFLIGHT, True, None),
        (layout.CONTRACTS, True, 3),
        (layout.DEFINITIONS, True, 1),
    ],
)
def test_a_record_of_the_monitor_that_cannot_be_written_is_counted_and_the_run_goes_on(tmp_path, name, folder, times):
    in_the_way = tmp_path / "runs" / "r" / name
    in_the_way.parent.mkdir(parents=True)
    if folder:
        in_the_way.write_text("a file where the folder goes")
    else:
        in_the_way.mkdir()
    lines: list[str] = []
    report = run(tmp_path, lines=lines)
    assert report.ok and len(calls) == 3
    failures = report.summary["record_failures"]
    assert list(failures) == [name]
    assert times is None or failures[name] == times
    assert any(line.startswith("[error]") and name in line and "not written" in line for line in lines)
    assert "finished_at" in json.loads((report.run_dir / layout.RUN_INFO).read_text())


def test_a_plan_write_that_fails_while_the_flow_runs_does_not_stop_it(tmp_path, monkeypatch):
    append = files.append_lines
    written = []

    def fills_up(path, lines, **kw):
        if Path(path).name == layout.PLAN:
            written.append(path)
            if len(written) > 1:
                raise OSError(errno.ENOSPC, "No space left on device")
        append(path, lines, **kw)

    monkeypatch.setattr("contraagent._internal.execution.run.append_lines", fills_up)

    async def flow():
        await count("x")
        await count("y")
        return (await count("z")).n

    report = run(tmp_path, flow)
    assert report.ok and report.value == 1 and calls == ["x", "y", "z"]
    assert report.summary["record_failures"] == {layout.PLAN: 2}


def test_a_deferral_that_cannot_be_written_does_not_stop_the_queue(tmp_path):
    run_ = Run("r", tmp_path, lock=False, log=lambda line: None)
    (run_.dir / layout.DEFERRED).mkdir()
    queue = run_.queue(run_.python_runner(), deadline_s=-1, grace_s=0)
    queue.add(make_python_task("late", lambda: None))
    queue.run()
    assert [task.key for task in queue.deferred] == ["python:late"]
    assert run_._record_failures() == {layout.DEFERRED: 1}


def test_a_service_event_that_cannot_be_written_is_counted(tmp_path):
    @python_task(kind="use", claims=["db"])
    def use(unit: str) -> Count:
        return Count(n=1)

    @contextlib.contextmanager
    def service(name: str):
        yield None

    (tmp_path / "runs" / "r" / layout.SERVICES).mkdir(parents=True)
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, services={"db": service}, log=lambda line: None)
    report = pipeline.run(lambda: use("a"), run_id="r")
    assert report.ok and report.summary["record_failures"][layout.SERVICES] >= 1


def test_a_transcript_that_cannot_be_opened_does_not_fail_the_task(tmp_path):
    (tmp_path / "runs" / "r" / layout.stream("note-a")).mkdir(parents=True)
    stub = StubAgent(default=writes_example())
    lines: list[str] = []
    report = run(tmp_path, lambda: note("a"), stub=stub, lines=lines)
    assert report.ok and [launch.key for launch in stub.launches] == ["note-a"]
    assert report.summary["record_failures"][layout.STREAMS] >= 1
    assert any("note-a.stream.jsonl not written" in line for line in lines)


def test_an_agent_runs_to_its_end_when_its_transcript_cannot_be_opened(tmp_path):
    (tmp_path / "s.jsonl").mkdir()
    launch = Launch(prompt="", cwd=tmp_path, limits=Limits(timeout_s=20), stream_path=tmp_path / "s.jsonl")
    out, _, code, killed = run_process([sys.executable, "-c", "print('finished')"], dict(os.environ), launch)
    assert (out.split(), code, killed) == ([b"finished"], 0, None)


@pytest.mark.skipif(sys.platform != "linux", reason="needs /dev/full")
def test_an_agent_runs_to_its_end_when_its_transcript_s_disk_is_full(tmp_path):
    done = tmp_path / "done"
    code = f"import time; print('one', flush=True); time.sleep(0.3); open({str(done)!r}, 'w').close(); print('two')"
    launch = Launch(prompt="", cwd=tmp_path, limits=Limits(timeout_s=20), stream_path=Path("/dev/full"))
    out, _, exit_code, killed = run_process([sys.executable, "-c", code], dict(os.environ), launch)
    assert (out, exit_code, killed) == (b"one\ntwo\n", 0, None) and done.exists()


def test_a_transcript_write_that_fails_ends_that_launch_s_part_with_no_gap(tmp_path, monkeypatch):
    write_all, writes = files.write_all, []

    def second_fails(fd, data):
        writes.append(data)
        if len(writes) == 2:
            raise OSError(errno.ENOSPC, "No space left on device")
        write_all(fd, data)

    monkeypatch.setattr(files, "write_all", second_fails)
    said: list[tuple[str, str]] = []
    stream = tmp_path / "s.jsonl"
    with failures.reported_to(lambda name, error, about, path: said.append((name, about))):
        transcript = Transcript(Launch(prompt="", label="note-a", cwd=tmp_path, stream_path=stream))
        for line in (b"one\n", b"two\n", b"three\n"):
            transcript.write(line)
        transcript.close()
    assert stream.read_bytes() == b"one\n" and said == [(layout.STREAMS, "note-a")]


def test_a_transcript_close_that_fails_does_not_raise(tmp_path, monkeypatch):
    said: list[str] = []
    with failures.reported_to(lambda name, error, about, path: said.append(name)):
        transcript = Transcript(Launch(prompt="", cwd=tmp_path, stream_path=tmp_path / "s.jsonl"))
        transcript.write(b"one\n")
        close = os.close

        def failing(fd):
            close(fd)
            raise OSError(errno.EIO, "Input/output error")

        with monkeypatch.context() as m:
            m.setattr(os, "close", failing)
            transcript.close()
    assert said == [layout.STREAMS]


def test_omp_rpc_reports_its_transcript_to_the_run_of_the_launch_s_thread(tmp_path):
    (tmp_path / "s.jsonl").mkdir()
    launch = Launch(prompt="", label="note-a", cwd=tmp_path, stream_path=tmp_path / "s.jsonl")
    proc = cast("Any", SimpleNamespace(stdout=io.StringIO("one\ntwo\n"), stderr=io.StringIO("")))
    said: list[tuple[str, str]] = []
    with failures.reported_to(lambda name, error, about, path: said.append((name, about))):
        frames, drain = OmpRpcBackend()._start_readers(proc, launch, [])
        got = [frames.get(timeout=10) for _ in range(3)]
    drain.join(10)
    assert got == [("line", "one\n"), ("line", "two\n"), ("eof", "")]
    assert said == [(layout.STREAMS, "note-a")]  # once for the launch, from the reader's thread


def test_a_replay_whose_transcript_cannot_be_written_plays_on(tmp_path):
    recordings = tmp_path / "recordings"
    stub = StubAgent(default=writes_example())
    recorded = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub, record=recordings, log=lambda line: None)
    assert recorded.run(lambda: note("a"), run_id="first").ok
    (tmp_path / "runs" / "second" / layout.stream("note-a")).mkdir(parents=True)
    replayed = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, replay=recordings, log=lambda line: None)
    report = replayed.run(lambda: note("a"), run_id="second")
    assert report.ok and report.summary["record_failures"] == {layout.STREAMS: 1}


# --- documents a resume rests on ---------------------------------------------------------


@pytest.mark.parametrize("text", ["", "{torn", "[]"])
def test_a_run_info_that_does_not_read_is_not_made_again(tmp_path, text):
    info = run(tmp_path).run_dir / layout.RUN_INFO
    info.write_text(text)
    calls.clear()
    for _ in range(2):  # the second time, too: the first let go of the run's lock
        with pytest.raises(ContraagentError, match=r"run\.json does not read"):
            run(tmp_path, resume=True)
    assert calls == [] and info.read_text() == text


def test_a_run_info_that_cannot_be_read_is_not_made_again(tmp_path, monkeypatch):
    info = run(tmp_path).run_dir / layout.RUN_INFO
    before = info.read_bytes()
    calls.clear()
    unreadable(monkeypatch, layout.RUN_INFO)
    with pytest.raises(ContraagentError, match=r"cannot read .*run\.json"):
        run(tmp_path, resume=True)
    assert calls == [] and info.read_bytes() == before


@pytest.mark.parametrize("text", ["", "\n", "{torn"])
def test_a_cursor_that_does_not_read_is_not_started_again(tmp_path, text):
    path = tmp_path / layout.CURSOR
    path.write_text(text)
    with pytest.raises(ValueError):
        CursorStore(path, "r").advance_stage("three")
    assert path.read_text() == text


def test_a_cursor_that_cannot_be_read_is_not_started_again(tmp_path, monkeypatch):
    cursor = CursorStore(tmp_path / layout.CURSOR, "r")
    cursor.advance_stage("one")
    before = cursor.path.read_bytes()
    unreadable(monkeypatch, layout.CURSOR)
    with pytest.raises(OSError):
        cursor.advance_stage("two")
    assert cursor.path.read_bytes() == before


# --- what is on disk when the power fails ------------------------------------------------


def flushes(monkeypatch, root: Path, journal: Path) -> list[tuple[str, int]]:
    """Each flush to disk, as it happens: the name the file has then under `root` (an inode
    number is used again once its file is gone), and the journal's size then."""
    seen: list[tuple[str, int]] = []

    def watched(real):
        def flush(fd):
            flushed = os.fstat(fd)
            for folder, _, names in os.walk(root):
                for path in (Path(folder, name) for name in names):
                    with contextlib.suppress(OSError):
                        if os.path.samestat(flushed, path.stat()):
                            seen.append((path.name, journal.stat().st_size if journal.exists() else 0))
            return real(fd)

        return flush

    for name in ("fsync", "fdatasync"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, watched(getattr(os, name)))
    return seen


def test_an_output_is_on_disk_before_the_row_that_says_it_is_ok(tmp_path, monkeypatch):
    journal = tmp_path / "runs" / "r" / layout.JOURNAL
    seen = flushes(monkeypatch, tmp_path, journal)
    report = run(tmp_path, lambda: count("a"))
    [output] = [p for p in (report.run_dir / layout.OUT).rglob("*.json") if p.is_file()]
    names = [name for name, _ in seen]
    assert (output.name, 0) in seen
    assert names.index(output.name) < names.index(layout.JOURNAL)
    assert any(name.startswith(".run.json.") for name in names)  # the file that then replaces it


def test_an_agent_s_output_is_on_disk_before_its_row(tmp_path, monkeypatch):
    journal = tmp_path / "runs" / "r" / layout.JOURNAL
    seen = flushes(monkeypatch, tmp_path, journal)
    report = run(tmp_path, lambda: note("a"), stub=StubAgent(default=writes_example()))
    [output] = [p for p in (report.run_dir / layout.OUT).rglob("*.json") if p.is_file()]
    assert (output.name, 0) in seen


def test_a_copied_output_is_on_disk_before_the_row_that_takes_it_over(tmp_path, monkeypatch):
    run(tmp_path, lambda: count("a"), run_id="first")
    journal = tmp_path / "runs" / "second" / layout.JOURNAL
    seen = flushes(monkeypatch, tmp_path, journal)
    report = run(tmp_path, lambda: count("a"), run_id="second", resume_from="first")
    [output] = [p for p in (report.run_dir / layout.OUT).rglob("*.json") if p.is_file()]
    assert calls == ["a"] and (output.name, 0) in seen


def test_a_cursor_is_on_disk_before_it_replaces_the_one_before(tmp_path, monkeypatch):
    seen = flushes(monkeypatch, tmp_path, tmp_path / "none")
    cursor = CursorStore(tmp_path / layout.CURSOR, "r")
    cursor.advance_stage("one")
    assert any(name.startswith(".cursor.json.") for name, _ in seen)


@pytest.mark.parametrize("code", sorted({errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS}))
def test_a_file_system_that_cannot_flush_does_not_fail_the_run(tmp_path, monkeypatch, code):
    def cannot(fd):
        raise OSError(code, os.strerror(code))

    for name in ("fsync", "fdatasync"):
        monkeypatch.setattr(os, name, cannot, raising=False)
    report = run(tmp_path)
    assert report.ok and "record_failures" not in report.summary


def test_a_flush_that_fails_is_a_journal_row_not_written(tmp_path, monkeypatch):
    journal = tmp_path / "runs" / "r" / layout.JOURNAL

    def failing(real):
        def flush(fd):
            if journal.exists() and os.path.samestat(os.fstat(fd), journal.stat()):
                raise OSError(errno.EIO, "Input/output error")
            return real(fd)

        return flush

    for name in ("fsync", "fdatasync"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, failing(getattr(os, name)))
    with pytest.raises(ContraagentError, match="journal row"):
        run(tmp_path, lambda: count("a"))
