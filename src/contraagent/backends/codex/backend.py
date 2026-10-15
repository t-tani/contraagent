"""Codex CLI backend: `codex exec --json`.

One launch is one `codex exec` (or `codex exec resume <thread id>`) in the
launch's cwd, with its JSONL events read as they arrive (`wire.EventReader`)
and the session's rollout file read after it ends (`wire.read_rollout`) for
what the events do not carry: per-call tokens, the model, the plan's usage.

What a launch sees (checked against codex-cli 0.162.1): no AGENTS.md
(`project_doc_max_bytes=0`), no hooks, plugins or execpolicy rules, and of the
skills only its plugins' and codex's own. Codex finds skills only in fixed
places (`$HOME/.agents/skills`, a repository's `.agents/skills`, `/etc/codex/skills`,
its bundled ones), so codex runs with a `HOME` of its own whose `.agents/skills`
links to each plugin's `skills/<name>`; the commands it runs get the real `HOME`
back (`shell_environment_policy.set.HOME`). Codex has no named-agent flag, so the
role's file is inlined into the prompt, as for omp. `Launch.system_prompt`
replaces codex's own instructions (`model_instructions_file`),
`append_system_prompt` is added as developer instructions, `json_schema`
becomes `--output-schema`, and a plugin's `.mcp.json` becomes `mcp_servers`.

`Limits.max_turns` counts tool calls and ends the launch past it.
`max_budget_usd` and `context_budget` are not enforced: codex reports no
cost, and per-call tokens only in the rollout file, after the launch.
"""

from __future__ import annotations

import atexit
import dataclasses
import json
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.base import PARENT_SESSION_ENV, Backend, apply_attestation
from contraagent.backends.codex.wire import RATE_LIMIT_RE, EventReader, call_usage, classify, find_rollout, read_rollout
from contraagent.backends.credentials import (
    Ambient,
    ApiKey,
    CredentialBase,
    CredentialBinding,
    CredentialError,
    Gateway,
    Secret,
    Subscription,
    child_env,
)
from contraagent.backends.launch import CallUsage, Launch, LaunchResult, RateLimit, Stop
from contraagent.backends.process import LaunchError, run_process, via_stdin

#: Config every launch gets: nothing the user or the project would add to the
#: instructions, and network access for the commands the agent runs.
ISOLATION_ARGS = (
    "--ignore-rules",
    "--disable",
    "hooks",
    "--disable",
    "plugins",
    "-c",
    "project_doc_max_bytes=0",
    "-c",
    "sandbox_workspace_write.network_access=true",
)
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


