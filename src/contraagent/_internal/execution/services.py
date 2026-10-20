"""Services: the long-lived helper a claim name stands for (`Pipeline(services=)`).

A service is a function of a claim name that returns a context manager (`Service`):
entering it starts the service and gives its address, exiting it stops it. The
pipeline names it by a claim name, or by an `fnmatch` pattern that gives each name it
matches a service of its own, as `claim_capacity` does (a name's own entry outranks a
pattern, the longest pattern the others). A task that claims the name holds the
service while it runs:

* the first task that claims the name starts it, on that task's worker thread,
  before the task's first attempt; a task that claims it while it starts waits for
  that start. How many tasks hold the name at once is its claim capacity, as for any
  claim: they all share the one service;
* the service runs until the run ends;
* a start that raises fails the task that started it and every task that claims the
  name after it, each with stop `launch_failed` and the start's exception as its
  reason; the run goes on. With a cool-off (`Services(cooloff_s=)`), the first task
  that claims the name once the cool-off has passed since the failed start tries the
  start again; without one, the start is not tried again in the run. A resumed run
  tries the start again;
* a stop that raises is recorded with its exception, and the service counts as
  stopped;
* the run's end stops every service still up, in the reverse order of their starts:
  a run that returns, raises or is interrupted (`close`; `Run.teardown` on SIGTERM
  and Ctrl-C).

A task reaches a service by its address, what the context manager gives (a string, or
None for a service with nothing to reach): an agent task in its environment
(`envvars.service(name)`), a Python task by `service_address(name)`. `services.jsonl`
records each start and stop (`ServiceEvent`).

Only a task that really runs holds its services: a Python task whose function runs, an
agent task that launches a coding agent. A task a stub run or a replay plays holds
none (`Services(plays=)`): no service starts for it, and nothing it plays reaches one
(its launch has no `envvars.service` variable).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from contraagent._internal.backends import live_processes
from contraagent._internal.dispatch.queue import RunnerConfig, TaskRunner, claim_entry
from contraagent._internal.dispatch.records import ServiceEvent, ServiceStopCause
from contraagent._internal.dispatch.task import Deferral, Task, TaskResult
from contraagent._internal.platform import envvars
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import append_lines
from contraagent._internal.runs.times import now_iso


class Service(Protocol):
    """A function of a claim name that returns a context manager: the service the name
    stands for (`Pipeline(services=)`). Entering it starts the service, and the value it
    gives is the service's address, a string its tasks reach it by (a URL, a socket
    path), or None when there is nothing to reach; exiting it stops the service. A
    generator function decorated with `contextlib.contextmanager` is one; so is a class
    with `__enter__` and `__exit__`, called with the name.

    It is called with the name a task claims, so a service declared under a pattern
    (`db:*`) starts one service for each name it matches (`db:alpha`, `db:beta`). It is
    entered on the worker thread of the task that starts it and exited on whichever
    thread stops it: the worker thread of the last task that held it, a timer's thread,
    or the run's own."""

    def __call__(self, name: str, /) -> AbstractContextManager[str | None]: ...


class ServiceFailed(Exception):
    """A service a task claims could not start for it; the message says which and why."""


_addresses: ContextVar[Mapping[str, str | None] | None] = ContextVar("contraagent_service_addresses", default=None)
#: The claim names of the task running here, beside the addresses of its services.
_claims: ContextVar[tuple[str, ...]] = ContextVar("contraagent_service_claims", default=())
_POINTER = "(contraagent docs tasks, Services)"


def service_address(name: str) -> str | None:
    """The address of the service claim name `name` stands for, in a Python task that
    claims the name: what its service gave as it started (None when it gives none).
    Called on the thread the task runs on. KeyError when no task is running here, when
    the running task does not claim `name`, or when the pipeline defines no service for
    the name (a run of `contraagent run`, which knows no service); the message says
    which."""
    held = _addresses.get()
    if held is None:
        raise KeyError(f"service_address({name!r}): no task is running here; call it in a Python task that claims {name!r} {_POINTER}")
    if name in held:
        return held[name]
    if name in _claims.get():
        raise KeyError(
            f"service_address({name!r}): the running task claims {name!r}, and the pipeline defines no service of that name: "
            f"give one in Pipeline(services={{{name!r}: ...}}) and run the flow from that program, since the command line "
            f"knows no service {_POINTER}"
        )
    claimed = ", ".join(sorted(held)) or "none"
    raise KeyError(f"service_address({name!r}): the running task claims no service of that name (its services: {claimed}) {_POINTER}")


