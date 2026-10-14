"""The task graph a flow builds, and `Pending`: a reference to a task's future output.

Calling a task inside a flow does not run it; it adds a node and returns a
`Pending`. Passing that `Pending` to another task as a parameter is the
dependency: the consumer waits for it, its output file becomes the consumer's
checked input, and its value is what the consumer receives.

A flow that is a generator yields a `Pending` (or a list or tuple of them) and
receives the checked output at the `yield` (`FlowDriver`, with this graph's
`waits_for`, `answer` and `created` as its callbacks). Passing a received
output on to another task is the same dependency as passing its `Pending`: the
graph remembers which `Pending` produced each output it answered (a model
instance, a list, a dict, a text) and puts the `Pending` back. A number, a
bool, None and a `str` the flow built are values, never a dependency.

Every node records where it was created (`Origin`, see `origin.py`) and how it
is numbered:

* its key is `<kind>-<unit>` (`python:` first for a Python task), or `key=`;
  the n-th task a flow call creates under one key is `<key>~n` (n >= 2), and
  its output file `<stem>~n<suffix>`. The output file is
  `<out>/<kind>/<unit>.json` (`.md` for a text output), and with `key=`
  `<out>/<kind>/<key>.json`, so tasks of one kind and unit with different keys
  never write one file. A key used by two flow calls raises
  `ValueError` at the second: `key=` tells them apart;
* each frame of its flow path carries the loops around its call site with
  their passes (`loops.py`); a pass of a `while` loop past `max_passes` raises
  `TooManyPasses` at the task call, and at the `yield` of a child flow call (a
  `for` loop ends with its iterable and has no limit);
* its fingerprint is a digest of its kind, unit, key and params (a `Pending`
  among them standing for its key), of its definition (`AgentTask.digest`,
  `PythonTask.digest`), and of each task it waits for: the content of its
  output file when the flow received that output and passed it on, else its
  fingerprint.
"""

from __future__ import annotations

import contextlib
import dataclasses
import glob
import hashlib
import inspect
import json
import re
import string
from collections.abc import Callable, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, RootModel
from pydantic_core import to_jsonable_python

from contraagent.contracts import InputContract, OutputContract, check_file
from contraagent.dispatch.flow import TaskFailed, result_or_raise
from contraagent.dispatch.python_task import PythonTaskPayload
from contraagent.dispatch.task import PYTHON_KEY_PREFIX, STOP_DUPLICATE_KEY, STOP_INVALID_OUTPUT, Frame, Origin, Task, TaskResult
from contraagent.errors import ContraagentError
from contraagent.pipeline import origin as origins
from contraagent.pipeline.loops import LoopCounter, counting, is_while

if TYPE_CHECKING:
    from contraagent.dispatch.flow import FlowCall, FlowDriver

Out = TypeVar("Out")

#: How many passes a `while` loop of flow code may make, by default.
MAX_PASSES = 10

_current: ContextVar[Graph | None] = ContextVar("contraagent_graph", default=None)


class TooManyPasses(ContraagentError):
    """A `while` loop of flow code went past `max_passes` passes: it created a task, or yielded a
    child flow call, in a later pass."""


class TextOutput(str):
    """A text output as a flow receives it. A `str` of its own (never interned, unlike a
    `str` the flow built), so passing it on to another task is recognized as the dependency."""

    __slots__ = ()


def current_graph() -> Graph:
    graph = _current.get()
    if graph is None:
        raise RuntimeError("a task is called inside a flow: pass the function that calls it to Pipeline.run(flow, ...)")
    return graph


