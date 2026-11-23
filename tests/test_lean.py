"""The Lean specification (`lean/`) stays in step with the code it describes: each of its
files is named after a module, its imports follow the layers, and the names the two share
are the same. These tests read the files only; Lean builds and proves in its own CI job."""

import json
import re
import tomllib
from pathlib import Path

import contraagent._internal.dispatch.task as task_module

ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = ROOT / "lean" / "Contraagent"
INTERNAL = ROOT / "src" / "contraagent" / "_internal"
VOCABULARY = ROOT / "tests" / "lean" / "vocabulary.json"

#: An import of a module of the specification, with the folder (the layer) it is in.
IMPORT = re.compile(r"^(?:(?:public|private|meta)\s+)*import\s+(?:all\s+)?Contraagent\.(\w+)\.", re.MULTILINE)


def snake(name: str) -> str:
    """A Lean file's or folder's name as the Python module's: `ResumeFrom` is `resume_from`."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def lean_files() -> list[Path]:
    files = sorted(SPECIFICATION.rglob("*.lean"))
    assert files, f"no Lean file under {SPECIFICATION}"
    return files


def test_every_lean_file_is_named_after_the_module_it_describes():
    """`Contraagent/<Layer>/<Module>.lean` describes `_internal/<layer>/<module>.py`, and a
    file below `Contraagent/<Layer>/<Module>/` holds theorems about that description."""
    wrong: list[str] = []
    for path in lean_files():
        parts = path.relative_to(SPECIFICATION).with_suffix("").parts
        name = path.relative_to(ROOT).as_posix()
        if len(parts) < 2:
            wrong.append(f"{name}: not in a layer's folder")
            continue
        module = INTERNAL / snake(parts[0]) / f"{snake(parts[1])}.py"
        if not module.is_file():
            wrong.append(f"{name}: no {module.relative_to(ROOT).as_posix()}")
        elif len(parts) > 2 and not (SPECIFICATION / parts[0] / f"{parts[1]}.lean").is_file():
            wrong.append(f"{name}: no lean/Contraagent/{parts[0]}/{parts[1]}.lean, the description its theorems are about")
    assert not wrong, "\n".join(wrong)


def test_lean_imports_follow_the_layers():
    """A Lean file imports only files of its own layer and of the layers `_internal` lets
    that layer import (pyproject.toml's `layers` contract, the latest layer first)."""
    contracts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["importlinter"]["contracts"]
    (layers,) = (c["layers"] for c in contracts if c["id"] == "layers")
    wrong: list[str] = []
    for path in lean_files():
        own = snake(path.relative_to(SPECIFICATION).parts[0])
        for imported in IMPORT.findall(path.read_text(encoding="utf-8")):
            if layers.index(snake(imported)) < layers.index(own):
                wrong.append(f"{path.relative_to(ROOT).as_posix()}: imports {imported}, a later layer than its own")
    assert not wrong, "\n".join(wrong)


def test_the_stop_values_are_those_task_py_names():
    vocabulary = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    stops = [value for name, value in vars(task_module).items() if name.startswith("STOP_")]
    assert vocabulary["stops"] == stops, (
        "the stop values of lean/Contraagent/Dispatch/Task.lean (`Stop.named`) and the STOP_* constants of "
        "dispatch/task.py differ; after changing the Lean file, rewrite tests/lean/vocabulary.json in lean/: "
        "lake exe contraagent-lean vocabulary > ../tests/lean/vocabulary.json"
    )
