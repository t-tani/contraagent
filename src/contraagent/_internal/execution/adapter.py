"""`TaskAdapter`: what a domain tells the runner about its tasks.

The runner owns the generic loop (route, launch, validate, classify);
everything that is the domain's own comes from here: what the prompt says,
which role and plugin directories the CLI loads, which files a task
reads and must leave behind. `pipeline.Pipeline` fills all of it from
`agent_task` declarations and their plugins.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from contraagent._internal.backends.base import Backend
from contraagent._internal.contracts.contract import InputContract, OutputContract
from contraagent._internal.dispatch.task import Task


class TaskAdapter:
    """What a domain tells the runner about its tasks. Override what you need.

    Every method has a working default, so the smallest adapter is the
    prompt:

        class Mine(TaskAdapter):
            def prompt(self, task, backend):
                return f"Summarize {task.params['path']}"
    """

    def prompt(self, task: Task, backend: Backend) -> str:
        """The prompt for this task. Default: `task.params['prompt']`."""
        return str(task.params.get("prompt", ""))

    def role(self, task: Task) -> str | None:
        """The role the coding agent runs as (`agents/<role>.md`; Claude Code's `--agent`), if any."""
        return None

    def plugin_dirs(self, task: Task) -> tuple[str, ...]:
        """Plugin directories handed to `--plugin-dir`, scoping what the agent sees."""
        return ()

    def context_files(self, task: Task, backend: Backend) -> tuple[str, ...]:
        """Files attached to the prompt. Default: `task.params['context_files']`."""
        return tuple(task.params.get("context_files", ()))

    def missing_params(self, task: Task) -> list[str]:
        """Names of required params absent from `task.params`; non-empty refuses the launch."""
        return []

    def output_contracts(self, task: Task) -> Sequence[OutputContract]:
        """Files the task must leave behind, and the schema each must satisfy."""
        return ()

    def input_contracts(self, task: Task) -> Sequence[InputContract]:
        """Files the task reads, checked before launch."""
        return ()

    def changes(self, task: Task) -> Sequence[str]:
        """Patterns, relative to the working directory, of the files the task may change:
        each attempt's changes under them are recorded, and a failed attempt's new files
        removed (`execution/changes.py`). Default: none."""
        return ()

    def env(self, task: Task) -> dict[str, str]:
        """Extra environment for this task's launch (the runner's own `CONTRAAGENT_*` win)."""
        return {}

    def definition(self, task: Task) -> dict[str, Any] | None:
        """What defines this kind of task, for the monitor.

        A dict with `role` (the named agent, `agents/<role>.md`),
        `plugin_dirs`, and `files` (`[{"path", "part", "text"}]`: the prompt
        template, the schema, the role's definition ...). `pipeline.SpecAdapter`
        fills it from the task's `agent_task` declaration and its plugin; the
        default says only which role and plugin directories the task runs with.
        """
        return {"role": self.role(task), "plugin_dirs": list(self.plugin_dirs(task)), "files": []}

    def settings_path(self, task: Task) -> str | None:
        """`--settings` path. Default: `settings.json` in the first plugin dir that has one."""
        return _first_in_plugins(self.plugin_dirs(task), "settings.json")

    def mcp_config_path(self, task: Task) -> str | None:
        """`--mcp-config` path. Default: `.mcp.json` in the first plugin dir that has one."""
        return _first_in_plugins(self.plugin_dirs(task), ".mcp.json")

    def tools(self, task: Task) -> tuple[str, ...] | None:
        """The agent's tools: None, the coding agent's own (as its role and settings allow);
        `()`, none: a light launch (`Backend.light_launch`)."""
        return None

    def system_prompt(self, task: Task) -> str | None:
        """Text that replaces the coding agent's own system prompt; None keeps it. A light
        launch's: its role's text."""
        return None


def _first_in_plugins(plugin_dirs: Sequence[str], name: str) -> str | None:
    for plug in plugin_dirs:
        cand = Path(plug) / name
        if cand.exists():
            return str(cand)
    return None
