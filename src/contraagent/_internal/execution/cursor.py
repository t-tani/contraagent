"""Externalize where a run is, so a resume never guesses.

`CursorStore` keeps the whole cursor — the run's stage, every unit's step,
every unit's in-flight dispatch, and a free-form marker list — in one JSON
file under one lock. Every mutation takes the lock, so two writers (a
worker thread and the main loop, or two processes) cannot interleave a
read-modify-write.

The file is `schemas.Cursor`'s only home: every write constructs or
mutates a `Cursor` (validated on construction and on every assignment)
before it is serialized.

Back-guard: advancing to an already-completed stage or step would walk the
cursor backward and leave a later one sitting in `completed` — a
contradictory cursor. `advance_stage` / `advance_step` refuse it, say so on
stderr, and return the *unchanged* cursor rather than raising.

The legal vocabulary is the domain's: pass `stages` / `steps` (any
iterable of names, e.g. an enum class) and an unknown name raises
`ValueError` before the model is touched. Omit them to accept any name.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from contraagent._internal.execution.schemas import Cursor, HistoryEntry, Inflight, UnitCursor
from contraagent._internal.platform import processes
from contraagent._internal.platform.locks import locks
from contraagent._internal.runs.files import read_document, write_document
from contraagent._internal.runs.times import now, now_iso

CURSOR_SCHEMA_VERSION = "1.0"


def _names(vocab: Iterable[Any] | None) -> frozenset[str] | None:
    if vocab is None:
        return None
    return frozenset(str(getattr(v, "value", v)) for v in vocab)


def parse_cursor(text: str) -> Cursor | None:
    """A cursor file's text as a `Cursor`, or None when it is empty or does not parse (a torn write)."""
    try:
        return Cursor.model_validate_json(text) if text.strip() else None
    except ValueError:
        return None


