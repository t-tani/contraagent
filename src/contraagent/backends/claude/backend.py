"""Claude Code backend: `claude -p` with stream-json output.

Each launch can load one static plugin dir (`--plugin-dir`), so the
invocation sees exactly one agent, its skill bundle, its command prompt,
and its settings — never the working tree's top-level .claude/ directory.

Ported from an earlier `claude -p` wrapper (`ClaudeCLI`): the full
argv surface, the live stream reader (per-call usage, rate limits,
denials, retries, budget/context/stall/denial stops), and the
result classifier. Env isolation (PARENT_SESSION_ENV + DEFAULT_ENV) and the
provider identity (`Credential`) are shared with the omp backend.
Plugin isolation rides on top: `--plugin-dir`, where a pipeline passes
`--agent` resolved from `.claude/agents/`.
"""

from __future__ import annotations

import atexit
import dataclasses
import json
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.base import PARENT_SESSION_ENV, Backend, apply_attestation
from contraagent.backends.claude.stream import RATE_LIMIT_RE, StreamReader, classify_result
from contraagent.backends.credentials import (
    Ambient,
    ApiKey,
    Bedrock,
    CredentialBase,
    CredentialBinding,
    CredentialError,
    Gateway,
    OAuthToken,
    Secret,
    Subscription,
    Vertex,
    WorkloadIdentity,
    child_env,
)
from contraagent.backends.launch import Launch, LaunchResult, RateLimit, Stop
from contraagent.backends.process import LaunchError, run_process, via_stdin

# Env added to every child: no CLAUDE.md files, no auto-memory (its index in the
# prompt, its writes). A task agent's instructions are its plugin and its call
# file. Confirmed present in CLI binaries >= 2.1.240; on older builds the reads
# silently resume and nothing breaks.
DEFAULT_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
# The settings files a launch reads when it names none: none. The user's, the
# project's and the local ones bring hooks, skills, commands, agents, plugins and
# permissions of their own; a task agent gets its plugin's (`--plugin-dir`, its
# settings.json through `--settings`). Built-in tools and skills are unaffected.
DEFAULT_SETTING_SOURCES = ""

# First CLI version supporting `--permission-prompts`. Older CLIs die on
# unknown flags, so the flag is withheld when the version is unknown.
PERMISSION_PROMPTS_MIN = (2, 1, 259)

# Hollow shape: <=1 turn, no tool use, raw tool-call text as the body.
_HOLLOW_RE = re.compile(r"\b(Bash|Read|Write|Edit|Skill|Agent|WebFetch|WebSearch)\(")

# Claude session ids are UUIDs. Anything else is refused before it is
# joined into a path: the id comes from the child's own stream, and a
# deletion keyed on it must not be steerable outside the session store.
_SESSION_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{0,63}$")


