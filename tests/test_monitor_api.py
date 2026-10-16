"""The monitor's HTTP contract: typed, published, compatible with the bundled UI, and local-only."""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from contraagent._internal.cli import main as cli_main
from contraagent._internal.monitor import api, server
from contraagent._internal.runs.names import BadName, check_name
from contraagent.backends import normalize_stream_line
from contraagent.monitor import Monitor, Panel


def client_for(monitor: Monitor, **kwargs) -> TestClient:
    return TestClient(server.create_app(monitor, **kwargs), base_url="http://127.0.0.1")


def raw(value) -> object:
    """What the core computed, as JSON: the wire before the contract existed."""
    return json.loads(json.dumps(value, default=str))


def test_every_endpoint_carries_what_the_core_computed(demo_runs):
    """The models are a description of the wire, not a change to it: each response
    equals the core's own dict (plus `api_version` on /api/info), so the bundled UI
    reads exactly what it read before."""
    mon = Monitor(demo_runs, panels={"notes": Panel(lambda r: {"run": r.id}, title="notes")})
    c = client_for(mon)
    info = c.get("/api/info").json()
    assert info == {"title": mon.title, "panels": raw(mon.panel_info()), "api_version": api.API_VERSION, "hosts": False}
    assert c.get("/api/runs").json() == raw(mon.runs())
    seen_streams = 0
    for run in [r["run"] for r in mon.runs()]:
        entries, total = mon.journal(run, 0)
        assert c.get(f"/api/runs/{run}/journal").json() == raw({"entries": entries, "total": total})
        for ep, want in (
            ("plan", mon.plan(run)),
            ("outputs", mon.outputs(run)),
            ("definitions", mon.definitions(run)),
            ("cursor", mon.cursor(run) or {}),
            ("procs", mon.procs(run)),
            ("panels/notes", mon.panel("notes", run)),
        ):
            assert c.get(f"/api/runs/{run}/{ep}").json() == raw(want), ep
        for key in {n["key"] for n in mon.plan(run)["nodes"]}:
            assert c.get(f"/api/runs/{run}/task/{key}").json() == raw(mon.task_detail(run, key))
        for f in sorted((demo_runs / run / "streams").glob("*.stream.jsonl")):
            key = f.name.removesuffix(".stream.jsonl")
            page, total = mon.stream(run, key, 0)
            got = c.get(f"/api/runs/{run}/stream/{key}").json()
            assert got == raw({**page, "total": total})
            assert got["events"]
            seen_streams += 1
    assert seen_streams


def test_the_demo_transcripts_parse_as_their_declared_events(demo_runs):
    mon = Monitor(demo_runs)
    page = TypeAdapter(api.StreamPage)
    kinds = set()
    for f in sorted((demo_runs / "docs" / "streams").glob("*.stream.jsonl")):
        events = page.validate_python(mon.stream("docs", f.name.removesuffix(".stream.jsonl"), 0)[0]).events
        assert not [e for e in events if isinstance(e, api.OtherEvent)]
        kinds |= {type(e).__name__ for e in events}
    assert {"LaunchEvent", "MessageUpdateEvent", "ToolStartEvent", "ToolEndEvent"} <= kinds


OMP = [
    ({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "hi"}}, api.MessageUpdateEvent),
    ({"type": "tool_execution_start", "toolName": "bash", "args": {"command": "ls"}, "toolCallId": "c1"}, api.ToolStartEvent),
    ({"type": "tool_execution_update", "toolName": "bash", "args": {}, "toolCallId": "c1"}, api.ToolStartEvent),
    ({"type": "tool_execution_end", "toolName": "bash", "result": {"content": [{"text": "ok"}]}, "toolCallId": "c1"}, api.ToolEndEvent),
    (
        {
            "type": "message_end",
            "message": {"role": "assistant", "content": [{"type": "toolCall", "name": "read", "arguments": {"path": "a"}, "id": "c2"}]},
        },
        api.ToolCallEchoEvent,
    ),
    (
        {
            "type": "message_end",
            "message": {"role": "toolResult", "toolName": "read", "toolCallId": "c2", "content": [{"type": "text", "text": "x"}]},
        },
        api.ToolResultEchoEvent,
    ),
    ({"type": "message_end", "message": {"role": "custom", "content": [{"type": "text", "content": "note"}]}}, api.NoticeEvent),
    ({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hm"}]}}, api.MessageEvent),
    ({"type": "message_start", "message": {"role": "user", "content": [{"type": "text", "text": "do it"}]}}, api.MessageEvent),
    ({"type": "turn_end", "message": {"content": [{"type": "thinking", "thinking": "done"}]}}, api.MessageEvent),
    ({"type": "auto_retry_start", "attempt": 2, "errorMessage": "429"}, api.RetryEvent),
    ({"type": "agent_start"}, api.OtherEvent),
    ({"type": "launch", "argv": ["omp"], "cwd": "/w", "prompt": "p", "ts": 1767225600.5}, api.LaunchEvent),
]
CLAUDE = [
    ({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}, api.MessageUpdateEvent),
    ({"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "hm"}]}}, api.MessageUpdateEvent),
    (
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "id": "t1", "input": {"command": "ls"}}]}},
        api.ToolStartEvent,
    ),
    ({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}, api.ToolEndEvent),
    ({"type": "system", "subtype": "init", "model": "m"}, api.NoticeEvent),
    ({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}}, api.NoticeEvent),
]


