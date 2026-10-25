"""The monitor's algorithms give what they gave before they were made faster: the plan's
levels (with no recursion, for a chain of any length) and its blocked tasks, against the
earlier recursive and fixed-point forms on random graphs; a log read on from where the
last read ended, against a read of the whole log; a file's view from its start alone,
against one from the whole file; and one scan of the host's processes for every run."""

import json
import random

import pytest

from contraagent._internal.monitor import core
from contraagent._internal.runs.files import parse_rows
from contraagent._internal.runs.procs import ProcLiveness
from contraagent.monitor import DirectorySource, Monitor, RunFile


def old_levels(nodes, by_key):
    depth: dict[str, int] = {}

    def level(key, trail=()):
        if key in depth:
            return depth[key]
        after = core._earlier(by_key.get(key, {}))
        deps = [d for d in after if d in by_key and d not in trail]
        floor = 0 if any(d not in by_key for d in after) else -1
        depth[key] = 1 + max((level(d, trail + (key,)) for d in deps), default=floor)
        return depth[key]

    return {n["key"]: level(n["key"]) for n in nodes}


def old_blocked(nodes, by_key):
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n["state"] == "pending" and any(by_key.get(d, {}).get("state") in ("failed", "blocked") for d in n["after"]):
                n["state"], changed = "blocked", True


def random_dag(rng, n):
    keys = [f"t{i}" for i in range(n)]
    nodes = []
    for i, key in enumerate(keys):
        earlier = keys[:i]
        after = rng.sample(earlier, min(len(earlier), rng.randint(0, 3)))
        given = rng.sample(earlier, min(len(earlier), rng.randint(0, 2)))
        if rng.random() < 0.1:
            after.append("not-queued")
        state = rng.choice(["pending", "pending", "pending", "done", "failed", "blocked", "running"])
        nodes.append({"key": key, "after": after, "given_from": given, "state": state})
    rng.shuffle(nodes)  # any order: dependents may come first
    return nodes


@pytest.mark.parametrize("seed", range(40))
def test_levels_and_blocked_tasks_are_those_of_the_earlier_forms(seed):
    rng = random.Random(seed)
    nodes = random_dag(rng, rng.randint(1, 60))
    by_key = {n["key"]: n for n in nodes}
    assert core._levels(nodes, by_key) == old_levels(nodes, by_key)
    copy = [dict(n) for n in nodes]
    old_blocked(copy, {n["key"]: n for n in copy})
    core._block_behind(nodes)
    assert [n["state"] for n in nodes] == [n["state"] for n in copy]


def test_a_chain_of_any_length_has_its_levels(tmp_path):
    nodes = [{"key": f"t{i}", "after": [f"t{i - 1}"] if i else []} for i in range(5000)]
    nodes.reverse()  # each comes before the task it waits for
    depth = core._levels(nodes, {n["key"]: n for n in nodes})
    assert depth["t0"] == 0 and depth["t4999"] == 4999


def write_log(path, lines):
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def test_a_log_read_on_is_the_log_read_whole(tmp_path):
    runs = tmp_path / "runs"
    (runs / "r").mkdir(parents=True)
    (runs / "r" / "run.json").write_text(json.dumps({"run_id": "r", "run_uid": "u", "format": 1}), encoding="utf-8")
    log = runs / "r" / "journal.jsonl"
    rows = [json.dumps({"key": f"k{i}", "ts": str(i)}) for i in range(5)]
    write_log(log, [rows[0], "not json", rows[1]])
    monitor = Monitor(runs)
    assert monitor.journal("r") == (parse_rows([rows[0], rows[1]]), 3)
    with log.open("a", encoding="utf-8") as f:
        f.write(rows[2] + "\n" + rows[3][:5])  # its last line not yet whole
    assert monitor.journal("r", 3) == (parse_rows([rows[2]]), 4)
    assert monitor._read_journal("r") == parse_rows([rows[0], rows[1], rows[2]])
    with log.open("a", encoding="utf-8") as f:
        f.write(rows[3][5:] + "\n")
    assert monitor.journal("r", 3) == (parse_rows([rows[2], rows[3]]), 5)
    write_log(log, [rows[4], rows[4], rows[4], rows[4], rows[4], rows[4]])  # another log, no shorter
    assert monitor._read_journal("r") == parse_rows([rows[4]] * 6)


@pytest.mark.parametrize(
    "content",
    [
        b'{"a": 1}',
        json.dumps({"text": "x" * 30_000}).encode(),
        ("é" * 25_000).encode(),
        ("日本語" * 9_000).encode(),
        b"\xff\xfe binary",
        ("x" * 100_000).encode() + b"\xff",
        b"\n".join(json.dumps({"n": i}).encode() for i in range(3000)),
    ],
)
def test_a_file_s_view_from_its_start_is_its_view_from_the_whole_file(tmp_path, content):
    runs = tmp_path / "runs"
    (runs / "r").mkdir(parents=True)
    (runs / "r" / "run.json").write_text(json.dumps({"run_id": "r", "cwd": str(tmp_path), "format": 1}), encoding="utf-8")
    (tmp_path / "out.json").write_bytes(content)
    monitor = Monitor(runs)
    for rows in (False, True):
        fast = monitor._file_view("r", "out.json", rows=rows)
        whole = Monitor(runs, source=_WholeFiles(runs))._file_view("r", "out.json", rows=rows)
        assert fast == whole


class _WholeFiles:
    """A source that reads files whole, as any `RunSource` but a directory does."""

    def __init__(self, root) -> None:
        self._inner = DirectorySource(root)

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def file(self, run: str, path: str) -> RunFile | None:
        return self._inner.file(run, path)


def test_the_live_runs_share_one_scan_of_the_host(tmp_path, monkeypatch):
    from contraagent._internal.runs import procs

    scans: list[int] = []
    monkeypatch.setattr(procs, "_scan", lambda: scans.append(1) or {})
    monkeypatch.setattr(procs, "is_alive", lambda info: True)
    runs = tmp_path / "runs"
    for run in ("a", "b"):
        (runs / run).mkdir(parents=True)
        (runs / run / "run.json").write_text(json.dumps({"run_id": run, "pid": 1, "format": 1}), encoding="utf-8")
    liveness = ProcLiveness(runs)
    first = liveness.snapshot("a")
    assert liveness.snapshot("a") is first
    liveness.snapshot("b")
    assert len(scans) == 1
    (runs / "a" / "run.json").write_text(json.dumps({"run_id": "a", "pid": 1, "format": 1, "finished_at": "x"}), encoding="utf-8")
    assert liveness.snapshot("a") is not first  # its run.json changed: seen at once
