"""The views of a run: what the monitor answers about a run, by name, in one table.

Each `View` in `VIEWS` is answered three ways from the same `read` and `model`:

* the HTTP endpoint `/api/runs/<run>/<name>` (`server.create_app`; `doc` is its description);
* the run feed's `<name>` event, sent when its value changed (`server.run_feed`, for the
  views the feed sends: the journal row by row, `procs`, `plan`, `outputs`, `forecast`, `cursor`);
* the export's `data/runs/<run>/<name>.json` (`export.export`, for the views with `export`).

`serialize` is how each of them is written: checked against its model, the keys the
core did not emit left out. `serialize_kept` writes a value the monitor keeps between
requests (`Monitor.plan`, `Monitor.outputs`) once, for every feed that sends it.
"""

from __future__ import annotations

import functools
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from contraagent._internal.monitor import api
from contraagent._internal.monitor.core import Monitor


@dataclass(frozen=True)
class View:
    """One view of a run: `name` (its endpoint's last part, its feed event, its export file),
    `read(monitor, run)` its value, `model` the contract it is checked against, `doc` the
    endpoint's description; `export` when an export holds it."""

    name: str
    read: Callable[[Monitor, str], Any]
    model: Any
    doc: str
    export: bool = True


def _journal(monitor: Monitor, run: str) -> dict:
    entries, total = monitor.journal(run)
    return {"entries": entries, "total": total}


#: The views of a run, in the order the API lists them. The journal's endpoint takes the line
#: offset `since` (its `read` is the whole journal, as the export holds it).
VIEWS: dict[str, View] = {
    v.name: v
    for v in (
        View("journal", _journal, api.JournalPage, "Journal rows after line offset `since`; `total` is the next offset."),
        View(
            "plan",
            lambda m, run: m.plan(run),
            api.Plan,
            "Every queued task with its dependencies and state, and the groups the UI draws as columns.",
        ),
        View(
            "outputs",
            lambda m, run: m.outputs(run),
            api.Outputs,
            "Every declared output/input contract: its file, the model it must satisfy, its status.",
        ),
        View(
            "forecast",
            lambda m, run: m.forecast(run),
            api.Forecast,
            "The tasks the run is expected to create and has not yet, from the run of the same flow that finished last "
            "before it started; a display only.",
        ),
        View("definitions", lambda m, run: m.definitions(run), list[api.TaskDefinition], "What defined each kind of task in this run."),
        View("cursor", lambda m, run: m.cursor(run) or {}, api.CursorView, "The resume cursor; `{}` when the run keeps none."),
        View(
            "procs", lambda m, run: m.procs(run), api.Procs, "The run's live agent launches, process tree and Python tasks.", export=False
        ),
    )
}


@functools.cache
def _adapter(model: Any) -> TypeAdapter:
    return TypeAdapter(model)


def serialize(model: Any, value: Any) -> str:
    """`value` checked against its contract model and written as the wire carries it (JSON).
    `exclude_unset`: a key the core did not emit is not invented (see `api`)."""
    adapter = _adapter(model)
    return adapter.dump_json(adapter.validate_python(value), exclude_unset=True, by_alias=True).decode()


#: How many written values `serialize_kept` keeps.
KEPT_TEXTS = 64
_texts: OrderedDict[tuple[int, int], tuple[Any, Any, str]] = OrderedDict()
_texts_lock = threading.Lock()


def serialize_kept(model: Any, value: Any) -> str:
    """`serialize(model, value)`, written once for the same value: a view the monitor
    keeps between requests is the same object until it is made again, so each client's
    feed is given the text the first one wrote. The last `KEPT_TEXTS` are kept, with the
    values themselves, so an id is never another value's."""
    key = (id(model), id(value))
    with _texts_lock:
        held = _texts.get(key)
        if held is not None and held[0] is model and held[1] is value:
            _texts.move_to_end(key)
            return held[2]
    text = serialize(model, value)
    with _texts_lock:
        _texts[key] = (model, value, text)
        while len(_texts) > KEPT_TEXTS:
            _texts.popitem(last=False)
    return text
