"""JSON pointers to the parts of a JSON output a task must keep (`agent_task(preserve=)`).

A pointer is an RFC 6901 JSON pointer (`/items/0/id`; `~1` is a `/` in a name, `~0` a
`~`) with one extension: a segment `*` is every member of the array or object at that
level, so `/items/*/id` is the `id` of every item. A name that is `*` itself cannot be
named.

    select({"items": [{"id": "a"}, {"id": "b"}]}, "/items/*/id")
    # {"/items/0/id": "a", "/items/1/id": "b"}

`syntax_error` and `schema_error` judge a pointer when a task is declared;
`select` and `kept` judge a file: which values the pointers select in it as it was, and
whether the file as it is now still holds each of them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

#: The segment that is every member of an array or an object.
ANY = "*"

_INDEX = re.compile(r"0|[1-9][0-9]*")
_BAD_ESCAPE = re.compile(r"~(?![01])")


def segments(pointer: str) -> list[str]:
    """The segments of `pointer`, `~1` and `~0` undone (`/a~1b/*` -> `["a/b", "*"]`)."""
    return [s.replace("~1", "/").replace("~0", "~") for s in pointer.split("/")[1:]]


def pointer_of(parts: Iterable[str | int]) -> str:
    """The pointer that names `parts`, each escaped (`["a/b", 3]` -> `/a~1b/3`)."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def syntax_error(pointer: Any) -> str | None:
    """Why `pointer` is not a pointer to a part of a document; None when it is one."""
    if not isinstance(pointer, str):
        return f"{pointer!r} is not a string"
    if pointer == "":
        return '"" is the whole document; name the parts to keep'
    if not pointer.startswith("/"):
        return f"{pointer!r} does not start with /"
    if _BAD_ESCAPE.search(pointer):
        return f"{pointer!r}: ~ is ~0 or ~1 (a ~ or a / in a name)"
    return None


def schema_error(pointer: str, json_schema: Mapping[str, Any]) -> str | None:
    """Why `json_schema` holds nothing at `pointer`; None when some branch of it can.

    It follows `properties`, `additionalProperties`, `items`, `prefixItems`, `$ref` into the
    schema's own `$defs`, and every branch of `anyOf`, `oneOf` and `allOf`. A part of the
    schema that says nothing of its type (`Any`) holds anything under it."""
    root = json_schema
    nodes = [json_schema]
    done: list[str] = []
    for seg in segments(pointer):
        where = pointer_of(done) or "the document"
        nexts: list[Mapping[str, Any]] = []
        lists = False
        for node in (n for top in nodes for n in _branches(top, root)):
            if _open(node):
                nexts.append({})
                continue
            props = node.get("properties") or {}
            extra = node.get("additionalProperties")
            if seg == ANY:
                nexts += [p for p in props.values() if isinstance(p, Mapping)]
            elif seg in props:
                nexts.append(props[seg])
            if (seg == ANY or seg not in props) and extra is not None and extra is not False:
                nexts.append(extra if isinstance(extra, Mapping) else {})
            items, prefix = node.get("items"), node.get("prefixItems") or []
            if node.get("type") == "array" or items is not None or prefix:
                lists = True
                if seg == ANY or _INDEX.fullmatch(seg):
                    i = int(seg) if seg != ANY else None
                    nexts += [p for j, p in enumerate(prefix) if (i is None or i == j) and isinstance(p, Mapping)]
                    if isinstance(items, Mapping) and (i is None or i >= len(prefix)):
                        nexts.append(items)
        if not nexts:
            if lists and seg != ANY and not _INDEX.fullmatch(seg):
                return f"{pointer!r}: {where} is a list; name an index or *"
            return f"{pointer!r}: {where} has no field {seg!r} in the output schema"
        nodes = nexts
        done.append(seg)
    return None


def _branches(node: Mapping[str, Any], root: Mapping[str, Any], seen: frozenset[str] = frozenset()) -> list[Mapping[str, Any]]:
    """`node` with its `$ref` followed, and each branch of its `anyOf`/`oneOf`/`allOf`."""
    ref = node.get("$ref")
    if isinstance(ref, str):
        if ref in seen or not ref.startswith("#/"):
            return [{}]
        target: Any = root
        for part in segments(ref[1:]):
            target = target.get(part, {}) if isinstance(target, Mapping) else {}
        node = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        seen = seen | {ref}
    out = [node]
    for key in ("anyOf", "oneOf", "allOf"):
        for branch in node.get(key) or ():
            if isinstance(branch, Mapping):
                out += _branches(branch, root, seen)
    return out


def _open(node: Mapping[str, Any]) -> bool:
    """A part of a schema that says nothing of what it holds: anything may be under it."""
    shaped = ("type", "properties", "additionalProperties", "items", "prefixItems", "anyOf", "oneOf", "allOf", "$ref", "enum", "const")
    return not any(k in node for k in shaped)


def select(document: Any, pointer: str) -> dict[str, Any]:
    """The values `pointer` selects in `document`, by the pointer that names each one alone
    (`*` replaced by the member's name or index). A part the document does not hold
    selects nothing."""
    found: dict[str, Any] = {}

    def walk(value: Any, rest: list[str], at: list[str | int]) -> None:
        if not rest:
            found[pointer_of(at)] = value
            return
        seg, more = rest[0], rest[1:]
        if isinstance(value, dict):
            for name in value if seg == ANY else [seg] if seg in value else []:
                walk(value[name], more, [*at, name])
        elif isinstance(value, list):
            for i in range(len(value)) if seg == ANY else [int(seg)] if _INDEX.fullmatch(seg) and int(seg) < len(value) else []:
                walk(value[i], more, [*at, i])

    walk(document, segments(pointer), [])
    return found


def select_all(document: Any, pointers: Iterable[str]) -> dict[str, Any]:
    """The values every one of `pointers` selects in `document` (`select`), in one map."""
    out: dict[str, Any] = {}
    for p in pointers:
        out.update(select(document, p))
    return out


def kept(document: Any, before: Mapping[str, Any]) -> list[str]:
    """What `document` no longer holds of `before` (`select_all` of the file as it was): one
    line per part, `/items/3/id changed: it must stay "a1" (now "b2")` or `/source removed:
    it must stay "x"`. Empty when every part is there with an equal value."""
    errors = []
    for pointer, was in before.items():
        now = select(document, pointer)
        if pointer not in now:
            errors.append(f"{pointer} removed: it must stay {_shown(was)}")
        elif not same(now[pointer], was):
            errors.append(f"{pointer} changed: it must stay {_shown(was)} (now {_shown(now[pointer])})")
    return errors


def same(a: Any, b: Any) -> bool:
    """Two JSON values are equal: numbers by value (`1` and `1.0`), a boolean only to a
    boolean, objects by their members whatever their order, arrays element by element."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b


def _shown(value: Any, limit: int = 120) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"
