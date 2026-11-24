"""Scenarios of the task graph, played on `Graph` and on the Lean specification.

    uv run python tests/lean/graph_scenarios.py     # rewrites tests/lean/graph_scenarios.jsonl

A scenario is some declarations and a list of task calls, each by a flow call;
`lean/Conformance/Graph.lean` has its fields. `play` plays one on `Graph` and returns, for
each call, the task's key, the keys it waits for and its output file, or why the call is
refused (`lake exe contraagent-lean graph`). `tests/lean/graph_scenarios.jsonl` holds
scenarios (`scenarios`) with what the specification answers for each;
`tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from contraagent import agent_task, python_task
from contraagent._internal.pipeline.graph import Graph

FILE = Path(__file__).with_name("graph_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "graph"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 150

#: Each refusal of a task call, by words of its message.
REFUSALS = {
    "is created by flow calls": "two_flow_calls",
    "is used twice": "key_used_twice",
    "give one of them another output_name": "same_layout",
    "not a path inside out/": "outside",
    "would both write": "one_writer",
    "already fills in (output_of)": "filled_before",
}


class Out(BaseModel):
    text: str = ""


class Calls:
    """Stands for the flow driver: which flow call's code calls a task."""

    def __init__(self) -> None:
        self.current: Any = None

    def received(self, call: Any) -> frozenset[str]:
        return frozenset()

    def add(self, task: Any) -> None:
        pass


def _declarations(kinds: list[dict[str, Any]]) -> list[Any]:
    made: list[Any] = []
    for k in kinds:
        other = made[k["outputOf"]] if k["outputOf"] is not None else None
        if k["python"]:

            def written(unit: str) -> Out:
                return Out()

            made.append(python_task(kind=k["kind"], output_name=k["outputName"])(written))
        else:
            output = Out if k["outputName"] is not None else None
            name = None if other is not None else k["outputName"]
            made.append(
                agent_task(k["kind"], instructions="Do it.", output=output, output_name=name, output_of=other, max_turns=1, timeout_s=1)
            )
    return made


def play(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Play `scenario` on a `Graph`: an answer for each call."""
    answers: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        graph = Graph(Path(tmp) / "out")
        calls = Calls()
        graph.driver = calls  # type: ignore[assignment]
        declarations = _declarations(scenario["kinds"])
        pendings: list[Any] = []
        with graph.building():
            for call in scenario["calls"]:
                calls.current = SimpleNamespace(id=call["flowCall"], frontier=())
                declaration = declarations[call["kind"]]
                options: dict[str, Any] = {}
                if call["key"] is not None:
                    options["key"] = call["key"]
                after = [pendings[i] for i in call["after"] if pendings[i] is not None]
                if after:
                    options["after"] = after
                called = declaration.options(**options) if options else declaration
                try:
                    pendings.append(called(call["unit"]) if call["unit"] else called())
                except ValueError as refused:
                    pendings.append(None)
                    names = [name for words, name in REFUSALS.items() if words in str(refused)]
                    answers.append({"refused": names[0] if names else f"another refusal: {refused}"})
                    continue
                node = graph.nodes[-1]
                output = None if node.output_path is None else node.output_path.relative_to(graph.out_dir).as_posix()
                answers.append({"key": node.key, "after": list(node.after), "output": output})
    return answers


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: up to five kinds, agent and Python tasks, with templates that give
    each unit a file, each key a file, or every task one file, kinds that fill in another's
    file, and up to twelve calls by three flow calls, some under a key of their own, some
    after earlier ones, some for a unit that puts the file outside `out/`."""
    templates = ["{kind}/{unit}.json", "{kind}/{unit}.json", "shared/{unit}.json", "{kind}/{key}.json", "{kind}.json", "{unit}/{kind}.json"]
    kinds: list[dict[str, Any]] = []
    for i in range(rng.randint(1, 5)):
        python = rng.random() < 0.3
        writers = [j for j, k in enumerate(kinds) if k["outputName"] is not None and k["outputOf"] is None]
        fills = not python and writers and rng.random() < 0.35
        writes = python or fills or rng.random() < 0.85
        kinds.append(
            {
                "kind": f"k{i}",
                "python": python,
                "outputName": rng.choice(templates) if writes else None,
                "outputOf": rng.choice(writers) if fills else None,
            }
        )
    calls = []
    for n in range(rng.randint(1, 12)):
        place = rng.randrange(len(kinds))
        calls.append(
            {
                "kind": place,
                "unit": rng.choice(["a", "a", "b", ".."] if kinds[place]["python"] else ["a", "a", "b", "", ".."]),
                "key": rng.choice([None, None, None, None, "x", "a/b", "k0-a", "k0-a~2"]),
                "after": sorted(i for i in range(n) if rng.random() < 0.2),
                "flowCall": rng.choice(["0", "0", "0", "0.1", "0.2"]),
            }
        )
    return {"kinds": kinds, "calls": calls}


def scenarios(seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [scenario(rng) for _ in range(count)]


def _exe() -> Any:
    spec = importlib.util.spec_from_file_location("lean_exe", Path(__file__).with_name("exe.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    _exe().rewrite(FILE, WHAT, scenarios(SEED, COUNT))
