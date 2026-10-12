"""`Pipeline.check`: everything about a flow that can be found wrong without launching anything.

It builds the task graph the way `Pipeline.run` does, then checks what a run
would otherwise find out one launch at a time:

* the flow: it builds; every `after=` names a task of the run. A generator
  flow is run to its first wait (every flow call it starts, up to the first
  `yield` that waits for a task), and an exception in any of them is
  reported;
* the kinds of the run: those of the tasks the flow created, and for a
  generator flow also its reachable kinds, the task declarations its code
  can reach (`reach.py`), since it creates the rest as it runs;
* each task created: its parameters fit its `params` model;
* each kind: an agent task's output schema has a JSON Schema and can be
  imported by the in-session hook (in a fresh interpreter, as the hook does),
  its command validators' programs are on PATH;
* each plugin: `plugin lint`;
* routing: the config against those kinds (budgets, efforts, failover chains,
  credentials and the traits tasks require), the coding agents' programs on
  PATH, and each model against the list its coding agent keeps locally
  (`Backend.catalogue`, e.g. `omp models`).

Nothing is launched, no run directory is written and no token is spent. The
one check left to a run is `Pipeline(preflight=True)`, which probes each route
of the same kinds.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import GeneratorType
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python

from contraagent.calls import schema_ref_of
from contraagent.dispatch.flow import FlowDriver
from contraagent.dispatch.task import kind_name
from contraagent.errors import ContraagentError, did_you_mean
from contraagent.pipeline.graph import Graph, Node, Pending
from contraagent.pipeline.reach import reachable
from contraagent.routing.plan import RoutingError, RoutingPlan
from contraagent.validators import CommandValidator

if TYPE_CHECKING:
    from contraagent.pipeline.pipeline import Pipeline

_PACKAGE = Path(__file__).resolve().parents[1]
#: Code that is not the caller's: contraagent, the standard library, installed packages.
_NOT_OWN = tuple(
    {_PACKAGE, *(Path(p).resolve() for name in ("stdlib", "platstdlib", "purelib", "platlib") if (p := sysconfig.get_paths().get(name)))}
)
_LOG_TAG = re.compile(r"^\[\w+\] ")  # a log line's `[task]`, not part of the warning


@dataclass
class CheckReport:
    """What `Pipeline.check` found. `ok` when there is no error; warnings do not fail it."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Task count by kind, in the order the flow first called each kind.
    kinds: dict[str, int] = field(default_factory=dict)
    #: The documentation topics that explain the errors (`contraagent docs <topic>`).
    topics: list[str] = field(default_factory=list)
    #: False when the flow raised before its tasks could be added.
    built: bool = True
    #: How each kind will run: agent/model, effort, budget, failover hops.
    routes: dict[str, str] = field(default_factory=dict)
    #: A generator flow's reachable kinds that its first step did not create, in the order found.
    later_kinds: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, topic: str, errors: list[str]) -> None:
        """Errors, and the documentation topic that explains them."""
        self.errors += errors
        if errors and topic not in self.topics:
            self.topics.append(topic)

    def __str__(self) -> str:
        tasks = sum(self.kinds.values())
        counts = ", ".join(f"{k} {n}" for k, n in self.kinds.items())
        later = f"; later kinds: {', '.join(self.later_kinds)}" if self.later_kinds else ""
        mark = "✓" if self.ok else "✗"
        if self.kinds:
            head = f"{mark} {tasks} tasks, {len(self.kinds)} kinds: {counts}{later}"
        elif later:
            head = f"{mark} 0 tasks{later}"
        else:
            head = "✗ the flow raised" if not self.built else "✗ the flow added no task"
        lines = [head]
        lines += [f"  {kind}: {route}" for kind, route in self.routes.items()]
        lines += [f"  error: {e}" for e in self.errors]
        lines += [f"  warning: {w}" for w in self.warnings]
        lines += [f"  read: {', '.join(f'`contraagent docs {t}`' for t in self.topics)}"] if self.topics else []
        return "\n".join(lines)


