"""Claude Code backend: `claude -p` with stream-json output.

Each launch can load one static plugin dir (`--plugin-dir`), so the
invocation sees exactly one agent, its skill bundle, its command prompt,
and its settings — never the working tree's top-level .claude/ directory.

It holds the argv surface and the credentials; the stream reader is `wire.py`,
the account of a login `login.py`. Env isolation (PARENT_SESSION_ENV + DEFAULT_ENV) and the
provider identity (`Credential`) are shared with the omp backend.
Plugin isolation rides on top: `--plugin-dir`, with `--agent` naming the
task's role in that plugin.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from types import ModuleType

from contraagent._internal.backends.base import PARENT_SESSION_ENV, Backend, ResumeById
from contraagent._internal.backends.claude import wire as claude_wire
from contraagent._internal.backends.claude.login import login_account
from contraagent._internal.backends.credentials import (
    Ambient,
    ApiKey,
    Bedrock,
    Credential,
    CredentialBinding,
    CredentialError,
    Gateway,
    OAuthToken,
    Subscription,
    Vertex,
    WorkloadIdentity,
    child_env,
    secret_value,
)
from contraagent._internal.backends.launch import ACCOUNT_SECRET, Launch, LaunchResult, account_digest
from contraagent._internal.backends.process import via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold

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

# Claude session ids are UUIDs. Anything else is refused before it is
# joined into a path: the id comes from the child's own stream, and a
# deletion keyed on it must not be steerable outside the session store.
_SESSION_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{0,63}$")


class ClaudeBackend(ResumeById, Backend):
    """Headless Claude Code: `claude -p` with stream-json output.

    `Launch.system_prompt` and `Launch.append_system_prompt` reach it as files of the
    launch's scratch directory (`--system-prompt-file`, `--append-system-prompt-file`), and
    a prompt past `STDIN_THRESHOLD` (`via_stdin`) over stdin, so no text of the task makes its
    command line longer than the operating system takes."""

    name = "claude"
    stop_hooks_file: str | None = "hooks/hooks.json"
    binary = "claude"
    effort_levels: tuple[str, ...] | None = ("low", "medium", "high", "xhigh", "max")
    # `--fallback-model` takes a comma-separated list and tries each in
    # order when the default is overloaded. Verified on 2.1.285.
    native_model_chain = True
    drivable_model_chain = True
    # `--tools ""`, `--system-prompt`, and the `--setting-sources ""` and
    # `--strict-mcp-config` every launch already gets.
    light_launch = True
    wire: ModuleType | None = claude_wire
    signals: Signals = claude_wire.SIGNALS
    # `--max-turns` and `--max-budget-usd` are its own; one call's input is watched.
    watched_limits: frozenset[str] = frozenset({"context_budget"})

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """Claude Code denies tools and their patterns itself (`--disallowedTools`)."""
        return None

    # A resumed session's `total_cost_usd` covers the session so far (measured on 2.1.296:
    # $0.00128, then $0.00212 for a second launch of one session).
    cost_is_session_total = True

    def __init__(self, binary: str = "claude", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)

    def fold(self, launch: Launch) -> EventFold:
        return claude_wire.StreamReader(launch.limits)

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
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and Claude Code's own login")
        provider = getattr(c, "provider", "anthropic")
        if provider != "anthropic" and not isinstance(c, Gateway):  # a gateway speaks the Anthropic API to claude
            raise CredentialError(f"claude cannot use a {provider} {c.type} credential")

        match c:
            case Subscription():
                out = {"CLAUDE_CONFIG_DIR": str(c.config_dir)} if c.config_dir else {}
                if c.isolate:
                    out["ANTHROPIC_CONFIG_DIR"] = self._isolated_dir(label, "anthropic", create=env is not None)
                where = c.config_dir or "~/.claude"
                return CredentialBinding(out, isolated=c.isolate, isolation=f"the /login in {where}; no other credential variable set")
            case ApiKey():
                out = {"ANTHROPIC_API_KEY": secret_value(c.key, env)}
            case OAuthToken():
                out = {"CLAUDE_CODE_OAUTH_TOKEN": secret_value(c.token, env)}
            case Gateway():
                # Checked against the real CLI: requests go to <base_url>/v1/messages, the token as
                # `Authorization: Bearer` (ANTHROPIC_AUTH_TOKEN) or `x-api-key` (ANTHROPIC_API_KEY),
                # and ANTHROPIC_CUSTOM_HEADERS as extra headers.
                out = {"ANTHROPIC_BASE_URL": c.endpoint(env)}
                if c.token is not None:
                    out["ANTHROPIC_AUTH_TOKEN" if c.auth == "bearer" else "ANTHROPIC_API_KEY"] = secret_value(c.token, env)
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
                    out["AWS_BEARER_TOKEN_BEDROCK"] = secret_value(c.bearer, env)
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

    #: The variables Claude Code authenticates with, in the order it prefers them: an
    #: ambient launch bills the first one set, else the /login of its config directory.
    _AUTH_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")

    def account(self, credential: Credential, model: str = "") -> str:
        """The account of a /login (its `oauthAccount.accountUuid` in the config directory's
        `.claude.json`), or of the token or key a credential holds; '' for Bedrock, Vertex,
        workload identity, or a secret that cannot be read."""
        c = credential
        try:
            match c:
                case Ambient():
                    held = next((self._base_env[k] for k in self._AUTH_ENV if self._base_env.get(k)), "")
                    if held:
                        return account_digest(ACCOUNT_SECRET, held)
                    return login_account(self._base_env.get("CLAUDE_CONFIG_DIR"))
                case Subscription():
                    return login_account(str(c.config_dir) if c.config_dir else self._base_env.get("CLAUDE_CONFIG_DIR"))
                case ApiKey():
                    return account_digest(ACCOUNT_SECRET, c.key.resolve(self._base_env))
                case OAuthToken():
                    return account_digest(ACCOUNT_SECRET, c.token.resolve(self._base_env))
                case Gateway() if c.token is not None:
                    return account_digest(ACCOUNT_SECRET, c.token.resolve(self._base_env))
        except CredentialError:
            return ""
        return ""

    #: What `apiKeySource` in claude's init event reads for each credential type
    #: (checked against the real CLI). Types not listed are not checked.
    _API_KEY_SOURCE = {"api_key": "ANTHROPIC_API_KEY", "subscription": "none", "oauth_token": "none"}

    def attest(self, launch_result: LaunchResult, credential: Credential) -> str | None:
        want = self._API_KEY_SOURCE.get(credential.type)
        got = launch_result.api_key_source
        if want is None or not got or got == want:
            return None
        return f"claude reports apiKeySource={got!r}; {credential.label} ({credential.type}) gives {want!r}"

    def _isolated_dir(self, label: str, which: str, create: bool = True) -> str:
        """An empty directory per launch label (a resumed launch keeps its label, and so
        its session), removed when this process exits."""
        return str(self.scratch(label, which, create=create))

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
        # Each text in a file of the launch's own (`_text_file`): one past 131072 bytes would
        # keep the process from starting. Claude Code reads it as UTF-8.
        if launch.system_prompt is not None:
            a += ["--system-prompt-file", str(self._text_file(launch, "system-prompt.md", launch.system_prompt))]
        if launch.append_system_prompt is not None:
            a += ["--append-system-prompt-file", str(self._text_file(launch, "append-system-prompt.md", launch.append_system_prompt))]
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
