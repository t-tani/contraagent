"""Reading and writing run records as files: one implementation of each.

* `write_document`: a document written whole, atomically (a reader sees the old text or
  the new, never a part).
* `append_lines`: lines appended to a log, each whole.
* `read_lines` (by line number) and `lines_at` (by byte offset, for a reader that keeps
  its place): a log's **complete** lines. A line is complete when its newline is written;
  a last line without one is still being written, and no reader sees it until it is
  complete. `seek_line` turns a line number into a byte offset.
* `parse_rows`, `read_rows`: the JSON objects of a log's lines; a line that does not
  parse, or is not an object, is skipped.

Lines are split on `\\n` only and decoded as UTF-8, an undecodable byte replaced: a
transcript is a coding agent's raw output.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import BinaryIO

#: How much of a log is read at a time while looking for a newline or counting lines.
BLOCK = 1 << 20

_append_lock = threading.Lock()


def write_document(path: str | os.PathLike[str], text: str | bytes, *, fsync: bool = False) -> Path:
    """Write the document `path` whole: `text` goes to a temporary file in the same
    folder, `.<name>.<pid>.<random>.tmp` (matched by no `*.json` or other suffix
    pattern), which then replaces `path`. A reader sees the old document or the new one,
    never a part; of writers racing on one document, the last replace wins. With `fsync`,
    the content is on disk before the replace. Returns `path`."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    data = text.encode() if isinstance(text, str) else text
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def append_lines(path: str | os.PathLike[str], lines: Iterable[str]) -> None:
    """Append `lines` to the log `path` (created when absent), each ended by a newline
    (one is added where a line has none), in one write: from any thread or process, the
    lines of one call are never split by another's."""
    data = "".join(line if line.endswith("\n") else line + "\n" for line in lines).encode()
    if not data:
        return
    with _append_lock:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o666)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
        finally:
            os.close(fd)


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
    with open(path, "rb") as f:
        raw, end = _take(f, start, max_bytes, max_lines)
    return _decode(raw), end


def seek_line(path: str | os.PathLike[str], n: int) -> tuple[int, int]:
    """Line `n` of the log `path`: `(n, the byte offset where it starts)`; when the log has
    fewer complete lines, `(their count, the byte offset after the last)`."""
    with open(path, "rb") as f:
        return _seek(f, n)


def read_lines(
    path: str | os.PathLike[str], since: int = 0, limit: int | None = None, max_bytes: int | None = None
) -> tuple[list[str], int]:
    """The complete lines `since`.. of the log `path`, bounded as `lines_at` bounds them, and
    how many complete lines it has. OSError when the log cannot be read."""
    with open(path, "rb") as f:
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
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            yield row


def read_rows(path: str | os.PathLike[str]) -> list[dict]:
    """The rows of the log `path` (`parse_rows` of its complete lines); none when it cannot be read."""
    try:
        return parse_rows(read_lines(path)[0])
    except OSError:
        return []