def check_flow(pipeline: Pipeline, flow: Callable[..., Any], args: tuple, kwargs: dict) -> CheckReport:
    report = CheckReport()
    with tempfile.TemporaryDirectory(prefix="contraagent-check-") as tmp:
        graph = Graph(Path(tmp) / "out", max_passes=pipeline.max_passes)
        driver = FlowDriver(waits_for=graph.waits_for, answer=graph.answer, created=graph.take_new, on_flow_call=graph.on_flow_call)
        graph.driver = driver
        with graph.building():
            try:
                value = flow(*args, **kwargs)
            except Exception as exc:
                report.built = False
                report.add("tasks", [f"flow: {where(exc)}{type(exc).__name__}: {exc}"])
                return report
            driven = isinstance(value, GeneratorType)
            if driven:
                try:
                    driver.start(value)  # every flow call it starts, to its first wait for a task
                finally:
                    driver.finish()
    for call in driver.calls.values():
        if call.error is not None:
            report.add("tasks", [f"flow call {call.id} ({call.function}): {where(call.error)}{type(call.error).__name__}: {call.error}"])
    top = driver.calls.get("0")
    report.built = bool(graph.nodes) or top is None or top.state != "raised"
    for node in graph.nodes:
        report.kinds[node.spec.kind] = report.kinds.get(node.spec.kind, 0) + 1
    specs = {node.spec.kind: node.spec for node in graph.nodes}
    if driven:
        report.add("tasks", _add_reachable(specs, reachable(flow, *args, *kwargs.values()), report))
    keys = {n.key for n in graph.nodes}
    report.add("tasks", [f"{n.key}: after={dep!r} names no task of this run" for n in graph.nodes for dep in n.after if dep not in keys])
    agent_specs = {kind: spec for kind, spec in specs.items() if spec.executor == "agent"}
    report.add("tasks", [e for n in graph.nodes if n.spec.executor == "agent" for e in _param_errors(n)])
    report.add("contracts", _schema_errors(agent_specs) + _validator_errors(list(specs.values())))
    report.add("plugins", _plugin_errors(agent_specs))
    _check_routing(pipeline, agent_specs, report)
    return report


def _add_reachable(specs: dict[str, Any], found: list[Any], report: CheckReport) -> list[str]:
    """Add the reachable kinds to `specs` (and to `report.later_kinds` when no task of
    theirs was created yet); the errors: two agent task declarations sharing a kind."""
    errs: list[str] = []
    for spec in found:
        seen = specs.get(spec.kind)
        if seen is None:
            specs[spec.kind] = spec
            report.later_kinds.append(spec.kind)
        elif seen is not spec and spec.executor == "agent" and seen.executor == "agent":
            errs.append(f"flow: two agent_task declarations share kind {spec.kind!r}")
    return errs


def where(exc: BaseException) -> str:
    """`file:line: ` of the innermost frame in the caller's own code: not contraagent, the
    standard library or an installed package (a `FileNotFoundError` names the flow's line,
    not pathlib's)."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if _own_code(f.filename)]
    return f"{frames[-1].filename}:{frames[-1].lineno}: " if frames else ""


def _own_code(filename: str) -> bool:
    path = Path(filename).resolve()
    return not filename.startswith("<") and not any(path.is_relative_to(p) for p in _NOT_OWN)


def _param_errors(node: Node) -> list[str]:
    """Parameters that would be refused when the call file is written, checked now.

    With no `Pending` among them they are validated as the run will: the whole
    `params` model, its constraints and validators. A value that holds a
    `Pending` is known only at run time: the other fields are then checked one by
    one against their annotation and constraints, without model validators.
    """
    model = node.spec.params
    if model is not None and not any(_holds_pending(v) for v in node.params.values()):
        try:
            model.model_validate(node.params)
        except ValidationError as exc:
            return [f"{node.key}: param {'.'.join(map(str, e['loc'])) or '-'}: {e['msg']}" for e in exc.errors()]
        return []
    errs: list[str] = []
    for name, value in node.params.items():
        if _holds_pending(value):
            continue
        try:
            if model is not None and name in model.model_fields:
                info = model.model_fields[name]
                field_type: Any = Annotated[info.annotation, info]  # the annotation with its constraints
                TypeAdapter(field_type).validate_python(value)
            else:
                to_jsonable_python(value)
        except ValidationError as exc:
            errs += [f"{node.key}: param {name}: {e['msg']}" for e in exc.errors()]
        except Exception as exc:  # not JSON-able, or an annotation TypeAdapter cannot take
            errs.append(f"{node.key}: param {name}: {exc}")
    return errs


def _holds_pending(value: Any) -> bool:
    if isinstance(value, Pending):
        return True
    if isinstance(value, (list, tuple, set)):
        return any(_holds_pending(v) for v in value)
    if isinstance(value, dict):
        return any(_holds_pending(v) for v in value.values())
    return False


def _schema_errors(specs: dict[str, Any]) -> list[str]:
    """Output schemas the call file cannot carry, or the in-session hook cannot import."""
    errs: list[str] = []
    refs: dict[str, dict] = {}
    for kind, spec in specs.items():
        schema: type[BaseModel] | None = spec.output_schema
        if schema is None:
            continue
        try:
            schema.model_json_schema()
        except Exception as exc:
            errs.append(f"{kind}: output {schema.__name__} has no JSON Schema: {exc}")
            continue
        ref = schema_ref_of(schema)
        if ref is None:
            errs.append(
                f"{kind}: output {schema.__qualname__} is defined in {schema.__module__}, where the in-session "
                "hook cannot import it; define it at the top level of an importable module"
            )
        else:
            refs[kind] = ref.model_dump()
    if refs:
        errs += [f"{kind}: {msg}" for kind, msg in _import_in_fresh_interpreter(refs).items()]
    return errs


_IMPORT_PROBE = """
import json, sys
from contraagent.calls import SchemaRef, import_schema
out = {}
for kind, ref in json.loads(sys.stdin.read()).items():
    if import_schema(SchemaRef(**ref)) is None:
        out[kind] = f"output {ref['module']}.{ref['qualname']} cannot be imported from {ref['search_path']} by the in-session hook"
