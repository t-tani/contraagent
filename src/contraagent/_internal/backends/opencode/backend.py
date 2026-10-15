"""opencode backend: `opencode run --format json`.

opencode takes everything a launch sets beyond the prompt and the model as config:
one JSON document in `OPENCODE_CONFIG_CONTENT`, merged over the user's own config
last. A launch's config holds its role (`instructions`: the role file is added to
opencode's own system prompt, which opencode's free models require), its plugins'
skills (`skills.paths`), MCP servers (`mcp`) and hooks (`plugin`), what it may not do
(`permission`), and its turn cap (`steps`).

A light launch runs as an agent of its own (`--agent`), whose prompt replaces
opencode's and whose permission denies every tool; it reads no user config either
(`XDG_CONFIG_HOME` is an empty directory: with no tool, nothing else reads it).

Where opencode would read the project's files or the user's Claude Code files
(`AGENTS.md`, `opencode.json`, `.opencode/`, `~/.claude/`), it is told not to
(`DEFAULT_ENV`). Its sessions stay out of the user's own database: a launch that may
be resumed keeps its session in its `session_dir`, any other in memory.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, ClassVar

from contraagent._internal.backends import opencode_key, plugin_files
from contraagent._internal.backends.base import PARENT_SESSION_ENV, Backend
from contraagent._internal.backends.credentials import (
    Ambient,
    ApiKey,
    Credential,
    CredentialBinding,
    CredentialError,
    Gateway,
    Subscription,
    check_provider,
    child_env,
    model_id,
    model_provider,
    secret_value,
)
from contraagent._internal.backends.launch import Launch, LaunchResult, Stop
from contraagent._internal.backends.opencode import catalogue
from contraagent._internal.backends.opencode import wire as opencode_wire
from contraagent._internal.backends.opencode_key import OpencodeKeyAccount
from contraagent._internal.backends.process import Sink, via_stdin
from contraagent._internal.backends.refusal import Signals, quota_refusal
from contraagent._internal.backends.wire import EventFold

#: Added to every launch: no project config, `AGENTS.md` or `.opencode/` directory, none of
#: the user's Claude Code files (`~/.claude/CLAUDE.md`, its skills), no skills under
#: `~/.agents/`, no self-update. Checked against opencode 1.19.0 with a project holding each.
DEFAULT_ENV = {
    "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
    "OPENCODE_DISABLE_AUTOUPDATE": "1",
}
#: The agent a light launch runs as.
LIGHT_AGENT = "contraagent-light"
#: Where a plugin's hooks are, rendered for opencode (`contraagent plugin render`).
HOOKS_FILE = "opencode/index.js"
_RULE_RE = re.compile(r"^(\w+)(?:\((.*)\))?$")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)


#: The opencode permissions whose rules take a pattern of what the tool is given: a
#: command (`bash`), a path from the worktree (`read`, `edit`), a URL (`webfetch`), a
#: skill's name (`skill`).
PATTERNED = ("bash", "read", "edit", "webfetch", "skill")


def worktree(cwd: Path) -> Path:
    """The directory opencode matches a `read` or `edit` pattern from: the git worktree
    `cwd` is in, or `/` outside one."""
    here = cwd.resolve()
    for d in (here, *here.parents):
        if (d / ".git").exists():
            return d
    return Path("/")


def _patterns(key: str, pattern: str, cwd: Path) -> list[str]:
    """Claude Code's pattern for a tool (`git push:*`, `secrets/**`, `domain:example.com`)
    as opencode's for permission `key`. A path is Claude Code's: `//` absolute, `~/` from
    home, anything else from `cwd`; opencode's `*` crosses `/`, so `src/*.md` denies
    deeper files too."""
    if key == "bash":
        return [pattern.replace(":*", "*")]
    if key in ("read", "edit"):
        if pattern.startswith("//"):
            path = Path(pattern[1:])
        elif pattern.startswith("~/"):
            path = Path(pattern).expanduser()
        else:
            path = cwd.resolve() / pattern.lstrip("/").removeprefix("./")
        return [Path(os.path.relpath(path, worktree(cwd))).as_posix()]
    if key == "webfetch" and pattern.startswith("domain:"):
        host = pattern.removeprefix("domain:")
        return [f"{scheme}://{host}{tail}" for scheme in ("https", "http") for tail in ("", "/*")]
    return [pattern]


def permission_rules(denied: tuple[str, ...], permission: dict[str, Any], cwd: Path) -> dict[str, Any]:
    """`permission` (opencode's, from a role's `tools:`) narrowed by `Limits.disallowed_tools`
    (Claude Code's names and patterns: `Bash(git push:*)`, `Read(secrets/**)`, `WebFetch`):
    a whole tool denied, or a pattern after the rule the tool had (`{"*": "allow", "git
    push*": "deny"}`; opencode takes the last rule that matches). A pattern of a tool
    already denied adds nothing."""
    out = dict(permission)
    for rule in denied:
        m = _RULE_RE.match(rule.strip())
        if not m:
            continue
        key = OpencodeBackend.PERMISSION_OF.get(m.group(1), m.group(1).lower())
        pattern = m.group(2)
        had = out.get(key, out.get("*", "allow"))
        if not pattern:
            out[key] = "deny"
        elif had != "deny":
            rules = had if isinstance(had, dict) else {"*": had}
            out[key] = {**rules, **dict.fromkeys(_patterns(key, pattern, cwd), "deny")}
    return out


def role_tools(role_file: Path) -> list[str] | None:
    """The tools a role's frontmatter allows (`tools: Read, Grep`), or None when it names none."""
    try:
        m = _FRONTMATTER_RE.match(role_file.read_text())
    except OSError:
        return None
    if not m:
        return None
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "tools" and value.strip():
            return [t.strip() for t in value.strip().strip("[]").split(",") if t.strip()]
    return None


def mcp_servers(mcp_config: str) -> dict[str, Any]:
    """A Claude Code `.mcp.json` (`mcpServers`) as opencode's `mcp`."""
    out = {}
    for name, s in plugin_files.mcp_servers(mcp_config).items():
        if s.get("url"):
            out[name] = {"type": "remote", "url": s["url"], **({"headers": s["headers"]} if s.get("headers") else {})}
        elif s.get("command"):
            out[name] = {
                "type": "local",
                "command": [s["command"], *(s.get("args") or [])],
                **({"environment": s["env"]} if s.get("env") else {}),
            }
    return out


class OpencodeBackend(OpencodeKeyAccount, Backend):
    """Headless opencode: `opencode run --format json`.

    Every launch sets `OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_DISABLE_CLAUDE_CODE`,
    `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_AUTOUPDATE` to `1`: no
    project config, AGENTS.md or `.opencode/`, none of the user's Claude Code files
    (`~/.claude/CLAUDE.md`, its skills), no skills under `~/.agents/`, no self-update. The
    task's role, skills, MCP servers and hooks are given as config
    (`OPENCODE_CONFIG_CONTENT`), and a session stays out of the user's database.
    """

    name = "opencode"
    binary = "opencode"
    # `--variant` takes the model's own reasoning levels, which differ by provider
    # (`opencode models --verbose` lists each model's): not checked here.
    effort_levels: tuple[str, ...] | None = None
    # A light launch runs as `LIGHT_AGENT`: its prompt replaces opencode's, every tool
    # is denied, and the user's config is not read.
    light_launch = True
    wire: ModuleType | None = opencode_wire
    signals: Signals = opencode_wire.SIGNALS
    # opencode has no flag for a cost cap or one call's input: each API call's cost and
    # input, as its `step_finish` reports them.
    watched_limits: frozenset[str] = frozenset({"max_budget_usd", "context_budget"})
    # `opencode models --verbose` lists every provider's models with their details.
    catalogue_timeout_s: float = 60.0
    # Claude Code's tool names (a role's `tools:`, `Limits.disallowed_tools`) as opencode's permissions.
    PERMISSION_OF: ClassVar[Mapping[str, str]] = MappingProxyType(
        {
            "Bash": "bash",
            "Read": "read",
            "Write": "edit",
            "Edit": "edit",
            "MultiEdit": "edit",
            "NotebookEdit": "edit",
            "Glob": "glob",
            "Grep": "grep",
            "LS": "list",
            "WebFetch": "webfetch",
            "WebSearch": "websearch",
            "Skill": "skill",
            "Agent": "task",
            "Task": "task",
            "TodoWrite": "todowrite",
        }
    )

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """opencode denies tools by its permissions (`permission_rules`): a whole tool, or a
        pattern of a command, a path, a URL's domain or a skill (`PATTERNED`), not of another tool."""
        rules = [(rule, _RULE_RE.match(rule.strip())) for rule in denied]
        odd = [
            rule
            for rule, m in rules
            if m
            and m.group(2)
            and (
                (key := cls.PERMISSION_OF.get(m.group(1), m.group(1).lower())) not in PATTERNED
                or (key == "webfetch" and not m.group(2).startswith("domain:"))
            )
        ]
        return f"opencode denies these tools whole only, not {', '.join(odd)}" if odd else None

    # --- argv and config ------------------------------------------------------

    def argv(self, launch: Launch) -> list[str]:
        a = [self.binary, "run", "--format", "json", "--print-logs", "--log-level", "ERROR", "--auto"]
        # A session is otherwise titled by a model call, on the run's own quota.
        a.append(f"--title={launch.label or 'contraagent'}")
        if launch.model:
            a.append(f"--model={launch.model}")
        if launch.effort:
            a.append(f"--variant={launch.effort}")
        if launch.tools == ():
            a.append(f"--agent={LIGHT_AGENT}")
        if launch.resume:
            a.append(f"--session={launch.resume}")
        a += [f"--file={f}" for f in launch.context_files]
        message = "\n\n".join(x for x in (launch.preamble, None if via_stdin(launch) else launch.prompt) if x)
        if message:
            # One element after `--`: a prompt may start with `-`.
            a += ["--", message]
        return a

    def config(self, launch: Launch) -> dict[str, Any]:
        """The opencode config of one launch (`OPENCODE_CONFIG_CONTENT`)."""
        if launch.tools == ():
            prompt = "\n\n".join(x for x in (launch.system_prompt, launch.append_system_prompt) if x)
            return {"agent": {LIGHT_AGENT: {"mode": "primary", "prompt": prompt, "permission": {"*": "deny"}}}}
        cfg: dict[str, Any] = {}
        instructions = []
        own = Path(launch.plugin_dirs[0]) if launch.plugin_dirs else None
        role_file = own / "agents" / f"{launch.role}.md" if own is not None and launch.role else None
        if role_file is not None and role_file.is_file():
            instructions.append(str(role_file))
        if launch.system_prompt or launch.append_system_prompt:
            instructions.append(
                self._text_file(launch.label, "system.md", "\n\n".join(x for x in (launch.system_prompt, launch.append_system_prompt) if x))
            )
        if instructions:
            cfg["instructions"] = instructions
        skills = [str(Path(p) / "skills") for p in launch.plugin_dirs if (Path(p) / "skills").is_dir()]
        if skills:
            cfg["skills"] = {"paths": skills}
        hooks = [f"file://{Path(p).resolve() / HOOKS_FILE}" for p in launch.plugin_dirs if (Path(p) / HOOKS_FILE).is_file()]
        if hooks:
            cfg["plugin"] = hooks
        if launch.mcp_config:
            servers = mcp_servers(launch.mcp_config) if Path(launch.mcp_config).is_file() else {}
            if servers:
                cfg["mcp"] = servers
        permission: dict[str, Any] = {}
        allowed = role_tools(role_file) if role_file is not None else None
        if launch.tools:
            allowed = list(launch.tools)
        if allowed is not None:
            permission = {"*": "deny", **{self.PERMISSION_OF.get(t, t.lower()): "allow" for t in allowed}}
        permission = permission_rules(launch.limits.disallowed_tools, permission, Path(launch.cwd))
        if permission:
            cfg["permission"] = permission
        if launch.limits.max_turns is not None:
            cfg["agent"] = {"build": {"steps": launch.limits.max_turns}}
        return cfg

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's minus the parent-session
        variables, `DEFAULT_ENV`, `launch.env`; for any credential but `ambient`, every
        other credential removed and the chosen one applied last. The launch's config
        goes over the credential's (`OPENCODE_CONFIG_CONTENT`). Raises `CredentialError`
        (LAUNCH_FAILED) when it cannot bind."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV, defaults=DEFAULT_ENV)
        cfg = _merged(json.loads(binding.env.get("OPENCODE_CONFIG_CONTENT") or "{}"), self.config(launch))
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(cfg, ensure_ascii=False)
        # opencode takes its directory from `PWD`, not from the process's own: the parent's
        # would put the session in the directory contraagent was started from.
        env["PWD"] = str(Path(launch.cwd).resolve())
        if launch.session_dir is not None:
            Path(launch.session_dir).mkdir(parents=True, exist_ok=True)
            env["OPENCODE_DB"] = str(Path(launch.session_dir).resolve() / "opencode.db")
        else:
            env["OPENCODE_DB"] = ":memory:"
        if launch.tools == ():
            env["XDG_CONFIG_HOME"] = str(self.scratch(launch.label, "config"))
        return env

    def _text_file(self, label: str, name: str, text: str) -> str:
        f = self.scratch(label, "instructions") / name
        f.write_text(text)
        return str(f)

    # --- credentials ----------------------------------------------------------
    #
    # opencode picks the provider from the model (`provider/model`) and that provider's key
    # from, highest first, `provider.<id>.options.apiKey` in its config, its stored logins
    # (`auth.json` in its data directory, or `OPENCODE_AUTH_CONTENT`, which replaces that
    # file), and the provider's environment variable. Every credential variable is removed
    # first. The chosen key goes into the launch's config, which is merged over the user's
    # last, so a key in the user's config cannot replace it; isolation also gives the
    # launch no stored login (`OPENCODE_AUTH_CONTENT` empty).

    def bind_credential(
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and opencode's own logins")
        provider = getattr(c, "provider", "")
        check_provider(c, model, provider)

        options: dict[str, Any] = {}
        entry: dict[str, Any] = {}
        match c:
            case Subscription():
                login = self._stored_login(provider, env) if env is not None else {"type": "api", "key": "<unresolved>"}
                if login.get("type") != "api":
                    # An OAuth login: opencode refreshes it and writes the whole store back, so
                    # the store cannot be narrowed to it for a launch.
                    return CredentialBinding(isolation=f"opencode's stored logins, all of them ({provider} is an OAuth login)")
                options["apiKey"] = str(login.get("key") or "")
                where = f"the stored {provider} login"
            case ApiKey():
                options["apiKey"] = secret_value(c.key, env)
                where = "this key"
            case Gateway():
                # Checked against the real opencode with a LiteLLM gateway: `anthropic` (and any
                # provider opencode knows) keeps its own API and models at `baseURL`; another
                # name is an OpenAI-compatible provider whose model is the one the launch names.
                options["baseURL"] = c.endpoint(env)
                if c.token is not None:
                    options["apiKey"] = secret_value(c.token, env)
                if c.headers:
                    options["headers"] = dict(c.headers)
                if provider not in KNOWN_PROVIDERS:
                    name = model_id(model) if model_provider(model) else ""
                    entry = {"npm": "@ai-sdk/openai-compatible", "name": provider, **({"models": {name: {}}} if name else {})}
                where = f"this gateway ({provider})"
            case _:
                raise CredentialError(f"opencode cannot use {c.type} credentials (not wired here)")
        out = {"OPENCODE_CONFIG_CONTENT": json.dumps({"provider": {provider: {**entry, "options": options}}})}
        if not c.isolate:
            return CredentialBinding(out, isolation=f"{where}; opencode's stored logins stay visible")
        out["OPENCODE_AUTH_CONTENT"] = "{}"
        return CredentialBinding(out, isolated=True, isolation=f"{where} and no stored login")

    def _stored_login(self, provider: str, env: dict[str, str]) -> dict[str, Any]:
        """The login opencode stores for `provider` (`auth.json` in its data directory)."""
        login = opencode_key.stored_login(provider, env)
        if login is None:
            raise CredentialError(f"opencode stores no {provider} login (`opencode providers login`)")
        return login

    # --- the account and its usage ---------------------------------------------

    def billed_key(self, credential: Credential, model: str) -> tuple[str, str]:
        """The OpenCode key a launch of `model` as `credential` bills, and the endpoint it
        goes to ('' for opencode.ai's), as opencode picks it: the credential's own key, else
        (`ambient`, a `subscription`) the stored login, then `OPENCODE_API_KEY`. ('', '')
        for another provider, or a key opencode would take from the user's config file."""
        provider = model_provider(model) or getattr(credential, "provider", "")
        if not opencode_key.is_opencode(provider):
            return "", ""
        env = self._base_env
        match credential:
            case ApiKey():
                return credential.key.resolve(env), ""
            case Gateway():
                return (credential.token.resolve(env) if credential.token is not None else ""), credential.endpoint(env)
            case Ambient() | Subscription():
                key = opencode_key.stored_key(provider, env)
                if not key and isinstance(credential, Ambient):
                    key = opencode_key.env_key(env)
                return key, ""
        return "", ""

    # --- running --------------------------------------------------------------

    def fold(self, launch: Launch) -> EventFold:
        return opencode_wire.EventReader(launch.model)

    def watch_stderr(self, launch: Launch) -> Sink | None:
        """A quota refusal in opencode's log ends the launch `rate_limited`: opencode would
        retry it for as long as the provider asks, printing nothing meanwhile."""

        def sink(raw: bytes) -> Stop | None:
            return Stop.RATE_LIMITED if opencode_wire.refusal_in_log(raw.decode("utf-8", "replace")) else None

        return sink

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """A launch ended on a refusal opencode only logged: the provider's words are its
        result, and the cool-off they state its quota refusal's."""
        if launch_result.stop is not Stop.RATE_LIMITED:
            return
        words = next((w for line in stderr.splitlines() if (w := opencode_wire.refusal_in_log(line))), "")
        if launch_result.quota_refusal is None or launch_result.quota_refusal.retry_after_s is None:
            launch_result.quota_refusal = quota_refusal(words)
        launch_result.result_text = launch_result.result_text or words

    def read_models(self) -> dict[str, int | None] | None:
        """Model ids and their context windows from `opencode models --verbose`
        (`catalogue`), or None when it cannot be read. opencode lists a window for each
        model (`limit.context`): exact."""
        out = self.run_catalogue(*catalogue.ARGS)
        return (catalogue.parse_models(out) or None) if out is not None else None


#: Providers opencode knows by name (the ones a gateway credential is likely to stand in
#: for); another provider name is set up as an OpenAI-compatible one.
KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "google", "openrouter", "opencode", "opencode-go"})


def _merged(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """`over` merged into `base`, objects key by key."""
    out = dict(base)
    for k, v in over.items():
        out[k] = _merged(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out
