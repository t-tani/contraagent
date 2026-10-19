"""A nested pipeline over data bundles: three layers of flow calls, nested
loops, a fan-out sized at run time, and a kind chosen at run time.

Per bundle, `unpack` lists its files and each is classified; every data file is
parsed by the kind its format needs (CSV or JSON), its top columns are ranked,
and each column's meaning is proposed and refined until `verify` accepts it.
One report per bundle, one summary over all of them.

The parsers claim `heavy`: one runs at a time, however many files are ready.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task, max_passes, python_task


class DataFile(BaseModel):
    name: str
    rows: int


class Layout(BaseModel):
    bundle: str
    files: list[DataFile]


class Class(BaseModel):
    name: str = Field(description="the file's name, copied from params.file.name")
    format: Literal["csv", "json"]
    data: bool = Field(description="whether the file holds table data worth parsing")


class Column(BaseModel):
    name: str
    nulls: int


class Table(BaseModel):
    columns: list[Column]


class Ranked(BaseModel):
    top: list[Column]


class Meaning(BaseModel):
    column: str
    reads: str = Field(description="one sentence: what the column means")


class Check(BaseModel):
    ok: bool
    note: str = Field(description="what to fix, when not ok")


class Report(BaseModel):
    bundle: str
    columns: int


@python_task
def unpack(unit: str) -> Layout:
    """List a bundle's files. A Python task: no agent needed to read a manifest."""
    sizes = {"east": [3, 1], "west": [2]}.get(unit, [1])
    return Layout(bundle=unit, files=[DataFile(name=f"{unit}-{i}", rows=n * 100) for i, n in enumerate(sizes)])


classify = agent_task(
    "classify", instructions="Classify params.file: its format and whether it holds table data.", output=Class, max_turns=6, timeout_s=120
)
parse_csv = agent_task(
    "parse_csv",
    instructions="Parse the CSV named by params.file into columns.",
    output=Table,
    max_turns=10,
    timeout_s=300,
    claims=["heavy"],
)
parse_json = agent_task(
    "parse_json",
    instructions="Parse the JSON named by params.file into columns.",
    output=Table,
    max_turns=10,
    timeout_s=300,
    claims=["heavy"],
)
propose = agent_task("propose", instructions="Propose what params.column means.", output=Meaning, max_turns=6, timeout_s=120)
refine = agent_task("refine", instructions="Revise params.meaning as params.check.note says.", output=Meaning, max_turns=6, timeout_s=120)


@python_task
def rank_columns(table: Table) -> Ranked:
    """Rank a table's columns by how many values they have. A Python task."""
    top = sorted(table.columns, key=lambda c: c.nulls)[:2]
    return Ranked(top=top)


@python_task
def verify(meaning: Meaning) -> Check:
    """Accept a proposed meaning when it reads as a full sentence. A Python task."""
    ok = meaning.reads.strip().endswith(".") and len(meaning.reads.split()) >= 3
    return Check(ok=ok, note="Write one full sentence." if not ok else "ok")


@python_task
def report(unit: str, meanings: list[Meaning]) -> Report:
    return Report(bundle=unit, columns=len(meanings))


@python_task
def summary(reports: list[Report]) -> str:
    return "\n".join(f"{r.bundle}: {r.columns} columns" for r in reports)


@max_passes(4)
async def analyse_file(cls: Class):
    """One data file: parse it by its format, rank its columns, then propose a
    meaning for each top column and refine it until `verify` accepts it. The `while`
    loop makes at most 4 passes: the `verify` of a fifth raises `TooManyPasses`."""
    parse = parse_csv if cls.format == "csv" else parse_json  # a kind chosen at run time; both reachable
    table = await parse(cls.name, file=cls)
    ranked = await rank_columns(cls.name, table=table)
    meanings = []
    for column in ranked.top:
        where = f"{cls.name}-{column.name}"
        meaning = await propose(where, column=column)
        while True:
            check = await verify(where, meaning=meaning)
            if check.ok:
                break
            meaning = await refine(where, meaning=meaning, check=check)
        meanings.append(meaning)
    return meanings


async def analyse_bundle(bundle: str):
    """One bundle: unpack it, classify every file, analyse each data file (a flow
    call each), then report. A file whose `classify` failed is left out."""
    layout = await unpack(bundle)
    tasks = [classify(f.name, file=f) for f in layout.files]  # fan-out sized by the layout
    classes = await asyncio.gather(*tasks, return_exceptions=True)  # a failure is its item
    data = [c for c in classes if isinstance(c, Class) and c.data]
    found = await asyncio.gather(*[analyse_file(c) for c in data])
    return await report(bundle, meanings=[m for file in found for m in file])


async def analyse(bundles: list[str]):
    """Every bundle at once (a flow call each), then one summary."""
    reports = await asyncio.gather(*[analyse_bundle(b) for b in bundles])
    return await summary(reports=reports)
