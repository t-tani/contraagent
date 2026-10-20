"""The task graph a flow builds, and `Pending`: a reference to a task's future output.

Calling a task inside a flow does not run it; it adds a node and returns a
`Pending`. Passing that `Pending` to another task as a parameter is the
dependency: the consumer waits for it, its output file becomes the consumer's
checked input, and its value is what the consumer receives.

An async flow awaits a `Pending` (`await triage(...)`, or several at once with
`asyncio.gather`) and receives the checked output at the `await` (`FlowDriver.wait`,
with this graph's `waits_for` and `answer` as its callbacks). The task reaches the
queue when it is called, whether or not anything awaits it. Passing a received
output on to another task is the same dependency as passing its `Pending`: the
graph remembers which `Pending` produced each output it answered (a model
instance, a list, a dict, a text) and puts the `Pending` back. A number, a
bool, None and a `str` the flow built are values, never a dependency.

Every node records where it was created (`Origin`, see `origin.py`) and how it
is numbered:

* its key is `<kind>-<unit>` (`python:` first for a Python task), or the `key` of
  its call options (`.options(key=)`);
  the n-th task a flow call creates under one key is `<key>~n` (n >= 2), and
  its output file `<stem>~n<suffix>`. The output file is its kind's `output_name`
  under `<out>`, filled in (default `<out>/<kind>/<unit>.json`, `.md` for a text
  output), `{unit}` being the key when its call options give one, so tasks of one kind
  and unit with different keys never write one file. A key used by two flow calls
  raises `ValueError` at the second: `.options(key=)` tells them apart;
* one output file, one writer: two kinds whose `output_name` templates name one
  file, or a task given a file another task writes (but by `output_of`), raise
  `ValueError` when the flow reaches the second (`layout`, `add`);
* each frame of its flow path carries the loops around its call site with
  their passes (`loops.py`); a pass of a `while` loop past its bound (its
  function's `@max_passes(n)`, else the run's `max_passes`) raises
  `TooManyPasses` at the task call, and at the creation of a child flow call (a
  `for` loop ends with its iterable and has no limit);
* its fingerprint is a digest of its kind, unit, key and params (a `Pending`
  among them standing for its key), of its definition (`AgentTask.digest`,
  `PythonTask.digest`), and of each task it waits for. An output it reads (a
  `Pending` among its params, or an output the flow received and passed on) stands
  for the content of its output file: when the flow received it, as received; else
  as the task is about to start. Another task it waits for (`after=`) stands for that
  task's fingerprint. The file an `output_of` task fills in stands for its content as
  the task is about to start, not for the task that wrote it last. So an upstream task
  that runs again and writes the same output leaves the fingerprint as it was, and one
  that writes another output changes it. The digest of each part is kept beside the
  fingerprint (`Task.fingerprint_parts`), so a resume names the parts that changed;
* a task that reads an output the flow did not receive, whose declaration gives
  `outside_state` or `output_of`, or that waits, other than for an output it reads, for
  a task of such a fingerprint, has a
  fingerprint that is complete only when it is about to start
  (`Task.fingerprint_at_start`): `starting` works it out again then, with the content of
  the output files it reads and the fingerprints the tasks it waits for started with.
  For `outside_state`, `starting` calls the function with the task's params resolved;
  the SHA-256 of the JSON of what it returned is part of the fingerprint. A task whose
  function raised or returned what is not JSON is refused (`refusal`);
* a resume skips a task whose journal row matches its fingerprint only when its output
  file still reads under its output schema (`output_reads`); else the task runs again.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import glob
import hashlib
import inspect
import json
import logging
import os
import re
import string
from collections.abc import Callable, Generator, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, RootModel
from pydantic_core import to_jsonable_python

from contraagent._internal.contracts.contract import InputContract, OutputContract, check_file
from contraagent._internal.contracts.rows import is_rows, row_of, rows_text
from contraagent._internal.dispatch.flow import TaskFailed, result_or_raise
from contraagent._internal.dispatch.python_task import PythonTaskPayload
from contraagent._internal.dispatch.records import DeferralCause, Frame
from contraagent._internal.dispatch.task import (
    PYTHON_KEY_PREFIX,
    STOP_DEFERRED,
    STOP_DUPLICATE_KEY,
    STOP_INVALID_OUTPUT,
    Deferral,
    Origin,
    Partial,
    Task,
    TaskResult,
    fingerprint_of,
)
from contraagent._internal.dispatch.templates import PARAM_FIELD
from contraagent._internal.errors import ContraagentError
from contraagent._internal.pipeline import origin as origins
from contraagent._internal.pipeline.loops import LoopCounter, bound, counting, is_while

if TYPE_CHECKING:
    from contraagent._internal.dispatch.flow import FlowCall, FlowDriver

Out = TypeVar("Out")

_logger = logging.getLogger(__name__)

#: How many passes a `while` loop of flow code may make, by default.
MAX_PASSES = 10

_current: ContextVar[Graph | None] = ContextVar("contraagent_graph", default=None)


class TooManyPasses(ContraagentError):
    """A `while` loop of flow code went past its bound (its function's `@max_passes(n)`, else the
    run's `max_passes`): it created a task, or a child flow call, in a later pass."""


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
    """A task's future output. Pass it to another task, await it in an async flow (its
    checked output, or `TaskFailed` / `TaskDeferred`), or read `.output` after the run."""

    _node: Node
    _graph: Graph
    _value: Any

    def __init__(self) -> None:
        raise TypeError("a Pending is what calling a task in a flow returns; it is not built by hand")

    @classmethod
    def _of(cls, node: Node, graph: Graph) -> Pending[Out]:
        pending = object.__new__(cls)
        pending._node, pending._graph, pending._value = node, graph, _UNSET
        return pending

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

    def _failure(self) -> str:
        """The stop of the task when it finished and did not succeed, else ''."""
        result = self.result
        return result.stop if result is not None and not result.ok else ""

    @property
    def output(self) -> Out:
        """The checked output: the schema instance, the text (a `TextOutput`), the rows (a
        `Rows`, a list), or the Python task's return value."""
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

    def __await__(self) -> Generator[Any, None, Out]:
        """Wait for the task in an async flow: its checked output (`Graph.answer`)."""
        driver = self._graph.driver
        if driver is None:
            raise RuntimeError(f"{self.key}: a Pending is awaited in an async flow that Pipeline.run runs")
        return driver.wait(self).__await__()

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
    upstream: list[Pending[Any]] = field(default_factory=list)
    #: Its `changes` patterns, with `{unit}`, `{key}` and `{kind}` filled in.
    changes: tuple[str, ...] = ()
    #: The names it claims: its kind's `claims` with `{unit}`, `{key}`, `{kind}` and
    #: `{params.<name>}` filled in.
    claims: tuple[str, ...] = ()
    #: Its call options' `priority`: a tie-breaker in the queue, not part of its fingerprint.
    priority: float = 0.0
    #: Its call options' `credential`; empty: its kind's. Not part of its fingerprint.
    credential: str = ""
    #: Its call options' `cancellable` (`Task.cancellable`). Not part of its fingerprint.
    cancellable: bool = False
    origin: Origin | None = None
    fingerprint: str = ""
    #: The keys of the tasks it waits for whose outputs the flow received and passed on.
    received: frozenset[str] = frozenset()
    #: The digest of each output file it reads, by its task's key: of a received output, its
    #: file's content when the flow passed it on; of another, when the task last started.
    reads: dict[str, str] = field(default_factory=dict)
    #: Its fingerprint is complete only when it is about to start (`Task.fingerprint_at_start`).
    at_start: bool = False
    #: The SHA-256 of its outside state when it last started; empty before, or when it declares none.
    outside: str = ""
    #: For a task that fills in another task's file (`output_of`): the key of the task it waits
    #: for that wrote the file last (None when none did), and the digest of the file as it was
    #: when the task last started (empty before, or when the file was missing).
    writer: str | None = None
    filled: str = ""
    #: The digest of each part of its fingerprint (`Task.fingerprint_parts`).
    parts: dict[str, str] = field(default_factory=dict)
    #: Why its outside state could not be worked out when it last started; empty when it could.
    outside_error: str = ""
    task: Task | None = field(default=None, repr=False)

    @property
    def output_schema(self) -> type[BaseModel] | None:
        return self.spec.output_schema

    def resolved_params(self) -> dict[str, Any]:
        """The parameters with every `Pending` replaced by its output."""
        return {k: _resolve(v) for k, v in self.params.items()}

    def input_contracts(self) -> list[InputContract]:
        """The upstream outputs this task reads: missing, off-contract, or written by a task
        that did not succeed refuses it."""
        return [
            InputContract(p.path, p._node.output_schema, producer=p.key, producer_failure=p._failure)
            for p in self.upstream
            if p.path is not None
        ]

    def output_contracts(self, params: Callable[[], dict[str, Any]] | None = None, call: Path | None = None) -> list[OutputContract]:
        """Its output contract; `params` and `call` reach the validators that take them."""
        if self.output_path is None:
            return []
        from_message = getattr(self.spec, "output_from", "file") == "message"
        return [
            OutputContract(
                self.output_path,
                self.output_schema,
                validators=self.spec.validators,
                params=params,
                call=call,
                from_message=from_message,
                unwrap=getattr(self.spec, "unwrap", False),
                preserve=getattr(self.spec, "preserve", ()),
            )
        ]


#: The `~n` after a file's stem: the file of the n-th task under one key.
_NUMBERED = re.compile(r"~[0-9]+$")


def _writes_output(spec: Any) -> bool:
    """An agent task with an output, or a Python task that returns one: a task with an output file."""
    return spec.output_format is not None and (spec.executor == "agent" or spec.output_schema is not None)


class Graph:
    """The nodes a flow added, in call order, and their results.

    `driver`: the `FlowDriver` of the run: each task created goes to it to be queued,
    and its current flow call is what creates a node (none: flow call "0", the flow
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
        #: Why a task of a kind cannot run as the credential its task call names (empty: it
        #: can); None while the kinds are not routed yet.
        self.check_credential: Callable[[str, str], list[str]] | None = None
        #: The run-wide override's credential (`Overrides.credential`): it outranks a task call's.
        self.credential_override = ""
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
        self._named: dict[int, Any] = {}  # id(spec) -> every declaration reached or created, for `kind_clash`
        self._prefix: dict[str, tuple[Frame, ...]] = {}  # flow call id -> the frames before its own
        self._produced: dict[int, tuple[Any, Pending[Any]]] = {}  # id(output) -> (output, its Pending)
        self._layouts: dict[str, str] = {}  # output_name with its kind filled in -> the kind
        self._writers: dict[Path, str] = {}  # output file -> the key of the task it is given to

    @contextlib.contextmanager
    def building(self) -> Iterator[Graph]:
        token = _current.set(self)
        try:
            with counting(self.loops):
                yield self
        finally:
            _current.reset(token)

    def _output_of(self, other: Any, name: str, base: str) -> tuple[Path, str | None]:
        """The output file of an `agent_task(output_of=other)` task named `name` (its unit, or
        its key), and the key of the task to wait for. The file is that of the latest task of
        `other`'s kind so far whose file, its `~n` aside, is `other`'s template filled in for
        this name; with none, the template's file itself. The task to wait for is the latest
        so far that writes the file, of any kind: two tasks never write it at once."""
        path = self._filled(other, name, base)
        for node in reversed(self.nodes):
            p = node.output_path
            if node.spec.kind == other.kind and p is not None and p.with_name(_NUMBERED.sub("", p.stem) + p.suffix) == path:
                path = p
                break
        writer = next((node.key for node in reversed(self.nodes) if node.output_path == path), None)
        return path, writer

    def _filled(self, spec: Any, name: str, base: str) -> Path:
        """`spec`'s `output_name` filled in for a task named `name` (its unit, or its key)
        under `out_dir`. A key that would take it outside raises."""
        rel = spec.output_name.format(unit=name, key=base, kind=spec.kind)
        segments = rel.replace(os.sep, "/").split("/")  # a backslash parts a path on Windows too
        if rel.startswith("/") or Path(rel).anchor or any(seg in ("", ".", "..") for seg in segments):
            raise ValueError(f"{spec.kind}: output_name {spec.output_name!r} filled in for key {base!r} is {rel!r}, not a path inside out/")
        return self.out_dir / rel

    def layout(self, spec: Any) -> None:
        """Make `spec`'s output file template one of the run's. A second kind whose
        `output_name`, its `{kind}` filled in, is the same text raises `ValueError`: both
        would write one file for each unit. A kind that writes another's file (`output_of`)
        has no template of its own."""
        if not _writes_output(spec) or getattr(spec, "output_of", None) is not None:
            return
        template = spec.output_name.replace("{kind}", spec.kind)
        owner = self._layouts.setdefault(template, spec.kind)
        if owner != spec.kind:
            raise ValueError(
                f"kinds {owner!r} and {spec.kind!r} both write out/{template}: give one of them another output_name, "
                f"or declare {spec.kind!r} with output_of= to fill in the other's file"
            )

    def add(
        self,
        spec: Any,
        *,
        unit: str,
        key: str | None,
        after: Sequence[Pending[Any] | str],
        params: dict[str, Any],
        priority: float = 0.0,
        credential: str = "",
        cancellable: bool = False,
    ) -> Pending[Any]:
        call = self.driver.current if self.driver is not None else None
        call_id = call.id if call is not None else "0"
        stem: str = f"{spec.kind}-{unit}" if unit else spec.kind
        given = key  # the key of its call options, when they give one
        base = key or (f"{PYTHON_KEY_PREFIX}{stem}" if spec.executor == "python" else stem)
        owner, n = self._bases.get(base, (call_id, 0))
        if owner != call_id:
            raise ValueError(
                f"task key {base!r} is created by flow calls {owner} and {call_id}; "
                "give one of them another key with .options(key=) to tell them apart"
            )
        n += 1
        key = base if n == 1 else f"{base}~{n}"
        if key in self._by_key:
            raise ValueError(f"task key {key!r} is used twice; give one of them another key with .options(key=) to tell them apart")
        frames = self._prefix.get(call_id, ()) + origins.frames_here(inspect.currentframe(), self.loops.loops)
        self.check_passes(frames, base, call_id)
        self.declare(spec)
        self.layout(spec)
        if credential and self.check_credential is not None:
            problems = self.check_credential(spec.kind, credential)
            if problems:
                raise ValueError(f"{key}: credential={credential!r}: {'; '.join(problems)}")
        claims = _expand_claims(spec, unit, key, params)  # before the key is taken: a raise leaves no gap in ~n
        out, writer = None, None
        if _writes_output(spec):
            # A task given a key writes a file of its own: two keys on one unit never share one.
            name = (given or unit or base.removeprefix(PYTHON_KEY_PREFIX)).replace("/", "_").replace(os.sep, "_").replace(":", "_")
            other = getattr(spec, "output_of", None)
            if other is not None:
                out, writer = self._output_of(other, name, base)
            else:
                out = self._filled(spec, name, base)
                if n > 1:
                    out = out.with_name(f"{out.stem}~{n}{out.suffix}")
                if (taken := self._writers.get(out)) is not None:
                    raise ValueError(
                        f"tasks {taken!r} and {key!r} would both write {out.relative_to(self.out_dir.parent).as_posix()}: "
                        "put {unit} or {key} in output_name, or give one of them output_of="
                    )
        self._bases[base] = (call_id, n)
        received: set[str] = set()
        params = {name: self._dependency(v, received) for name, v in params.items()}
        upstream = list(_pendings(params.values()))
        deps = [*(p.key for p in upstream), *((a.key if isinstance(a, Pending) else str(a)) for a in after)]
        if writer is not None and writer not in deps:
            deps.append(writer)
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
            priority=priority,
            credential=credential,
            cancellable=cancellable,
            received=frozenset(received),
            writer=writer,
        )
        reads = _reads(node)
        node.at_start = (
            getattr(spec, "outside_state", None) is not None
            or getattr(spec, "output_of", None) is not None
            or any(k not in received for k in reads)
            or any((up := self._by_key.get(k)) is not None and up.at_start for k in node.after if k not in reads)
        )
        node.fingerprint = self._fingerprint(node)
        self.nodes.append(node)
        self._by_key[key] = node
        if out is not None and getattr(spec, "output_of", None) is None:
            self._writers[out] = key
        if self.driver is not None:
            self.driver.add(self.task_of(node))
        return Pending._of(node, self)

    def agent_specs(self) -> dict[str, Any]:
        """kind -> AgentTask, for every agent kind created or reached so far: the declaration
        its tasks were created by, else the first one reached."""
        return {**self._specs, **self._reached}

    def tasks(self) -> list[Task]:
        return [self.task_of(n) for n in self.nodes]

    def starting(self, task: Task) -> Task:
        """`task` as it is about to start, the tasks it waits for finished: for one whose
        fingerprint is complete only then (`Task.fingerprint_at_start`), its outside state
        worked out now and its fingerprint again, with the content of the output files it
        reads now and the fingerprints the tasks it waits for started with. Any other task
        as it is."""
        node = self._by_key.get(task.key)
        if node is None or not node.at_start:
            return task
        node.outside, node.outside_error = "", ""
        fn = getattr(node.spec, "outside_state", None)
        if fn is not None:
            try:
                params = node.resolved_params()
            except Exception:  # an input that is not there: the input check refuses the task
                params = None
            if params is not None:
                node.outside, node.outside_error = _outside_digest(node.spec.kind, fn, node.unit, params)
        if getattr(node.spec, "output_of", None) is not None and node.output_path is not None:
            node.filled = _file_digest(node.output_path)
        node.fingerprint = self._fingerprint(node, started=True)
        new = replace(task, fingerprint=node.fingerprint, outside=node.outside, fingerprint_parts=dict(node.parts))
        node.task = new
        return new

    def filled_after(self, task: Task) -> str:
        """For a task that fills in another task's file (`output_of`): the digest of the file
        as it is now, after an attempt (journal `output_of_after`); empty for any other task."""
        node = self._by_key.get(task.key)
        if node is None or node.output_path is None or getattr(node.spec, "output_of", None) is None:
            return ""
        return _file_digest(node.output_path)

    def refusal(self, task: Task) -> str:
        """Why `task` cannot run: its outside state could not be worked out when it was about
        to start (`starting`); empty when it could."""
        node = self._by_key.get(task.key)
        return node.outside_error if node is not None else ""

    def output_reads(self, task: Task) -> bool:
        """Whether `task`'s output file reads under its current output schema, as the flow
        would receive it (`Pending.output`): what a resume asks before it skips the task. A
        task with no output file reads."""
        node = self._by_key.get(task.key)
        if node is None or node.output_path is None:
            return True
        return check_file(node.output_path, node.output_schema).ok

    def input_deferral(self, task: Task) -> Deferral | None:
        """Why `task` is not launched: an earlier task whose output it reads was deferred
        (cause `dependency_deferred`, `dependency` its key), so its input will not be there.
        None when every task it reads from was not deferred. A task that only waits for
        another (`after=`) is not deferred with it."""
        node = self._by_key.get(task.key)
        if node is None:
            return None
        for up in node.upstream:
            result = self.results.get(up.key)
            if result is not None and result.stop == STOP_DEFERRED:
                return Deferral(f"input from {up.key} was deferred", DeferralCause(cause="dependency_deferred", dependency=up.key))
        return None

    def record(self, result: TaskResult) -> None:
        """Remember a task's final result (a refused duplicate never replaces its key's own)."""
        if result.stop != STOP_DUPLICATE_KEY or result.task.key not in self.results:
            self.results[result.task.key] = result

    # --- FlowDriver callbacks --------------------------------------------------

    def waits_for(self, item: Any) -> Task:
        """What an awaited `Pending` waits for: its task."""
        if isinstance(item, Pending) and item._graph is self:
            return self.task_of(item._node)
        if isinstance(item, Pending):
            raise TypeError(f"{item.key} was created by another run")
        raise TypeError(f"a flow awaits what a task call returns, not {type(item).__name__}")

    def answer(self, item: Pending[Any], result: TaskResult) -> Any:
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

    def flow_call_created(self, call: FlowCall) -> tuple[Frame, ...]:
        """The flow path where a child flow call was created: its parent's frames where its
        code created the Task, with their loops' passes (empty for a top flow call). The
        child's tasks' flow paths start with it (`flow_path`)."""
        parent = call.parent
        if parent is None:
            return ()
        if parent.task is not None and asyncio.current_task() is parent.task:  # the parent's code runs
            here = origins.frames_here(inspect.currentframe(), self.loops.loops)
        else:
            here = origins.suspended_frames(parent.coro, self.loops.loops)
        frames = self._prefix.get(parent.id, ()) + here
        self._prefix[call.id] = frames
        return frames

    def flow_path(self, call: FlowCall) -> tuple[Frame, ...]:
        """The flow path where `call` was created (`flow_call_created`)."""
        return self._prefix.get(call.id, ())

    def flow_call_ended(self, call: FlowCall) -> None:
        """Forget the passes counted in a flow call's frames."""
        self.loops.drop(call)

    def on_flow_call(self, event: str, call: FlowCall) -> None:
        """A `FlowDriver` `on_flow_call`: the flow path of a child flow call as it is created,
        checked against `max_passes` (`TooManyPasses` fails the child, and its parent
        receives it where it awaits the child)."""
        if event == "create":
            self.check_passes(self.flow_call_created(call), f"flow call {call.id} ({call.function})", call.id)
        elif event == "end":
            self.flow_call_ended(call)

    def check_passes(self, frames: tuple[Frame, ...], what: str, call_id: str) -> None:
        """`TooManyPasses` when a `while` loop of `frames` is past its bound: its function's
        `@max_passes(n)`, else the run's `max_passes`. A `for` loop ends with its iterable
        and has no limit."""
        for frame in frames:
            for loop in frame.loops:
                if loop.pass_ is None or not is_while(frame.file, loop.line):
                    continue
                own = bound(frame.file, loop.line)
                limit = own if own is not None else self.max_passes
                if loop.pass_ > limit:
                    whose = f"max_passes={limit} of {frame.function}" if own is not None else f"max_passes={limit}"
                    further = (
                        f"a larger @max_passes(n) on {frame.function}"
                        if own is not None
                        else f"@max_passes(n) on {frame.function}, Pipeline(max_passes=) or [defaults] max_passes"
                    )
                    raise TooManyPasses(
                        f"{what}: pass {loop.pass_} of the loop at {frame.file}:{loop.line} is more than {whose} "
                        f"(flow call {call_id}); a `while` loop meant to go further takes {further}"
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
        it creates is known only when it does (`declare`). A kind that clashes with another
        declaration's (`kind_clash`) raises, and its output file template is checked against
        the others' (`layout`), whatever its executor."""
        self._name(spec)
        self.layout(spec)
        if spec.executor != "agent" or spec.kind in self._specs or spec.kind in self._reached:
            return
        if self.new_kind is not None:
            self.new_kind(spec)
        self._reached[spec.kind] = spec

    def declare(self, spec: Any) -> None:
        """Make an agent task's kind one of the run's as a task of it is added. One kind, one
        declaration: a second declaration of the kind that differs from the first one created
        (`AgentTask.differences`) raises. `new_kind` is called the first time, unless the
        kind was reached with the same `config`, `requires` and `tools` (its routing). A kind
        that clashes with another declaration's (`kind_clash`) raises."""
        self._name(spec)
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

    def _name(self, spec: Any) -> None:
        """Remember `spec` among the run's declarations; raise when its kind clashes with one's."""
        if id(spec) in self._named:
            return
        for other in self._named.values():
            if message := kind_clash(other, spec):
                raise ValueError(message)
        self._named[id(spec)] = spec

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

    def _fingerprint(self, node: Node, *, started: bool = False) -> str:
        """See the module docstring: the digest of each part of the task's work (`Node.parts`,
        named as `Task.fingerprint_parts`), and the fingerprint of them. `definition`: its
        declaration's digest; `params`: its params, a `Pending` among them standing for its
        key; `output:<key>`: each output it reads, by its file's content (one the flow
        received, as it was when the flow passed it on; one it did not, as the task is about
        to start, `started`; before, empty); `after:<key>`: the fingerprint of each other task
        it waits for; `outside`: its outside state, for a task that declares one, once it is
        worked out (`starting`; before, and when it could not be, empty); `output_of`: the
        file it fills in, for an `output_of` task, as it was when the task was about to start
        (before, empty), which stands for the task that wrote it last."""
        spec = node.spec
        if id(spec) not in self._digests:
            self._digests[id(spec)] = spec.digest()
        for p in node.upstream:
            if p.path is None:
                continue
            if p.key in node.received:
                node.reads.setdefault(p.key, _file_digest(p.path))
            else:
                node.reads[p.key] = _file_digest(p.path) if started else ""
        params = json.dumps(
            to_jsonable_python(_keys_for_pendings(node.params), fallback=repr),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=repr,
        )
        parts = {"definition": self._digests[id(spec)], "params": hashlib.sha256(params.encode()).hexdigest()}
        for k in node.after:
            if k in node.reads:
                parts[f"output:{k}"] = node.reads[k]
            elif k != node.writer:
                up = self._by_key.get(k)
                parts[f"after:{k}"] = up.fingerprint if up is not None else ""
        if getattr(spec, "outside_state", None) is not None:
            parts["outside"] = node.outside
        if getattr(spec, "output_of", None) is not None:
            parts["output_of"] = node.filled
        node.parts = parts
        return fingerprint_of(spec.kind, node.unit or node.key, node.key, parts)

    def _credential_of(self, node: Node) -> str:
        """The credential the task call's tasks run as: its own, unless the run-wide override
        outranks it (logged)."""
        if node.credential and self.credential_override:
            if node.credential != self.credential_override:
                _logger.warning(
                    f"[route] {node.key}: runs as {self.credential_override}, the override's credential, "
                    f"not {node.credential}, its task call's"
                )
            return ""
        return node.credential

    def _task(self, node: Node) -> Task:
        task = Task(
            kind=node.spec.kind,
            unit=node.unit or node.key,
            key=node.key,
            after=node.after,
            params={k: v for k, v in node.params.items() if isinstance(v, (str, int, float, bool))},
            origin=node.origin,
            fingerprint=node.fingerprint,
            fingerprint_at_start=node.at_start,
            outside=node.outside,
            fingerprint_parts=dict(node.parts),
            claims=node.claims,
            priority=node.priority,
            credential=self._credential_of(node),
            cancellable=node.cancellable,
            rerun_on_resume=getattr(node.spec, "rerun_on_resume", False),
            base_kind=getattr(node.spec, "base_kind", ""),
            payload=node,
        )
        if self.tail is not None:
            task = replace(task, tail_s=self.tail(task))
        if node.spec.executor == "agent":
            return task

        def call(node: Node = node) -> Partial[Any] | None:
            """Run the function and write its output; a `Partial` it returned, for the runner."""
            schema = node.output_schema
            partial = None
            if self.stub is not None and self.stub.plays(node.spec.kind):
                params = node.resolved_params()
                node.spec.arguments(node.unit, params)  # a stub run refuses what a run refuses
                rows = is_rows(schema)
                json_schema = row_of(schema).model_json_schema() if node.output_path is not None and schema is not None else None
                has_output, value = self.stub.play_python(self.run_id, node.key, node.spec.kind, node.unit, params, json_schema, rows=rows)
                if not has_output:
                    return None
            else:
                value = node.spec.invoke(node.unit, node.resolved_params())
                if isinstance(value, Partial):
                    partial, value = value, value.value
            # A Python task is given an output path only when it declares an output schema.
            if node.output_path is None or schema is None:
                return partial
            doc = value if isinstance(value, schema) else schema.model_validate(value)
            node.output_path.parent.mkdir(parents=True, exist_ok=True)
            text = rows_text(doc.root) if is_rows(schema) else doc.model_dump_json(indent=2)  # pyright: ignore[reportAttributeAccessIssue]
            node.output_path.write_text(text, encoding="utf-8", newline="\n")
            return partial

        return dataclasses.replace(
            task,
            fn=call,
            payload=PythonTaskPayload(
                input_contracts=tuple(node.input_contracts()),
                output_contracts=tuple(node.output_contracts(params=node.resolved_params)),
                definition=node.spec.definition(),
                retries=node.spec.retries,
                retry_on=node.spec.retry_on,
            ),
        )


def kind_clash(a: Any, b: Any) -> str | None:
    """Why two task declarations cannot be in one run, or None: the kind of one is the base
    kind of the other (`agent_task(implementations=)`), or both have one kind and are not
    implementations of one base kind. Two declarations of one kind otherwise are judged by
    `AgentTask.differences`."""
    for one, two in ((a, b), (b, a)):
        base = getattr(two, "base_kind", "")
        if base and one.kind == base:
            return (
                f"kind {base!r} of {_declaration(one)} is also the base kind of {_declaration(two, base_only=True)}, "
                f"whose implementation kinds take its [tasks.{base}] table and its group; give one of them another name"
            )
    if a.kind == b.kind and getattr(a, "base_kind", "") != getattr(b, "base_kind", ""):
        first, second = (a, b) if getattr(a, "base_kind", "") else (b, a)  # the implementation first
        return f"kind {a.kind!r} is declared by {_declaration(first)} and by {_declaration(second)}; give one of them another name"
    return None


def _declaration(spec: Any, *, base_only: bool = False) -> str:
    """A task declaration as its code wrote it."""
    if spec.executor == "python":
        return f"@python_task {spec.kind}"
    base = getattr(spec, "base_kind", "")
    if not base:
        return f"agent_task({spec.kind!r})"
    if base_only:
        return f"agent_task({base!r}, implementations=...)"
    return f"agent_task({base!r}, implementations=...) (implementation {spec.kind[len(base) + 1 :]!r})"


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
    m = PARAM_FIELD.fullmatch(field_name)
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
            raise TypeError(f"{kind}(): claim {template!r} names params.{name}, an output not received yet; await it first")
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise TypeError(f"{kind}(): claim {template!r} names params.{name}, which holds {v!r}; a claim takes strings and numbers")
    return [str(v) for v in items]


def _outside_digest(kind: str, fn: Callable[..., Any], unit: str, params: dict[str, Any]) -> tuple[str, str]:
    """(the SHA-256 of the JSON of what `fn(unit, params)` returns, why it could not be worked
    out): one of the two is empty."""
    try:
        value = fn(unit, params)
    except Exception as exc:
        return "", f"{kind}: outside_state raised {type(exc).__name__}: {exc}"
    try:
        text = json.dumps(to_jsonable_python(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "", (
            f"{kind}: outside_state returned {type(value).__name__}, which is not JSON; "
            "return a string, a number, a list or a dict of them, or a pydantic model"
        )
    return hashlib.sha256(text.encode()).hexdigest(), ""


def _file_digest(path: Path) -> str:
    try:
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _reads(node: Node) -> set[str]:
    """The keys of the tasks whose output files `node` reads: each `Pending` among its params
    (an output received and passed on included) of a task with an output file."""
    return {p.key for p in node.upstream if p.path is not None}


def _tracked(value: Any) -> bool:
    """Whether an answered output is remembered as its task's: an object made for it,
    never a number, a bool, None or a `str` the flow could have built (or an empty tuple,
    which Python shares)."""
    return isinstance(value, (BaseModel, list, dict, set, TextOutput)) or (type(value) is tuple and len(value) > 0)


def _pendings(values) -> Iterator[Pending[Any]]:
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