@pytest.mark.parametrize("format,raw_event,model", [("omp", e, m) for e, m in OMP] + [("claude", e, m) for e, m in CLAUDE])
def test_each_normalized_event_has_its_model(format, raw_event, model):
    [ev] = normalize_stream_line(format, json.dumps(raw_event))
    page = TypeAdapter(api.StreamPage)
    parsed = page.validate_python({"events": [ev], "total": 1, "behind": 0})
    assert type(parsed.events[0]) is model
    assert json.loads(page.dump_json(parsed, exclude_unset=True))["events"] == [ev]  # the wire is unchanged


def test_plain_text_and_custom_events_pass_through():
    [text] = normalize_stream_line("omp", "plain narration")
    odd = {"type": "message_update", "delta": None, "mine": 1}  # a custom normalizer's own idea
    parsed = TypeAdapter(api.StreamPage).validate_python({"events": [text, odd], "total": 2, "behind": 0})
    assert type(parsed.events[0]) is api.MessageUpdateEvent and type(parsed.events[1]) is api.OtherEvent
    assert parsed.model_dump(exclude_unset=True)["events"][1] == odd


def test_the_live_feed_says_when_the_journal_replay_is_over(demo_runs):
    """`ready` follows the first round: every journal row on disk, then every other view."""
    mon = Monitor(demo_runs)
    run = mon.runs()[0]["run"]

    async def first_round() -> list[dict[str, str]]:
        async def connected() -> bool:
            return False

        out = []
        async for msg in server.run_feed(mon, run, connected):
            out.append(msg)
            if msg["event"] == "ready":
                return out
        raise AssertionError("the feed ended")

    msgs = asyncio.run(first_round())
    names = [m["event"] for m in msgs]
    assert names.count("journal") == json.loads(msgs[-1]["data"])["journal"] == mon.journal(run)[1] > 0
    assert names.count("ready") == 1
    assert {"procs", "plan", "outputs", "cursor"} <= set(names)


def test_the_committed_openapi_document_is_current():
    committed = server.OPENAPI_FILE.read_text()
    assert committed == server.openapi_document(), (
        "openapi.json is stale: run `uv run contraagent monitor --openapi src/contraagent/_internal/monitor/openapi.json`"
    )


def test_the_contract_is_served_and_describes_the_live_feeds(tmp_path):
    c = client_for(Monitor(tmp_path))
    doc = c.get("/api/openapi.json").json()
    assert doc == json.loads(server.openapi_document())
    assert doc["info"]["version"] == api.API_VERSION == c.get("/api/info").json()["api_version"]
    sse = doc["paths"]["/events"]["get"]["responses"]["200"]["content"]["text/event-stream"]["schema"]
    assert sse == {"$ref": "#/components/schemas/RunEvent"}
    names = {m["$ref"].rsplit("/", 1)[-1] for m in doc["components"]["schemas"]["RunEvent"]["anyOf"]}
    assert names == {
        "JournalMessage",
        "ProcsMessage",
        "PlanMessage",
        "OutputsMessage",
        "CursorMessage",
        "PanelMessage",
        "ReadyMessage",
    }
    assert "StreamMessage" in doc["components"]["schemas"]
    assert c.get("/api/docs").status_code == 404  # interactive docs are opt-in
    assert client_for(Monitor(tmp_path), docs=True).get("/api/docs").status_code == 200


def test_openapi_flag_writes_the_document(tmp_path):
    out = tmp_path / "openapi.json"
    assert cli_main(["monitor", "--openapi", str(out)]) == 0
    assert out.read_text() == server.openapi_document()


