"""A task's templates: text naming `{unit}`, `{key}`, `{kind}` and `{params.<name>}`, filled
from one task call. A claim (`claims=`) is one; in a stub run, so is each string of an
output's example (`fill_example`)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

#: A template's `{params.<name>}` field, without its braces.
PARAM_FIELD = re.compile(r"params\.([A-Za-z_][A-Za-z0-9_]*)")
#: A field as written in a template.
_FIELD = re.compile(r"\{(unit|key|kind|params\.[A-Za-z_][A-Za-z0-9_]*)\}")


def fill_example(value: Any, *, unit: str, key: str, kind: str, params: Mapping[str, Any]) -> Any:
    """`value` with each of its strings filled in, in lists and objects too: a field whose
    value is a string or a number is replaced by it; any other field (`{unit}` of a task
    with no unit, a parameter the call does not give, or one that holds a list or an
    object), and any other text in braces, stays as written."""

    def one(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in ("unit", "key", "kind"):
            v: Any = {"unit": unit, "key": key, "kind": kind}[name]
            return v if v else m.group(0)
        v = params.get(name.removeprefix("params."), m)
        return str(v) if isinstance(v, (str, int, float)) and not isinstance(v, bool) else m.group(0)

    if isinstance(value, str):
        return _FIELD.sub(one, value)
    if isinstance(value, list):
        return [fill_example(v, unit=unit, key=key, kind=kind, params=params) for v in value]
    if isinstance(value, dict):
        return {k: fill_example(v, unit=unit, key=key, kind=kind, params=params) for k, v in value.items()}
    return value
