"""Reading and writing run records as files: one implementation of each.

* `write_document`: a document written whole, atomically (a reader sees the old text or
  the new, never a part); with `fsync`, on disk when it returns.
* `append_lines`: lines appended to a log, each whole; with `fsync`, on disk when it
  returns. `open_log` and `write_all` are its parts, for a writer that holds a log open.
  A last line cut short (a write that failed, a process killed as it wrote) is ended by
  the next write, so it spoils no line but itself.
* `read_lines` (by line number) and `lines_at` (by byte offset, for a reader that keeps
  its place): a log's **complete** lines. A line is complete when its newline is written;
  a last line without one is still being written, and no reader sees it until it is
  complete. `seek_line` turns a line number into a byte offset; `last_line` reads the
  last complete line from the end.
* `parse_rows`: the JSON objects of lines, for a reader of what a run left; a line that
  does not parse, or is not an object, is skipped.
* `read_log`, `read_rows`: a whole log for a reader that rests on it: empty only when it
  is absent, `OSError` when it cannot be read; `read_log` also says which lines did not
  read.

Lines are split on `\\n` only and decoded as UTF-8, an undecodable byte replaced: a
transcript is a coding agent's raw output.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import threading
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, BinaryIO, NamedTuple

from contraagent._internal.platform import sharing
from contraagent._internal.platform.flushing import flush_file, flush_folder

#: How much of a log is read at a time while looking for a newline or counting lines.
BLOCK = 1 << 20

_append_lock = threading.Lock()

#: `os.open`'s flag for a file whose bytes are written as given: on Windows a file descriptor
#: is opened in text mode otherwise, and each `\n` written becomes `\r\n`.
BINARY = getattr(os, "O_BINARY", 0)


def write_document(path: str | os.PathLike[str], text: str | bytes, *, fsync: bool = False) -> Path:
    """Write the document `path` whole: `text` goes to a temporary file in the same
    folder, `.<name>.<pid>.<random>.tmp` (matched by no `*.json` or other suffix
    pattern), which then replaces `path`. A reader sees the old document or the new one,
    never a part. A reader that holds the old one open does not stop the replace, on
    Windows too (`platform.sharing.replace`). Of writers racing on one document, the last
    replace wins. With `fsync`, the content is on disk before the replace, and the
    replace when this returns. Returns `path`."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    data = text.encode() if isinstance(text, str) else text
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | BINARY, 0o666)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            if fsync:
                f.flush()
                flush_file(f.fileno())
        sharing.replace(tmp, path)
        if fsync:
            flush_folder(path.parent)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def read_document(path: str | os.PathLike[str]) -> str:
    """The document `path` whole, as UTF-8 (a byte that is none is replaced): the old one or
    the new one while `write_document` replaces it, which this read does not stop (on
    Windows too: see `platform.sharing`). `OSError` when `path` cannot be read."""
    with sharing.open_text(path) as f:
        return f.read()


def write_all(fd: int, data: bytes) -> None:
    """Write all of `data` to `fd`: one write can take a part of it. `OSError` when it cannot."""
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


class OpenLog(NamedTuple):
    """A log open for appending (`open_log`)."""

    #: Its file descriptor.
    fd: int
    #: Its size when it was opened.
    size: int
    #: What the first write to it starts with: a newline when its last line has none, else
    #: nothing.
    lead: bytes


def open_log(path: str | os.PathLike[str]) -> OpenLog:
    """Open the log `path` for appending (created when absent). The caller is the log's one
    writer, so a last line without its newline is one whose write was cut (a full disk, a
    host that lost power), not one being written. The first write ends it, with the newline
    of `OpenLog.lead` in the same write as what follows: what is written then starts a line
    of its own, and a write cut again leaves the first bytes of that same data."""
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | BINARY, 0o666)
    try:
        st = os.fstat(fd)
        lead = b""
        if stat.S_ISREG(st.st_mode) and st.st_size:
            os.lseek(fd, st.st_size - 1, os.SEEK_SET)
            if os.read(fd, 1) != b"\n":
                lead = b"\n"
    except BaseException:
        os.close(fd)
        raise
    return OpenLog(fd, st.st_size, lead)


def append_lines(path: str | os.PathLike[str], lines: Iterable[str], *, fsync: bool = False) -> None:
    """Append `lines` to the log `path` (created when absent), each ended by a newline
    (one is added where a line has none), in one write, which first ends a last line cut
    short (`open_log`): from any thread, the lines of one call are never split by
    another's. Across processes that holds where the OS appends atomically (POSIX), not on
    Windows; a run's logs have one writer process, the one that holds the run lock. With
    `fsync`, the lines are on disk when this returns, and the log's name with them when
    they are its first.

    A reader skips the line that was cut (`parse_rows`) and reads every line appended
    after it."""
    data = "".join(line if line.endswith("\n") else line + "\n" for line in lines).encode()
    if not data:
        return
    with _append_lock:
        log = open_log(path)
        try:
            write_all(log.fd, log.lead + data)
        except BaseException:
            os.close(log.fd)
            raise
    try:  # out of the lock: a flush takes milliseconds
        if fsync:
            flush_file(log.fd)
            if not log.size:
                flush_folder(Path(path).parent)
    finally:
        os.close(log.fd)


def _decode(raw: list[bytes]) -> list[str]:
    # A newline byte is never inside a UTF-8 sequence, so each line decodes on its own.
    return [line.decode("utf-8", errors="replace") for line in raw]


