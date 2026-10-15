"""Run the demo pipeline and watch it in the monitor.

    python -m contraagent.docs.examples.demo.run                    # demo agent, ~40s; serves the monitor too
    python -m contraagent.docs.examples.demo.run --real claude      # the same flow on a real `claude -p`
    python -m contraagent.docs.examples.demo.run --no-serve         # only write demo-runs/docs
    python -m contraagent.docs.examples.demo.run --no-serve --fast  # short pauses (what the tests run)

It writes `inputs/` and `demo-runs/` in the current directory.

Open http://127.0.0.1:8787 while it runs. With the demo agent:

* `beta`'s summary is rate limited on its primary model and fails over to the fallback hop;
* `delta`'s summary has two points first: the `three_points` validator sends it back
  into the same session, and the second round passes;
* `alpha`'s note has no heading first: the `heading` linter sends it back;
* `gamma`'s first review fails twice before it succeeds (retries), and does not
  approve: its summary is revised, scored and reviewed again (pass 2);
* `epsilon`'s `score` is partial: its word counter is unavailable, so its figures are a
  placeholder; the review runs on them, and a resume would score it again;
* `zeta`'s `prepare` raises: its summary is refused before launch, so its review
  loop ends there, and the report covers the other units.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from contraagent import Overrides, Pipeline
from contraagent.backends import Backend, CallFile, CallUsage, LaunchResult, QuotaRefusal, Stop, Usage
from contraagent.config import QuotaReading
from contraagent.docs.examples.demo.tasks import docs
from contraagent.monitor import Panel, RunRecords

HERE = Path(__file__).resolve().parent

UNITS = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")


class DemoAgent(Backend):
    """Plays a coding agent for showing the monitor: reads its call file, streams a
    lifelike transcript with token usage and quota readings, writes the output.
    Tests script replies with `contraagent.testing.StubAgent` instead."""

    name, binary = "stub", "stub"

    def __init__(self, pace: float = 1.0):
        super().__init__()
        self.pace = pace  # 0: no pauses between transcript events
        self.rounds: dict[str, int] = {}
        self.used = 12.0  # a subscription's 5-hour utilization (%), as the account goes
        now = datetime.now(UTC)
        self.resets = tuple((now + timedelta(hours=h)).isoformat(timespec="seconds") for h in (3, 5 * 24 + 2))
        self._lock = threading.Lock()

    def argv(self, launch):
        return ["stub", "-p", "--model", launch.model or "demo-model", "--agent", launch.role or "-"]

    def env(self, launch):
        return {}

    def run(self, launch):
        started = time.monotonic()
        started_at = datetime.now(UTC).isoformat(timespec="seconds")
        call_path = CallFile.path_of(launch)
        assert call_path is not None, "every launch of the demo is an agent task's"
        call = CallFile.read(call_path)
        with self._lock:
            n = self.rounds[launch.label] = self.rounds.get(launch.label, 0) + 1
        stream = Path(launch.stream_path) if launch.stream_path else None
        self.mark_launch(launch)  # one marker per round

        def emit(event, pause=0.5):
            if stream:
                with open(stream, "a") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            time.sleep(self.pace * pause * random.uniform(0.6, 1.4))

        def text(delta):
            emit({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": delta}}, 0.25)

        def tool(name, args, output, err=False):
            cid = f"{launch.label}-{random.randrange(10**6)}"
            emit({"type": "tool_execution_start", "toolCallId": cid, "toolName": name, "args": args})
            emit(
                {
                    "type": "tool_execution_end",
                    "toolCallId": cid,
                    "toolName": name,
                    "isError": err,
                    "result": {"content": [{"type": "text", "text": output}]},
                }
            )

        def done(stop=Stop.COMPLETED, **kw):
            # Plausible token counts, priced at Sonnet-like list rates (USD per million tokens).
            fresh, cached, written = random.randint(1500, 4000), random.randint(8000, 20000), random.randint(0, 3000)
            out = random.randint(150, 900) if stop != Stop.RATE_LIMITED else 0
            usage = Usage(
                calls=[CallUsage(model=launch.model or "demo-model", input=fresh, cache_read=cached, cache_creation=written, output=out)],
                output_total=out,
            )
            cost = (fresh * 3 + written * 3.75 + cached * 0.3 + out * 15) / 1_000_000
            with self._lock:  # one reading per session start, account-wide, as Claude Code reports it
                reading = QuotaReading(
                    status="allowed",
                    five_hour_pct=round(self.used, 1),
                    seven_day_pct=round(40 + self.used / 10, 1),
                    five_hour_resets_at=self.resets[0],
                    seven_day_resets_at=self.resets[1],
                    observed_at=started_at,
                )
                self.used += cost * 40
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=stop,
                ok=stop == Stop.COMPLETED,
                model=launch.model,
                wall_s=round(time.monotonic() - started, 2),  # what the launch actually took
                usage=usage,
                cost_usd=round(cost, 6),
                quota=[reading],
                session_id=f"s-{launch.label}",
                **kw,
            )

        def write(content):
            assert call.output is not None  # every kind of the demo declares an output
            Path(call.output.path).write_text(content, encoding="utf-8")
            tool("write", {"path": call.output.path}, "ok")

        unit = call.unit
        text(f"## {call.kind} {unit}\nRound {n} on `{launch.model or 'default'}` as `{launch.role}`.\n")
        tool("read", {"path": str(call_path)}, json.dumps(call.params, ensure_ascii=False)[:300])
        if call.kind == "summarize":
            if launch.model == "primary-model" and unit == "beta":
                tool("bash", {"command": "curl -s https://api.example/limits"}, "429 Too Many Requests", err=True)
                return done(Stop.RATE_LIMITED, quota_refusal=QuotaRefusal(retry_after_s=600))
            points = ["parses a config file", "validates it", "reports errors"]
            write(json.dumps({"unit": unit, "points": points[:2] if unit == "delta" and n == 1 else points}))
        elif call.kind == "review":
            if launch.label == "review-gamma" and n < 3:
                return done(Stop.ERROR, stderr_tail="tool crashed")
            first = launch.label == "review-gamma"  # gamma's first review does not approve
            write(json.dumps({"approved": not first, "note": "Name the file format." if first else "Accurate and complete."}))
        elif call.kind == "revise":
            points = call.params["summary"]["points"]
            write(json.dumps({"unit": unit, "points": [f"{points[0]} (TOML)", *points[1:]]}))
        elif call.kind == "write_note":
            heading = "" if unit == "alpha" and n == 1 else f"# {unit}\n\n"
            body = "\n\n".join(f"{p}。" for p in call.params["summary"]["points"])
            write(f"{heading}{body}\n")
        # The second demo pipeline: contraagent.docs.examples.analysis
        elif call.kind == "classify":
            name = call.params["file"]["name"]
            write(json.dumps({"name": name, "format": "json" if name.endswith("1") else "csv", "data": True}))
        elif call.kind in ("parse_csv", "parse_json"):
            write(json.dumps({"columns": [{"name": "id", "nulls": 0}, {"name": "amount", "nulls": 1}, {"name": "note", "nulls": 9}]}))
        elif call.kind == "propose":
            short = launch.label == "propose-east-0-id" and n == 1  # one column's first reading is sent back by `verify`
            col = call.params["column"]["name"]
            write(json.dumps({"column": col, "reads": "value" if short else f"The {col} column."}))
        elif call.kind == "refine":
            col = call.params["meaning"]["column"]
            write(json.dumps({"column": col, "reads": f"The {col} column, in words."}))
        text("Done.\n")
        return done()


def notes(run: RunRecords) -> dict:
    """Each unit's note, read through the run's records, so it shows on a hub too."""
    keys = {row["unit"]: row["key"] for row in run.journal() if row["kind"] == "write_note" and row["ok"]}
    return {unit: note.text for unit, key in sorted(keys.items()) if (note := run.output(key)) is not None}


#: The demo's own view in the monitor: a tab of each run.
PANELS = {"notes": Panel(notes, title="notes", description="What write_note produced", icon="✎")}


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", metavar="AGENT", help="use a real coding agent (claude, omp) instead of the demo agent")
    ap.add_argument("--no-serve", action="store_true", help="do not start the monitor")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--fast", action="store_true", help="demo agent with short pauses (what the tests run)")
    args = ap.parse_args(argv)

    inputs = Path("inputs")
    inputs.mkdir(exist_ok=True)
    for u in UNITS:  # the raw input each unit starts from
        (inputs / f"{u}.md").write_text(f"# {u}\nThe {u} component parses a config file, validates it and reports errors.\n")

    if args.real:
        pipeline = Pipeline(None, runs_dir="demo-runs", overrides=Overrides(agent=args.real))
    else:
        pipeline = Pipeline(HERE / "pipeline.toml", runs_dir="demo-runs", backends={"stub": DemoAgent(pace=0.03 if args.fast else 1.0)})

    if not args.no_serve:
        from contraagent.monitor import Monitor, serve

        monitor = Monitor("demo-runs", title="contraagent demo", panels=PANELS)
        threading.Thread(target=serve, daemon=True, args=(monitor, "127.0.0.1", args.port)).start()
        time.sleep(1)
        print(f"monitor: http://127.0.0.1:{args.port}", flush=True)

    # The second demo pipeline: a nested flow (three layers of flow calls, nested
    # loops). Run first so `docs` stays the most recently updated run.
    from contraagent.docs.examples.analysis.flow import analyse

    shutil.rmtree(Path("demo-runs", "analyse"), ignore_errors=True)
    if args.real:
        nested = Pipeline(None, runs_dir="demo-runs", overrides=Overrides(agent=args.real))
    else:
        nested = Pipeline(
            None,
            runs_dir="demo-runs",
            backends={"stub": DemoAgent(pace=0.03 if args.fast else 1.0)},
            overrides=Overrides(agent="stub"),
        )
    nested.run(analyse, bundles=["east", "west", "south"])

    shutil.rmtree(Path("demo-runs", "docs"), ignore_errors=True)  # the demo starts over each time
    report = pipeline.run(docs, units=list(UNITS))
    print(f"done: {len(report.results) - len(report.failed)}/{len(report.results)} tasks ok; run in {report.run_dir}")
    for r in report.failed:
        print(f"  {r.task.key}: {r.stop} {r.reason[:100]}")
    if not args.no_serve:
        print("monitor still up; Ctrl-C to stop", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    return report


if __name__ == "__main__":
    # The library reports routing and progress through `logging` (INFO); a
    # program that configures no logging would show none of it.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    main()