class CursorStore:
    """The run's resume cursor in one flock-guarded JSON file (see the module docstring)."""

    def __init__(
        self,
        path: str | Path,
        run: str = "",
        *,
        stages: Iterable[object] | None = None,
        steps: Iterable[object] | None = None,
        skip_when_completed: Iterable[object] = (),
    ) -> None:
        self.path: Path = Path(path)
        self.run = run
        self._stages = _names(stages)
        self._steps = _names(steps)
        # Steps an ordered step list drops once recorded complete; every other
        # step always runs (the cheap, idempotent ones).
        self._skip = _names(skip_when_completed) or frozenset()
        self._ordered_steps = [str(getattr(s, "value", s)) for s in (steps or ())]

    # --- storage -----------------------------------------------------------

    def _save(self, cursor: Cursor) -> None:
        """Written whole (`write_document`): a concurrent reader never sees a half-written file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_document(self.path, cursor.model_dump_json(indent=2) + "\n")

    @contextlib.contextmanager
    def _locked(self):
        """An exclusive lock (`locks`) across one read-modify-write, released even if
        the holder is killed mid-task."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path.with_suffix(self.path.suffix + ".lock"), os.O_CREAT | os.O_RDWR, 0o666)
        try:
            locks.lock(fd)
        except BaseException:
            os.close(fd)
            raise
        try:
            yield
        finally:
            locks.unlock(fd)
            os.close(fd)

    def read(self) -> Cursor | None:
        """The cursor on disk, or None when empty/absent/unreadable (a torn write)."""
        try:
            if not self.path.is_file():
                return None
            return parse_cursor(read_document(self.path))
        except OSError:
            return None

    def load(self) -> Cursor:
        """The cursor, or a fresh one when none exists yet. A malformed file raises."""
        text = read_document(self.path) if self.path.is_file() else ""
        if text.strip():
            return Cursor.model_validate_json(text)
        return Cursor(schema_version=CURSOR_SCHEMA_VERSION, run=self.run, updated_at=now())

    # --- mutations ---------------------------------------------------------

    def advance_stage(self, name: str, at: datetime | None = None) -> Cursor:
        """Move the run to stage `name`, completing the prior stage."""
        if self._stages is not None and name not in self._stages:
            raise ValueError(f"unknown stage {name!r}")
        with self._locked():
            cur = self.load()
            if name in cur.completed_stages:
                sys.stderr.write(f"cursor: refusing to advance to already-completed stage {name!r}; left at {cur.stage!r}\n")
                return cur
            when = at or now()
            prev = cur.stage
            if prev is not None and prev != name and prev not in cur.completed_stages:
                cur.completed_stages = [*cur.completed_stages, prev]
            cur.stage = name
            cur.history = [*cur.history, HistoryEntry(name=name, at=when)]
            cur.updated_at = when
            self._save(cur)
            return cur

    def advance_step(self, unit: str, step: str, at: datetime | None = None, loop_pass: int | None = None) -> Cursor:
        """Move `unit` to `step`, completing its prior step (same back-guard, per unit).

        Also stamps the unit's `stage` to the run's current stage, so a unit
        not touched since an earlier stage visibly lags rather than looking done.
        """
        if self._steps is not None and step not in self._steps:
            raise ValueError(f"unknown step {step!r}")
        with self._locked():
            cur = self.load()
            up = cur.units.get(unit) or UnitCursor()
            if step in up.completed:
                sys.stderr.write(f"cursor: refusing to advance unit {unit!r} to already-completed step {step!r}; left at {up.step!r}\n")
                return cur
            when = at or now()
            prev = up.step
            if prev is not None and prev != step and prev not in up.completed:
                up.completed = [*up.completed, prev]
            up.stage = cur.stage
            up.step = step
            if loop_pass is not None:
                up.loop_pass = loop_pass
            up.history = [*up.history, HistoryEntry(name=step, at=when)]
            cur.units = {**cur.units, unit: up}
            cur.updated_at = when
            self._save(cur)
            return cur

    def set_inflight(self, unit: str, item_ids: list[str], at: datetime | None = None) -> Cursor:
        """Record the work items dispatched but not yet recorded, before dispatch.

        Refuses when the previous dispatcher for this unit is still alive,
        checked against the OS process table: alive or dead is a fact to
        look up, not a duration to assume past. A dead dispatcher's record
        (the ordinary post-crash resume case, see `resume_view`) is replaced.
        """
        with self._locked():
            cur = self.load()
            up = cur.units.get(unit) or UnitCursor()
            prior = up.inflight
            if prior is not None and processes.identity_ok(prior.pid, prior.start_ticks):
                raise RuntimeError(
                    f"{self.run}/{unit}: pid {prior.pid} already has "
                    f"{prior.item_ids} in flight (since {prior.since}); "
                    f"refusing to also dispatch {item_ids} alongside it"
                )
            when = at or now()
            pid = os.getpid()
            up.inflight = Inflight(item_ids=list(item_ids), since=when, pid=pid, start_ticks=processes.start_ticks(pid))
            cur.units = {**cur.units, unit: up}
            cur.updated_at = when
            self._save(cur)
            return cur

    def clear_inflight(self, unit: str) -> Cursor:
        with self._locked():
            cur = self.load()
            up = cur.units.get(unit) or UnitCursor()
            up.inflight = None
            cur.units = {**cur.units, unit: up}
            cur.updated_at = now()
            self._save(cur)
            return cur

    def record(self, marker_key: str, entry: Mapping[str, Any]) -> Cursor:
        """Append `entry` to the marker list `marker_key`, stamped with `recorded_at`
        unless it carries one."""
        with self._locked():
            cur = self.load()
            entry = dict(entry)
            entry.setdefault("recorded_at", now_iso("microseconds"))
            cur.markers = {**cur.markers, marker_key: [*cur.markers.get(marker_key, []), entry]}
            cur.updated_at = now()
            self._save(cur)
            return cur

    # --- reads -------------------------------------------------------------

    def steps_to_run(self, unit: str) -> list[str]:
        """The steps `unit` still owes, in declared order: a step in
        `skip_when_completed` is dropped once the unit's `completed` names it."""
        up = self.load().units.get(unit)
        done = set(up.completed) if up is not None else set()
        return [s for s in self._ordered_steps if not (s in self._skip and s in done)]

    def resume_view(self) -> dict[str, Any]:
        """A thin diagnostic snapshot for a resume's startup print."""
        cur = self.load()
        return {
            "resume_stage": cur.stage,
            "units": {
                name: {
                    "stage": up.stage,
                    "step": up.step,
                    "completed": list(up.completed),
                    "redispatch_item_ids": list(up.inflight.item_ids) if up.inflight else [],
                }
                for name, up in cur.units.items()
            },
        }