class ClaudeBackend(Backend):
    """Headless Claude Code: `claude -p` with stream-json output."""

    name = "claude"
    binary = "claude"
    effort_levels = ("low", "medium", "high", "xhigh", "max")
    # `--fallback-model` takes a comma-separated list and tries each in
    # order when the default is overloaded. Verified on 2.1.285.
    native_model_chain = True
    drivable_model_chain = True

    def __init__(self, binary: str = "claude", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)
        self._version: str | None = None
        self._isolation_root: Path | None = None

    def version(self) -> str:
        """First word of `claude --version`. Queried once; empty when absent."""
        if self._version is None:
            exe = shutil.which(self.binary, path=self.base_path())
            if not exe:
                self._version = ""
            else:
                try:
                    p = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30, env=self._base_env)
                    self._version = (p.stdout.split() or [""])[0]
                except (OSError, subprocess.SubprocessError):
                    self._version = ""
        return self._version

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's minus the parent-session
        variables, claude's own defaults and `launch.env`; for any credential but
        `ambient`, with every other credential removed and the chosen one applied last."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        return child_env(
            self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV, defaults={**DEFAULT_ENV, "AGMSG_SKIP": "1"}
        )

    # --- credentials -------------------------------------------------------
    #
    # Claude Code's own precedence, highest first (code.claude.com/docs/en/authentication):
    # cloud provider (CLAUDE_CODE_USE_*) > ANTHROPIC_AUTH_TOKEN > ANTHROPIC_API_KEY >
    # apiKeyHelper > CLAUDE_CODE_OAUTH_TOKEN > Anthropic profile / federation > /login.
    # Every one of those variables is removed first, so only the chosen one is set.
    # What remains ambient is file state: the /login credentials and settings in
    # CLAUDE_CONFIG_DIR, and Anthropic profiles in ANTHROPIC_CONFIG_DIR. Isolation
    # points both at empty directories: with no login there, a credential that does
    # not work fails ("Not logged in", checked against the real CLI) instead of
    # falling back to the subscription.

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and Claude Code's own login")
        provider = getattr(c, "provider", "anthropic")
        if provider != "anthropic" and not isinstance(c, Gateway):  # a gateway speaks the Anthropic API to claude
            raise CredentialError(f"claude cannot use a {provider} {c.type} credential")

        def secret(s: Secret) -> str:
            return s.resolve(env) if env is not None else "<unresolved>"

        match c:
            case Subscription():
                out = {"CLAUDE_CONFIG_DIR": str(c.config_dir)} if c.config_dir else {}
                if c.isolate:
                    out["ANTHROPIC_CONFIG_DIR"] = self._isolated_dir(label, "anthropic", create=env is not None)
                where = c.config_dir or "~/.claude"
                return CredentialBinding(out, isolated=c.isolate, isolation=f"the /login in {where}; no other credential variable set")
            case ApiKey():
                out = {"ANTHROPIC_API_KEY": secret(c.key)}
            case OAuthToken():
                out = {"CLAUDE_CODE_OAUTH_TOKEN": secret(c.token)}
            case Gateway():
                # Checked against the real CLI: requests go to <base_url>/v1/messages, the token as
                # `Authorization: Bearer` (ANTHROPIC_AUTH_TOKEN) or `x-api-key` (ANTHROPIC_API_KEY),
                # and ANTHROPIC_CUSTOM_HEADERS as extra headers.
                out = {"ANTHROPIC_BASE_URL": c.endpoint(env)}
                if c.token is not None:
                    out["ANTHROPIC_AUTH_TOKEN" if c.auth == "bearer" else "ANTHROPIC_API_KEY"] = secret(c.token)
                if c.headers:
                    out["ANTHROPIC_CUSTOM_HEADERS"] = c.header_lines()
            case WorkloadIdentity():
                out = {
                    "ANTHROPIC_FEDERATION_RULE_ID": c.federation_rule_id,
                    "ANTHROPIC_ORGANIZATION_ID": c.organization_id,
                    "ANTHROPIC_IDENTITY_TOKEN_FILE": str(c.identity_token_file),
                }
                if c.service_account_id:
                    out["ANTHROPIC_SERVICE_ACCOUNT_ID"] = c.service_account_id
                if c.workspace_id:
                    out["ANTHROPIC_WORKSPACE_ID"] = c.workspace_id
            case Bedrock():
                out = {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": c.region}
                if c.bearer is not None:
                    out["AWS_BEARER_TOKEN_BEDROCK"] = secret(c.bearer)
                elif c.aws_profile:
                    out["AWS_PROFILE"] = c.aws_profile
            case Vertex():
                out = {"CLAUDE_CODE_USE_VERTEX": "1", "ANTHROPIC_VERTEX_PROJECT_ID": c.project, "CLOUD_ML_REGION": c.region}
                if c.credentials_file:
                    out["GOOGLE_APPLICATION_CREDENTIALS"] = str(c.credentials_file)
            case _:
                raise CredentialError(f"claude cannot use {c.type} credentials")
        if c.isolate:
            out["CLAUDE_CONFIG_DIR"] = self._isolated_dir(label, "claude", create=env is not None)
            out["ANTHROPIC_CONFIG_DIR"] = self._isolated_dir(label, "anthropic", create=env is not None)
            return CredentialBinding(
                out, isolated=True, isolation="empty CLAUDE_CONFIG_DIR and ANTHROPIC_CONFIG_DIR: no stored login to fall back to"
            )
        return CredentialBinding(out, isolation="the user's config dirs stay visible")

    #: What `apiKeySource` in claude's init event reads for each credential type
    #: (checked against the real CLI). Types not listed are not checked.
    _API_KEY_SOURCE = {"api_key": "ANTHROPIC_API_KEY", "subscription": "none", "oauth_token": "none"}

    def attest(self, launch_result: LaunchResult, credential: CredentialBase) -> str | None:
        want = self._API_KEY_SOURCE.get(credential.type)
        got = launch_result.api_key_source
        if want is None or not got or got == want:
            return None
        return f"claude reports apiKeySource={got!r}; {credential.label} ({credential.type}) gives {want!r}"

    def _isolated_dir(self, label: str, which: str, create: bool = True) -> str:
        """An empty directory per launch label (a resumed launch keeps its label, and so
        its session), under one root this process removes at exit."""
        if self._isolation_root is None:
            self._isolation_root = Path(tempfile.mkdtemp(prefix="contraagent-claude-"))
            atexit.register(shutil.rmtree, self._isolation_root, True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label) or "launch"
        d = self._isolation_root / safe / which
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def resumable(self, launch: Launch) -> Launch:
        """Claude reports its session id; it only has to keep the session
        on disk (`--no-session-persistence` would leave nothing to resume)."""
        return dataclasses.replace(launch, persist_session=True)

    def resumed(self, launch: Launch, prior: LaunchResult, prompt: str) -> Launch | None:
        if not prior.session_id or not launch.persist_session:
            return None
        return dataclasses.replace(
            launch, prompt=prompt, resume=prior.session_id, session_id=None, preamble=None, context_files=(), prompt_via_stdin=None
        )

    def discard_session(self, launch: Launch, session_id: str) -> None:
        """Remove the transcript `resumable` made Claude keep.

        Claude writes it under its own config dir, at
        `projects/<cwd slug>/<id>.jsonl` with an optional `<id>/` beside it
        (subagent transcripts, tool results). The slug is Claude's
        encoding of the cwd, so the id is looked up across project dirs
        rather than re-derived. A caller who asked for persistence keeps
        its session.
        """
        if launch.persist_session or not _SESSION_ID_RE.match(session_id or ""):
            return
        try:
            config_dir = self.bind_credential(launch.credential, launch.model, label=launch.label).env.get("CLAUDE_CONFIG_DIR")
        except CredentialError:
            config_dir = None
        root = Path(config_dir or self._base_env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
        for hit in root.glob(f"*/{session_id}.jsonl"):
            hit.unlink(missing_ok=True)
            side = hit.with_suffix("")
            if side.is_dir():
                shutil.rmtree(side, ignore_errors=True)

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """A quota refusal on stderr is a rate limit, not an error.

        The result event normally carries `api_error_status` and
        `classify_result` reads that. This covers the launches that die before
        a result is emitted — a quota or auth failure during startup
        prints its message and exits, and without this it classifies as a
        generic error, which is not in the failover path.
        """
        if launch_result.stop not in (Stop.ERROR, Stop.NO_OUTPUT, Stop.API_ERROR):
            return
        text = stderr or ""
        if not RATE_LIMIT_RE.search(text):
            return
        launch_result.stop = Stop.RATE_LIMITED
        launch_result.ok = False
        if launch_result.rate_limit is None:
            launch_result.rate_limit = RateLimit(status="quota")

    def argv(self, launch: Launch) -> list[str]:
        """Assemble argv. Variable-length options stay last so they cannot
        swallow the next argument."""
        g = launch.limits
        a = [self.binary, "-p"]
        for plug in launch.plugin_dirs:
            a += ["--plugin-dir", plug]
        if not via_stdin(launch):
            a.append(launch.prompt)
        a += ["--model", launch.model, "--output-format", "stream-json", "--verbose"]
        if launch.fallback_model:
            a += ["--fallback-model", launch.fallback_model]
        if launch.resume:
            # `--session-id` names a new session; with `--resume` it would
            # demand `--fork-session`, and the point is to stay in this one.
            a += ["--resume", launch.resume]
        elif launch.session_id:
            a += ["--session-id", launch.session_id]
        if launch.permission_mode:
            a += ["--permission-mode", launch.permission_mode]
        if launch.permission_prompts and self._version_tuple() >= PERMISSION_PROMPTS_MIN:
            a += ["--permission-prompts", launch.permission_prompts]
        if launch.role:
            a += ["--agent", launch.role]
        if launch.effort:
            a += ["--effort", launch.effort]
        if launch.system_prompt is not None:
            a += ["--system-prompt", launch.system_prompt]
        if launch.append_system_prompt is not None:
            a += ["--append-system-prompt", launch.append_system_prompt]
        if launch.json_schema is not None:
            a += ["--json-schema", json.dumps(launch.json_schema, ensure_ascii=False)]
        if launch.settings is not None:
            a += ["--settings", launch.settings]
        a += ["--setting-sources", launch.setting_sources if launch.setting_sources is not None else DEFAULT_SETTING_SOURCES]
        if launch.mcp_config is not None:
            a += ["--mcp-config", launch.mcp_config]
        if launch.strict_mcp:
            a += ["--strict-mcp-config"]
        if not launch.persist_session:
            a += ["--no-session-persistence"]
        if launch.exclude_dynamic_sections:
            a += ["--exclude-dynamic-system-prompt-sections"]
        if g.max_turns is not None:
            a += ["--max-turns", str(g.max_turns)]
        if g.max_budget_usd is not None:
            a += ["--max-budget-usd", str(g.max_budget_usd)]
        if launch.allowed_tools:
            a += ["--allowedTools", *launch.allowed_tools]
        if g.disallowed_tools:
            a += ["--disallowedTools", *g.disallowed_tools]
        if launch.tools is not None:
            a += ["--tools", ",".join(launch.tools) if launch.tools else ""]
        return a

    def _version_tuple(self) -> tuple[int, ...]:
        """`claude --version` as a number tuple. Unparseable means (0,)
        (version-gated flags stay off)."""
        try:
            return tuple(int(x) for x in self.version().split(".")[:3])
        except ValueError:
            return (0,)

    def run(self, launch: Launch) -> LaunchResult:
        """Build argv/env, spawn, read stream-json live with limit stops,
        and return the LaunchResult. Overrides the base run loop: the stream
        reader (usage, denials, budget) has to see each line as it
        arrives, which `run_process`'s optional sink makes possible
        without duplicating its own process-management loop here."""
        started = datetime.now(UTC).isoformat(timespec="seconds")
        t0 = time.monotonic()
        argv = self.argv(launch)
        version = self.version()
        cred = launch.credential.label
        if not shutil.which(self.binary, path=self.base_path()):
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                started_at=started,
                wall_s=0.0,
                exit_code=None,
                cli_version=version,
                argv=argv,
                model=launch.model,
                credential=cred,
                stderr_tail=f"{self.binary} not on PATH",
            )
        try:
            env = self.env(launch)
        except CredentialError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                started_at=started,
                wall_s=0.0,
                exit_code=None,
                cli_version=version,
                argv=argv,
                model=launch.model,
                credential=cred,
                stderr_tail=f"credential: {exc}",
            )

        reader = StreamReader(launch.limits)
        try:
            _, stderr_tail, exit_code, killed = run_process(
                argv, env, launch, sink=lambda line: reader.feed(line.decode("utf-8", "replace"))
            )
        except LaunchError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                started_at=started,
                wall_s=time.monotonic() - t0,
                exit_code=None,
                cli_version=version,
                argv=argv,
                model=launch.model,
                credential=cred,
                stderr_tail=str(exc),
            )
        wall = time.monotonic() - t0

        res = reader.result or {}
        reader.usage.output_total = int((res.get("usage") or {}).get("output_tokens") or 0)
        text = str(res.get("result") or "")
        tool_uses = dict(reader.tool_uses)
        hollow = (res.get("num_turns") or 0) <= 1 and not tool_uses and bool(_HOLLOW_RE.search(text))
        stop = killed or classify_result(res, exit_code, reader.saw_any)
        launch_result = LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=stop,
            ok=(stop is Stop.COMPLETED and not hollow),
            started_at=started,
            wall_s=wall,
            exit_code=exit_code,
            cli_version=reader.cli_version or version,
            argv=argv,
            model=launch.model,
            credential=cred,
            api_key_source=reader.api_key_source,
            session_id=str(res.get("session_id") or reader.session_id or ""),
            num_turns=res.get("num_turns"),
            duration_api_ms=res.get("duration_api_ms"),
            result_text=text,
            structured_output=res.get("structured_output"),
            cost_usd=res.get("total_cost_usd"),
            usage=reader.usage,
            rate_limit=reader.rate_limit,
            rate_limits=list(reader.rate_limits),
            permission_denials=list(res.get("permission_denials") or []) or list(reader.denied),
            tool_uses=tool_uses,
            web_queries=list(reader.web_queries),
            hollow=hollow,
            stderr_tail=stderr_tail,
            raw_result=res,
            init_model=reader.init_model,
            init_tools=reader.init_tools,
            init_errors=reader.init_errors,
            api_retries=reader.api_retries,
            retry_errors=dict(reader.retry_errors),
            hook_errors=list(reader.hook_errors),
        )
        apply_attestation(self, launch_result, launch)
        return launch_result
