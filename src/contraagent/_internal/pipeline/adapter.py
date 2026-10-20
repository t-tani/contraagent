"""`SpecAdapter`: the `TaskAdapter` a pipeline hands its runner, built from `agent_task` declarations.

For each agent task it writes the call file (its params, copied as JSON at the task
call, their JSON Schema, and its output contract) just before launch, points the CLI at the task's plugin
and role, and declares the contract the runner checks after the turn: the output it
must leave behind with its validators.
"""

from __future__ import annotations

import copy
import json
import string
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contraagent._internal.backends import plugin_files
from contraagent._internal.backends.base import Backend, exit_dir, safe_label
from contraagent._internal.contracts.calls import CallFile, CallOutput, call_prompt, inline_prompt, schema_ref_of
from contraagent._internal.contracts.contract import OutputContract
from contraagent._internal.contracts.validators import CommandValidator
from contraagent._internal.dispatch.task import Task
from contraagent._internal.execution.adapter import McpServers, TaskAdapter
from contraagent._internal.pipeline.graph import Node
from contraagent._internal.platform import envvars
from contraagent._internal.plugins.scaffold import DEFAULT_SETTINGS
from contraagent._internal.runs import layout


def checked_mcp_servers(key: str, given: object) -> dict[str, dict[str, Any]]:
    """What a `McpServers` function returned for task `key`, as `.mcp.json` `mcpServers`:
    a table of servers by name, each with a `command` (a local server) or a `url` (a
    remote one), every value one JSON can hold. Anything else raises `TypeError`."""
    where = f"Pipeline(mcp_servers=) for {key}"
    if not isinstance(given, Mapping):
        raise TypeError(f"{where} returned {type(given).__name__}: return the servers by name, or None for the plugin's")
    out: dict[str, dict[str, Any]] = {}
    for name, server in given.items():
        if not isinstance(name, str) or not name:
            raise TypeError(f"{where}: a server's name is a non-empty string, not {name!r}")
        if not isinstance(server, Mapping) or not any(isinstance(server.get(k), str) and server.get(k) for k in ("command", "url")):
            raise TypeError(f"{where}: server {name!r} is {server!r}; give it a command (a local server) or a url (a remote one)")
        try:
            out[name] = json.loads(json.dumps(dict(server)))
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{where}: server {name!r} holds a value JSON cannot hold: {exc}") from None
    return out