print(json.dumps(out))
"""


def _import_in_fresh_interpreter(refs: dict[str, dict]) -> dict[str, str]:
    """What the hook (`contraagent call validate`, same interpreter) would fail to import."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _IMPORT_PROBE], input=json.dumps(refs), capture_output=True, text=True, timeout=60, check=True
        )
        return json.loads(proc.stdout)
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        return {kind: f"output import not checked: {exc}" for kind in refs}


def _validator_errors(specs: list[Any]) -> list[str]:
    errs: dict[str, str] = {}
    for spec in specs:
        for v in spec.validators:
            if not isinstance(v, CommandValidator) or not v.argv:
                continue
            if shutil.which(v.argv[0]) is None:
                errs.setdefault(v.argv[0], f"{spec.kind}: validator {v.name}: {v.argv[0]} is not on PATH")
            if v.needs_call and spec.executor == "python":
                message = f"{spec.kind}: validator {v.name} uses {{call}}; a Python task has no call file"
                errs.setdefault(f"call:{spec.kind}", message)
    return list(errs.values())


def _plugin_errors(specs: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    seen: set[Path] = set()
    for spec in specs.values():
        if spec.plugin is None or spec.plugin.root in seen:
            continue
        seen.add(spec.plugin.root)
        errs += [f"plugin {spec.plugin.root}: {e}" for e in spec.plugin.lint()]
    return errs


def _check_routing(pipeline: Pipeline, specs: dict[str, Any], report: CheckReport) -> None:
    if not specs:
        return
    with _warnings_of("contraagent") as warnings:
        try:
            plan = RoutingPlan.build(
                pipeline.config,
                list(specs),
                pipeline.backends,
                pipeline.overrides,
                declared={kind: spec.config for kind, spec in specs.items()},
                requirements={kind: spec.requires for kind, spec in specs.items()},
            )
        except RoutingError as exc:
            report.add("routing", [f"routing: {e}" for e in exc.errors])
            plan = None
        except (ContraagentError, ValueError) as exc:  # a malformed [credentials] or [defaults] table
            report.add("routing", [f"routing: {exc}"])
            plan = None
    report.warnings += ["routing: " + _LOG_TAG.sub("", w) for w in warnings]
    if plan is None:
        return
    report.routes = plan.routes()
    agents = {rc.agent for rc in plan.configs.values()} | {r.agent for router in plan.routers.values() for r in router.routes}
    for agent in sorted(agents):
        backend = pipeline.backends.get(agent)
        if backend is not None and backend.binary and shutil.which(backend.binary, path=backend.base_path()) is None:
            report.warnings.append(f"routing: {agent}: {backend.binary} is not on PATH; its launches would fail")
    _check_models(pipeline, plan, report)


def _check_models(pipeline: Pipeline, plan: RoutingPlan, report: CheckReport) -> None:
    """Each route's model against its coding agent's own list. A provider-qualified id
    (`provider/model`) the list lacks is an error; a bare name the list lacks is a
    warning, since an agent may resolve it another way (omp: a role alias, a fuzzy match)."""
    routes: dict[tuple[str, str], list[str]] = {}  # (agent, model) -> kinds
    for kind, rc in plan.configs.items():
        router = plan.routers.get(kind)
        pairs = [(r.agent, r.model) for r in router.routes] if router is not None else [(rc.agent, rc.model)]
        for pair in pairs:
            if pair[1] and kind_name(kind) not in routes.setdefault(pair, []):
                routes[pair].append(kind_name(kind))
    catalogues: dict[str, set[str] | None] = {}
    for (agent, model), kinds in routes.items():
        backend = pipeline.backends.get(agent)
        if backend is None:
            continue
        if agent not in catalogues:
            catalogues[agent] = backend.catalogue()
        listed = catalogues[agent]
        if listed is None or _listed(model, listed):
            continue
        which = f"{', '.join(kinds)}: model {model!r} is not in the {agent} model list{did_you_mean(model, listed)}"
        if "/" in model:
            report.add("routing", [f"routing: {which}"])
        else:
            report.warnings.append(f"routing: {which}; {agent} may still resolve it")


def _listed(model: str, listed: set[str]) -> bool:
    """`model` names a listed id: exactly, with a `:<effort>` suffix, or without its provider."""
    base = model.rpartition(":")[0]
    if model in listed or base in listed:
        return True
    if "/" in model:
        return False
    bare = {m.partition("/")[2] for m in listed}
    return model in bare or base in bare


@contextlib.contextmanager
def _warnings_of(logger_name: str) -> Iterator[list[str]]:
    """The warnings `logger_name` (and its children) log inside the block."""
    caught: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            caught.append(record.getMessage())

    handler = Catch(logging.WARNING)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield caught
    finally:
        logger.removeHandler(handler)