def _take(f: BinaryIO, start: int, max_bytes: int | None, max_lines: int | None) -> tuple[list[bytes], int]:
    """The complete lines of `f` from byte `start`, bounded as `lines_at` bounds them, and the
    byte offset after the last."""
    if max_lines is not None and max_lines <= 0:
        return [], start
    f.seek(start)
    buf = f.read(max_bytes) if max_bytes is not None else f.read()
    cut = buf.rfind(b"\n")
    while cut < 0:
        more = f.read(BLOCK)
        if not more:
            return [], start
        found = more.find(b"\n")
        if found >= 0:
            cut = len(buf) + found
        buf += more
    raw = buf[: cut + 1].split(b"\n")[:-1]
    if max_lines is not None:
        raw = raw[:max_lines]
    return raw, start + sum(len(line) + 1 for line in raw)


def _seek(f: BinaryIO, n: int) -> tuple[int, int]:
    """`seek_line` on an open file."""
    count = pos = after = 0
    if n <= 0:
        return 0, 0
    f.seek(0)
    while block := f.read(BLOCK):
        here = block.count(b"\n")
        if count + here < n:
            count += here
            if here:
                after = pos + block.rfind(b"\n") + 1
            pos += len(block)
            continue
        at = -1
        for _ in range(n - count):
            at = block.find(b"\n", at + 1)
        return n, pos + at + 1
    return count, after


def _count(f: BinaryIO, start: int) -> int:
    """The complete lines of `f` from byte `start`."""
    f.seek(start)
    n = 0
    while block := f.read(BLOCK):
        n += block.count(b"\n")
    return n


def lines_at(
    path: str | os.PathLike[str], start: int = 0, max_bytes: int | None = None, max_lines: int | None = None
) -> tuple[list[str], int]:
    """The complete lines of the log `path` from byte `start` (a line's start), without
    their newline: at most `max_lines`, and at most `max_bytes` bytes with their newlines
    unless the first line alone is longer. Returns them and the byte offset after the last
    one; `([], start)` when no complete line follows `start`. OSError when the log cannot
    be read."""
    with sharing.open_shared(path) as f:
        raw, end = _take(f, start, max_bytes, max_lines)
    return _decode(raw), end


def last_line(path: str | os.PathLike[str]) -> str | None:
    """The last complete line of the log `path`, without its newline, read backwards from
    the end a block at a time; None when it has no complete line. OSError when the log
    cannot be read."""
    with sharing.open_shared(path) as f:
        pos = f.seek(0, os.SEEK_END)
        buf = b""
        end: int | None = None  # where the last complete line's newline is, in `buf`
        while pos > 0:
            step = min(BLOCK, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            end = buf.rfind(b"\n") if end is None else end + step
            if end < 0:
                end = None
                continue
            start = buf.rfind(b"\n", 0, end)
            if start >= 0:
                return _decode([buf[start + 1 : end]])[0]
        return _decode([buf[:end]])[0] if end is not None else None


def seek_line(path: str | os.PathLike[str], n: int) -> tuple[int, int]:
    """Line `n` of the log `path`: `(n, the byte offset where it starts)`; when the log has
    fewer complete lines, `(their count, the byte offset after the last)`."""
    with sharing.open_shared(path) as f:
        return _seek(f, n)


def read_lines(
    path: str | os.PathLike[str], since: int = 0, limit: int | None = None, max_bytes: int | None = None
) -> tuple[list[str], int]:
    """The complete lines `since`.. of the log `path`, bounded as `lines_at` bounds them, and
    how many complete lines it has. OSError when the log cannot be read."""
    with sharing.open_shared(path) as f:
        n, at = _seek(f, since)
        if n < since:
            return [], n
        raw, end = _take(f, at, max_bytes, limit)
        return _decode(raw), since + len(raw) + _count(f, end)


def parse_rows(lines: Iterable[str]) -> list[dict]:
    """The JSON objects of `lines`; a line that does not parse (a torn write) or is not an
    object is skipped."""
    return list(iter_rows(lines))


def iter_rows(lines: Iterable[str]) -> Iterator[dict]:
    """`parse_rows`, one row at a time."""
    for line in lines:
        if (row := _row(line)) is not None:
            yield row


def _row(line: str) -> dict[str, Any] | None:
    """The JSON object of `line`, else None."""
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


class LogRows(NamedTuple):
    """A whole log, read (`read_log`)."""

    #: The JSON objects of its complete lines, in their order.
    rows: list[dict[str, Any]]
    #: The numbers, from 1, of its complete lines that are no JSON object; a blank line is none.
    unread: list[int]
    #: Whether its last line has no newline.
    cut_short: bool


def read_log(path: str | os.PathLike[str]) -> LogRows:
    """The whole log `path`; empty when it is absent, and only then. `OSError` when it
    cannot be read: what cannot be read is not known to be empty."""
    try:
        with sharing.open_shared(path) as f:
            *lines, tail = f.read().split(b"\n")
    except FileNotFoundError:
        return LogRows([], [], False)
    rows: list[dict[str, Any]] = []
    unread: list[int] = []
    for n, line in enumerate(_decode(lines), 1):
        if (row := _row(line)) is not None:
            rows.append(row)
        elif line.strip():
            unread.append(n)
    return LogRows(rows, unread, bool(tail))


def read_rows(path: str | os.PathLike[str]) -> list[dict]:
    """The rows of the log `path` (`read_log`): none when it is absent, `OSError` when it
    cannot be read."""
    return read_log(path).rows
