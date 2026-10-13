"""`SpecAdapter`: the `TaskAdapter` a pipeline hands its runner, built from `agent_task` declarations.

For each agent task it writes the call file (parameters, output contract)
just before launch, points the CLI at the task's plugin and role, and declares
the contracts the runner checks after the turn: the upstream outputs it reads,
and the output it must leave behind with its validators.
"""

from __future__ import annotations

import string
from pathlib import Path

from pydantic_core import to_jsonable_python

from contraagent import envvars, rundir
from contraagent.backends.base import Backend
from contraagent.calls import CallFile, CallOutput, call_prompt, schema_ref_of
from contraagent.contracts import InputContract, OutputContract
from contraagent.dispatch.task import Task
from contraagent.execution.adapter import TaskAdapter
from contraagent.pipeline.graph import Node
from contraagent.plugins.scaffold import DEFAULT_SETTINGS
from contraagent.validators import CommandValidator


class SpecAdapter(TaskAdapter):
    def __init__(self, run_id: str, run_dir: Path, cwd: Path | None = None) -> None:
        self.run_id = run_id
        self.calls_dir = Path(run_dir) / rundir.CALLS
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()

    @staticmethod
    def _node(task: Task) -> Node:
        return task.payload

    def call_path(self, task: Task) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in task.key)
        return self.calls_dir / f"{safe}.json"

    def call(self, task: Task) -> CallFile:
        node = self._node(task)
        spec = node.spec
        params = node.resolved_params()
        if spec.params is not None:
            params = spec.params.model_validate(params).model_dump(mode="json")
        else:
            params = to_jsonable_python(params)
        output = None
        if node.output_path is not None:
            schema = spec.output_schema
            output = CallOutput(
                path=str(node.output_path),
                format=spec.output_format,
                json_schema=schema.model_json_schema() if schema is not None else {},
                schema_ref=schema_ref_of(schema) if schema is not None else None,
                commands=[v.to_dict() for v in spec.validators if isinstance(v, CommandValidator)],
            )
        return CallFile(
            run=self.run_id, key=task.key, kind=spec.kind, unit=node.unit, params=params, output=output, cwd=str(self.cwd.resolve())
        )

    # --- TaskAdapter -------------------------------------------------------

    def prompt(self, task: Task, backend: Backend) -> str:
        call = self.call(task)
        path = call.write(self.call_path(task))
        if call.output is not None:  # the agent writes the file; the directory is ours
            Path(call.output.path).parent.mkdir(parents=True, exist_ok=True)
        instructions = ""
        if self._node(task).spec.instructions:
            values = {k: str(v) for k, v in call.params.items() if isinstance(v, (str, int, float, bool))}
            instructions = string.Template(self._node(task).spec.instructions).safe_substitute(
                values, unit=call.unit, key=call.key, kind=call.kind
            )
        return call_prompt(path, call, instructions)

    def role(self, task: Task) -> str | None:
        return self._node(task).spec.role

    def plugin_dirs(self, task: Task) -> tuple[str, ...]:
        """The task's own plugin first, then the skill plugins of `skills_from`."""
        return tuple(str(p.root) for p in self._node(task).spec.plugins)

    def settings_path(self, task: Task) -> str | None:
        """The task's own plugin's `settings.json`; for a task with no plugin, the template's
        permissions (`DEFAULT_SETTINGS`, as JSON text)."""
        plugin = self._node(task).spec.plugin
        if plugin is None:
            return " ".join(DEFAULT_SETTINGS.split())
        f = plugin.root / "settings.json"
        return str(f) if f.is_file() else None

    def mcp_config_path(self, task: Task) -> str | None:
        """The task's own plugin's `.mcp.json`, if it has one."""
        plugin = self._node(task).spec.plugin
        f = plugin.root / ".mcp.json" if plugin is not None else None
        return str(f) if f is not None and f.is_file() else None

    def context_files(self, task: Task, backend: Backend) -> tuple[str, ...]:
        """A coding agent with no named-agent flag (omp) gets the role's file attached;
        one with `--agent` (Claude Code) resolves the role itself."""
        spec = self._node(task).spec
        if spec.plugin is None or spec.role is None or not backend.needs_inline_role_file:
            return ()
        return (str(spec.plugin.role_file(spec.role)),)

    def env(self, task: Task) -> dict[str, str]:
        return {envvars.CALL: str(self.call_path(task))}

    def changes(self, task: Task) -> tuple[str, ...]:
        return self._node(task).changes

    def output_contracts(self, task: Task) -> list[OutputContract]:
        return self._node(task).output_contracts(params=lambda: self.call(task).params, call=self.call_path(task))

    def input_contracts(self, task: Task) -> list[InputContract]:
        return self._node(task).input_contracts()

    def definition(self, task: Task) -> dict:
        spec = self._node(task).spec
        base = (
            spec.plugin.definition(spec.role)
            if spec.plugin is not None
            else {"plugin": False, "role": spec.role, "plugin_dirs": [], "files": []}
        )
        for shared in spec.skills_from:
            base["plugin_dirs"] = [*base["plugin_dirs"], str(shared.root)]
            base["files"] += [
                {"path": f"{shared.name}/{rel}", "part": "skill", "text": text[:40_000]} for rel, text in shared.skill_files()
            ]
        if spec.instructions:
            base["files"] = [{"path": "instructions", "part": "instructions", "text": spec.instructions}, *base["files"]]
        return {
            **base,
            "params": spec.params.__name__ if spec.params is not None else None,
            "requires": list(spec.requires),
            "changes": list(spec.changes),
            "output": (
                spec.output_schema.__name__ if spec.output_schema is not None else ("text" if spec.output_format == "text" else None)
            ),
            "validators": [getattr(v, "name", "") or getattr(v, "__name__", "") for v in spec.validators],
        }
