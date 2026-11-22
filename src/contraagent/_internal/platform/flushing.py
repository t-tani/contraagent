"""What was written, put on disk, so that a power loss does not take it back.

* `flush_file`: a file's content and size (`fdatasync` on Linux, `fsync` elsewhere).
* `flush_path`: `flush_file` of the file at a path.
* `flush_folder`: a folder's entries, so that a file created or renamed in it keeps its
  name. POSIX only: Windows opens no folder as a file, and NTFS journals its entries.

A file system that has no flush (some network and FUSE ones) answers `UNSUPPORTED`, which
is no error: nothing more can be done there. Any other failure is raised, since what was
written may then not be on disk.
"""

from __future__ import annotations

import errno
import os
import sys

#: The `errno` values of a file system that cannot flush.
UNSUPPORTED = frozenset({errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS})


def flush_file(fd: int) -> None:
    """Put what was written to the open file `fd` on disk."""
    try:
        if sys.platform == "linux":
            os.fdatasync(fd)
        else:
            os.fsync(fd)
    except OSError as exc:
        if exc.errno not in UNSUPPORTED:
            raise


def flush_path(path: str | os.PathLike[str]) -> None:
    """`flush_file` of the file at `path`; nothing when it is absent or may not be opened."""
    flags = os.O_RDWR if sys.platform == "win32" else os.O_RDONLY  # Windows flushes a writable handle only
    try:
        fd = os.open(path, flags)
    except (FileNotFoundError, PermissionError):
        return
    try:
        flush_file(fd)
    finally:
        os.close(fd)


def flush_folder(path: str | os.PathLike[str]) -> None:
    """Put the entries of the folder `path` on disk; nothing where it cannot be opened."""
    if sys.platform == "win32":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        flush_file(fd)
    finally:
        os.close(fd)