class Pending[Out]:
    """A task's future output. Pass it to another task, yield it in a generator flow, or
    read `.output` after the run."""

    def __init__(self, node: Node, graph: Graph) -> None:
        self._node = node
        self._graph = graph
        self._value: Any = _UNSET

    @property
    def key(self) -> str:
        return self._node.key

    @property
    def unit(self) -> str:
        return self._node.unit

    @property
    def path(self) -> Path | None:
        """The output file, or None for a task with no output."""
        return self._node.output_path

    @property
    def origin(self) -> Origin | None:
        """Where the flow created the task."""
        return self._node.origin

    @property
    def result(self) -> TaskResult | None:
        """The task's final `TaskResult`, once it has finished."""
        return self._graph.results.get(self.key)

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok

    @property
    def output(self) -> Out:
        """The checked output: the schema instance, the text (a `TextOutput`), or the
        Python task's return value."""
        if self._value is _UNSET:
            node = self._node
            if node.output_path is None:
                raise ValueError(f"{self.key} has no output")
            chk = check_file(node.output_path, node.output_schema)
            if not chk.ok:
                raise ValueError(f"{self.key}: no valid output: {'; '.join(chk.errors)}")
            value = chk.value.root if isinstance(chk.value, RootModel) else chk.value
            self._value = TextOutput(value) if isinstance(value, str) else value
        return self._value

    def __repr__(self) -> str:
        state = "pending" if self.result is None else self.result.stop
        return f"Pending({self.key!r}, {state})"


_UNSET = object()


@dataclass(eq=False)
class Node:
    spec: Any  # AgentTask or PythonTask
    key: str
    unit: str
    params: dict[str, Any]
    after: tuple[str, ...]
    output_path: Path | None
    upstream: list[Pending] = field(default_factory=list)
    #: Its `changes` patterns, with `{unit}`, `{key}` and `{kind}` filled in.
    changes: tuple[str, ...] = ()
    #: The names it claims: its kind's `claims` with `{unit}`, `{key}`, `{kind}` and
    #: `{params.<name>}` filled in.
    claims: tuple[str, ...] = ()
    origin: Origin | None = None
    fingerprint: str = ""
    task: Task | None = field(default=None, repr=False)

    @property
    def output_schema(self) -> type[BaseModel] | None:
        return self.spec.output_schema

    def resolved_params(self) -> dict[str, Any]:
        """The parameters with every `Pending` replaced by its output."""
        return {k: _resolve(v) for k, v in self.params.items()}

    def input_contracts(self) -> list[InputContract]:
        """The upstream outputs this task reads: missing or off-contract refuses it."""
        return [InputContract(p.path, p._node.output_schema, producer=p.key) for p in self.upstream if p.path is not None]

    def output_contracts(self, params: Callable[[], dict[str, Any]] | None = None, call: Path | None = None) -> list[OutputContract]:
        """Its output contract; `params` and `call` reach the validators that take them."""
        if self.output_path is None:
            return []
        from_message = getattr(self.spec, "output_from", "file") == "message"
        return [
            OutputContract(
                self.output_path, self.output_schema, validators=self.spec.validators, params=params, call=call, from_message=from_message
            )
        ]


