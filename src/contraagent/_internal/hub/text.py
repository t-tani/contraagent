"""The text a hub holds, where a host's text is wider.

A Python string can hold two things a hub cannot:

* a lone surrogate, which is how Python gives a byte that is not UTF-8 in a file name or
  an argument, and which JSON text can escape. UTF-8 has no form for it, so neither has
  the wire. It becomes its escape written out (`\\udce9`, six characters), as Python
  logs it, so two such names stay two.
* a NUL, which a disk leaves where it lost a write, and which Postgres takes in no text
  and no jsonb. Outside a transcript, which is stored as bytes and keeps it, it becomes
  SUB (U+001A), the control character for one that cannot be represented. SUB is one
  byte as NUL is, and is as invalid in JSON wherever it stands: a line keeps its length,
  and a damaged line reads on the hub as it does on its host, as no row.

`protocol`'s models apply these, so a relay sends and a hub stores the same text. A reader
that looks up what a host named (`HubSource.file`) applies them to the name it looks up.
"""

from __future__ import annotations

from typing import Any

SUB = "\x1a"


def wire_text(text: str) -> str:
    """`text` as UTF-8 can carry it."""
    return text if text.isascii() else text.encode("utf-8", "backslashreplace").decode("utf-8")


def record_text(text: str) -> str:
    """`text` as a hub holds it outside a transcript: `wire_text`, and no NUL."""
    return wire_text(text).replace("\x00", SUB)


def record_value(value: Any) -> Any:
    """A JSON value with `record_text` applied to each of its strings, keys included."""
    if isinstance(value, str):
        return record_text(value)
    if isinstance(value, dict):
        return {record_value(k): record_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [record_value(v) for v in value]
    return value
