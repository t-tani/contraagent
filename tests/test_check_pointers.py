"""The pointers of the messages `contraagent check` and a run give: one form,
`(contraagent docs <topic>, <section>)` or `(contraagent docs <topic>)`, naming a topic
`contraagent docs` prints and a section of it."""

import ast
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.pipeline.check import POINTER
from contraagent.backends import OmpBackend
from contraagent.testing import StubAgent

SOURCE = Path(__file__).resolve().parents[1] / "src" / "contraagent" / "_internal"
DOCS = Path(__file__).resolve().parents[1] / "src" / "contraagent" / "docs"
#: Text that is no message: the `contraagent docs` command's own help, and the prose a
#: new plugin's README holds.
NOT_MESSAGES = {"docs.py", "cli.py:usage", "scaffold.py"}
#: `contraagent docs` followed by a word: a pointer, unless it is a command's syntax.
MENTION = re.compile(r"contraagent docs (?=[a-z])")


def _strings(tree: ast.AST) -> list[str]:
    """Each string literal of `tree` but its docstrings, an f-string's values as `{}`."""
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    parts = {id(v) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for v in node.values}
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.append("".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings | parts:
            out.append(node.value)
    return out


def _headings(topic: str) -> list[str]:
    text = (DOCS / f"{topic}.md").read_text(encoding="utf-8")
    return [line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")]


def _pointers() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path.name in NOT_MESSAGES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings = _strings(tree)
        if path.name == "cli.py":
            strings = [s for s in strings if not s.lstrip().startswith("contraagent docs [TOPIC]") and "--pointer" not in s]
        for text in strings:
            for m in MENTION.finditer(text):
                found.append((f"{path.relative_to(SOURCE)}", text[max(0, m.start() - 1) :]))
    return found


POINTERS = _pointers()


def test_the_messages_carry_pointers():
    assert len(POINTERS) >= 6, POINTERS  # the scan finds them


@pytest.mark.parametrize(("where", "text"), POINTERS, ids=[f"{w}:{t[:40]}" for w, t in POINTERS])
def test_each_pointer_has_the_one_form_and_names_a_topic_and_its_section(where, text):
    m = POINTER.match(text)
    if m is None and text.startswith("(contraagent docs {}"):
        return  # CheckReport's own `(contraagent docs {topic})`
    assert m is not None, f"{where}: {text[:80]!r} is not (contraagent docs <topic>[, <section>])"
    topic, section = m.group(1), m.group(2)
    assert (DOCS / f"{topic}.md").is_file(), f"{where}: no topic {topic!r}"
    if section is not None:
        headings = _headings(topic)
        assert any(h == section or h.startswith(f"{section}:") for h in headings), (
            f"{where}: topic {topic} has no section {section!r}; its sections: {headings}"
        )


class Note(BaseModel):
    text: str


note = agent_task("note", instructions="n", output=Note, max_turns=1, timeout_s=10)


def test_the_read_line_names_each_error_s_own_pointer_else_its_check_s_topic(tmp_path):
    config = PipelineConfig(
        {
            "tasks": {
                "note": {"agent": "omp", "model": "anthropic/m", "disallowed_tools": ["Grep(*.env)"], "max_corrections": 50},
            },
        }
    )
    p = Pipeline(config, backends={**StubAgent().backends(), "omp": OmpBackend()}, runs_dir=tmp_path, cwd=tmp_path)
    report = p.check(lambda: note("a"))
    assert not report.ok
    denied = [e for e in report.errors if "omp cannot hold Grep(*.env)" in e]
    assert denied and denied[0].endswith("(contraagent docs agents, What each one does)"), report.errors
    assert report.topics == ["contracts", "agents"] or report.topics == ["agents", "contracts"], report.topics
    read = str(report).splitlines()[-1]
    assert "(contraagent docs agents, What each one does)" in read
    assert "(contraagent docs contracts, Checked twice, by the same rules)" in read
    assert "routing" not in read
