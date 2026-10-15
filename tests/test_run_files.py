"""`contraagent._internal.runs`: a run document is replaced whole, never seen in part; a log is
appended whole and read by complete lines; one file name per task key; one time format."""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import pytest

import contraagent
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import append_lines, lines_at, parse_rows, read_lines, read_rows, seek_line, write_document
from contraagent._internal.runs.times import iso_of, now_iso, parse_iso


def test_write_document_replaces_whole_and_leaves_no_temporary(tmp_path: Path):
    path = tmp_path / "run.json"
    path.write_text('{"old": true, "padding": "' + "x" * 1000 + '"}')
    assert write_document(path, '{"new": 1}') == path
    assert json.loads(path.read_text()) == {"new": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["run.json"]


def test_write_document_keeps_no_temporary_when_the_replace_fails(tmp_path: Path):
    (tmp_path / "x.json").mkdir()  # a folder in the way: the replace fails
    with pytest.raises(OSError):
        write_document(tmp_path / "x.json", "{}")
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_concurrent_writers_end_with_one_valid_document(tmp_path: Path):
    path = tmp_path / "doc.json"
    barrier = threading.Barrier(8)

    def writer(n: int) -> None:
        barrier.wait()
        for i in range(50):
            write_document(path, json.dumps({"writer": n, "i": i, "body": "y" * 4000}))

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    doc = json.loads(path.read_text())
    assert doc["i"] == 49 and len(doc["body"]) == 4000
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]


def test_a_reader_listing_json_never_sees_a_temporary_or_a_part(tmp_path: Path):
    folder = tmp_path / layout.CONTRACTS
    folder.mkdir()
    stop = threading.Event()
    errors: list[str] = []

    def writer(n: int) -> None:
        i = 0
        while not stop.is_set():
            write_document(folder / f"t{n % 3}.json", json.dumps({"n": n, "i": i, "body": "z" * 4000}))
            i += 1

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    try:
        for _ in range(300):
            for p in folder.glob("*.json"):
                if not p.name.startswith("t"):
                    errors.append(f"listed {p.name}")
                    continue
                try:
                    doc = json.loads(p.read_text())
                except ValueError as e:
                    errors.append(f"{p.name}: {e}")
                    continue
                if len(doc["body"]) != 4000:
                    errors.append(f"{p.name}: partial body")
    finally:
        stop.set()
        for t in threads:
            t.join()
    assert errors == []
    assert sorted(p.name for p in folder.iterdir()) == ["t0.json", "t1.json", "t2.json"]


#: The modules that write run records: documents (`run.json`, `cursor.json`, `contracts/`,
#: `definitions/`, `calls/`, `inflight/`, `pipeline/`) and logs; and a hub's and a relay's own files.
WRITERS = (
    "execution/run.py",
    "execution/journal.py",
    "execution/cursor.py",
    "execution/pipeline_files.py",
    "backends/launch.py",
    "contracts/contract.py",
    "contracts/calls.py",
    "execution/runner.py",
    "execution/python_tasks.py",
    "pipeline/adapter.py",
    "hub/relay.py",
    "hub/store.py",
    "hub/segment_objects.py",
)


def test_writers_of_run_records_go_through_write_document_and_append_lines():
    root = Path(contraagent.__file__).parent / "_internal"
    direct: list[str] = []
    for name in WRITERS:
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                attr, owner = node.func.attr, node.func.value
                if attr in ("write_text", "write_bytes") or (
                    attr in ("replace", "rename") and isinstance(owner, ast.Name) and owner.id == "os"
                ):
                    direct.append(f"{name}:{node.lineno} {attr}")
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and ("a" in mode.value or "w" in mode.value):
                    direct.append(f"{name}:{node.lineno} open {mode.value!r}")
    assert direct == []


# --- logs: appended whole, read by complete lines ----------------------------------------