class SpecAdapter(TaskAdapter):
    """`mcp_servers`: the run's `McpServers` function (`Pipeline(mcp_servers=)`), or None."""

    def __init__(self, run_id: str, run_dir: Path, cwd: Path | None = None, mcp_servers: McpServers | None = None) -> None:
        self.run_id = run_id
        self.calls_dir = Path(run_dir) / layout.CALLS
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.mcp_servers = mcp_servers
        self._mcp_dir: Path | None = None

    @staticmethod
    def _node(task: Task) -> Node:
        return task.payload

    def call_path(self, task: Task) -> Path:
        return self.calls_dir.parent / layout.task_entry(layout.CALLS, task.key)

    def call(self, task: Task) -> CallFile:
        node = self._node(task)
        spec = node.spec
        params = copy.deepcopy(node.params)
        output = None
        if node.output_path is not None:
            schema = spec.output_schema
            output = CallOutput(
                path=node.output_path.as_posix(),
                format=spec.output_format,
                from_=spec.output_from,
                json_schema=spec.output_json_schema,
                schema_ref=schema_ref_of(schema) if schema is not None else None,
                commands=[v.to_dict() for v in spec.validators if isinstance(v, CommandValidator)],
                preserve=list(spec.preserve),
            )
        return CallFile(
            run=self.run_id,
            key=task.key,
            kind=spec.kind,
            unit=node.unit,
            params=params,
            params_json_schema=spec.params_json_schema,
            output=output,
            cwd=str(self.cwd.resolve()),
        )

    # --- TaskAdapter -------------------------------------------------------

    def prompt(self, task: Task, backend: Backend) -> str:
        """The call protocol, which names the call file; for a light launch, the call itself
        (the agent has no tool to read a file with), the call file still written for the record."""
        call = self.call(task)
        path = call.write(self.call_path(task))
        if call.output is not None:  # the agent writes the file; the directory is ours
            Path(call.output.path).parent.mkdir(parents=True, exist_ok=True)
        spec = self._node(task).spec
        if spec.light:
            # A light launch with no plugin has its instructions as its system prompt.
            return inline_prompt(call, self._instructions(task, call) if spec.plugin is not None else "")
        return call_prompt(path, call, self._instructions(task, call))

    def _instructions(self, task: Task, call: CallFile) -> str:
        """The task's `instructions`, `$name` filled in from its params, unit, key and kind."""
        text = self._node(task).spec.instructions
        if not text:
            return ""
        values = {k: str(v) for k, v in call.params.items() if isinstance(v, (str, int, float, bool))}
        return string.Template(text).safe_substitute(values, unit=call.unit, key=call.key, kind=call.kind)

    def role(self, task: Task) -> str | None:
        """The role, as Claude Code's `--agent`; none for a light launch, whose role is its system prompt."""
        spec = self._node(task).spec
        return None if spec.light else spec.role

    def plugin_dirs(self, task: Task) -> tuple[str, ...]:
        """The task's own plugin first, then the skill plugins of `skills_from`; none for a
        light launch (no skill, hook or MCP server can act without tools)."""
        spec = self._node(task).spec
        return () if spec.light else tuple(str(p.root) for p in spec.plugins)

    def tools(self, task: Task) -> tuple[str, ...] | None:
        return self._node(task).spec.tools

    def system_prompt(self, task: Task) -> str | None:
        spec = self._node(task).spec
        if not spec.light:
            return None
        return spec.system_prompt(self._instructions(task, self.call(task)) if spec.plugin is None else None)

    def settings_path(self, task: Task) -> str | None:
        """The task's own plugin's `settings.json`; for a task with no plugin, the template's
        permissions (`DEFAULT_SETTINGS`, as JSON text); none for a light launch."""
        spec = self._node(task).spec
        if spec.light:
            return None
        if spec.plugin is None:
            return " ".join(DEFAULT_SETTINGS.split())
        f = spec.plugin.root / "settings.json"
        return str(f) if f.is_file() else None

    def mcp_config_path(self, task: Task) -> str | None:
        """The task's own plugin's `.mcp.json`, if it has one; none for a light launch. With
        `mcp_servers`, the servers it returns, written to a file of their own in an owner-only
        temporary directory (a server's arguments may hold a secret, so never in the run
        directory), removed when the process ends, however it ends (`exit_dir`)."""
        servers = self.mcp_servers_of(task)
        if servers is None:
            return self._plugin_mcp(task)
        if self._mcp_dir is None:
            self._mcp_dir = exit_dir("mcp-")
        path = self._mcp_dir / f"{safe_label(task.key)}.mcp.json"
        plugin_files.write_mcp_servers(path, servers)
        return str(path)

    def mcp_servers_of(self, task: Task) -> dict[str, dict[str, Any]] | None:
        """What `mcp_servers` returns for `task`, checked: None when there is no `mcp_servers`,
        it returns None, or the task is a light launch. A value that is not a table of named
        servers, each with a `command` or a `url`, raises `TypeError`."""
        if self.mcp_servers is None or self._node(task).spec.light:
            return None
        own = self._plugin_mcp(task)
        given = self.mcp_servers(task, self.call(task).params, plugin_files.mcp_servers(own) if own is not None else {})
        return None if given is None else checked_mcp_servers(task.key, given)

    def _plugin_mcp(self, task: Task) -> str | None:
        spec = self._node(task).spec
        f = spec.plugin.root / ".mcp.json" if spec.plugin is not None and not spec.light else None
        return str(f) if f is not None and f.is_file() else None

    def context_files(self, task: Task, backend: Backend) -> tuple[str, ...]:
        """A coding agent with no named-agent flag (omp) gets the role's file attached;
        one with `--agent` (Claude Code) resolves the role itself. A light launch has its
        role as its system prompt."""
        spec = self._node(task).spec
        if spec.light or spec.plugin is None or spec.role is None or not backend.needs_inline_role_file:
            return ()
        return (str(spec.plugin.role_file(spec.role)),)

    def env(self, task: Task) -> dict[str, str]:
        return {envvars.CALL: str(self.call_path(task))}

    def changes(self, task: Task) -> tuple[str, ...]:
        return self._node(task).changes

    def output_contracts(self, task: Task) -> list[OutputContract]:
        return self._node(task).output_contracts(params=lambda: self.call(task).params, call=self.call_path(task))

    def definition(self, task: Task) -> dict:
        spec = self._node(task).spec
        base = (
            spec.plugin.definition(spec.role)
            if spec.plugin is not None
            else {"plugin": False, "role": spec.role, "plugin_dirs": [], "files": []}
        )
        for shared in spec.skills_from:
            base["plugin_dirs"] = [*base["plugin_dirs"], shared.root.as_posix()]
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
            "output_from": spec.output_from,
            "preserve": list(spec.preserve),
            "output_of": spec.output_of.kind if spec.output_of is not None else None,
            **({"base_kind": spec.base_kind} if spec.base_kind else {}),
            "tools": list(spec.tools) if spec.tools is not None else None,
        }
