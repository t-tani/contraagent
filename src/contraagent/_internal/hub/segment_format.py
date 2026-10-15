"""The bytes of a sealed transcript segment, and its block table.

A segment holds consecutive lines of one log. Its lines are cut into blocks of whole
lines, each about `BLOCK_BYTES` uncompressed (a longer line makes a block of its own),
and each block is one zstd frame at `LEVEL`, compressed on its own so that any run of
blocks can be read with one ranged read and decompressed without the rest. The object is

    frame 0 | frame 1 | ... | frame n-1 | lines frame | seek table

* frame i: block i, a zstd frame with its content size, holding the block's lines, each
  followed by `\\n`.
* lines frame: a zstd skippable frame (magic `LINES_MAGIC`, then its content size as u32
  LE) holding, per block, its first line number (u64 LE) and line count (u32 LE).
* seek table: the zstd seekable format's seek table, which must end the object: a
  skippable frame (magic `SEEK_TABLE_MAGIC`, content size u32 LE) holding, per block, its
  compressed size and its uncompressed size (u32 LE each), then the 9-byte seek table
  footer: the number of frames (u32 LE), a descriptor byte (0: no checksums) and
  `SEEKABLE_MAGIC` (u32 LE).

`zstd -d` decompresses the whole object into the segment's lines (it skips skippable
frames), and the footer alone rebuilds the block table (`footer_length`, `parse_footer`),
so the bucket is enough to rebuild an index.

The block table of a segment (`Block`, packed by `pack_blocks` at `BLOCK_ENTRY.size`
bytes per block) gives each block's first line, its offset and size in the object, and
its uncompressed size: line k is in the last block whose first line is <= k.
"""

from __future__ import annotations

import struct
import threading
from collections.abc import Sequence
from typing import NamedTuple

import zstandard

#: A block is cut before the line that would take it past this many uncompressed bytes.
BLOCK_BYTES = 256 << 10

#: The zstd level of every block.
LEVEL = 3

SEEK_TABLE_MAGIC = 0x184D2A5E
SEEKABLE_MAGIC = 0x8F92EAB1
LINES_MAGIC = 0x184D2A50

#: One packed `Block`: first line, offset, compressed size, uncompressed size.
BLOCK_ENTRY = struct.Struct("<QQII")

_SKIPPABLE_HEADER = struct.Struct("<II")
_SEEK_ENTRY = struct.Struct("<II")
_LINES_ENTRY = struct.Struct("<QI")
_SEEK_FOOTER = struct.Struct("<IBI")

#: The bytes at the end of every segment object that give the footer's length.
TAIL_BYTES = _SEEK_FOOTER.size


class BadSegment(ValueError):
    """Bytes that are not a segment object (or not the part of one they should be)."""


class Block(NamedTuple):
    """One block of a sealed segment."""

    first_line: int
    offset: int
    compressed: int
    size: int


_local = threading.local()


def _compressor() -> zstandard.ZstdCompressor:
    c = getattr(_local, "c", None)
    if c is None:
        c = _local.c = zstandard.ZstdCompressor(level=LEVEL, write_content_size=True)
    return c


def _decompressor() -> zstandard.ZstdDecompressor:
    d = getattr(_local, "d", None)
    if d is None:
        d = _local.d = zstandard.ZstdDecompressor()
    return d


def cut(raw: bytes, first_line: int, block_bytes: int = BLOCK_BYTES) -> list[tuple[int, int]]:
    """The blocks of `raw` (whole lines, each ending in a newline) as (first line, byte
    offset) pairs, cut as `BlockCutter` cuts them."""
    cutter = BlockCutter(first_line, block_bytes)
    pos = 0
    while pos < len(raw):
        end = raw.index(b"\n", pos) + 1
        cutter.add(end - pos)
        pos = end
    return cutter.starts


class BlockCutter:
    """Cuts lines into blocks as they arrive: `starts` holds each block's first line and
    byte offset; a block takes lines until the next would take it past `block_bytes`."""

    def __init__(self, first_line: int, block_bytes: int = BLOCK_BYTES) -> None:
        self.block_bytes = block_bytes
        self.starts: list[tuple[int, int]] = [(first_line, 0)]
        self.lines = 0
        self.size = 0
        self._block = 0
        self._first = first_line

    def add(self, size: int) -> None:
        """One more line of `size` bytes, its newline included."""
        if self._block and self._block + size > self.block_bytes:
            self.starts.append((self._first + self.lines, self.size))
            self._block = 0
        self._block += size
        self.lines += 1
        self.size += size


