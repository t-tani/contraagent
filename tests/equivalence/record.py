"""Record what each example flow does on the stub agent into `tests/fixtures/equivalence/<version>/`.

    <checkout>/.venv/bin/python tests/equivalence/record.py tests/fixtures/equivalence/<version>

The script runs on whichever contraagent its interpreter imports, and each version runs
its own examples (`contraagent.docs.examples`), so the interpreter of another checkout
records that version: `git worktree add <dir> <tag>`, `uv sync` in it, then run this
file with `<dir>/.venv/bin/python`. It imports only the public modules (and sets
`RetryingRunner.backoff` to 0, as the tests do), so it runs on 0.6.2 and later.

Each entry of `FLOWS` is one run: an example's flow function with its keyword arguments,
on the stub agent (`stub`: what `contraagent run --stub` does, no model called and no
Python task's function run; `approve`: the same, but the reviews approve), or on the
stub that the example's own tests script (`demo`, `tutorial`: their Python tasks run,
and some replies fail). A run is recorded as its `summary`: every task by key (kind,
unit, final stop), each file under the run directory's `out/` by the SHA-256 of its
content, the `RunReport` counts (ok, failed, deferred, partial, the flow errors' types)
and the flow's value. Run ids, times, absolute paths, line numbers, reasons and flow
call ids are left out or replaced, so two versions that do the same thing write the
same file. Each flow runs alone in an empty directory, so the order of its tasks does
not matter and the summary is the same on every run.
`tests/test_equivalence.py` runs `summary` on the current tree and compares.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contraagent import Pending, Pipeline, RunReport
from contraagent.testing import StubAgent, writes_example

UNITS = ["alpha", "beta"]
#: The reports the tutorial's tests triage.
REPORTS = ["login-timeout", "csv-export", "dark-mode"]
#: The replies of the `approve` scenario: alpha's first review asks for a revision, every
#: other review approves (on the stub alone a review never approves, and the loop stops at
#: its pass limit).
APPROVE = {
    "review": {"approved": True, "note": ""},
    "review-alpha": [{"approved": False, "note": "Too short."}, {"approved": True, "note": ""}],
}
#: The units the demo's tests run: zeta's input is malformed, epsilon's score is partial.
DEMO_UNITS = ["alpha", "beta", "delta", "epsilon", "zeta"]


@dataclass(frozen=True)
class Flow:
    """One recorded run: `examples/<example>/<module>.py:<function>(**kwargs)`, with the
    example's `pipeline.toml` when `config`, on `scenario`'s agent."""

    example: str
    module: str
    function: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    config: bool = False
    scenario: str = "stub"

    @property
    def id(self) -> str:
        """The flow's name in the fixtures and the tests: `<example>.<function>`, then
        `.<scenario>` but for a plain stub run."""
        base = f"{self.example}.{self.function}"
        return base if self.scenario == "stub" else f"{base}.{self.scenario}"


FLOWS = [
    Flow("analysis", "flow", "analyse", {"bundles": ["q3", "q4"]}),
    Flow("before", "flow", "backlogs", {"topics": {"search": ["faster index"], "billing": ["invoices by email"]}}),
    Flow("changes", "flow", "topics", {"subjects": {"alpha": "caching", "beta": "retries"}}),
    Flow("claims", "flow", "topics", {"names": UNITS}),
    Flow("concurrency", "flow", "reports", {"units": UNITS}),
    Flow("credentials", "flow", "summarize_all", {"documents": ["plan", "contract"]}, config=True),
    Flow("demo", "tasks", "docs", {"units": UNITS}, config=True),
    Flow("demo", "tasks", "docs_one_review", {"units": UNITS}, config=True),
    Flow("demo", "tasks", "docs", {"units": DEMO_UNITS}, config=True, scenario="demo"),
    Flow("demo", "tasks", "docs_one_review", {"units": DEMO_UNITS}, config=True, scenario="demo"),
    Flow("implementations", "flow", "review_all", {"units": {"api": "python", "worker": "go"}}),
    Flow("light", "flow", "items", {"titles": {"n1": "A patch for the login server", "n2": "Our new plan"}}),
    Flow("mcp", "flow", "ask_all", {"questions": {"papers": "Which paper measures the cache?"}}),
    Flow("missing", "flow", "reviews", {"units": {"alpha": ["a.md", "b.md"], "beta": ["c.md"]}}),
    Flow("outside", "flow", "topics", {"names": UNITS}),
    Flow("partial", "flow", "topics", {"names": UNITS}),
    Flow("preserve", "flow", "reports", {"units": {"q3": ["Revenue", "Costs"]}}),
    Flow("retries", "flow", "topics", {"names": UNITS}),
    Flow("review", "flow", "docs", {"units": UNITS}),
    Flow("review", "flow", "docs", {"units": UNITS}, scenario="approve"),
    Flow("review", "flow", "publish", {"units": UNITS}, scenario="approve"),
    Flow("rows", "flow", "reviews", {"units": UNITS}),
    Flow("runner", "flow", "reviews", {"units": UNITS}),
    Flow("scopes", "flow", "topics", {"names": UNITS}),
    Flow("security", "flow", "audit_all", {"modules": ["auth", "upload"]}, config=True),
    Flow("services", "flow", "topics", {"names": UNITS}),
    Flow("skills", "tasks", "notes", {"units": UNITS}),
    Flow("time_box", "flow", "cycle", {"topics": UNITS}),
    Flow("tutorial", "tasks", "triage_all", {"reports": REPORTS}, config=True),
    Flow("tutorial", "tasks", "triage_and_plan", {"reports": REPORTS}, config=True),
    Flow("tutorial", "tasks", "triage_all", {"reports": REPORTS}, config=True, scenario="tutorial"),
    Flow("tutorial", "tasks", "triage_and_plan", {"reports": REPORTS}, config=True, scenario="tutorial"),
]


def _module(flow: Flow) -> Any:
    return importlib.import_module(f"contraagent.docs.examples.{flow.example}.{flow.module}")


def present(flow: Flow) -> bool:
    """Whether the installed version's example defines the flow."""
    try:
        return callable(getattr(_module(flow), flow.function, None))
    except ImportError:
        return False


