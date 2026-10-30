"""Codex's tokens, read from recordings of a real codex (`codex exec --json` and its rollout file).

`tests/fixtures/codex/<version>/` holds a launch (`json.jsonl`), a launch that resumed its
thread (`resume.jsonl`) and the thread's rollout file after both (`rollout.jsonl`), slimmed
by `fixtures/codex/record.py`. A newer codex gets a new directory recorded the same way;
the tests run on every recording. The rollout file is codex's own: each test that takes it
away or changes its form checks that the tokens do not quietly become 0.
"""

import json
from pathlib import Path

import pytest

from contraagent._internal.backends.codex.wire import TOKEN_KEYS, EventReader, read_rollout
from contraagent._internal.contracts.contract import fold_spend
from contraagent.backends import Launch, LaunchResult, Stop

FIXTURES = Path(__file__).parent / "fixtures" / "codex"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="gpt-5.6-luna")
#: `EventReader.earlier` of a launch that started its thread.
NEW_THREAD: dict = {}


def events(version: str, name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / f"{name}.jsonl").read_text().splitlines() if line.strip()]


def turn_usage(version: str, name: str) -> dict:
    return next(e["usage"] for e in events(version, name) if e["type"] == "turn.completed")


def rollout_lines(version: str) -> list[bytes]:
    return (FIXTURES / version / "rollout.jsonl").read_bytes().splitlines(keepends=True)


def first_launch_end(version: str) -> int:
    """The rollout's size when the first launch ended: where the resumed launch reads from."""
    end = 0
    for line in rollout_lines(version):
        end += len(line)
        if json.loads(line).get("payload", {}).get("type") == "task_complete":
            return end
    raise AssertionError("the recording has no task_complete")


def is_call(ev: dict) -> bool:
    return ev.get("type") == "event_msg" and ev.get("payload", {}).get("type") == "token_count"


def first_rollout(version: str, tmp_path: Path, change=lambda ev, calls: ev) -> Path:
    """The rollout as the first launch left it, with `change(line, calls so far)` applied to
    each line (None drops it)."""
    out, calls, size = [], 0, 0
    for line in rollout_lines(version):
        size += len(line)
        if size > first_launch_end(version):
            break
        ev = json.loads(line)
        calls += is_call(ev)
        new = change(ev, calls)
        if new is not None:
            out.append(json.dumps(new) + "\n")
    path = tmp_path / "rollout.jsonl"
    path.write_text("".join(out), encoding="utf-8", newline="\n")
    return path


def read(evs: list[dict], *, rollout=None, earlier: dict | None = NEW_THREAD) -> LaunchResult:
    reader = EventReader()
    reader.earlier = earlier
    for e in evs:
        reader.feed(e)
    reader.rollout = rollout
    return reader.result(LAUNCH, "codex", exit_code=0, killed=None)


def totals(r: LaunchResult) -> tuple[int, int]:
    return sum(c.context for c in r.usage.calls), sum(c.output for c in r.usage.calls)


def turn_totals(usage: dict) -> tuple[int, int]:
    return usage["input_tokens"], usage["output_tokens"]


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_takes_each_call_from_the_rollout(version, tmp_path):
    r = read(events(version, "json"), rollout=read_rollout(first_rollout(version, tmp_path)))
    assert r.stop is Stop.COMPLETED and r.ok and r.result_text == "done"
    assert r.tool_uses == {"command_execution": 2} and r.unread_events == {}, "codex sends events this reader does not know"
    assert r.usage_unknown == "" and len(r.usage.calls) == 3 and r.num_turns == 3
    assert totals(r) == turn_totals(turn_usage(version, "json")), "the calls add up to the printed totals"
    assert r.context_window and r.quota and r.cli_version == version and r.init_model == LAUNCH.model


@pytest.mark.parametrize("version", VERSIONS)
def test_a_launch_with_no_rollout_keeps_the_printed_totals_and_says_so(version):
    r = read(events(version, "json"))
    assert r.usage_unknown == "calls" and r.ok
    assert len(r.usage.calls) == 1 and totals(r) == turn_totals(turn_usage(version, "json"))
    assert r.quota == [] and r.context_window is None