def encode(raw: bytes | memoryview, starts: Sequence[tuple[int, int]], line_count: int) -> tuple[bytes, list[Block]]:
    """The object of a segment whose lines are `raw`, cut at `starts` (`BlockCutter.starts`),
    `line_count` lines in all; and its block table."""
    compressor = _compressor()
    frames: list[bytes] = []
    blocks: list[Block] = []
    counts: list[int] = []
    offset = 0
    first = starts[0][0]
    for i, (line, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(raw)
        upto = starts[i + 1][0] if i + 1 < len(starts) else first + line_count
        frame = compressor.compress(raw[start:end])
        frames.append(frame)
        blocks.append(Block(line, offset, len(frame), end - start))
        counts.append(upto - line)
        offset += len(frame)
    lines = b"".join(_LINES_ENTRY.pack(b.first_line, n) for b, n in zip(blocks, counts, strict=True))
    seek = b"".join(_SEEK_ENTRY.pack(b.compressed, b.size) for b in blocks)
    footer = (
        _SKIPPABLE_HEADER.pack(LINES_MAGIC, len(lines))
        + lines
        + _SKIPPABLE_HEADER.pack(SEEK_TABLE_MAGIC, len(seek) + _SEEK_FOOTER.size)
        + seek
        + _SEEK_FOOTER.pack(len(blocks), 0, SEEKABLE_MAGIC)
    )
    return b"".join(frames) + footer, blocks


def footer_length(tail: bytes) -> int:
    """The length of the footer (lines frame and seek table) of an object that ends with `tail`
    (at least its last `TAIL_BYTES` bytes)."""
    if len(tail) < TAIL_BYTES:
        raise BadSegment("too short for a seek table footer")
    n, descriptor, magic = _SEEK_FOOTER.unpack(tail[-TAIL_BYTES:])
    if magic != SEEKABLE_MAGIC or descriptor != 0:
        raise BadSegment("no seek table at the end")
    return 2 * _SKIPPABLE_HEADER.size + n * (_LINES_ENTRY.size + _SEEK_ENTRY.size) + TAIL_BYTES


def parse_footer(footer: bytes) -> tuple[list[Block], int]:
    """The block table and the line count that a footer (`footer_length` bytes) describes."""
    n = _SEEK_FOOTER.unpack(footer[-TAIL_BYTES:])[0]
    if len(footer) != footer_length(footer):
        raise BadSegment("footer of the wrong length")
    magic, size = _SKIPPABLE_HEADER.unpack_from(footer, 0)
    if magic != LINES_MAGIC or size != n * _LINES_ENTRY.size:
        raise BadSegment("no lines frame before the seek table")
    at = _SKIPPABLE_HEADER.size
    lines = [_LINES_ENTRY.unpack_from(footer, at + i * _LINES_ENTRY.size) for i in range(n)]
    at += size
    magic, size = _SKIPPABLE_HEADER.unpack_from(footer, at)
    if magic != SEEK_TABLE_MAGIC or size != n * _SEEK_ENTRY.size + TAIL_BYTES:
        raise BadSegment("bad seek table header")
    at += _SKIPPABLE_HEADER.size
    blocks: list[Block] = []
    offset = 0
    for i in range(n):
        compressed, raw = _SEEK_ENTRY.unpack_from(footer, at + i * _SEEK_ENTRY.size)
        blocks.append(Block(lines[i][0], offset, compressed, raw))
        offset += compressed
    count = sum(c for _, c in lines)
    return blocks, count


def pack_blocks(blocks: Sequence[Block]) -> bytes:
    """A block table as bytes (`BLOCK_ENTRY` per block), as an index keeps it."""
    return b"".join(BLOCK_ENTRY.pack(*b) for b in blocks)


def unpack_blocks(data: bytes) -> list[Block]:
    """The block table `pack_blocks` packed."""
    if len(data) % BLOCK_ENTRY.size:
        raise BadSegment("a block table of the wrong length")
    return [Block(*e) for e in BLOCK_ENTRY.iter_unpack(data)]


def decode(frame: bytes | memoryview) -> list[str]:
    """The lines of one block's frame."""
    raw = _decompressor().decompress(frame)
    return raw.decode().split("\n")[:-1]