class Graph:
    """The nodes a flow added, in call order, and their results.

    `driver`: the `FlowDriver` running the flow, when it is a generator; its
    current flow call is what creates a node (none: flow call "0", the flow
    itself). `new_kind(spec)`: called to route an agent task's kind, when it is
    reached (`reached`) or first created (`declare`), before its node is added;
    what it raises, the task call raises.
    `tail(task)`: each task's `tail_s`, the expected wall time of the work its
    flow creates after it (`JournalEstimates.tail`); None leaves it unset.
    `stub`: in a stub run, the stub agent that plays its Python tasks (`StubAgent.play_python`)
    but the kinds it executes (`StubAgent.plays`); None runs every function.
    `run_id`: the run's id, for the stub's record of what it played.
    """

    def __init__(self, out_dir: Path, *, max_passes: int = MAX_PASSES) -> None:
        self.out_dir = Path(out_dir)
        self.max_passes = max_passes
        self.nodes: list[Node] = []
        self.results: dict[str, TaskResult] = {}
        self.driver: FlowDriver | None = None
        self.new_kind: Callable[[Any], None] | None = None
        self.tail: Callable[[Task], float | None] | None = None
        self.stub: Any = None
        self.run_id = ""
        self._by_key: dict[str, Node] = {}
        self._bases: dict[str, tuple[str, int]] = {}  # key before numbering -> (flow call id, tasks so far)
        #: The passes of the loops of flow code while the flow runs (`loops.py`).
        self.loops = LoopCounter(current=lambda: self.driver.current if self.driver is not None else None)
        self._digests: dict[int, str] = {}  # id(spec) -> its definition's digest
        self._specs: dict[str, Any] = {}  # agent kind -> the declaration its tasks were created by
        self._reached: dict[str, Any] = {}  # agent kind with no task yet -> the reachable declaration routed
        self._prefix: dict[str, tuple[Frame, ...]] = {}  # flow call id -> the frames before its own
        self._produced: dict[int, tuple[Any, Pending]] = {}  # id(output) -> (output, its Pending)
        self._taken = 0

    @contextlib.contextmanager
    def building(self) -> Iterator[Graph]:
        token = _current.set(self)
        try:
            with counting(self.loops):
                yield self
        finally:
            _current.reset(token)

    def add(
        self,
        spec: Any,
        *,
        unit: str,
        key: str | None,
        after: Sequence[Pending | str],
        params: dict[str, Any],
    ) -> Pending:
        call = self.driver.current if self.driver is not None else None
        call_id = call.id if call is not None else "0"
        stem: str = f"{spec.kind}-{unit}" if unit else spec.kind
        given = key  # key=, when the task call gave one
        base = key or (f"{PYTHON_KEY_PREFIX}{stem}" if spec.executor == "python" else stem)
        owner, n = self._bases.get(base, (call_id, 0))
        if owner != call_id:
            raise ValueError(f"task key {base!r} is created by flow calls {owner} and {call_id}; pass key= to tell them apart")
        n += 1
        key = base if n == 1 else f"{base}~{n}"
        if key in self._by_key:
            raise ValueError(f"task key {key!r} is used twice; pass key= to tell them apart")
        frames = self._prefix.get(call_id, ()) + origins.frames_here(inspect.currentframe(), self.loops.loops)
        self.check_passes(frames, base, call_id)
        self.declare(spec)
        claims = _expand_claims(spec, unit, key, params)  # before the key is taken: a raise leaves no gap in ~n
        self._bases[base] = (call_id, n)
        received: set[str] = set()
        params = {name: self._dependency(v, received) for name, v in params.items()}
        upstream = list(_pendings(params.values()))
        deps = [*(p.key for p in upstream), *((a.key if isinstance(a, Pending) else str(a)) for a in after)]
        out = None
        if spec.output_format is not None and (spec.executor == "agent" or spec.output_schema is not None):
            # A task given key= writes a file of its own: two keys on one unit never share one.
            name = (given or unit or base.removeprefix(PYTHON_KEY_PREFIX)).replace("/", "_").replace(":", "_")
            file = Path(spec.output_name.format(unit=name, key=base, kind=spec.kind))
            if n > 1:
                file = file.with_name(f"{file.stem}~{n}{file.suffix}")
            out = self.out_dir / spec.kind / file
        origin = Origin(flow=frames, created_from=call.frontier if call is not None else (), flow_call=call_id)
        filled = {"unit": glob.escape(unit or base), "key": glob.escape(base), "kind": spec.kind}
        node = Node(
            spec=spec,
            key=key,
            unit=unit,
            params=params,
            after=tuple(dict.fromkeys(deps)),
            output_path=out,
            upstream=upstream,
            origin=origin,
            changes=tuple(p.format(**filled) for p in getattr(spec, "changes", ())),
            claims=claims,
        )
        node.fingerprint = self._fingerprint(node, received)
        self.nodes.append(node)
        self._by_key[key] = node
        return Pending(node, self)

    def agent_specs(self) -> dict[str, Any]:
        """kind -> AgentTask, for every agent kind created or reached so far: the declaration
        its tasks were created by, else the first one reached."""
        return {**self._specs, **self._reached}

    def tasks(self) -> list[Task]:
        return [self.task_of(n) for n in self.nodes]

    def take_new(self) -> list[Task]:
        """The tasks of the nodes added since the last call: what is to be queued."""
        new, self._taken = self.nodes[self._taken :], len(self.nodes)
        return [self.task_of(n) for n in new]

    def record(self, result: TaskResult) -> None:
        """Remember a task's final result (a refused duplicate never replaces its key's own)."""
        if result.stop != STOP_DUPLICATE_KEY or result.task.key not in self.results:
            self.results[result.task.key] = result

    # --- FlowDriver callbacks --------------------------------------------------

    def waits_for(self, item: Any) -> Task:
        """What a yielded `Pending` waits for: its task."""
        if isinstance(item, Pending) and item._graph is self:
            return self.task_of(item._node)
        if isinstance(item, Pending):
            raise TypeError(f"{item.key} was created by another run")
        raise TypeError(f"a flow yields what a task call returns, a generator, or a list or tuple of them, not {type(item).__name__}")

    def answer(self, item: Pending, result: TaskResult) -> Any:
        """What a flow receives for a finished task: its checked output (None for a task
        with no output). `TaskFailed` / `TaskDeferred` for one that did not succeed, and
        `TaskFailed` (`invalid_output`) for an output that no longer passes its checks."""
        result_or_raise(item, result)
        if item.path is None:
            return None
        try:
            value = item.output
        except ValueError as exc:
            raise TaskFailed(dataclasses.replace(result, ok=False, stop=STOP_INVALID_OUTPUT, reason=str(exc)), item) from None
        if _tracked(value):
            self._produced[id(value)] = (value, item)
        return value

    def flow_call_started(self, call: FlowCall) -> tuple[Frame, ...]:
        """The flow path where a child flow call was yielded: its parent's frames at the
        `yield`, with their loops' passes (empty for a top flow call). The child's tasks'
        flow paths start with it."""
        if call.parent is None:
            return ()
        frames = self._prefix.get(call.parent.id, ()) + origins.generator_frames(call.parent.gen, self.loops.loops)
        self._prefix[call.id] = frames
        return frames

    def flow_call_ended(self, call: FlowCall) -> None:
        """Forget the passes counted in a flow call's frames."""
        self.loops.drop(call)

    def on_flow_call(self, event: str, call: FlowCall) -> None:
        """A `FlowDriver` `on_flow_call`: the flow path of a child flow call, checked
        against `max_passes` (`TooManyPasses` fails the child, and its parent receives it at
        the `yield`)."""
        if event == "start":
            self.check_passes(self.flow_call_started(call), f"flow call {call.id} ({call.function})", call.id)
        else:
            self.flow_call_ended(call)

    def check_passes(self, frames: tuple[Frame, ...], what: str, call_id: str) -> None:
        """`TooManyPasses` when a `while` loop of `frames` is past `max_passes`. A `for` loop
        ends with its iterable and has no limit."""
        for frame in frames:
            for loop in frame.loops:
                if loop.pass_ is not None and loop.pass_ > self.max_passes and is_while(frame.file, loop.line):
                    raise TooManyPasses(
                        f"{what}: pass {loop.pass_} of the loop at {frame.file}:{loop.line} is more than "
                        f"max_passes={self.max_passes} (flow call {call_id}); a `while` loop meant to go further takes "
                        "Pipeline(max_passes=) or [defaults] max_passes"
                    )

    # --- internals ---------------------------------------------------------------

    def task_of(self, node: Node) -> Task:
        if node.task is None:
            node.task = self._task(node)
        return node.task

    def reached(self, spec: Any) -> None:
        """Make a reachable agent kind one of the run's (`agent_specs`) before any task of it
        is created: `new_kind` is called for a kind not seen yet. The flow's code may reach
        other declarations of a kind too (a default argument the caller replaces); which one
        it creates is known only when it does (`declare`)."""
        if spec.executor != "agent" or spec.kind in self._specs or spec.kind in self._reached:
            return
        if self.new_kind is not None:
            self.new_kind(spec)
        self._reached[spec.kind] = spec

    def declare(self, spec: Any) -> None:
        """Make an agent task's kind one of the run's as a task of it is added. One kind, one
        declaration: a second declaration of the kind that differs from the first one created
        (`AgentTask.differences`) raises. `new_kind` is called the first time, unless the
        kind was reached with the same `config`, `requires` and `tools` (its routing)."""
        if spec.executor != "agent":
            return
        seen = self._specs.get(spec.kind)
        if seen is not None:
            if seen is not spec and (parts := seen.differences(spec)):
                raise ValueError(
                    f"kind {spec.kind!r} is declared by two agent_task calls with different {', '.join(parts)}: "
                    f"one kind is one definition and one [tasks.{spec.kind}] table; give one of them another kind"
                )
            return
        routed = self._reached.pop(spec.kind, None)
        routing = (spec.config, spec.requires, spec.tools)
        if self.new_kind is not None and (routed is None or (routed.config, routed.requires, routed.tools) != routing):
            self.new_kind(spec)
        self._specs[spec.kind] = spec

    def _dependency(self, value: Any, received: set[str]) -> Any:
        """`value` with every output this graph answered replaced by its `Pending`; the keys
        of those go to `received`."""
        hit = self._produced.get(id(value))
        if hit is not None and hit[0] is value:
            received.add(hit[1].key)
            return hit[1]
        if isinstance(value, list) or type(value) is tuple:
            items = [self._dependency(v, received) for v in value]
            return type(value)(items) if any(a is not b for a, b in zip(items, value, strict=True)) else value
        if isinstance(value, dict):
            pairs = {k: self._dependency(v, received) for k, v in value.items()}
            return pairs if any(pairs[k] is not value[k] for k in value) else value
        return value

    def _fingerprint(self, node: Node, received: set[str]) -> str:
        """See the module docstring. A received output stands for itself (its file's
        content), so an upstream task that ran again and wrote the same output leaves this
        fingerprint as it was."""
        spec = node.spec
        if id(spec) not in self._digests:
            self._digests[id(spec)] = spec.digest()
        after = {}
        for k in node.after:
            up = self._by_key.get(k)
            if up is not None and k in received and up.output_path is not None:
                after[k] = _file_digest(up.output_path)
            else:
                after[k] = up.fingerprint if up is not None else ""
        body = {
            "kind": spec.kind,
            "unit": node.unit,
            "key": node.key,
            "definition": self._digests[id(spec)],
            "params": to_jsonable_python(_keys_for_pendings(node.params), fallback=repr),
            "after": after,
        }
        text = json.dumps(body, sort_keys=True, ensure_ascii=False, default=repr)
        return hashlib.sha256(text.encode()).hexdigest()

    def _task(self, node: Node) -> Task:
        task = Task(
            kind=node.spec.kind,
            unit=node.unit or node.key,
            key=node.key,
            after=node.after,
            params={k: v for k, v in node.params.items() if isinstance(v, (str, int, float, bool))},
            origin=node.origin,
            fingerprint=node.fingerprint,
            claims=node.claims,
            rerun_on_resume=getattr(node.spec, "rerun_on_resume", False),
            payload=node,
        )
        if self.tail is not None:
            task.tail_s = self.tail(task)
        if node.spec.executor == "agent":
            return task

        def call(node: Node = node) -> None:
            schema = node.output_schema
            if self.stub is not None and self.stub.plays(node.spec.kind):
                params = node.resolved_params()
                json_schema = schema.model_json_schema() if node.output_path is not None and schema is not None else None
                has_output, value = self.stub.play_python(self.run_id, node.key, node.spec.kind, node.unit, params, json_schema)
                if not has_output:
                    return
            else:
                value = node.spec.invoke(node.unit, node.resolved_params())
            # A Python task is given an output path only when it declares an output schema.
            if node.output_path is None or schema is None:
                return
            doc = value if isinstance(value, schema) else schema.model_validate(value)
            node.output_path.parent.mkdir(parents=True, exist_ok=True)
            node.output_path.write_text(doc.model_dump_json(indent=2))

        return dataclasses.replace(
            task,
            fn=call,
            payload=PythonTaskPayload(
                input_contracts=tuple(node.input_contracts()),
                output_contracts=tuple(node.output_contracts(params=node.resolved_params)),
                definition=node.spec.definition(),
            ),
        )


