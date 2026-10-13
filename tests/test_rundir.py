"""`rundir.write_document`: a run document is replaced whole, never seen in part."""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import pytest

import contraagent
from contraagent import rundir


def test_write_document_replaces_whole_and_leaves_no_temporary(tmp_path: Path):
    path = tmp_path / "run.json"
    path.write_text('{"old": true, "padding": "' + "x" * 1000 + '"}')
    assert rundir.write_document(path, '{"new": 1}') == path
    assert json.loads(path.read_text()) == {"new": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["run.json"]


def test_write_document_keeps_no_temporary_when_the_replace_fails(tmp_path: Path):
    (tmp_path / "x.json").mkdir()  # a folder in the way: the replace fails
    with pytest.raises(OSError):
        rundir.write_document(tmp_path / "x.json", "{}")
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_concurrent_writers_end_with_one_valid_document(tmp_path: Path):
    path = tmp_path / "doc.json"
    barrier = threading.Barrier(8)

    def writer(n: int) -> None:
        barrier.wait()
        for i in range(50):
            rundir.write_document(path, json.dumps({"writer": n, "i": i, "body": "y" * 4000}))

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    doc = json.loads(path.read_text())
    assert doc["i"] == 49 and len(doc["body"]) == 4000
    assert [p.name for p in tmp_path.iterdir()] == ["doc.json"]


def test_a_reader_listing_json_never_sees_a_temporary_or_a_part(tmp_path: Path):
    folder = tmp_path / rundir.CONTRACTS
    folder.mkdir()
    stop = threading.Event()
    errors: list[str] = []

    def writer(n: int) -> None:
        i = 0
        while not stop.is_set():
            rundir.write_document(folder / f"t{n % 3}.json", json.dumps({"n": n, "i": i, "body": "z" * 4000}))
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


#: The modules that write run documents (`run.json`, `contracts/`, `definitions/`, `calls/`, `inflight/`).
WRITERS = (
    "execution/run.py",
    "contracts.py",
    "calls.py",
    "execution/runner.py",
    "execution/python_tasks.py",
    "pipeline/adapter.py",
)


def test_writers_of_run_documents_go_through_write_document():
    root = Path(contraagent.__file__).parent
    direct: list[str] = []
    for name in WRITERS:
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr, owner = node.func.attr, node.func.value
            if attr in ("write_text", "write_bytes") or (
                attr in ("replace", "rename") and isinstance(owner, ast.Name) and owner.id == "os"
            ):
                direct.append(f"{name}:{node.lineno} {node.func.attr}")
    assert direct == []