# --- security ----------------------------------------------------------------


def test_no_other_origin_can_read_the_api(tmp_path):
    evil = {"Origin": "https://evil.example"}
    r = client_for(Monitor(tmp_path)).get("/api/runs", headers=evil)
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers
    dev = client_for(Monitor(tmp_path), cors_origins=["http://localhost:5173"])
    assert (
        dev.get("/api/runs", headers={"Origin": "http://localhost:5173"}).headers["access-control-allow-origin"] == "http://localhost:5173"
    )
    assert "access-control-allow-origin" not in dev.get("/api/runs", headers=evil).headers


def test_only_local_host_names_are_answered(tmp_path):
    app = server.create_app(Monitor(tmp_path))
    for base in ("http://127.0.0.1:8787", "http://localhost:8787", "http://[::1]:8787"):
        assert TestClient(app, base_url=base).get("/api/info").status_code == 200, base
    rebound = TestClient(app, base_url="http://attacker.example:8787")  # DNS rebinding: a page's own name
    assert rebound.get("/api/runs").status_code == 400
    assert rebound.get("/events?run=x").status_code == 400
    lan = server.create_app(Monitor(tmp_path), allowed_hosts=["box.lan"])
    assert TestClient(lan, base_url="http://box.lan").get("/api/info").status_code == 200


@pytest.fixture
def secret_layout(tmp_path):
    """runs/r1 is a real run; secret/ sits next to runs/ with files a traversal would read."""
    runs = tmp_path / "runs"
    (runs / "r1" / "streams").mkdir(parents=True)
    (runs / "r1" / "journal.jsonl").write_text("")
    secret = tmp_path / "secret"
    (secret / "streams").mkdir(parents=True)
    row = {"ts": "t", "key": "leak", "kind": "k", "stop": "completed", "ok": True}
    (secret / "journal.jsonl").write_text(json.dumps(row) + "\n")
    (secret / "streams" / "leak.stream.jsonl").write_text('{"type":"launch","argv":["SECRET"],"cwd":"","prompt":""}\n')
    (runs / "r1" / "streams" / "ok.stream.jsonl").write_text("")
    return runs


BAD_RUNS = ["..", ".hidden", "..%2Fsecret", "a..b", "%2E%2E"]


def test_traversal_is_refused_by_the_python_api(secret_layout):
    mon = Monitor(secret_layout)
    for call in (
        lambda: mon.stream("../secret", "leak", 0),
        lambda: mon.stream("r1", "../../secret/streams/leak", 0),
        lambda: mon.journal("../secret"),
        lambda: mon.plan("../secret"),
        lambda: mon.outputs(".."),
        lambda: mon.definitions(".."),
        lambda: mon.cursor("../secret"),
        lambda: mon.procs("../secret"),
        lambda: mon.task_detail("../secret", "leak"),
        lambda: mon.task_detail("r1", "../x"),
        lambda: mon.stream_size("r1", ".x"),
        lambda: mon.stream("r1", ".x", 0),
    ):
        with pytest.raises(ValueError):
            call()
    assert mon.stream("r1", "ok", 0)[0]["events"] == []
    assert mon.journal("r1") == ([], 0)


@pytest.mark.parametrize("bad", BAD_RUNS)
def test_traversal_is_refused_on_every_endpoint(secret_layout, bad):
    c = client_for(Monitor(secret_layout, panels={"p": lambda r: {"r": r.id}}))
    for ep in ("journal", "plan", "outputs", "definitions", "cursor", "procs", "task/leak", "stream/leak", "panels/p"):
        r = c.get(f"/api/runs/{bad}/{ep}")
        assert r.status_code == 404, (bad, ep, r.status_code)
        assert "SECRET" not in r.text and "leak" not in r.json().get("entries", [])
    assert c.get(f"/events?run={bad}").status_code == 404
    assert c.get(f"/events/stream?run={bad}&key=leak").status_code == 404


@pytest.mark.parametrize("bad", ["..%2F..%2Fsecret%2Fstreams%2Fleak", "..", ".leak", "a%2Fb", "x%5C..%5Cy"])
def test_traversal_through_a_task_key_is_refused(secret_layout, bad):
    c = client_for(Monitor(secret_layout))
    assert c.get(f"/events/stream?run=r1&key={bad}").status_code == 404
    for ep in ("stream", "task"):
        r = c.get(f"/api/runs/r1/{ep}/{bad}")
        assert r.status_code == 404 and "SECRET" not in r.text, (ep, bad)


