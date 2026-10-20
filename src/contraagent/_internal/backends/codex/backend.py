"""Codex CLI backend: `codex exec --json`.

One launch is one `codex exec` (or `codex exec resume <thread id>`) in the
launch's cwd, with its JSONL events read as they arrive (`wire.EventReader`)
and the session's rollout file read after it ends (`wire.read_rollout`) for
what the events do not carry: per-call tokens, the model, the plan's usage. When it
cannot be read, the launch's tokens are the totals its `turn.completed` event printed, and
`LaunchResult.usage_unknown` says so.

What a launch sees (checked against codex-cli 0.162.1): no AGENTS.md
(`project_doc_max_bytes=0`), no plugins or execpolicy rules, of the hooks only its
plugins' (`codex.hooks`: rendered into `codex/hooks.json`, passed as config and trusted
by hash), and of the skills only its plugins' and codex's own. Codex finds skills only in fixed
places (`$HOME/.agents/skills`, a project's `.agents/skills` and `.codex/skills`,
`/etc/codex/skills`, its bundled ones), so codex runs with a `HOME` of its own whose
`.agents/skills` links to each plugin's `skills/<name>`, and each project skill is
turned off by its path (`skills.config`, `project_skills`); the commands it runs get
the real `HOME` back (`shell_environment_policy.set.HOME`). Codex has no named-agent flag, so the
role's file is inlined into the prompt, as for omp. `Launch.system_prompt`
replaces codex's own instructions (`model_instructions_file`),
`append_system_prompt` is added as developer instructions, `json_schema`
becomes `--output-schema`, and a plugin's `.mcp.json` becomes `mcp_servers`.

`Limits.max_turns` counts tool calls and ends the launch past it.
Codex's `workspace-write` sandbox makes the launch's cwd writable and, by default, `/tmp`
and `$TMPDIR` too, and its Linux sandbox leaves empty `.git`, `.agents` and `.codex` paths
behind in a writable root (`codex-rs/linux-sandbox/src/bwrap.rs`). So `/tmp` and `$TMPDIR`
are taken out (`sandbox_workspace_write.exclude_slash_tmp`, `exclude_tmpdir_env_var`) and the
launch gets a temporary directory of its own instead (`launch_tmp`), its one writable root
besides the cwd (`sandbox_workspace_write.writable_roots`) and the `TMPDIR`, `TMP` and `TEMP`
of codex and of the commands it runs; it is removed when the launch ends.

`max_budget_usd` and `context_budget` are not enforced: codex reports no
cost, and per-call tokens only in the rollout file, after the launch.
"""

from __future__ import annotations

import dataclasses
import json
import secrets
import shutil
from pathlib import Path
from types import ModuleType

from contraagent._internal.backends import plugin_files
from contraagent._internal.backends.base import PARENT_SESSION_ENV, Backend, ResumeById, safe_label, temp_root
from contraagent._internal.backends.codex import wire as codex_wire
from contraagent._internal.backends.codex.hooks import HOOKS_FILE, hooks_config
from contraagent._internal.backends.codex.wire import EventReader, find_rollout, read_rollout
from contraagent._internal.backends.credentials import (
    Ambient,
    ApiKey,
    Credential,
    CredentialBinding,
    CredentialError,
    Gateway,
    Subscription,
    child_env,
    secret_value,
)
from contraagent._internal.backends.launch import Launch, Stop
from contraagent._internal.backends.process import via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold, LimitsWatch
from contraagent._internal.platform.links import links

#: Config every launch gets: nothing the user or the project would add to the
#: instructions, and network access for the commands the agent runs. Hooks are turned on
#: only for a launch whose plugins have some (`hook_args`).
ISOLATION_ARGS = (
    "--ignore-rules",
    "--disable",
    "plugins",
    "-c",
    "project_doc_max_bytes=0",
    "-c",
    "sandbox_workspace_write.network_access=true",
)
#: The variables that name a temporary directory: each is the launch's own (`launch_tmp`).
TMP_VARS = ("TMPDIR", "TMP", "TEMP")
#: `Launch.permission_mode` (Claude Code's names) to codex's sandbox.
SANDBOX = {"bypassPermissions": "danger-full-access", "plan": "read-only"}
#: Provider ids codex defines itself; a gateway may not reuse one.
_BUILTIN_PROVIDERS = ("openai", "oss", "ollama", "lmstudio")


