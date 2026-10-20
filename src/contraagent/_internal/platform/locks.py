"""An exclusive lock on an open file, which the OS releases when its holder ends, however
it ends: a run's lock and a cursor's read-modify-write rest on that.

* POSIX (Linux, macOS): `flock` on the whole file (`PosixLocks`).
* Windows: `msvcrt.locking` on the file's first byte (`WindowsLocks`); a lock past the
  end of the file is allowed, so the file may be empty.

On both, a lock is held by one open file, so a second open of the same file is refused
it, in this process as in another. `locks` is this OS's; each takes the OS's call in its
constructor, so each can be tested on any OS against a fake.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Protocol


class Locks(Protocol):
    """An exclusive lock on an open file (a file descriptor), on one OS."""

    def try_lock(self, fd: int) -> bool:
        """Take the lock if no other open file holds it; True when taken."""
        ...

    def lock(self, fd: int) -> None:
        """Take the lock, waiting while another open file holds it."""
        ...

    def unlock(self, fd: int) -> None:
        """Give the lock back."""
        ...


class PosixLocks:
    """`flock`; `flock` and its constants are given in a test."""

    def __init__(self, fcntl_module=None) -> None:
        if fcntl_module is None:
            import fcntl as fcntl_module
        self._f: Any = fcntl_module

    def try_lock(self, fd: int) -> bool:
        """False only when another open file holds the lock (`EWOULDBLOCK`, which Python
        raises as `BlockingIOError`). Any other `OSError` is raised: a file system with no
        `flock` (`ENOLCK` on some NFS mounts) is not a lock someone else holds."""
        try:
            self._f.flock(fd, self._f.LOCK_EX | self._f.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def lock(self, fd: int) -> None:
        self._f.flock(fd, self._f.LOCK_EX)

    def unlock(self, fd: int) -> None:
        self._f.flock(fd, self._f.LOCK_UN)


class WindowsLocks:
    """`msvcrt.locking` on the first byte; `msvcrt` (its `locking`, `LK_NBLCK`, `LK_UNLCK`)
    is given in a test. `poll_s`: how often a waiting `lock` tries again."""

    def __init__(self, msvcrt_module=None, poll_s: float = 0.05) -> None:
        if msvcrt_module is None:
            import msvcrt as msvcrt_module
        self._m: Any = msvcrt_module
        self._poll_s = poll_s

    def try_lock(self, fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)  # the lock is on the bytes from the file position
        try:
            self._m.locking(fd, self._m.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def lock(self, fd: int) -> None:
        while not self.try_lock(fd):
            time.sleep(self._poll_s)

    def unlock(self, fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        self._m.locking(fd, self._m.LK_UNLCK, 1)


#: This OS's locks.
locks: Locks = WindowsLocks() if sys.platform == "win32" else PosixLocks()