def test_task_keys_keep_their_legitimate_characters():
    for key in ("python:prepare-alpha", "summarize-beta", "a_b.c@v2", "write_note-alpha"):
        assert check_name(key) == key
    for bad in ("", ".", "..", "a/b", "a\\b", "a..b", ".x", "a\0b", "a\nb"):
        with pytest.raises(BadName):
            check_name(bad)


# --- small items ---------------------------------------------------------------


def test_a_missing_extra_is_named_not_a_traceback(monkeypatch, capsys):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "uvicorn" else real(name, *a))
    assert cli_main(["monitor", "--runs-dir", "nowhere"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("contraagent monitor: ") and "contraagent[monitor]" in err and "uvicorn" in err
    with pytest.raises(ModuleNotFoundError, match=r"contraagent\[monitor\]"):
        server.create_app(Monitor("nowhere"))


def test_the_page_makes_no_third_party_requests():
    static = Path(server.STATIC)
    for f in static.iterdir():
        if f.suffix == ".png":  # an image requests nothing
            continue
        text = f.read_text()
        assert "googleapis" not in text and "gstatic" not in text, f.name


def test_the_plan_tells_the_failed_task_from_the_ones_it_stopped(demo_runs):
    """`prepare-zeta` raised; the summary refused for its missing output never ran."""
    state = {n["key"]: n["state"] for n in Monitor(demo_runs).plan("docs")["nodes"]}
    assert state["python:prepare-zeta"] == "failed"
    assert state["summarize-zeta"] == "blocked"
    assert state["review-gamma"] == "done"  # failed twice, then succeeded
    assert state["python:report"] == "done"


def test_a_task_shows_every_param_it_was_given(demo_runs):
    """A value from an earlier task is a param too (the call file has it; the contract record keeps scalars only)."""
    io = Monitor(demo_runs).task_detail("docs", "summarize-delta")["io"]
    assert io["params"]["prepared"]["unit"] == "delta"
    assert Monitor(demo_runs).task_detail("docs", "python:report")["io"]["params"] == {}


def test_the_run_list_counts_tasks_as_the_run_page_does(demo_runs):
    """31 tasks: 28 done, 1 partial (score-epsilon), 1 failed (prepare-zeta), 1 never started;
    33 journal rows, 1 of them never ran."""
    row = next(r for r in Monitor(demo_runs).runs() if r["run"] == "docs")
    assert row["tasks"] == {
        "total": 31,
        "done": 28,
        "partial": 1,
        "failed": 1,
        "not_started": 1,
        "running": 0,
        "waiting": 0,
        "not_run": 0,
        "skipped": 0,
    }
    assert (row["attempts"], row["not_run"]) == (33, 1)


def test_a_python_task_kind_records_its_function(demo_runs):
    """A Python task's definition is its function: where it is, what it takes and returns, its source."""
    d = next(x for x in Monitor(demo_runs).definitions("docs") if x["kind"] == "prepare")
    assert d["executor"] == "python" and d["function"].endswith("prepare")
    assert d["signature"] == "prepare(unit: str) -> contraagent.docs.examples.demo.tasks.Prepared"
    assert d["output"] == "Prepared" and d["file"].endswith("tasks.py") and d["line"] > 0
    assert "checked description of the input" in d["doc"]
    assert d["files"][0]["text"].lstrip().startswith("@python_task")


def test_the_run_list_says_how_the_subscription_went(demo_runs):
    """The demo's stub reports a rising 5-hour utilization; the run keeps its first and last reading."""
    row = next(r for r in Monitor(demo_runs).runs() if r["run"] == "docs")
    [account] = row["quota"]  # the demo runs on one credential
    assert account["credential"] == "ambient"
    first, last = account["first"], account["last"]
    assert first["observed_at"] <= last["observed_at"] and first["five_hour_pct"] < last["five_hour_pct"]
    assert row["cost_usd"] > 0 and row["tokens"]["calls"] > 0


def test_utilization_is_kept_per_account():
    """Two subscriptions (a pool): each account's readings stay apart; the one closest to its weekly limit first."""
    from contraagent._internal.monitor.core import _first_last

    def r(cred, at, week):
        return {"credential": cred, "observed_at": f"2026-10-11T00:00:0{at}+00:00", "seven_day_pct": week, "five_hour_pct": 10.0}

    accounts = _first_last([r("sub-a", 1, 40.0), r("sub-b", 2, 70.0), r("sub-a", 3, 42.0), r("sub-b", 4, 75.0)])["quota"]
    assert [(a["credential"], a["first"]["seven_day_pct"], a["last"]["seven_day_pct"]) for a in accounts] == [
        ("sub-b", 70.0, 75.0),
        ("sub-a", 40.0, 42.0),
    ]


def test_a_text_output_is_shown_as_its_text(demo_runs):
    notes = [o for r in Monitor(demo_runs).outputs("docs")["contracts"] for o in r["outputs"] if o["path"].endswith(".md")]
    written = [o["file"]["content"] for o in notes if o["file"]["exists"]]
    assert written and all(isinstance(c, str) and c.startswith("# ") for c in written)


def test_a_unitless_python_task_has_the_same_unit_everywhere(demo_runs):
    mon = Monitor(demo_runs)
    record = next(r for r in mon.outputs("docs")["contracts"] if r["key"] == "python:report")
    row = next(r for r in mon.journal("docs")[0] if r["key"] == "python:report")
    assert record["unit"] == row["unit"] == ""


def test_a_python_task_s_outputs_from_earlier_tasks_are_its_inputs_by_producer(demo_runs):
    record = next(r for r in Monitor(demo_runs).outputs("docs")["contracts"] if r["key"] == "python:report")
    # Given only outputs of earlier tasks: no param of its own, each output an input named by its producer.
    assert record["params"] == {}
    producers = {i["producer"] for i in record["inputs"]}
    assert {"summarize-alpha", "revise-gamma"} <= producers, producers  # a revision writes its summary's file
    alpha = next(i for i in record["inputs"] if i["producer"] == "summarize-alpha")
    assert alpha["path"].endswith("out/summarize/alpha.json")


# --- flow calls and origins ----------------------------------------------------


@pytest.fixture(scope="module")
def review_run(tmp_path_factory):
    """The review example on the stub agent: unit b is revised once (review-b~2)."""
    from contraagent import Pipeline
    from contraagent.docs.examples.review import flow as example
    from contraagent.testing import StubAgent

    def verdict(launch):
        return {"approved": launch.unit != "b" or launch.key.endswith("~2"), "note": "more"}

    agent = StubAgent(
        {"summarize": lambda launch: {"unit": launch.unit, "points": ["p"]}, "revise": lambda launch: launch.params["summary"]}
        | {"review": verdict}
    )
    runs = tmp_path_factory.mktemp("review") / "runs"
    examples = Path(example.__file__).resolve().parents[1]  # the run's working directory holds the flow's file
    rep = Pipeline(None, runs_dir=runs, backends=agent.backends(), cwd=examples, log=lambda line: None).run(example.docs, units=["a", "b"])
    assert rep.ok, rep.failed
    return runs


def test_the_plan_carries_each_tasks_origin_and_the_flow_calls(review_run):
    plan = client_for(Monitor(review_run)).get("/api/runs/docs/plan").json()
    nodes = {n["key"]: n for n in plan["nodes"]}
    module = "contraagent.docs.examples.review.flow"
    second = nodes["review-b~2"]
    assert [f["function"] for f in second["flow"]] == [f"{module}.docs", f"{module}.review_loop"]
    assert {f["file"] for f in second["flow"]} == {"review/flow.py"}  # relative to the run's working directory
    [loop] = second["flow"][1]["loops"]
    assert loop["pass"] == 2 and loop["line"] < second["flow"][1]["line"] and second["flow"][0]["loops"] == []
    assert (second["created_from"], second["flow_call"]) == (["revise-b"], "0.2")
    assert nodes["python:report"]["flow_call"] == "0" and nodes["python:report"]["created_from"] == ["review-a", "review-b~2"]
    calls = plan["flow_calls"]
    assert [(c["id"], c["parent"], c["function"], c["state"], c["error"]) for c in calls] == [
        ("0", None, f"{module}.docs", "returned", None),
        ("0.1", "0", f"{module}.review_loop", "returned", None),
        ("0.2", "0", f"{module}.review_loop", "returned", None),
    ]
    assert calls[0]["flow"] == [] and [(f["function"], f["file"], f["loops"]) for f in calls[1]["flow"]] == [
        (f"{module}.docs", "review/flow.py", [])
    ]


def test_journal_rows_carry_the_fingerprint_and_flow_call(review_run):
    entries = client_for(Monitor(review_run)).get("/api/runs/docs/journal").json()["entries"]
    row = next(e for e in entries if e["key"] == "review-b~2")
    assert len(row["fingerprint"]) == 64 and row["flow_call"] == "0.2"


def test_a_file_outside_the_runs_working_directory_is_served_as_recorded(review_run, tmp_path):
    run = tmp_path / "docs"
    run.mkdir()
    for name in ("plan.jsonl", "flow_calls.jsonl", "journal.jsonl"):
        (run / name).write_text((review_run / "docs" / name).read_text())
    (run / "run.json").write_text(json.dumps({"run_id": "docs", "cwd": str(tmp_path)}))
    plan = Monitor(tmp_path).plan("docs", live={})
    files = {f["file"] for n in plan["nodes"] for f in n["flow"]} | {f["file"] for c in plan["flow_calls"] for f in c["flow"]}
    assert len(files) == 1 and Path(files.pop()).is_absolute()


def test_a_run_whose_tasks_no_flow_created_has_no_flow_call(tmp_path):
    run = tmp_path / "byhand"
    run.mkdir()
    (run / "plan.jsonl").write_text(json.dumps({"key": "a", "kind": "a", "unit": "", "after": [], "executor": "agent"}) + "\n")
    plan = client_for(Monitor(tmp_path)).get("/api/runs/byhand/plan").json()
    assert plan["flow_calls"] == [] and "flow_call" not in plan["nodes"][0]  # an origin field it never had is absent


def test_the_live_feed_sends_the_plan_when_a_flow_call_ends(review_run, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "TICK_S", 0.01)
    run = tmp_path / "docs"
    run.mkdir()
    rows = (review_run / "docs" / "flow_calls.jsonl").read_text().splitlines()
    starts = [r for r in rows if json.loads(r)["event"] == "start"]
    (run / "flow_calls.jsonl").write_text("\n".join(starts) + "\n")
    (run / "plan.jsonl").write_text((review_run / "docs" / "plan.jsonl").read_text())
    mon = Monitor(tmp_path)

    async def feed() -> list[str]:
        async def connected() -> bool:
            return False

        states: list[str] = []
        async for msg in server.run_feed(mon, "docs", connected):
            if msg["event"] == "plan":
                plan = json.loads(msg["data"])
                states.append(plan["flow_calls"][0]["state"])
                looped = next(n for n in plan["nodes"] if n["key"] == "review-b~2")
                assert looped["flow"][1]["loops"][0]["pass"] == 2  # the wire's name, as in plan.jsonl
            if msg["event"] == "ready":
                with open(run / "flow_calls.jsonl", "a") as f:
                    f.write(json.dumps({"ts": "", "id": "0", "event": "end", "state": "raised", "error": "ValueError: no"}) + "\n")
            if len(states) == 2:
                return states
        raise AssertionError("the feed ended")

    assert asyncio.run(feed()) == ["running", "raised"]


def test_a_task_detail_is_one_task_key(demo_runs):
    """Two passes of one task are two tasks: review-gamma's detail holds none of review-gamma~2's rows."""
    mon = Monitor(demo_runs)
    first, second = mon.task_detail("docs", "review-gamma"), mon.task_detail("docs", "review-gamma~2")
    assert first["rows"] and {r["key"] for r in first["rows"]} == {"review-gamma"}
    assert second["rows"] and {r["key"] for r in second["rows"]} == {"review-gamma~2"}
    assert first["definition"]["kind"] == second["definition"]["kind"] == "review"


def test_a_pipelines_own_journal_columns_are_named_and_passed_through(tmp_path):
    """`Run(row_extras=)` columns reach the API as written, and the run and the task name them."""
    d = tmp_path / "r1"
    d.mkdir()
    done = {"kind": "write", "stop": "completed", "ok": True}
    rows = [
        {"ts": "2026-10-14T00:00:00+00:00", "key": "write-a", **done, "effect": "new"},
        {"ts": "2026-10-14T00:01:00+00:00", "key": "write-b", **done, "effect": "updated", "lines": 3},
    ]
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    client = client_for(Monitor(tmp_path))
    [summary] = client.get("/api/runs").json()
    assert summary["row_extras"] == ["effect", "lines"]
    page = client.get("/api/runs/r1/journal").json()
    assert [e.get("effect") for e in page["entries"]] == ["new", "updated"] and page["entries"][1]["lines"] == 3
    detail = client.get("/api/runs/r1/task/write-b").json()
    assert detail["row_extras"] == ["effect", "lines"]
    assert client.get("/api/runs/r1/task/write-a").json()["row_extras"] == ["effect"]