def toml(value: object) -> str:
    """A `-c key=value` value: a TOML string, list, inline table, number or boolean."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}={toml(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(toml(v) for v in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


#: Where codex finds a project's skills, in the working directory and each directory above
#: it up to the repository's root (checked against codex-cli 0.162.1).
PROJECT_SKILL_DIRS = (".agents/skills", ".codex/skills")


def project_skills(cwd: Path, keep: set[Path]) -> list[Path]:
    """The project's skill files codex would load in `cwd` (`PROJECT_SKILL_DIRS`, from `cwd`
    up to the nearest directory holding `.git`, or `cwd` alone outside a repository), except
    those under a directory in `keep` (a plugin's skills)."""
    cwd = cwd.resolve()
    chain = [cwd, *cwd.parents]
    root = next((d for d in chain if (d / ".git").exists()), None)
    dirs = chain[: chain.index(root) + 1] if root is not None else [cwd]
    found: list[Path] = []
    for d in dirs:
        for sub in PROJECT_SKILL_DIRS:
            for f in sorted((d / sub).rglob("SKILL.md")):
                f = f.resolve()
                if not any(f.is_relative_to(k) for k in keep):
                    found.append(f)
    return found


def mcp_servers(path: str) -> dict[str, dict]:
    """A plugin's `.mcp.json` (`mcpServers`) as codex `mcp_servers` tables: stdio servers
    (`command`, `args`, `env`) and streamable HTTP ones (`url`)."""
    out: dict[str, dict] = {}
    for name, spec in plugin_files.mcp_servers(path).items():
        if spec.get("command"):
            table: dict = {"command": spec["command"], "args": list(spec.get("args") or [])}
            if spec.get("env"):
                table["env"] = dict(spec["env"])
        elif spec.get("url"):
            table = {"url": spec["url"]}
        else:
            continue
        out[name] = table
    return out


class CodexBackend(ResumeById, Backend):
    """Headless Codex CLI: `codex exec --json`.

    A plugin's hooks reach Codex as config: `codex/hooks.json` (`contraagent plugin
    render`) is passed as one `-c hooks={...}` value, and nothing is written into a
    `CODEX_HOME`. Codex runs a hook an administrator does not manage only when the config
    trusts it, `hooks.state."<key>".trusted_hash` equal to the hook's hash, so the launch
    sets that for each of the plugin's hooks:

    - the key is `<source>:<event>:<group index>:<handler index>`, the source of `-c`
      values being the path `/<session-flags>/config.toml`, the event in snake case
      (`pre_tool_use`, `post_tool_use`, `stop`);
    - the hash is `sha256:` and the hex SHA-256 of a compact JSON with sorted keys of the
      normalized hook: `event_name`, the group's `matcher` (none for `Stop`) and its one
      handler with its `timeout` filled in (600 seconds when unset) and `async`.

    The same `hooks.state` turns off every hook the user's `config.toml` trusts
    (`enabled = false`); with any credential but `ambient`, the user's config is not read
    at all.
    """

    name = "codex"
    binary = "codex"
    stop_hooks_file: str | None = HOOKS_FILE
    # `model_reasoning_effort`; the levels `~/.codex/models_cache.json` lists for each model.
    effort_levels: tuple[str, ...] | None = ("low", "medium", "high", "xhigh", "max", "ultra")
    # No `--agent`: the role's file goes into the prompt.
    needs_inline_role_file = True
    wire: ModuleType | None = codex_wire
    signals: Signals = codex_wire.SIGNALS
    # `max_turns` counts tool calls; codex reports no cost, and per-call tokens only in the
    # rollout file, after the launch, so the cost and context budgets are not enforced.
    watched_limits: frozenset[str] = frozenset({"max_turns"})

    def __init__(self, binary: str = "codex", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)
        #: Each thread's tokens so far, as its last launch's `turn.completed` printed them: a
        #: resumed launch's own tokens are its totals minus these (`EventReader.earlier`).
        self._thread_usage: dict[str, dict] = {}

    def scratch_parent(self) -> Path:
        """Not under /tmp: codex refuses to put its helper binaries in a CODEX_HOME there."""
        return Path(self._base_env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "contraagent"

    # --- credentials -------------------------------------------------------
    #
    # Codex reads its login from `$CODEX_HOME/auth.json` (a ChatGPT login or a stored
    # API key) unless `CODEX_API_KEY` is set, and its model provider from
    # `$CODEX_HOME/config.toml`. Every credential variable is removed first. Isolation
    # points CODEX_HOME at an empty directory and ignores the user's config.toml, so
    # a credential that does not work fails instead of falling back to the stored login.

    def bind_credential(
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and codex's own login and config.toml")

        provider = getattr(c, "provider", "")
        if isinstance(c, (Subscription, ApiKey)) and provider != "openai":
            raise CredentialError(f"codex cannot use a {provider} {c.type} credential (provider must be openai)")
        args: tuple[str, ...] = ("--ignore-user-config",) if c.isolate else ()
        match c:
            case Subscription():
                out = {"CODEX_HOME": str(c.config_dir)} if c.config_dir else {}
                where = c.config_dir or "~/.codex"
                return CredentialBinding(
                    out,
                    args=(*args, "-c", 'forced_login_method="chatgpt"'),
                    isolated=c.isolate,
                    isolation=f"the ChatGPT login in {where}; no other credential variable set",
                )
            case ApiKey():
                out = {"CODEX_API_KEY": secret_value(c.key, env)}
            case Gateway():
                # A provider of its own, speaking the Responses API to <base_url>/responses, with
                # the token as `Authorization: Bearer` (env_key) or `x-api-key` (env_http_headers).
                pid = f"{c.provider}-gateway" if c.provider in _BUILTIN_PROVIDERS else c.provider
                key_var = f"{''.join(ch if ch.isalnum() else '_' for ch in c.provider).upper()}_API_KEY"
                table: dict = {"name": pid, "base_url": c.endpoint(env), "wire_api": "responses"}
                out = {}
                if c.token is not None:
                    out[key_var] = secret_value(c.token, env)
                    if c.auth == "bearer":
                        table["env_key"] = key_var
                    else:
                        table["env_http_headers"] = {"x-api-key": key_var}
                if c.headers:
                    table["http_headers"] = dict(c.headers)
                args += ("-c", f"model_provider={toml(pid)}", "-c", f"model_providers.{pid}={toml(table)}")
            case _:
                raise CredentialError(f"codex cannot use {c.type} credentials")
        if c.isolate:
            out["CODEX_HOME"] = str(self.scratch(label, "codex-home", create=env is not None))
            return CredentialBinding(out, args=args, isolated=True, isolation="empty CODEX_HOME, user config.toml ignored: no stored login")
        return CredentialBinding(out, args=args, isolation="the user's CODEX_HOME stays visible")

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's minus the parent-session variables
        and `launch.env`; for any credential but `ambient`, every other one removed and the
        chosen one applied last. A launch that keeps no session writes codex's thread index
        to a scratch `CODEX_SQLITE_HOME`, not the user's. `HOME` is the launch's own
        (`skill_home`), so `CODEX_HOME` is always named."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        defaults = {} if launch.persist_session else {"CODEX_SQLITE_HOME": str(self.scratch(launch.label, "state"))}
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV, defaults=defaults)
        env.setdefault("CODEX_HOME", str(self.codex_home(launch)))
        env["HOME"] = str(self.skill_home(launch))
        env.update(dict.fromkeys(TMP_VARS, str(self.launch_tmp(launch))))
        return env

    def launch_tmp(self, launch: Launch) -> Path:
        """The launch's own temporary directory, `<temp_root>/codex-<label>-<random>`: its
        `TMPDIR` and the sandbox's one writable root besides the cwd. `exchange` makes it
        (owner-only) and removes it when the launch ends, however it ends."""
        token = vars(self).setdefault("_tmp_token", secrets.token_hex(6))
        return temp_root() / f"codex-{safe_label(launch.label)}-{token}"

    def real_home(self) -> str:
        """The user's own `HOME`: what the commands codex runs see."""
        return self._base_env.get("HOME") or str(Path.home())

    def codex_home(self, launch: Launch) -> Path:
        """Where the launch's codex keeps its login and sessions."""
        try:
            home = self.bind_credential(launch.credential, launch.model, label=launch.label).env.get("CODEX_HOME")
        except CredentialError:
            home = None
        return Path(home or self._base_env.get("CODEX_HOME") or Path(self.real_home()) / ".codex")

    def skill_home(self, launch: Launch) -> Path:
        """The `HOME` codex runs with: its `.agents/skills` holds a link to each skill
        (`skills/<name>/SKILL.md`) of the launch's plugins, the task's own first; a name
        already linked is not linked again. Made afresh for every launch."""
        home = self.scratch(launch.label, "home")
        skills = home / ".agents" / "skills"
        shutil.rmtree(skills, ignore_errors=True)  # removes the links, never what they point to
        skills.mkdir(parents=True)
        for plug in launch.plugin_dirs:
            for found in sorted((Path(plug) / "skills").glob("*/SKILL.md")):
                link = skills / found.parent.name
                if not link.exists(follow_symlinks=False):  # a symbolic link, or a junction on Windows
                    links.link(found.parent.resolve(), link)
        return home

    # --- sessions ----------------------------------------------------------

    def discard_session(self, launch: Launch, session_id: str) -> None:
        """Remove the rollout file `resumable` made codex keep. A caller who asked for persistence keeps it."""
        if launch.persist_session:
            return
        found = find_rollout(self.codex_home(launch), session_id)
        if found is not None:
            found.unlink(missing_ok=True)

    # --- argv --------------------------------------------------------------

    def prepare(self, launch: Launch) -> Launch:
        """`launch` with its preamble and attached files written into the prompt: codex attaches no files."""
        if not launch.preamble and not launch.context_files:
            return launch
        parts = [launch.preamble] if launch.preamble else []
        for f in launch.context_files:
            parts.append(f'<file path="{f}">\n{Path(f).read_text(encoding="utf-8")}\n</file>')
        parts.append(launch.prompt)
        return dataclasses.replace(launch, prompt="\n\n".join(parts), preamble=None, context_files=())

    def argv(self, launch: Launch) -> list[str]:
        """Assemble argv. `codex exec resume` takes neither `-s` nor `-C`, so the sandbox is
        set through `-c` and the directory is the process's cwd."""
        launch = self.prepare(launch)
        a = [self.binary, "exec"]
        if launch.resume:
            a += ["resume", launch.resume]
        a += ["--json", "--skip-git-repo-check", *ISOLATION_ARGS, *self.hook_args(launch)]
        # codex runs with the launch's own HOME (`skill_home`); the commands it runs do not.
        a += ["-c", f"shell_environment_policy.set.HOME={toml(self.real_home())}"]
        a += self.tmp_args(launch)
        # The project's own skills: codex has no switch for them, only a per-file `enabled = false`.
        keep = {(Path(p) / "skills").resolve() for p in launch.plugin_dirs}
        disabled = [{"path": str(f), "enabled": False} for f in project_skills(Path(launch.cwd), keep)]
        if disabled:
            a += ["-c", f"skills.config={toml(disabled)}"]
        a += ["-c", f"sandbox_mode={toml(SANDBOX.get(launch.permission_mode or '', 'workspace-write'))}"]
        if launch.model:
            a += ["-m", launch.model]
        if launch.effort:
            a += ["-c", f"model_reasoning_effort={toml(launch.effort)}"]
        if launch.system_prompt is not None:
            f = self.scratch(launch.label, "instructions") / "system.md"
            f.write_text(launch.system_prompt, encoding="utf-8", newline="\n")
            a += ["-c", f"model_instructions_file={toml(str(f))}"]
        if launch.append_system_prompt is not None:
            a += ["-c", f"developer_instructions={toml(launch.append_system_prompt)}"]
        if launch.json_schema is not None:
            f = self.scratch(launch.label, "schema") / "schema.json"
            f.write_text(json.dumps(launch.json_schema, ensure_ascii=False), encoding="utf-8", newline="\n")
            a += ["--output-schema", str(f)]
        if launch.mcp_config is not None:
            for name, table in mcp_servers(launch.mcp_config).items():
                if "command" in table:
                    table["env"] = {"HOME": self.real_home(), **table.get("env", {})}
                a += ["-c", f"mcp_servers.{toml(name)}={toml(table)}"]
        a += self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label).args
        a.append("-" if via_stdin(launch) else launch.prompt)
        return a

    def tmp_args(self, launch: Launch) -> list[str]:
        """The sandbox's temporary directory: `/tmp` and `$TMPDIR` not writable, the launch's
        own (`launch_tmp`) writable and named by `TMP_VARS` in the commands codex runs."""
        tmp = str(self.launch_tmp(launch))
        a = [
            "-c",
            "sandbox_workspace_write.exclude_slash_tmp=true",
            "-c",
            "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "-c",
            f"sandbox_workspace_write.writable_roots={toml([tmp])}",
        ]
        for var in TMP_VARS:
            a += ["-c", f"shell_environment_policy.set.{var}={toml(tmp)}"]
        return a

    def hook_args(self, launch: Launch) -> list[str]:
        """The plugins' rendered hooks (`codex/hooks.json`), trusted by hash, with the user's own
        turned off (`codex.hooks.hooks_config`); hooks turned off when there are none."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        user_config = None if binding.isolated else self.codex_home(launch) / "config.toml"
        table = hooks_config(launch.plugin_dirs, self.real_home(), user_config)
        if table is None:
            return ["--disable", "hooks"]
        return ["--enable", "hooks", "-c", f"hooks={toml(table)}"]

    # --- run ---------------------------------------------------------------

    def fold(self, launch: Launch) -> EventFold:
        return EventReader()

    def exchange(
        self, launch: Launch, argv: list[str], env: dict[str, str], fold: EventFold, watch: LimitsWatch
    ) -> tuple[bytes, str, int | None, Stop | None]:
        """The events read live (a refused credential and `max_turns` end the launch), then the
        session's rollout file for what they do not carry; a launch that keeps no session
        leaves no rollout behind. A resumed thread's rollout is read from where it ended. The
        launch's temporary directory (`launch_tmp`) lives only as long as its process."""
        assert isinstance(fold, EventReader)
        fold.earlier = self._thread_usage.get(launch.resume) if launch.resume else {}
        home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
        earlier = find_rollout(home, launch.resume) if launch.resume else None
        start = earlier.stat().st_size if earlier is not None else 0
        tmp = self.launch_tmp(launch)
        tmp.mkdir(mode=0o700, exist_ok=True)
        try:
            out = super().exchange(launch, argv, env, fold, watch)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if fold.thread_id and fold.turn_usage:
            self._thread_usage[fold.thread_id] = fold.turn_usage
        found = find_rollout(home, fold.thread_id)
        if found is not None:
            fold.rollout = read_rollout(found, start if found == earlier else 0)
            if not launch.persist_session:
                found.unlink(missing_ok=True)
        return out
