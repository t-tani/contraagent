"""Where a relative `plugin=` path of `agent_task` starts: the file that declares the task."""

import importlib.util
import textwrap
from pathlib import Path

from contraagent.plugins import new_plugin

DECLARE = """
from contraagent import agent_task
from pydantic import BaseModel

class Out(BaseModel):
    unit: str
"""


def load(path: Path, source: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"plugin_paths_{path.parent.name}_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_relative_plugin_path_starts_at_the_declaring_file(tmp_path):
    new_plugin(tmp_path / "flows" / "plugins" / "review")
    module = load(tmp_path / "flows" / "decl.py", DECLARE + 'review = agent_task("review", plugin="plugins/review", output=Out)\n')
    assert module.review.plugin.root == tmp_path / "flows" / "plugins" / "review"


def test_a_standard_library_frame_between_the_file_and_agent_task_is_passed_over(tmp_path):
    new_plugin(tmp_path / "flows" / "plugins" / "review")
    module = load(
        tmp_path / "flows" / "decl.py",
        DECLARE
        + "import functools\n"
        + "declare = functools.singledispatch(agent_task)\n"
        + 'review = declare("review", plugin="plugins/review", output=Out)\n',
    )
    assert module.review.plugin.root == tmp_path / "flows" / "plugins" / "review"


def test_a_helper_in_another_directory_takes_an_absolute_path(tmp_path):
    new_plugin(tmp_path / "flows" / "plugins" / "review")
    new_plugin(tmp_path / "lib" / "plugins" / "review")
    helper = "def review(plugin):\n    return agent_task('review', plugin=plugin, output=Out)\n"
    helpers = load(tmp_path / "lib" / "helpers.py", DECLARE + helper)
    # Relative: from the helper's own file, the one that calls `agent_task`.
    assert helpers.review("plugins/review").plugin.root == tmp_path / "lib" / "plugins" / "review"
    # Absolute, as a caller builds it from its own `__file__`: the caller's plugin.
    assert helpers.review(tmp_path / "flows" / "plugins" / "review").plugin.root == tmp_path / "flows" / "plugins" / "review"
