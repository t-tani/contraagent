"""A pipeline's own records in its run, and a run panel that shows them.

    contraagent monitor --runs-dir runs --panels path/to/records.py:PANELS

The flow and its Python tasks keep what the pipeline wants to see of a run in the run
itself: `contraagent.log(name, row)` appends a row to a pipeline log,
`contraagent.save(name, value)` writes a pipeline document. A relay ships them to a hub
with the rest of the run, and the panel reads them back through the `RunRecords` it is
given, wherever the monitor reads the run.
"""

from __future__ import annotations

from pydantic import BaseModel

import contraagent
from contraagent import python_task
from contraagent.monitor import Panel, RunRecords
from contraagent.monitor.api import BlocksBody, PanelTile, TableBody, TableColumn, TilesBody


class Count(BaseModel):
    unit: str
    words: int


@python_task
def count(unit: str, text: str) -> Count:
    """A Python task: count a text's words, and log the count as a row of `counts`."""
    words = len(text.split())
    contraagent.log("counts", {"unit": unit, "words": words})
    return Count(unit=unit, words=words)


def tally(texts: dict[str, str]):
    """Every text's count at once; then the flow keeps the total as the document `total`."""
    counts = yield [count(unit, text=text) for unit, text in texts.items()]
    contraagent.save("total", {"units": len(counts), "words": sum(c.words for c in counts)})


def words(run: RunRecords) -> BlocksBody:
    """The run's counts, from its pipeline log, and their total, from its pipeline document."""
    total = run.document("total") or {}  # None while the flow has not saved it
    return BlocksBody(
        blocks=[
            TilesBody(tiles=[PanelTile(id="words", label="Words", value=total.get("words", "—"))]),
            TableBody(
                title="By unit",
                columns=[TableColumn(id="unit", label="Unit"), TableColumn(id="words", label="Words", format="number")],
                rows=run.log("counts"),
            ),
        ],
    )


#: What `contraagent monitor --panels records.py:PANELS` loads.
PANELS = {"words": Panel(words, title="Words", description="Words counted per unit", icon="#")}