def _demo_inputs(work: Path) -> None:
    """The input files the demo's tests write."""
    (work / "inputs").mkdir()
    for u in DEMO_UNITS:
        (work / "inputs" / f"{u}.md").write_text(f"# {u}\nThe {u} component parses a config file.\n", encoding="utf-8", newline="\n")


def _pipeline(flow: Flow, work: Path) -> Pipeline:
    """The pipeline the example's tests build: its `pipeline()` factory when it has one."""
    module = _module(flow)
    options: dict[str, Any] = {"runs_dir": work / "runs", "cwd": work, "log": lambda line: None}
    if flow.config:
        options["config"] = Path(module.__file__).parent / "pipeline.toml"
    if flow.scenario == "stub":
        options["stub"] = StubAgent(default=writes_example())
    elif flow.scenario == "approve":
        options["stub"] = StubAgent(APPROVE, default=writes_example())
    elif flow.scenario == "demo":
        from contraagent.docs.examples.demo import test_demo

        _demo_inputs(work)
        options["backends"] = test_demo.stub().backends()
    elif flow.scenario == "tutorial":
        from contraagent.docs.examples.tutorial import test_tutorial

        options["backends"] = test_tutorial.stub().backends()
    else:
        raise ValueError(f"unknown scenario {flow.scenario!r}")
    factory: Callable[..., Pipeline] = getattr(module, "pipeline", Pipeline)
    return factory(**options)


@contextlib.contextmanager
def _inside(work: Path) -> Iterator[None]:
    """The working directory is `work` while the flow runs: the demo's Python tasks read
    `inputs/` relative to it."""
    before = Path.cwd()
    os.chdir(work)
    try:
        yield
    finally:
        os.chdir(before)


def _no_backoff() -> None:
    """A retried attempt does not wait out its backoff, as in the tests."""
    from contraagent.engine import RetryingRunner

    RetryingRunner.backoff = staticmethod(lambda base, attempt: 0.0)  # type: ignore[method-assign]


def summary(flow: Flow, work: Path) -> dict[str, Any]:
    """Run `flow` in the empty directory `work` and return its normalized summary."""
    _no_backoff()
    work = work.resolve()
    with _inside(work):
        report = _pipeline(flow, work).run(getattr(_module(flow), flow.function), **flow.kwargs)
    return normalize(flow, report, work)


def normalize(flow: Flow, report: RunReport, work: Path) -> dict[str, Any]:
    """What `report` and its run directory say, with nothing that changes from one run to the next."""
    run = report.run_dir.resolve()

    def text(s: str) -> str:
        return s.replace(str(run), "<run>").replace(str(work), "<work>").replace(report.run_id, "<run-id>")

    def value(v: Any) -> Any:
        if isinstance(v, Pending):
            try:
                return value(v.output)
            except ValueError:  # its task did not write a valid output
                return {"pending": "no output"}
        if isinstance(v, BaseModel):
            return value(v.model_dump(mode="json"))
        if isinstance(v, dict):
            return {str(k): value(x) for k, x in v.items()}
        if isinstance(v, list | tuple):
            return [value(x) for x in v]
        if isinstance(v, BaseException):
            return {"exception": type(v).__name__}
        if isinstance(v, str):
            return text(v)
        if v is None or isinstance(v, bool | int | float):
            return v
        return {"repr": type(v).__name__}

    tasks = {key: {"kind": r.task.kind, "unit": r.task.unit, "stop": r.stop} for key, r in sorted(report.results.items())}
    outputs = {}
    out = run / "out"
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        content = text(path.read_text(encoding="utf-8", errors="surrogateescape"))
        outputs[path.relative_to(out).as_posix()] = hashlib.sha256(content.encode("utf-8", errors="surrogateescape")).hexdigest()
    return {
        "flow": flow.id,
        "call": f"examples/{flow.example}/{flow.module}.py:{flow.function}",
        "kwargs": flow.kwargs,
        "config": flow.config,
        "scenario": flow.scenario,
        "tasks": tasks,
        "outputs": outputs,
        "report": {
            "ok": report.ok,
            "failed": len(report.failed),
            "deferred": len(report.deferred),
            "partial": len(report.partial),
            "flow_errors": sorted(type(c.error).__name__ for c in report.flow_errors),
        },
        "value": value(report.value),
    }


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    dest = Path(args[0])
    dest.mkdir(parents=True, exist_ok=True)
    for flow in FLOWS:
        if not present(flow):
            print(f"{flow.id}: not in this version's examples", file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            data = summary(flow, Path(tmp))
        (dest / f"{flow.id}.json").write_text(dumps(data), encoding="utf-8", newline="\n")
        print(f"{flow.id}: {len(data['tasks'])} tasks, ok={data['report']['ok']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