def service_environment() -> dict[str, str]:
    """The variables an agent task launched here is given: one per service it claims
    that has an address (`envvars.service`)."""
    held = _addresses.get() or {}
    return {envvars.service(name): address for name, address in held.items() if address is not None}


def env_clashes(names: list[str]) -> list[tuple[str, str]]:
    """The pairs of `names` that share one environment variable (`a-b`, `a_b`)."""
    seen: dict[str, str] = {}
    clashes: list[tuple[str, str]] = []
    for name in names:
        var = envvars.service(name)
        if var in seen and seen[var] != name:
            clashes.append((seen[var], name))
        seen.setdefault(var, name)
    return clashes


@dataclass
class _State:
    """One claim name's service: whether it is up, who holds it, how its start ended."""

    service: Service
    lock: threading.RLock = field(default_factory=threading.RLock)
    holders: int = 0
    context: AbstractContextManager[str | None] | None = None
    address: str | None = None
    failed: str = ""  # why its last start failed
    failed_at: float = 0.0  # when it failed (`time.monotonic`), for the cool-off
    started: int = 0  # the order of its last start, for the run's end


class Services:
    """The services of one run, by the claim name or pattern each stands for. `run_dir`:
    where `services.jsonl` is written; `log`: a progress line, and whether it is a warning;
    `plays(task)`: whether the run plays `task` (a stub run, a replay), so that it holds
    no service; `cooloff_s`: the seconds after a failed start before a task that claims
    the name tries the start again (None: never in this run)."""

    def __init__(
        self,
        services: Mapping[str, Service],
        run_dir: Path,
        *,
        log: Callable[[str, bool], None] | None = None,
        plays: Callable[[Task], bool] | None = None,
        cooloff_s: float | None = None,
    ) -> None:
        self._services = dict(services)
        self._cooloff_s = cooloff_s
        self._plays = plays or (lambda task: False)
        self._file = run_dir / layout.SERVICES
        self._log = log or (lambda line, warning: None)
        self._states: dict[str, _State] = {}
        self._lock = threading.Lock()
        self._starts = 0
        self._closed = False

    def names(self, task: Task) -> list[str]:
        """The names `task` claims that stand for a service, in the order it claims them."""
        return [n for n in dict.fromkeys(task.claims) if claim_entry(self._services, n) is not None]

    def wrap(self, runner: TaskRunner, on_failed: Callable[[TaskResult], None] | None = None) -> TaskRunner:
        """`runner`, with each task holding the services it claims while it runs.
        `on_failed(result)`: a task failed because a service did not start (to journal it)."""
        return _Holding(self, runner, on_failed)

    @contextmanager
    def held(self, task: Task) -> Iterator[None]:
        """Hold every service `task` claims while the block runs: started first when not
        up; none for a task the run plays. ServiceFailed, before the block, when one cannot
        start."""
        names = self.names(task)
        if not names or self._plays(task):
            with _running(task, {}):
                yield
            return
        clashes = env_clashes(names)
        if clashes:
            a, b = clashes[0]
            raise ServiceFailed(f"services {a!r} and {b!r} share the variable {envvars.service(a)}: claim one of them")
        addresses: dict[str, str | None] = {}
        try:
            for name in names:
                addresses[name] = self._acquire(name, task)
        except BaseException:
            for name in addresses:
                self._release(name)
            raise
        try:
            with _running(task, addresses):
                yield
        finally:
            for name in addresses:
                self._release(name)

    def close(self, cause: ServiceStopCause = "run_end") -> None:
        """Stop every service still up, the last started first; no service starts after."""
        with self._lock:
            self._closed = True
            states = sorted(self._states.items(), key=lambda item: -item[1].started)
        for name, state in states:
            with state.lock:
                if state.context is not None:
                    self._stop(name, state, cause)

    def interrupted(self) -> None:
        """`close` for a run stopped by a signal (`Run.on_teardown`)."""
        self.close("interrupted")

    # --- one name ----------------------------------------------------------

    def _state(self, name: str) -> _State:
        with self._lock:
            state = self._states.get(name)
            if state is None:
                service = claim_entry(self._services, name)
                assert service is not None
                state = self._states[name] = _State(service)
            return state

    def _acquire(self, name: str, task: Task) -> str | None:
        state = self._state(name)
        with state.lock:
            if state.failed:
                if self._cooloff_s is None or time.monotonic() - state.failed_at < self._cooloff_s:
                    raise ServiceFailed(state.failed)
                state.failed = ""
            if self._closed or live_processes.launches_refused():
                raise ServiceFailed(f"service {name!r} did not start: the run is ending")
            if state.context is None:
                self._start(name, state, task)
            state.holders += 1
            return state.address

    def _start(self, name: str, state: _State, task: Task) -> None:
        t0 = time.monotonic()
        try:
            context = state.service(name)
            address = context.__enter__()
            if address is not None and not isinstance(address, str):
                context.__exit__(None, None, None)
                raise TypeError(f"it gave {address!r}, not a string or None")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            state.failed = f"service {name!r} did not start: {error}"[:300]
            state.failed_at = time.monotonic()
            self._record(ServiceEvent(ts=now_iso(), event="start", name=name, key=task.key, error=error, wall_s=_since(t0)))
            self._log(f"[service] {state.failed}", True)
            raise ServiceFailed(state.failed) from exc
        state.context, state.address = context, address
        with self._lock:
            self._starts += 1
            state.started = self._starts
        self._record(ServiceEvent(ts=now_iso(), event="start", name=name, key=task.key, address=address, wall_s=_since(t0)))
        self._log(f"[service] {name} started for {task.key}" + (f" at {address}" if address else ""), False)

    def _release(self, name: str) -> None:
        state = self._state(name)
        with state.lock:
            state.holders -= 1

    def _stop(self, name: str, state: _State, cause: ServiceStopCause) -> None:
        context, state.context, state.address = state.context, None, None
        if context is None:
            return
        t0 = time.monotonic()
        error = None
        try:
            context.__exit__(None, None, None)
        except Exception as exc:  # a stop that raises still counts as stopped
            error = f"{type(exc).__name__}: {exc}"
        self._record(ServiceEvent(ts=now_iso(), event="stop", name=name, cause=cause, error=error, wall_s=_since(t0)))
        if error is not None:
            self._log(f"[service] {name}: its stop raised {error}"[:300], True)
        else:
            self._log(f"[service] {name} stopped ({cause.replace('_', ' ')})", False)

    def _record(self, event: ServiceEvent) -> None:
        try:
            append_lines(self._file, [event.model_dump_json(exclude_none=True)])
        except OSError as exc:  # a record that cannot be written must not stop the service's tasks
            self._log(f"[service] {self._file.name}: {exc}", True)


