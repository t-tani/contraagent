"""A file replaced while other processes read it, on Linux, macOS and Windows alike.

* `open_shared`: a file opened for reading that does not stop a replace of it.
* `replace`: a file put in place of another, which readers that hold the old one open do
  not stop: they go on reading the old file, and a later open reads the new one.

POSIX gives both: `open` and `rename`. On Windows a file is replaced only when every open
handle to it lets it be deleted (`FILE_SHARE_DELETE`), which Python's `open` does not ask
for, and `os.replace` (`MoveFileExW`) fails while any handle to the target is open. So on
Windows `open_shared` opens with `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE`,
and `replace` renames with POSIX semantics: the source is opened with `DELETE` access and
renamed by `SetFileInformationByHandle(FileRenameInfoEx, FILE_RENAME_FLAG_REPLACE_IF_EXISTS
| FILE_RENAME_FLAG_POSIX_SEMANTICS)`. Git does the same for its reftable list (the
`ps/mingw-rename` series, compat/mingw.c), and so does Rust's `std::fs::rename`
(rust-lang/rust#131072). See MS-FSCC 2.4.42.2, FileRenameInformationEx.

Where the file system has no POSIX rename (FAT, exFAT, some network shares, Windows before
10 version 1607), the call fails with `ERROR_INVALID_PARAMETER` or `ERROR_NOT_SUPPORTED`,
and `replace` uses `os.replace`. There, and for a process outside contraagent that holds the
target without `FILE_SHARE_DELETE` (an editor, a virus scanner), the replace is refused
while the target is open. `replace` then waits until that holder closes it, however long
that takes, and logs once which file it waits for: a lost write is worse than a late one.
It raises at once when the refusal is one that no close ends: the target is a folder, is
read-only, or its access control denies deleting it.
"""

from __future__ import annotations

import io
import logging
import os
import stat
import sys
import time
from typing import BinaryIO

_logger = logging.getLogger(__name__)

#: How often a refused replace is tried again while another process holds the target: the
#: time between that holder's close and the replace, never a limit on the wait.
POLL_S = 0.05


if sys.platform == "win32":
    import _winapi
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _GENERIC_READ = 0x80000000
    _DELETE = 0x00010000
    _SYNCHRONIZE = 0x00100000
    _SHARE_ALL = 0x1 | 0x2 | 0x4  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    _OPEN_EXISTING = 3

    _FILE_RENAME_INFO_EX = 22  # FILE_INFO_BY_HANDLE_CLASS.FileRenameInfoEx
    _REPLACE_IF_EXISTS = 0x1  # FILE_RENAME_FLAG_REPLACE_IF_EXISTS
    _POSIX_SEMANTICS = 0x2  # FILE_RENAME_FLAG_POSIX_SEMANTICS

    _ERROR_ACCESS_DENIED = 5
    _ERROR_NOT_SUPPORTED = 50
    _ERROR_INVALID_PARAMETER = 87

    class _RenameInfo(ctypes.Structure):
        """FILE_RENAME_INFO; `FileName` runs on past the structure, NUL-terminated."""

        _fields_ = (
            ("Flags", wintypes.DWORD),  # a union with BOOLEAN ReplaceIfExists
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),  # in bytes, without the NUL
            ("FileName", wintypes.WCHAR * 1),
        )

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _set_info = _kernel32.SetFileInformationByHandle
    _set_info.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    _set_info.restype = wintypes.BOOL

    def _create(path: str, access: int) -> int:
        """`CreateFileW` of an existing file with every sharing mode; `OSError` names `path`."""
        try:
            return _winapi.CreateFile(path, access, _SHARE_ALL, 0, _OPEN_EXISTING, 0, 0)
        except OSError as e:
            raise OSError(e.errno, e.strerror, path, e.winerror) from None

    def _open(path: str) -> BinaryIO:
        handle = _create(path, _GENERIC_READ)
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            _winapi.CloseHandle(handle)
            raise
        return open(fd, "rb")

    def _rename_posix(src: str, dst: str) -> bool:
        """Rename `src` over `dst` with POSIX semantics; False where the file system has none."""
        target = ctypes.create_unicode_buffer(os.path.abspath(dst))
        offset = _RenameInfo.FileName.offset
        buf = ctypes.create_string_buffer(max(ctypes.sizeof(_RenameInfo), offset + ctypes.sizeof(target)))
        info = _RenameInfo.from_buffer(buf)
        info.Flags = _REPLACE_IF_EXISTS | _POSIX_SEMANTICS
        info.FileNameLength = ctypes.sizeof(target) - ctypes.sizeof(wintypes.WCHAR)
        ctypes.memmove(ctypes.addressof(buf) + offset, target, ctypes.sizeof(target))
        handle = _create(src, _DELETE | _SYNCHRONIZE)
        try:
            if _set_info(handle, _FILE_RENAME_INFO_EX, ctypes.byref(buf), len(buf)):
                return True
            error = ctypes.get_last_error()
        finally:
            _winapi.CloseHandle(handle)
        if error in (_ERROR_INVALID_PARAMETER, _ERROR_NOT_SUPPORTED):
            return False
        raise OSError(0, ctypes.FormatError(error), src, error, dst)

    def _replace_once(src: str, dst: str) -> None:
        if not _rename_posix(src, dst):
            os.replace(src, dst)

    def _refusal_stays(dst: str) -> bool:
        """Whether a refused replace onto `dst` is refused for a reason no close ends: `dst`
        is a folder, is read-only, or may not be deleted. A holder that did not share
        deleting makes the open below fail with a sharing violation instead."""
        try:
            st = os.lstat(dst)
        except FileNotFoundError:
            return False
        if stat.S_ISDIR(st.st_mode) or st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
            return True
        try:
            _winapi.CloseHandle(_create(dst, _DELETE))
        except OSError as e:
            return e.winerror == _ERROR_ACCESS_DENIED
        return False

else:

    def _open(path: str) -> BinaryIO:
        return open(path, "rb")

    def _replace_once(src: str, dst: str) -> None:
        os.replace(src, dst)

    def _refusal_stays(dst: str) -> bool:
        return True


def open_shared(path: str | os.PathLike[str]) -> BinaryIO:
    """`path` opened for reading, as bytes. A replace of `path` is not stopped by it, and it
    goes on reading the old file. `OSError` when `path` cannot be opened."""
    return _open(os.fspath(path))


def open_text(path: str | os.PathLike[str]) -> io.TextIOWrapper:
    """`open_shared`, decoded as UTF-8 (a byte that is none is replaced), newlines as `open`
    reads them in text mode."""
    return io.TextIOWrapper(open_shared(path), encoding="utf-8", errors="replace")


def replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    """Put the file `src` in place of `dst`, in one step: an open of `dst` finds the old file
    or the new one, and a reader that holds the old one open goes on reading it. On Windows,
    while a process that does not share deleting holds `dst` (or `dst` is on a file system
    without POSIX rename and anything holds it), this waits until it is closed; see the
    module. `OSError` when the replace is refused for another reason."""
    src, dst = os.fspath(src), os.fspath(dst)
    waiting = False
    while True:
        try:
            _replace_once(src, dst)
            return
        except PermissionError:
            if _refusal_stays(dst):
                raise
        if not waiting:
            _logger.warning("%s is held open by another process; its replace waits until it is closed", dst)
            waiting = True
        time.sleep(POLL_S)
