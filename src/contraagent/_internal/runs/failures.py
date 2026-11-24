"""Where a run record that only the monitor reads is reported when it cannot be written.

Such a record never fails what wrote it: the writer reports it here and goes on. A run's
runners name the run's report for the thread they run a task on (`reported_to`), so a
writer below them (a transcript, a contract record) reports to the run, which says it and
counts it (`record_failures`), without being given the run. Outside a run the report is a
warning of this module's logger.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import Protocol

_logger = logging.getLogger(__name__)


class RecordFailed(Protocol):
    """`report(name, error, about, path)`: the record `path` could not be written for
    `error`; `name` is what it is counted by (a log's name, or the folder of a record kept
    one file per task or kind), `about` the task, kind or flow call it is of."""

    def __call__(self, name: str, error: Exception, about: str, path: Path, /) -> None: ...


def _warn(name: str, error: Exception, about: str, path: Path) -> None:
    what = f" for {about}" if about else ""
    _logger.warning("[error] %s not written%s: %s: %s", path.as_posix(), what, type(error).__name__, error)


_report: ContextVar[RecordFailed | None] = ContextVar("contraagent_record_failed", default=None)


@contextlib.contextmanager
def reported_to(report: RecordFailed | None) -> Iterator[None]:
    """The records that fail in the block are reported to `report`; None keeps the report in effect."""
    if report is None:
        yield
        return
    token = _report.set(report)
    try:
        yield
    finally:
        _report.reset(token)


def reporter() -> RecordFailed:
    """The report in effect on this thread. A writer that writes on a thread of its own
    takes it on the thread that starts it."""
    return _report.get() or _warn
