"""One launch's appends to its task's transcript (`Launch.stream_path`).

A transcript is what the monitor shows, so a write that fails never fails the launch: the
first failure is reported (`runs.failures`), and the rest of that launch's output is left
out of the transcript, so that what it holds has no gap. The next launch appends again, on
a line of its own (`files.open_log`).
"""

from __future__ import annotations

import os
from pathlib import Path

from contraagent._internal.backends.launch import Launch
from contraagent._internal.runs import failures, files, layout


class Transcript:
    """Appends to `launch.stream_path`; does nothing when the launch keeps no transcript.
    Made on the launch's thread, then written and closed by one thread."""

    def __init__(self, launch: Launch) -> None:
        self._path: Path | None = Path(launch.stream_path) if launch.stream_path is not None else None
        self._about = launch.label
        self._report = failures.reporter()
        self._fd: int | None = None

    def write(self, data: bytes) -> None:
        """Append `data`, all of it. Never raises for a write that fails."""
        if self._path is None:
            return
        try:
            if self._fd is None:
                log = files.open_log(self._path)
                self._fd, data = log.fd, log.lead + data
            files.write_all(self._fd, data)
        except Exception as exc:  # the agent's work matters more than its transcript
            self._failed(self._path, exc)

    def close(self) -> None:
        """Close the transcript. Never raises for a close that fails (a network file system
        can report a write's error there)."""
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            os.close(fd)
        except OSError as exc:
            if self._path is not None:
                self._failed(self._path, exc)

    def _failed(self, path: Path, error: Exception) -> None:
        self._path = None  # no more of this launch is written
        self.close()
        self._report(layout.STREAMS, error, self._about, path)