def mcp_servers(path: str) -> dict[str, dict]:
    """A plugin's `.mcp.json` (`mcpServers`) as codex `mcp_servers` tables: stdio servers
    (`command`, `args`, `env`) and streamable HTTP ones (`url`)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict] = {}
    for name, spec in (data.get("mcpServers") or {}).items():
        if not isinstance(spec, dict):
            continue
        if spec.get("command"):
            table: dict = {"command": spec["command"], "args": list(spec.get("args") or [])}
            if spec.get("env"):
                table["env"] = dict(spec["env"])
        elif spec.get("url"):
            table = {"url": spec["url"]}
        else:
            continue
        out[str(name)] = table
    return out


class CodexBackend(Backend):
    """Headless Codex CLI: `codex exec --json`."""

    name = "codex"
    binary = "codex"
    # `model_reasoning_effort`; the levels `~/.codex/models_cache.json` lists for each model.
    effort_levels = ("low", "medium", "high", "xhigh", "max", "ultra")
    # No `--agent`: the role's file goes into the prompt.
    needs_inline_role_file = True

    def __init__(self, binary: str = "codex", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)
        self._version: str | None = None
        self._scratch_root: Path | None = None

    def version(self) -> str:
        """The version `codex --version` prints (`codex-cli 0.162.1`). Queried once; empty when absent."""
        if self._version is None:
            exe = shutil.which(self.binary, path=self.base_path())
            self._version = ""
            if exe:
                try:
                    p = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30, env=self._base_env)
                    self._version = (p.stdout.split() or [""])[-1]
                except (OSError, subprocess.SubprocessError):
                    pass
        return self._version

    def _scratch(self, label: str, which: str, create: bool = True) -> Path:
        """A directory per launch label and purpose, under one root this process removes at exit."""
        if self._scratch_root is None:
            # Not under /tmp: codex refuses to put its helper binaries in a CODEX_HOME there.
            cache = Path(self._base_env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "contraagent"
            cache.mkdir(parents=True, exist_ok=True)
            self._scratch_root = Path(tempfile.mkdtemp(prefix="codex-", dir=cache))
            atexit.register(shutil.rmtree, self._scratch_root, True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label) or "launch"
        d = self._scratch_root / safe / which
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    # --- credentials -------------------------------------------------------
    #
    # Codex reads its login from `$CODEX_HOME/auth.json` (a ChatGPT login or a stored
    # API key) unless `CODEX_API_KEY` is set, and its model provider from
    # `$CODEX_HOME/config.toml`. Every credential variable is removed first. Isolation
    # points CODEX_HOME at an empty directory and ignores the user's config.toml, so
    # a credential that does not work fails instead of falling back to the stored login.

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and codex's own login and config.toml")

        def secret(s: Secret) -> str:
            return s.resolve(env) if env is not None else "<unresolved>"

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
                out = {"CODEX_API_KEY": secret(c.key)}
            case Gateway():
                # A provider of its own, speaking the Responses API to <base_url>/responses, with
                # the token as `Authorization: Bearer` (env_key) or `x-api-key` (env_http_headers).
                pid = f"{c.provider}-gateway" if c.provider in _BUILTIN_PROVIDERS else c.provider
                key_var = f"{''.join(ch if ch.isalnum() else '_' for ch in c.provider).upper()}_API_KEY"
                table: dict = {"name": pid, "base_url": c.endpoint(env), "wire_api": "responses"}
                out = {}
                if c.token is not None:
                    out[key_var] = secret(c.token)
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
            out["CODEX_HOME"] = str(self._scratch(label, "codex-home", create=env is not None))
            return CredentialBinding(out, args=args, isolated=True, isolation="empty CODEX_HOME, user config.toml ignored: no stored login")
        return CredentialBinding(out, args=args, isolation="the user's CODEX_HOME stays visible")

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's minus the parent-session variables
        and `launch.env`; for any credential but `ambient`, every other one removed and the
        chosen one applied last. A launch that keeps no session writes codex's thread index
        to a scratch `CODEX_SQLITE_HOME`, not the user's. `HOME` is the launch's own
        (`skill_home`), so `CODEX_HOME` is always named."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        defaults = {} if launch.persist_session else {"CODEX_SQLITE_HOME": str(self._scratch(launch.label, "state"))}
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV, defaults=defaults)
        env.setdefault("CODEX_HOME", str(self.codex_home(launch)))
        env["HOME"] = str(self.skill_home(launch))
        return env

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
        home = self._scratch(launch.label, "home")
        skills = home / ".agents" / "skills"
        shutil.rmtree(skills, ignore_errors=True)  # removes the links, never what they point to
        skills.mkdir(parents=True)
        for plug in launch.plugin_dirs:
            for found in sorted((Path(plug) / "skills").glob("*/SKILL.md")):
                link = skills / found.parent.name
                if not link.is_symlink():
                    link.symlink_to(found.parent.resolve(), target_is_directory=True)
        return home

    # --- sessions ----------------------------------------------------------

    def resumable(self, launch: Launch) -> Launch:
        """Codex reports its thread id; the thread has to stay where `codex exec resume` finds it."""
        return dataclasses.replace(launch, persist_session=True)

    def resumed(self, launch: Launch, prior: LaunchResult, prompt: str) -> Launch | None:
        if not prior.session_id or not launch.persist_session:
            return None
        return dataclasses.replace(
            launch, prompt=prompt, resume=prior.session_id, session_id=None, preamble=None, context_files=(), prompt_via_stdin=None
        )

    def discard_session(self, launch: Launch, session_id: str) -> None:
        """Remove the rollout file `resumable` made codex keep. A caller who asked for persistence keeps it."""
        if launch.persist_session:
            return
        found = find_rollout(self.codex_home(launch), session_id)
        if found is not None:
            found.unlink(missing_ok=True)

    # --- argv --------------------------------------------------------------

    def composed(self, launch: Launch) -> Launch:
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
        launch = self.composed(launch)
        a = [self.binary, "exec"]
        if launch.resume:
            a += ["resume", launch.resume]
        a += ["--json", "--skip-git-repo-check", *ISOLATION_ARGS]
        # codex runs with the launch's own HOME (`skill_home`); the commands it runs do not.
        a += ["-c", f"shell_environment_policy.set.HOME={toml(self.real_home())}"]
        a += ["-c", f"sandbox_mode={toml(SANDBOX.get(launch.permission_mode or '', 'workspace-write'))}"]
        if launch.model:
            a += ["-m", launch.model]
        if launch.effort:
            a += ["-c", f"model_reasoning_effort={toml(launch.effort)}"]
        if launch.system_prompt is not None:
            f = self._scratch(launch.label, "instructions") / "system.md"
            f.write_text(launch.system_prompt, encoding="utf-8")
            a += ["-c", f"model_instructions_file={toml(str(f))}"]
        if launch.append_system_prompt is not None:
            a += ["-c", f"developer_instructions={toml(launch.append_system_prompt)}"]
        if launch.json_schema is not None:
            f = self._scratch(launch.label, "schema") / "schema.json"
            f.write_text(json.dumps(launch.json_schema, ensure_ascii=False), encoding="utf-8")
            a += ["--output-schema", str(f)]
        if launch.mcp_config is not None:
            for name, table in mcp_servers(launch.mcp_config).items():
                if "command" in table:
                    table["env"] = {"HOME": self.real_home(), **table.get("env", {})}
                a += ["-c", f"mcp_servers.{toml(name)}={toml(table)}"]
        a += self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label).args
        a.append("-" if via_stdin(launch) else launch.prompt)
        return a

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """A quota refusal on stderr is a rate limit, not an error: a launch that dies
        before its first event prints only there."""
        if launch_result.stop not in (Stop.ERROR, Stop.NO_OUTPUT, Stop.API_ERROR, Stop.LAUNCH_FAILED):
            return
        if not RATE_LIMIT_RE.search(stderr or ""):
            return
        launch_result.stop = Stop.RATE_LIMITED
        launch_result.ok = False
        if launch_result.rate_limit is None:
            launch_result.rate_limit = RateLimit(status="quota")

    # --- run ---------------------------------------------------------------

    def run(self, launch: Launch) -> LaunchResult:
        """Build argv/env, spawn, read the events live (a refused credential and
        `max_turns` end the launch), then read the rollout file and return the LaunchResult."""
        started = datetime.now(UTC).isoformat(timespec="seconds")
        t0 = time.monotonic()
        version = self.version()

        def failed(argv: list[str], why: str) -> LaunchResult:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                started_at=started,
                wall_s=time.monotonic() - t0,
                cli_version=version,
                argv=argv,
                model=launch.model,
                credential=launch.credential.label,
                stderr_tail=why,
            )

        try:
            launch = self.composed(launch)
            argv = self.argv(launch)
            env = self.env(launch)
        except CredentialError as exc:
            return failed([], f"credential: {exc}")
        except OSError as exc:
            return failed([], f"attached file: {exc}")
        if not shutil.which(self.binary, path=self.base_path()):
            return failed(argv, f"{self.binary} not on PATH")

        home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
        earlier = find_rollout(home, launch.resume) if launch.resume else None
        start = earlier.stat().st_size if earlier is not None else 0
        reader = EventReader()
        cap = launch.limits.max_turns

        def sink(line: bytes) -> Stop | None:
            stop = reader.feed(line.decode("utf-8", "replace"))
            if stop is None and cap is not None and sum(reader.tool_uses.values()) > cap:
                return Stop.MAX_TURNS
            return stop

        try:
            _, stderr_tail, exit_code, killed = run_process(argv, env, launch, sink=sink)
        except LaunchError as exc:
            return failed(argv, str(exc))
        wall = time.monotonic() - t0

        rollout = None
        found = find_rollout(home, reader.thread_id)
        if found is not None:
            rollout = read_rollout(found, start if found == earlier else 0)
            if not launch.persist_session:
                found.unlink(missing_ok=True)
        calls = rollout.calls if rollout is not None else []
        if not calls and reader.usage:
            # No rollout to read: the turn's sum stands in as one call.
            calls = [call_usage(reader.usage, launch.model)]
        model = (rollout.model if rollout is not None else "") or launch.model
        stop = killed or classify(reader, exit_code)
        text = reader.result_text
        structured = None
        if launch.json_schema is not None and stop is Stop.COMPLETED:
            try:
                structured = json.loads(text)
            except ValueError:
                structured = None
        rate_limits = list(rollout.rate_limits) if rollout is not None else []
        launch_result = LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=stop,
            ok=stop is Stop.COMPLETED,
            started_at=started,
            wall_s=wall,
            exit_code=exit_code,
            cli_version=(rollout.cli_version if rollout is not None else "") or version,
            argv=argv,
            model=launch.model,
            credential=launch.credential.label,
            session_id=reader.thread_id,
            result_text=text,
            structured_output=structured,
            tool_uses=dict(reader.tool_uses),
            web_queries=list(reader.web_queries),
            rate_limit=rate_limits[-1] if rate_limits else None,
            rate_limits=rate_limits,
            unread_events=dict(reader.unread),
            init_model=model,
            context_window=rollout.context_window if rollout is not None else None,
            api_retries=reader.api_retries,
            retry_errors=dict(reader.retry_errors),
            stderr_tail="\n".join(x for x in (reader.failure, stderr_tail) if x)[-2000:],
            raw_result={"usage": reader.usage} if reader.usage else {},
        )
        launch_result.usage.calls = [CallUsage(c.model or model, c.input, c.cache_read, c.cache_creation, c.output) for c in calls]
        # The turn's own sum counts a resumed thread's earlier turns too; the calls do not.
        launch_result.usage.output_total = launch_result.usage.output
        self.reclassify(launch_result, stderr_tail)
        apply_attestation(self, launch_result, launch)
        return launch_result