@contextmanager
def _running(task: Task, addresses: Mapping[str, str | None]) -> Iterator[None]:
    """`task` runs here, holding the services of `addresses` (`service_address`)."""
    held, claims = _addresses.set(addresses), _claims.set(tuple(task.claims))
    try:
        yield
    finally:
        _claims.reset(claims)
        _addresses.reset(held)


def _since(t0: float) -> float:
    return round(time.monotonic() - t0, 3)


class _Holding:
    """A runner whose tasks hold the services they claim while they run (`Services.wrap`)."""

    def __init__(self, services: Services, runner: TaskRunner, on_failed: Callable[[TaskResult], None] | None) -> None:
        self._services, self._runner, self._on_failed = services, runner, on_failed

    def config(self, task: Task) -> RunnerConfig:
        return self._runner.config(task)

    def deferral(self, task: Task) -> Deferral | None:
        ask: Any = getattr(self._runner, "deferral", None)
        return ask(task) if ask is not None else None

    def cancel(self, task: Task) -> None:
        ask: Any = getattr(self._runner, "cancel", None)
        if ask is not None:
            ask(task)

    def run(self, task: Task) -> TaskResult:
        try:
            with self._services.held(task):
                return self._runner.run(task)
        except ServiceFailed as exc:
            result = TaskResult.launch_failed(task, str(exc))
            if self._on_failed is not None:
                self._on_failed(result)
            return result
