"""Antigravity CLI backend: `agy -p --output-format stream-json`.

One launch is one `agy -p` in the launch's cwd, its events read as they arrive
(`wire.StreamReader`). agy has no flag for a plugin, a system prompt or an MCP server: it
finds them in the `.agents/` directory of each folder of its workspace. So a launch gets a
directory of its own, made afresh in its scratch directory and added to the workspace
(`--add-dir`), whose `.agents/` holds what the task gives it (checked against agy 1.5.9):

- `skills/<name>/`: a copy of each skill of the launch's plugins. agy does not follow a
  symbolic link to a skill, and does not read a `skills.json` of an added folder.
- `hooks.json`: the plugins' rendered hooks, each run through a bridge (`hooks.py`).
- `mcp_config.json`: the launch's MCP servers (`Launch.mcp_config`), each allowed by a
  permission rule, since nobody answers a prompt.
- `agents/contraagent.md`: the system prompt of a light launch (`Launch.tools == ()`), as
  an agent of agy's own (`--agent`) with no tools, which takes none of the workspace's
  customizations.

agy names an agent's tools in the agent's file, and an agent whose file names none has
none. So a role is not an agent of agy's: its file is written into the prompt, as for
Codex, with the preamble and `Launch.append_system_prompt`. `Launch.system_prompt` is the
agent's own text only in a light launch (`Launch.tools == ()`); in another launch it goes
at the head of the prompt too.

What a launch still sees of its host: the rules and the `.agents/` directory of its working
directory and of the directories above it up to the repository's root (`AGENTS.md`,
`GEMINI.md`), and the user's own in `~/.gemini/`. agy has no switch for them outside a
light launch.

A launch runs in agy's `auto` mode, set in the settings of the launch alone (`agentMode`),
whatever mode the user saved (checked against agy 1.5.9). In `auto` mode agy edits files
without asking, runs each command in its terminal sandbox, which has no network, and
reviews a command that asks to leave the sandbox itself: one it lets through runs. In
agy's other modes a command needs an approval, and a headless session has nobody to give
one: agy ends the launch at the first such call, with no output (`denied`). So does
`auto` mode for a command its review does not let through, and for every command on an
account that has no `auto` mode. The mode is a setting and not `--mode auto`, which
prints a warning for some accounts that have it. The workspace is the cwd, the run's
`out/` and the input roots (`--add-dir`).

The prompt is on the command line (`-p`), or past `STDIN_THRESHOLD` one JSON message on
stdin (`--input-format stream-json`): `agy -p` takes no prompt from stdin. `json_schema`
and the settings of the launch (`--settings`: its permission rules) are files of the
launch's scratch directory.

`Limits.max_turns` and `context_budget` are enforced by contraagent, from the tokens each
response reports; agy reports no cost, so `max_budget_usd` is not enforced.

A model id names its reasoning level (`gemini-3.8-flash-high`), or lacks one and takes
`Launch.effort` (`gemini-3.8-flash` and `--effort high`). agy refuses an effort beside an
id that names a level, so `effort` is passed only with an id that names none (`_effort`).
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any

from contraagent._internal.backends import plugin_files
from contraagent._internal.backends.agy import catalogue
from contraagent._internal.backends.agy import wire as agy_wire
from contraagent._internal.backends.agy.hooks import HOOKS_FILE, OBJECTIONS, PENDING, STATE_ENV, native_hooks
from contraagent._internal.backends.base import DENY_POINTER, PARENT_SESSION_ENV, Backend, ResumeById, context_in_prompt
from contraagent._internal.backends.credentials import (
    Ambient,
    ApiKey,
    Credential,
    CredentialBinding,
    CredentialError,
    Subscription,
    child_env,
    secret_value,
)
from contraagent._internal.backends.launch import Launch, Stop, readable_roots, writable_out
from contraagent._internal.backends.process import run_process, via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold, LimitsWatch
from contraagent._internal.dispatch.records import QuotaReading
from contraagent._internal.platform import envvars
from contraagent._internal.platform.commands import commands
from contraagent._internal.runs.times import now_iso

#: Added to every launch: agy does not replace itself with a newer version while a run uses it.
DEFAULT_ENV = {"AGY_CLI_DISABLE_AUTO_UPDATE": "true"}
#: The provider a credential for agy names: the Google login, or a Gemini API key.
PROVIDER = "google"
#: The agent a light launch runs as: its file is the launch's system prompt.
LIGHT_AGENT = "contraagent"
#: `Launch.permission_mode` (Claude Code's names) as agy's flags.
MODES: dict[str, tuple[str, ...]] = {
    "bypassPermissions": ("--dangerously-skip-permissions",),
    "acceptEdits": ("--mode", "accept-edits"),
    "plan": ("--mode", "plan"),
}
#: `Launch.permission_mode` as the `agentMode` of the launch's settings, where no flag of
#: `MODES` sets the mode: `auto` for a launch that names none, agy's default mode (which
#: asks before each command) for `default`.
AGENT_MODES: dict[str, str] = {"": "auto", "default": ""}
#: Claude Code's tool names (`Limits.disallowed_tools`) as the action of an agy permission rule.
ACTION_OF = {
    "Bash": "command",
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "write_file",
    "MultiEdit": "write_file",
    "NotebookEdit": "write_file",
    "WebFetch": "read_url",
}
_RULE_RE = re.compile(r"^(\w+)(?:\((.*)\))?$")
#: An agy conversation id, before it is joined into a path.
_CONVERSATION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{0,63}$")
#: How long agy may take to report the plan's usage, in seconds.
USAGE_TIMEOUT_S = 30.0
#: How long one usage report serves the launches that start, in seconds: the report is the
#: plan's, a request to Google that takes agy some seconds.
USAGE_FRESH_S = 60.0


def deny_rule(rule: str) -> str | None:
    """agy's permission rule for one of `Limits.disallowed_tools` (Claude Code's names and
    patterns), or None when agy has none for it:

    - `Bash` is `command(*)`, and `Bash(git push:*)` the prefix `command(git push)`, which
      agy matches word by word;
    - `Read`, `Write`, `Edit`, `MultiEdit` and `NotebookEdit` are `read_file(*)` and
      `write_file(*)`, and with a path the file or the directory and all under it
      (`Read(secrets/**)` is `read_file(secrets)`): `//` absolute, `~/` from home, anything
      else from the workspace;
    - `WebFetch` is `read_url(*)`, and `WebFetch(domain:example.com)` that domain;
    - an MCP tool `mcp__<server>__<tool>` is `mcp(<server>/<tool>)`, a server all its tools.

    A pattern with a wildcard in its middle, and any other tool, has no rule."""
    m = _RULE_RE.match(rule.strip())
    if not m:
        return None
    name, pattern = m.group(1), m.group(2)
    if name.startswith("mcp__"):
        server, _, tool = name.removeprefix("mcp__").partition("__")
        return f"mcp({server}/{tool or '*'})" if server and not pattern else None
    action = ACTION_OF.get(name)
    if action is None:
        return None
    if not pattern:
        return f"{action}(*)"
    if action == "command":
        prefix = pattern.removesuffix(":*").removesuffix("*").strip()
        return f"command({prefix})" if prefix and "*" not in prefix else None
    if action == "read_url":
        host = pattern.removeprefix("domain:").strip()
        return f"read_url({host})" if pattern.startswith("domain:") and host and "*" not in host else None
    path = pattern.removesuffix("/**").removesuffix("/*")
    if not path or any(ch in path for ch in "*?["):
        return None
    if path.startswith("//"):
        path = path[1:]
    elif path.startswith("~/"):
        path = str(Path(path).expanduser())
    else:
        path = path.lstrip("/").removeprefix("./")
    return f"{action}({path})" if path else None


def mcp_config(path: str) -> dict[str, dict]:
    """A Claude Code `.mcp.json` (`mcpServers`) as the servers of agy's `mcp_config.json`:
    a stdio server (`command`, `args`, `env`) or a streamable HTTP one (`url`, `headers`)."""
    out: dict[str, dict] = {}
    for name, spec in plugin_files.mcp_servers(path).items():
        if spec.get("command"):
            server: dict = {"command": spec["command"], "args": list(spec.get("args") or [])}
            if spec.get("env"):
                server["env"] = dict(spec["env"])
        elif spec.get("url"):
            server = {"url": spec["url"]}
            if spec.get("headers"):
                server["headers"] = dict(spec["headers"])
        else:
            continue
        out[name] = server
    return out


def agent_file(system_prompt: str, added: str | None, structured: bool = False) -> str:
    """The file of the agent a light launch runs as: no tools, none of the workspace's
    customizations or MCP servers, and the system prompt (with `added` after it) as its
    text. With `structured` (a launch with a `json_schema`) it has agy's `finish` tool, which
    hands in the structured answer: without it agy asks for the answer again and gets none."""
    head = [
        "---",
        f"name: {LIGHT_AGENT}",
        "description: The system prompt of one contraagent launch.",
        f"tools: [{'finish' if structured else ''}]",
        "inheritCustomizations: false",
        "inheritMcp: false",
        "---",
    ]
    body = system_prompt if not added else f"{system_prompt}\n\n{added}"
    return "\n".join(head) + "\n" + body.rstrip("\n") + "\n"


class AgyBackend(ResumeById, Backend):
    """Headless Antigravity CLI: `agy -p --output-format stream-json`.

    A launch's plugins reach agy through a directory of the launch's own, added to its
    workspace (`--add-dir`): its `.agents/` holds a copy of the plugins' skills, their
    rendered hooks (`agy/hooks.json`, run through `contraagent plugin hook --agent agy`)
    and the launch's MCP servers. The role's file, the preamble and
    `Launch.append_system_prompt` are written into the prompt, which goes over stdin as
    one JSON message past `STDIN_THRESHOLD`. A light launch (`Launch.tools == ()`) runs as
    an agent of agy's own whose file is `Launch.system_prompt`, with no tools and none of
    the workspace's customizations.

    Credentials: `ambient` and a `subscription` of provider `google` are the Google login
    agy keeps in the system's keyring (a `subscription` names no `config_dir`); an
    `api_key` of provider `google` is a Gemini API key (`GEMINI_API_KEY`, with agy's
    `modelProvider` set to `gemini` for the launch).

    A launch runs in agy's `auto` mode (`agentMode` in the launch's settings): commands in
    agy's terminal sandbox, with no network, and agy's own review of a command that asks
    to leave it. `Launch.permission_mode` names another one: `acceptEdits` and `plan` are
    agy's modes of those names, `default` its default mode, and `bypassPermissions` is
    `--dangerously-skip-permissions`. In `acceptEdits` and `default` a command needs an
    approval nobody can give, so agy ends the launch at the first one (`denied`).
    `Limits.disallowed_tools` become deny rules of agy's permissions (`deny_rule`), which
    hold in every mode.

    A launch that keeps no session (`Launch.persist_session` False) removes the
    conversation agy saved for it: `conversations/<id>.db` and `brain/<id>/` under
    `~/.gemini/antigravity-cli/`.
    """

    name = "agy"
    binary = "agy"
    stop_hooks_file: str | None = HOOKS_FILE
    effort_levels: tuple[str, ...] | None = catalogue.LEVELS
    # A custom agent has only the tools its file lists: the role's file goes into the prompt.
    needs_inline_role_file = True
    # An agent of agy's own with `tools: []`, the system prompt as its text, and
    # `inheritCustomizations` and `inheritMcp` off (`agent_file`).
    light_launch = True
    wire: ModuleType | None = agy_wire
    signals: Signals = agy_wire.SIGNALS
    # agy has no turn cap and reports no cost: its responses are counted, and one call's input watched.
    watched_limits: frozenset[str] = frozenset({"max_turns", "context_budget"})

    def __init__(self, binary: str = "agy", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)
        #: The last usage report: when it was asked (`time.monotonic()`), its text, its time.
        self._usage: tuple[float, str, str] = (0.0, "", "")
        self._usage_lock = threading.Lock()

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """agy denies by its permission rules (`deny_rule`): a command or its prefix, a file or a
        directory read or written, a domain, an MCP tool; not another tool, nor a wildcard
        inside a pattern."""
        odd = [rule for rule in denied if deny_rule(rule) is None]
        if not odd:
            return None
        return (
            f"agy cannot hold {', '.join(odd)}: its rules deny a command or its prefix (Bash), a file or a directory "
            "(Read, Write, Edit, MultiEdit, NotebookEdit), a domain (WebFetch(domain:...)) and an MCP tool "
            f"(mcp__server__tool) {DENY_POINTER}"
        )

    # --- credentials -------------------------------------------------------
    #
    # agy signs in with Google and keeps the tokens in the system's keyring, not in a
    # directory a launch could name. A Gemini API key is used only when agy's settings say
    # `"modelProvider": "gemini"`; with that setting and no key agy exits at startup, so a
    # key that does not work fails instead of falling back to the login.

    def bind_credential(
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment, agy's own settings and its Google login")
        provider = getattr(c, "provider", "")
        match c:
            case Subscription() if provider == PROVIDER:
                if c.config_dir or c.profile:
                    raise CredentialError(
                        "agy keeps its Google login in the system's keyring: a subscription for it names no config_dir or profile"
                    )
                return CredentialBinding(isolated=c.isolate, isolation="agy's Google login; no API key variable set, modelProvider unset")
            case ApiKey() if provider == PROVIDER:
                return CredentialBinding(
                    {"GEMINI_API_KEY": secret_value(c.key, env)},
                    isolated=c.isolate,
                    isolation="GEMINI_API_KEY with modelProvider gemini: the Gemini API, never the Google login",
                )
            case Subscription() | ApiKey():
                raise CredentialError(f"agy cannot use a {provider} {c.type} credential (provider must be {PROVIDER})")
            case _:
                raise CredentialError(f"agy cannot use {c.type} credentials")

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's minus the parent-session
        variables, no self-update, and `launch.env`; for any credential but `ambient`, every
        other one removed and the chosen one applied last. The bridge of the plugins' hooks
        finds the launch's hook state by `STATE_ENV`."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV, defaults=DEFAULT_ENV)
        env[STATE_ENV] = str(self._hook_state(launch))
        return env

    def _settings(self, launch: Launch) -> dict[str, Any]:
        """The settings of this launch alone (`--settings`): its mode (`AGENT_MODES`; a light
        launch, which calls no tool, names none), the deny rules of `Limits.disallowed_tools`,
        an allow rule for each MCP server the launch brings, and the model provider its
        credential names (`gemini` for an API key, agy's own for a Google login)."""
        out: dict[str, Any] = {}
        mode = AGENT_MODES.get(launch.permission_mode or "")
        if mode is not None and not self._light(launch):
            out["agentMode"] = mode
        deny = [r for r in map(deny_rule, launch.limits.disallowed_tools) if r is not None]
        allow = [f"mcp({name}/*)" for name in self._mcp_servers(launch)]
        if deny or allow:
            out["permissions"] = {**({"allow": allow} if allow else {}), **({"deny": list(dict.fromkeys(deny))} if deny else {})}
        if isinstance(launch.credential, ApiKey):
            out["modelProvider"] = "gemini"
        elif isinstance(launch.credential, Subscription):
            out["modelProvider"] = ""
        return out

    # --- what the task gives the launch ----------------------------------------

    def _hook_state(self, launch: Launch) -> Path:
        """Where the bridge keeps what the launch's hooks said (`hooks.STATE_ENV`)."""
        return self.scratch(launch.label, "hooks")

    def _mcp_servers(self, launch: Launch) -> dict[str, dict]:
        return mcp_config(launch.mcp_config) if launch.mcp_config and launch.tools != () else {}

    def _light(self, launch: Launch) -> bool:
        """Whether `launch` runs with no tools, as the agent whose file is its system prompt."""
        return launch.tools == ()

    def _customizations(self, launch: Launch) -> Path | None:
        """The directory whose `.agents/` holds what the task gives the launch, made afresh:
        the plugins' skills (the task's own first; a name already there is not copied
        again), their hooks and the launch's MCP servers, or, for a light launch, the agent
        that is its system prompt. None when there is nothing to give."""
        root = self.scratch(launch.label, "workspace")
        agents = root / ".agents"
        shutil.rmtree(agents, ignore_errors=True)
        if self._light(launch):
            target = agents / "agents" / f"{LIGHT_AGENT}.md"
            target.parent.mkdir(parents=True)
            text = agent_file(launch.system_prompt or "", launch.append_system_prompt, structured=launch.json_schema is not None)
            target.write_text(text, encoding="utf-8", newline="\n")
            return root
        for plug in launch.plugin_dirs:
            for found in sorted((Path(plug) / "skills").glob("*/SKILL.md")):
                target = agents / "skills" / found.parent.name
                if not target.exists():
                    shutil.copytree(found.parent.resolve(), target)
        python = launch.env.get(envvars.PYTHON) or sys.executable
        hooks = native_hooks(launch.plugin_dirs, python)
        if hooks:
            agents.mkdir(parents=True, exist_ok=True)
            (agents / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8", newline="\n")
        servers = self._mcp_servers(launch)
        if servers:
            agents.mkdir(parents=True, exist_ok=True)
            (agents / "mcp_config.json").write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n", encoding="utf-8", newline="\n")
        return root if agents.is_dir() else None

    # --- sessions ----------------------------------------------------------

    def _data_dir(self) -> Path:
        """Where agy keeps its conversations: `~/.gemini/antigravity-cli`."""
        return Path(self._base_env.get("HOME") or Path.home()) / ".gemini" / "antigravity-cli"

    def discard_session(self, launch: Launch, session_id: str) -> None:
        """Remove the conversation agy saved for a launch. A caller who asked for persistence
        keeps it."""
        if not launch.persist_session:
            self._remove_conversation(session_id)

    def _remove_conversation(self, session_id: str) -> None:
        """Remove what agy keeps of one conversation: its database and its transcript directory."""
        if not _CONVERSATION_RE.match(session_id or ""):
            return
        root = self._data_dir()
        (root / "conversations" / f"{session_id}.db").unlink(missing_ok=True)
        shutil.rmtree(root / "brain" / session_id, ignore_errors=True)

    # --- argv --------------------------------------------------------------

    def prepare(self, launch: Launch) -> Launch:
        """`launch` with its preamble and attached files written into the prompt: agy attaches
        no files. `append_system_prompt` goes at the head of the prompt too, on the first
        launch of a session, and so does a `system_prompt` of a launch that keeps its tools;
        a light launch has both in its agent's file."""
        if self._light(launch):
            return context_in_prompt(launch, append=False)
        launch = context_in_prompt(launch)
        if launch.system_prompt is None or launch.resume:
            return launch
        return dataclasses.replace(launch, prompt=f"{launch.system_prompt}\n\n{launch.prompt}", system_prompt=None)

    def _effort(self, launch: Launch) -> str | None:
        """The `--effort` a launch takes, or None. agy names a model's reasoning level in its
        id (`gemini-3.8-flash-high`) or takes it beside the id that lacks one
        (`gemini-3.8-flash` and `--effort high`), and refuses an effort beside an id that
        names a level, or beside a model that has none (checked against agy 1.5.9). So
        `Launch.effort` is passed only with a model id that names no level, and not for one
        `agy models` lists as it is, with no level to choose."""
        model = launch.model
        if not launch.effort or not model or catalogue.base_id(model) != model:
            return None
        listed = self._labels()
        if model in listed and not any(k != model and catalogue.base_id(k) == model for k in listed):
            return None
        return launch.effort

    def argv(self, launch: Launch) -> list[str]:
        """Assemble argv. No text of the task is on it but a prompt under `STDIN_THRESHOLD`."""
        launch = self.prepare(launch)
        a = [self.binary]
        a += ["--input-format", "stream-json"] if via_stdin(launch) else ["-p", launch.prompt]
        a += ["--output-format", "stream-json"]
        if launch.model:
            a += ["--model", launch.model]
        effort = self._effort(launch)
        if effort:
            a += ["--effort", effort]
        a += MODES.get(launch.permission_mode or "", ())
        if launch.resume:
            a += ["--conversation", launch.resume]
        given = self._customizations(launch)
        if self._light(launch):
            a += ["--agent", LIGHT_AGENT]
        out = writable_out(launch)
        for folder in (given, out, *readable_roots(launch)):
            if folder is not None:
                a += ["--add-dir", str(folder)]
        if launch.json_schema is not None:
            a += ["--json-schema", str(self._text_file(launch, "schema.json", json.dumps(launch.json_schema, ensure_ascii=False)))]
        settings = self._settings(launch)
        if settings:
            a += ["--settings", str(self._text_file(launch, "settings.json", json.dumps(settings, ensure_ascii=False)))]
        return a

    # --- run ---------------------------------------------------------------

    def fold(self, launch: Launch) -> EventFold:
        return agy_wire.StreamReader(launch.limits, resume=launch.resume or "", hook_state=self._hook_state(launch))

    def exchange(
        self, launch: Launch, argv: list[str], env: dict[str, str], fold: EventFold, watch: LimitsWatch
    ) -> tuple[bytes, str, int | None, Stop | None]:
        """The process run to its end, with a prompt past `STDIN_THRESHOLD` given as one JSON
        message on stdin. The hooks' state starts empty, and a launch that keeps no session
        leaves no conversation behind; nor does one that was to continue a conversation agy
        did not find, of the conversation agy started instead."""
        state = self._hook_state(launch)
        for name in (OBJECTIONS, PENDING):
            (state / name).unlink(missing_ok=True)

        def sink(raw: bytes) -> Stop | None:
            return fold.feed_line(raw) or watch()

        message = json.dumps({"event": "user", "message": {"content": launch.prompt}}, ensure_ascii=False) + "\n"
        try:
            return run_process(argv, env, launch, sink=sink, stderr_sink=self.watch_stderr(launch), stdin_text=message)
        finally:
            if isinstance(fold, agy_wire.StreamReader) and fold.resume_missed:
                self._remove_conversation(fold.session_id)
            else:
                self.discard_session(launch, fold.session_id)

    # --- what agy says about itself ---------------------------------------------

    def _labels(self) -> dict[str, str]:
        """The label of each model id `agy models` lists, asked once; empty when it cannot be read."""

        def read() -> dict[str, str]:
            out = self.run_catalogue(*catalogue.ARGS, env=DEFAULT_ENV)
            return catalogue.parse_models(out) if out is not None else {}

        return self._once("_model_labels", read)

    def read_models(self) -> dict[str, int | None] | None:
        """The model ids `agy models` lists for the login, each also without its reasoning
        level (`--model gemini-3.8-flash --effort high`); None when it cannot be read. agy
        lists no context window."""
        labels = self._labels()
        return dict.fromkeys(catalogue.model_ids(labels)) if labels else None

    def usage_reading(self, launch: Launch) -> QuotaReading | None:
        """The weekly and 5-hour usage of the plan's group that holds the launch's model, as
        `agy -p /usage --output-format json` reports it for the Google login (no model is
        called; one report serves the launches of `USAGE_FRESH_S`). None for an API key,
        for a model `agy models` does not list, or when the report cannot be read."""
        if not launch.model or isinstance(launch.credential, ApiKey):
            return None
        labels = self._labels()
        label = labels.get(launch.model) or next((v for k, v in labels.items() if catalogue.base_id(k) == launch.model), "")
        if not label:
            return None
        try:
            binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        except CredentialError:
            return None
        env = child_env(self._base_env, launch.credential, binding, {}, drop=PARENT_SESSION_ENV, defaults=DEFAULT_ENV)
        report, observed_at = self._usage_report(env)
        return catalogue.usage_reading(report, label, observed_at=observed_at) if report else None

    def _usage_report(self, env: dict[str, str]) -> tuple[str, str]:
        """What `agy -p /usage --output-format json` prints and when it was asked, asked again
        once the last answer is older than `USAGE_FRESH_S`; ('', '') when agy gives none.
        Launches that start together wait for one answer."""
        with self._usage_lock:
            asked, report, observed_at = self._usage
            if report and time.monotonic() - asked < USAGE_FRESH_S:
                return report, observed_at
            try:
                proc = subprocess.run(
                    commands.resolve([self.binary, *catalogue.USAGE_ARGS], self.base_path()),
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=USAGE_TIMEOUT_S,
                    stdin=subprocess.DEVNULL,
                    encoding="utf-8",
                    errors="replace",
                )
            except (OSError, subprocess.SubprocessError):
                return "", ""
            if proc.returncode != 0 or not proc.stdout.strip():
                return "", ""
            self._usage = (time.monotonic(), proc.stdout, now_iso())
            return proc.stdout, self._usage[2]