#: A claim's `{params.<name>}` field.
CLAIM_PARAM = re.compile(r"params\.([A-Za-z_][A-Za-z0-9_]*)")


def _expand_claims(spec: Any, unit: str, key: str, params: dict[str, Any]) -> tuple[str, ...]:
    """The names a task claims: each of its kind's templates filled in. `{params.<name>}` is
    a parameter of the call: a list gives one name per element (several lists, every
    combination). In order and once each. Raises at the task call for a `{unit}` of a task
    with no unit, a missing parameter, an output not received yet, or a value that is not
    a string or a number, or a list with no element (the claim would hold nothing)."""
    out: list[str] = []
    for template in getattr(spec, "claims", ()):
        names = [""]
        for literal, field_name, _, _ in string.Formatter().parse(template):
            names = [n + literal for n in names]
            if field_name is not None:
                values = _claim_values(spec.kind, template, field_name, unit, key, params)
                names = [n + v for n in names for v in values]
        out += names
    return tuple(dict.fromkeys(out))


def _claim_values(kind: str, template: str, field_name: str, unit: str, key: str, params: dict[str, Any]) -> list[str]:
    if field_name == "unit":
        if not unit:
            raise ValueError(f"{kind}(): claim {template!r} names {{unit}}, and the task has no unit")
        return [unit]
    if field_name in ("key", "kind"):
        return [key if field_name == "key" else kind]
    m = CLAIM_PARAM.fullmatch(field_name)
    if m is None:  # the declaration admits no other field (`spec._checked_claims`)
        raise ValueError(f"{kind}(): claim {template!r} names {field_name}; it may name unit, key, kind and params.<name>")
    name = m.group(1)
    if name not in params:
        raise ValueError(f"{kind}(): claim {template!r} names params.{name}, and the call gives no {name}")
    value = params[name]
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    if not items:
        raise ValueError(f"{kind}(): claim {template!r} names params.{name}, an empty list; the task would claim nothing")
    for v in items:
        if isinstance(v, Pending):
            raise TypeError(f"{kind}(): claim {template!r} names params.{name}, an output not received yet; yield it first")
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise TypeError(f"{kind}(): claim {template!r} names params.{name}, which holds {v!r}; a claim takes strings and numbers")
    return [str(v) for v in items]