@pytest.mark.parametrize("version", VERSIONS)
def test_a_resumed_launch_reads_its_own_calls_from_where_the_rollout_was(version):
    rollout = read_rollout(FIXTURES / version / "rollout.jsonl", first_launch_end(version))
    r = read(events(version, "resume"), rollout=rollout, earlier=turn_usage(version, "json"))
    assert r.usage_unknown == "" and len(r.usage.calls) == 1
    # The printed totals are the thread's: the first launch's are in them.
    earlier, now = turn_usage(version, "json"), turn_usage(version, "resume")
    assert totals(r) == (now["input_tokens"] - earlier["input_tokens"], now["output_tokens"] - earlier["output_tokens"])
    # With the earlier totals unknown (another process launched them), the rollout's calls stand.
    assert read(events(version, "resume"), rollout=rollout, earlier=None).usage.calls == r.usage.calls


@pytest.mark.parametrize("version", VERSIONS)
def test_a_resumed_launch_with_no_rollout_counts_only_its_own_tokens(version):
    earlier, now = turn_usage(version, "json"), turn_usage(version, "resume")
    r = read(events(version, "resume"), earlier=earlier)
    assert r.usage_unknown == "calls"
    assert totals(r) == (now["input_tokens"] - earlier["input_tokens"], now["output_tokens"] - earlier["output_tokens"])
    # Earlier totals unknown: the thread's totals stand, more than the launch spent and never 0.
    r = read(events(version, "resume"), earlier=None)
    assert r.usage_unknown == "calls" and totals(r) == turn_totals(now)


def rename_token_counts(ev: dict, calls: int) -> dict:
    return {**ev, "payload": {**ev["payload"], "type": "token_usage"}} if is_call(ev) else ev


def drop_second_call(ev: dict, calls: int) -> dict | None:
    """A rollout rewritten under a resumed launch's offset loses a line: here, the second call."""
    return None if is_call(ev) and calls == 2 else ev


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize(
    "change",
    [
        pytest.param(rename_token_counts, id="token-counts-renamed"),
        pytest.param(lambda ev, calls: {**ev, "type": f"v2_{ev.get('type')}"}, id="every-line-renamed"),
        pytest.param(lambda ev, calls: {"kind": ev.get("type"), "body": ev.get("payload")}, id="no-payload"),
        pytest.param(drop_second_call, id="a-call-missing"),
    ],
)
def test_a_rollout_in_another_form_does_not_make_the_tokens_0(version, change, tmp_path):
    rollout = read_rollout(first_rollout(version, tmp_path, change))
    r = read(events(version, "json"), rollout=rollout)
    assert r.usage_unknown == "calls"
    assert totals(r) == turn_totals(turn_usage(version, "json")) and totals(r)[0] > 0


def test_a_rollout_that_is_gone_or_unreadable_reads_as_none(tmp_path):
    assert not read_rollout(tmp_path / "missing.jsonl").known
    (tmp_path / "bad.jsonl").write_bytes(b"\xff\xfe not json\n[1, 2]\n")
    assert not read_rollout(tmp_path / "bad.jsonl").known


@pytest.mark.parametrize("version", VERSIONS)
def test_a_launch_that_printed_no_totals_and_left_no_rollout_has_unknown_tokens(version):
    """Killed in its turn: no `turn.completed`, and codex kept no rollout."""
    cut = [e for e in events(version, "json") if e["type"] != "turn.completed"]
    r = read(cut)
    assert r.usage_unknown == "tokens" and r.usage.calls == []
    # Before any turn started nothing was spent: nothing is unknown.
    assert read(cut[:1]).usage_unknown == ""


def test_printed_totals_that_are_not_numbers_are_unknown_tokens():
    evs = [
        {"type": "thread.started", "thread_id": "t"},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": {"input_tokens": "x"}},
    ]
    r = read(evs)
    assert r.usage_unknown == "tokens" and r.usage.calls == []


@pytest.mark.parametrize("version", VERSIONS)
def test_the_token_keys_are_the_ones_codex_prints(version):
    assert set(TOKEN_KEYS) <= set(turn_usage(version, "json"))


@pytest.mark.parametrize(
    ("first", "second", "folded"),
    [("", "", ""), ("calls", "", "calls"), ("", "calls", "calls"), ("tokens", "calls", "tokens"), ("calls", "tokens", "tokens")],
)
def test_an_attempts_unknown_usage_is_the_most_of_its_launches(first, second, folded):
    a = LaunchResult(label="t", usage_unknown=first)
    b = LaunchResult(label="t", usage_unknown=second)
    assert fold_spend(a, b, resumed=True).usage_unknown == folded
