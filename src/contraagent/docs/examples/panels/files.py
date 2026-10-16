"""A run's outputs as files: a tree of a directory per kind and a file per unit, each file's text beside it.

    contraagent monitor --runs-dir runs --panels path/to/files.py:PANELS

A tree body whose file nodes carry their code: selecting a file shows its text,
highlighted, with no request of its own. A task with no output file leads to the
task instead (a `link`); a badge says how a failed attempt ended.
"""

from __future__ import annotations

import json

from contraagent.monitor import BlocksBody, CodeBody, NoteBody, Panel, RunRecords, TreeBody, TreeLink, TreeNode


def language(text: str) -> str:
    """`json` for a text that parses as JSON, else plain text."""
    try:
        json.loads(text)
    except ValueError:
        return ""
    return "json"


def files(run: RunRecords) -> BlocksBody:
    """Each agent task's output, by kind and unit; the last attempt of each task counts."""
    last = {row["key"]: row for row in run.journal() if not row["key"].startswith("python:")}
    kinds: dict[str, list[TreeNode]] = {}
    for key, row in sorted(last.items()):
        output = run.output(key)
        text = output.text if output is not None else None
        name = f"{row.get('unit') or row['kind']}.json"
        badge, tone = (None, None) if row["ok"] else (row["stop"], "failed")
        if text is None:
            node = TreeNode(id=key, name=name, badge=badge or "no file", tone=tone or "muted", link=TreeLink(task=key))
        else:
            code = CodeBody(text=text, language=language(text), path=f"out/{row['kind']}/{name}")
            node = TreeNode(id=key, name=name, badge=badge, tone=tone, code=code)
        kinds.setdefault(row["kind"], []).append(node)
    tree = TreeBody(nodes=[TreeNode(name=kind, children=nodes) for kind, nodes in sorted(kinds.items())])
    return BlocksBody(
        blocks=[
            NoteBody(text="A file is the output of a task's last attempt; its badge names how an attempt that failed ended."),
            tree,
        ]
    )


#: What `contraagent monitor --panels files.py:PANELS` loads.
PANELS = {"files": Panel(files, title="Output files", description="Each task's output, as a file", icon="▤")}