def _file_digest(path: Path) -> str:
    try:
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _tracked(value: Any) -> bool:
    """Whether an answered output is remembered as its task's: an object made for it,
    never a number, a bool, None or a `str` the flow could have built (or an empty tuple,
    which Python shares)."""
    return isinstance(value, (BaseModel, list, dict, set, TextOutput)) or (type(value) is tuple and len(value) > 0)


def _pendings(values) -> Iterator[Pending]:
    for v in values:
        if isinstance(v, Pending):
            yield v
        elif isinstance(v, (list, tuple, set)):
            yield from _pendings(v)
        elif isinstance(v, dict):
            yield from _pendings(v.values())


def _keys_for_pendings(v: Any) -> Any:
    """`v` with each `Pending` as `{"task": key}`, for a fingerprint."""
    if isinstance(v, Pending):
        return {"task": v.key}
    if isinstance(v, (list, tuple)):
        return [_keys_for_pendings(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _keys_for_pendings(x) for k, x in v.items()}
    return v


def _resolve(v: Any) -> Any:
    if isinstance(v, Pending):
        return v.output
    if isinstance(v, (list, tuple)):
        return type(v)(_resolve(x) for x in v)
    if isinstance(v, dict):
        return {k: _resolve(x) for k, x in v.items()}
    return v