def test_lines_are_read_by_byte_offset_and_a_last_line_without_its_newline_waits(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_bytes("a\nbé\n".encode() + b"c" * 100 + b"\nd")
    assert lines_at(path, 0) == (["a", "bé"] + ["c" * 100], 107)
    assert lines_at(path, 0, max_lines=1) == (["a"], 2)
    assert lines_at(path, 0, max_bytes=4) == (["a"], 2)
    assert lines_at(path, 2, max_bytes=4) == (["bé"], 6)
    assert lines_at(path, 6, max_bytes=4) == (["c" * 100], 107)  # a longer line goes alone
    assert lines_at(path, 107) == ([], 107)  # "d" has no newline yet
    assert seek_line(path, 0) == (0, 0) and seek_line(path, 2) == (2, 6) and seek_line(path, 9) == (3, 107)
    assert read_lines(path) == (["a", "bé", "c" * 100], 3)
    assert read_lines(path, 1, 1) == (["bé"], 3)
    assert read_lines(path, 1, max_bytes=1) == (["bé"], 3)  # at least one line
    assert read_lines(path, 3) == ([], 3) and read_lines(path, 7) == ([], 3)
    assert read_lines(path, 0, 0) == ([], 3)


def test_a_line_breaks_at_a_newline_only(tmp_path):
    path = tmp_path / "log.jsonl"
    row = {"text": "one two\rthree\x0bfour"}
    path.write_bytes(json.dumps(row, ensure_ascii=False).encode() + b"\n" + b'{"b": "\xff"}\n')
    assert read_rows(path) == [row, {"b": "�"}]


def test_rows_skip_a_torn_line_and_a_value_that_is_not_an_object():
    assert parse_rows(['{"a": 1}', '{"a": 2', "[1, 2]", "3", '{"b": 3}']) == [{"a": 1}, {"b": 3}]


def test_appended_lines_are_never_split_by_another_writer(tmp_path):
    path = tmp_path / "log.jsonl"
    barrier = threading.Barrier(8)

    def writer(n: int) -> None:
        barrier.wait()
        for i in range(100):
            append_lines(path, [json.dumps({"n": n, "i": i, "body": "x" * 3000}), json.dumps({"n": n, "i": i, "second": True})])

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = read_rows(path)
    assert len(rows) == 1600
    assert all(b["n"] == a["n"] and b["i"] == a["i"] and b.get("second") for a, b in zip(rows[::2], rows[1::2], strict=True))


# --- names --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "name"),
    [
        ("summarize-alpha", "summarize-alpha"),
        ("python:prepare-alpha", "python_prepare-alpha"),
        ("review-a~2", "review-a_2"),
        ("x/../y", "x____y"),
        (".hidden", "_hidden"),
        ("a@h.1", "a_h.1"),
    ],
)
def test_a_task_key_has_one_file_name_in_every_folder(key, name):
    assert layout.file_name(key) == name
    assert layout.stream(key) == f"streams/{name}.stream.jsonl"
    assert layout.stream_name(layout.stream(key)) == name
    folders = (layout.CONTRACTS, layout.CALLS, layout.INFLIGHT)
    assert [layout.task_entry(f, key) for f in folders] == [f"{f}/{name}.json" for f in folders]


def test_a_contract_path_is_relative_to_the_run_cwd():
    assert layout.file_path("out/a.json", "/w") == Path("/w/out/a.json")
    assert layout.file_path("/abs/a.json", "/w") == Path("/abs/a.json")
    assert layout.file_path("out/a.json", None) == Path("out/a.json")
    records = [json.dumps({"outputs": [{"path": "out/a.json"}], "inputs": [{"path": "in/b.json"}, {"path": "out/a.json"}]}), "{torn"]
    assert layout.contract_paths(records) == ["out/a.json", "in/b.json"]


# --- times --------------------------------------------------------------------------------


def test_times_are_written_in_utc_and_read_back_with_a_zone():
    assert iso_of(0) == "1970-01-01T00:00:00+00:00"
    assert iso_of(0.5, "milliseconds") == "1970-01-01T00:00:00.500+00:00"
    assert now_iso().endswith("+00:00") and len(now_iso()) == 25
    at = parse_iso("2026-10-15T09:30:00Z")
    assert at is not None and at.utcoffset() is not None and at == parse_iso("2026-10-15T09:30:00")
    assert parse_iso("2026-10-15T18:30:00+09:00") == at
    assert parse_iso("") is None and parse_iso("yesterday") is None and parse_iso(None) is None


def test_every_writer_of_a_task_file_names_it_by_file_name(tmp_path):
    from contraagent import Task
    from contraagent._internal.pipeline.adapter import SpecAdapter

    task = Task("review", unit="a", key="review-a~2")
    assert SpecAdapter("r1", tmp_path).call_path(task) == tmp_path / layout.task_entry(layout.CALLS, task.key)
    assert layout.task_entry(layout.CALLS, task.key) == "calls/review-a_2.json"
