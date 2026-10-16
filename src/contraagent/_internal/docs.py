"""The documentation installed with the package (`contraagent/docs/`): Markdown topics and the
examples they quote, read and printed.

`README.md` is the index; its list (`- [Title](name.md): summary`) names the
topics, in order. A line `::code{file="..." from="..." to="..."}` in a topic
quotes a file: from the first line containing `from` up to, not including, the
first later line containing `to`. `contraagent docs` prints the topics with
their quotes expanded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from contraagent._internal.errors import ContraagentError

#: Where the documentation is installed.
DIR = Path(__file__).resolve().parents[1] / "docs"
INDEX = DIR / "README.md"

#: What `contraagent docs --pointer` prints: a block for the instruction file a
#: project's coding agent reads (AGENTS.md, CLAUDE.md), pointing it at these docs.
POINTER = """\
## contraagent

This project uses contraagent to run coding-agent tasks as a Python pipeline. Its
documentation is installed with the package and matches the installed version. The
documentation, the docstrings of the public API and the messages of
`contraagent check` hold every fact that a pipeline needs, so contraagent's source
code is not needed.

- `contraagent docs` prints the index, with the order in which to read the topics.
  `contraagent docs <topic>` prints one topic. Read `guide`, then `tutorial`.
  `contraagent docs --path` prints where the documentation and its examples are.
- contraagent's API is newer than your training data. Read the topic before you
  write or change the code.
- Check your work in this order, which launches no coding agent and spends nothing.
  First, `contraagent check <file>:<flow> --kwargs '{...}'` until it prints ✓.
  Second, a stub run, `contraagent run <file>:<flow> --stub --kwargs '{...}'`, which
  checks the flow's wiring on the smallest outputs that the schemas accept. A validator
  that needs real content rejects them, and the run's last line names it: that result
  is expected. Third, tests of the flow on `contraagent.testing.StubAgent` in pytest,
  with replies that carry real content (`contraagent docs testing`).
- A run on the coding agents (`contraagent run <file>:<flow> --config pipeline.toml`)
  spends tokens. The person who asked for the pipeline starts it, unless they ask you
  to, and watches it in `contraagent monitor`.
"""

_ENTRY = re.compile(r"^- \[(?P<title>[^\]]+)\]\((?P<file>[\w./-]+\.md)\): (?P<summary>.+)$")
_CODE = re.compile(r"^::code\{(?P<attrs>.*)\}\s*$")
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_FENCE = re.compile(r"^\s*```")


class DocsError(ContraagentError):
    """An unknown topic, or a quote that does not resolve."""


@dataclass(frozen=True)
class Entry:
    """One line of an index's list."""

    title: str
    path: Path
    summary: str

    @property
    def name(self) -> str:
        return self.path.stem


def entries(index: Path = INDEX) -> list[Entry]:
    """The pages an index lists, in its order."""
    return [
        Entry(m["title"], (index.parent / m["file"]).resolve(), m["summary"])
        for line in index.read_text().splitlines()
        if (m := _ENTRY.match(line))
    ]


def topics() -> list[Entry]:
    """This package's topics."""
    return entries(INDEX)


def text(topic: str | None = None) -> str:
    """The index, or one topic, with its quotes expanded."""
    if topic is None:
        return INDEX.read_text()
    known = {t.name: t for t in topics()}
    if topic not in known:
        raise DocsError(f"no topic {topic!r}; the topics: {', '.join(known)}")
    return expand(known[topic].path, DIR)


def expand(page: Path, root: Path) -> str:
    """`page`'s Markdown with every `::code{...}` line replaced by the code it quotes,
    fenced and titled with its path relative to `root` (the package's own directory)."""
    out: list[str] = []
    fenced = False
    for line in page.read_text().splitlines():
        if _FENCE.match(line):
            fenced = not fenced
        m = None if fenced else _CODE.match(line)
        out += quote(page, dict(_ATTR.findall(m["attrs"])), root) if m else [line]
    return "\n".join(out) + "\n"


def quote(page: Path, attrs: dict[str, str], root: Path) -> list[str]:
    """The fenced lines one `::code{...}` stands for."""
    where = f"{page.name}: ::code{{file={attrs.get('file')!r}}}"
    source = (page.parent / attrs.get("file", "")).resolve()
    if "file" not in attrs or not source.is_file():
        raise DocsError(f"{where}: no such file")
    lines = source.read_text().rstrip("\n").split("\n")
    if start := attrs.get("from"):
        i = next((i for i, line in enumerate(lines) if start in line), None)
        if i is None:
            raise DocsError(f"{where}: no line contains {start!r}")
        lines = lines[i:]
    if end := attrs.get("to"):
        j = next((j for j, line in enumerate(lines) if j > 0 and end in line), None)
        if j is None:
            raise DocsError(f"{where}: no later line contains {end!r}")
        lines = lines[:j]
    while lines and not lines[-1].strip():
        lines.pop()
    fence = "`" * max(3, 1 + max((len(run) for line in lines for run in re.findall(r"`+", line)), default=0))
    lang = attrs.get("lang") or source.suffix.lstrip(".")
    return [f'{fence}{lang} title="{source.relative_to(root.resolve())}"', *lines, fence]
