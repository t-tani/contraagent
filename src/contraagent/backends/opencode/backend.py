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

import atexit
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from contraagent.backends.base import PARENT_SESSION_ENV, OneShotBackend
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
from contraagent.backends.launch import Launch, LaunchResult, RateLimit, Stop
from contraagent.backends.opencode.wire import line_usage, parse_events, refusal_in_log
from contraagent.backends.process import Sink, via_stdin

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
#: Claude Code's tool names (a role's `tools:`, `Limits.disallowed_tools`) as opencode's permissions.
PERMISSION_OF = {
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
_RULE_RE = re.compile(r"^(\w+)(?:\((.*)\))?$")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)


def permission_rules(denied: tuple[str, ...]) -> dict:
    """`Limits.disallowed_tools` (Claude Code's patterns: `Bash(git push:*)`, `WebFetch`) as
    opencode's `permission`: a whole tool denied, or a `bash` command pattern."""
    out: dict = {}
    for rule in denied:
        m = _RULE_RE.match(rule.strip())
        if not m:
            continue
        key = PERMISSION_OF.get(m.group(1), m.group(1).lower())
        pattern = m.group(2)
        if pattern and key == "bash":
            rules = out.get(key)
            out[key] = {**(rules if isinstance(rules, dict) else {}), pattern.replace(":*", "*"): "deny"}
        else:
            out[key] = "deny"
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


def mcp_servers(mcp_config: str) -> dict:
    """A Claude Code `.mcp.json` (`mcpServers`) as opencode's `mcp`."""
    try:
        servers = json.loads(Path(mcp_config).read_text()).get("mcpServers") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for name, s in servers.items():
        if not isinstance(s, dict):
            continue
        if s.get("url"):
            out[name] = {"type": "remote", "url": s["url"], **({"headers": s["headers"]} if s.get("headers") else {})}
        elif s.get("command"):
            out[name] = {
                "type": "local",
                "command": [s["command"], *(s.get("args") or [])],
                **({"environment": s["env"]} if s.get("env") else {}),
            }
    return out


class OpencodeBackend(OneShotBackend):
    """Headless opencode: `opencode run --format json`."""

    name = "opencode"
    binary = "opencode"
    # `--variant` takes the model's own reasoning levels, which differ by provider
    # (`opencode models --verbose` lists each model's): not checked here.
    effort_levels = None
    # A light launch runs as `LIGHT_AGENT`: its prompt replaces opencode's, every tool
    # is denied, and the user's config is not read.
    light_launch = True

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None):
        super().__init__(binary, base_env)
        self._scratch: Path | None = None

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

    def config(self, launch: Launch) -> dict:
        """The opencode config of one launch (`OPENCODE_CONFIG_CONTENT`)."""
        if launch.tools == ():
            prompt = "\n\n".join(x for x in (launch.system_prompt, launch.append_system_prompt) if x)
            return {"agent": {LIGHT_AGENT: {"mode": "primary", "prompt": prompt, "permission": {"*": "deny"}}}}
        cfg: dict = {}
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
        permission: dict = {}
        allowed = role_tools(role_file) if role_file is not None else None
        if launch.tools:
            allowed = list(launch.tools)
        if allowed is not None:
            permission = {"*": "deny", **{PERMISSION_OF.get(t, t.lower()): "allow" for t in allowed}}
        permission.update(permission_rules(launch.limits.disallowed_tools))
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
            env["XDG_CONFIG_HOME"] = self._dir(launch.label, "config")
        return env

    def _dir(self, label: str, which: str) -> str:
        """A directory per launch label, under one root this process removes at exit."""
        if self._scratch is None:
            self._scratch = Path(tempfile.mkdtemp(prefix="contraagent-opencode-"))
            atexit.register(shutil.rmtree, self._scratch, True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label) or "launch"
        d = self._scratch / safe / which
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def _text_file(self, label: str, name: str, text: str) -> str:
        f = Path(self._dir(label, "instructions")) / name
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
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and opencode's own logins")
        provider = getattr(c, "provider", "")
        model_provider = model.split("/", 1)[0] if "/" in model else ""
        if model_provider and provider and provider != model_provider:
            raise CredentialError(f"model {model} is a {model_provider} model; credential {c.label} is for {provider}")

        def secret(s: Secret) -> str:
            return s.resolve(env) if env is not None else "<unresolved>"

        options: dict = {}
        entry: dict = {}
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
                options["apiKey"] = secret(c.key)
                where = "this key"
            case Gateway():
                # Checked against the real opencode with a LiteLLM gateway: `anthropic` (and any
                # provider opencode knows) keeps its own API and models at `baseURL`; another
                # name is an OpenAI-compatible provider whose model is the one the launch names.
                options["baseURL"] = c.endpoint(env)
                if c.token is not None:
                    options["apiKey"] = secret(c.token)
                if c.headers:
                    options["headers"] = dict(c.headers)
                if provider not in KNOWN_PROVIDERS:
                    name = model.split("/", 1)[1] if model_provider else ""
                    entry = {"npm": "@ai-sdk/openai-compatible", "name": provider, **({"models": {name: {}}} if name else {})}
                where = f"this gateway ({provider})"
            case _:
                raise CredentialError(f"opencode cannot use {c.type} credentials (not wired here)")
        out = {"OPENCODE_CONFIG_CONTENT": json.dumps({"provider": {provider: {**entry, "options": options}}})}
        if not c.isolate:
            return CredentialBinding(out, isolation=f"{where}; opencode's stored logins stay visible")
        out["OPENCODE_AUTH_CONTENT"] = "{}"
        return CredentialBinding(out, isolated=True, isolation=f"{where} and no stored login")

    def _stored_login(self, provider: str, env: dict[str, str]) -> dict:
        """The login opencode stores for `provider` (`auth.json` in its data directory)."""
        data = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "opencode" / "auth.json"
        try:
            login = json.loads(data.read_text()).get(provider)
        except (OSError, ValueError, AttributeError):
            login = None
        if not isinstance(login, dict):
            raise CredentialError(f"opencode stores no {provider} login (`opencode providers login`)")
        return login

    # --- running --------------------------------------------------------------

    def watch(self, launch: Launch) -> Sink | None:
        """`max_budget_usd` and `context_budget`, which opencode has no flag for: each API
        call's cost and input, as its `step_finish` reports them."""
        cap, budget = launch.limits.max_budget_usd, launch.limits.context_budget
        if cap is None and budget is None:
            return None
        spent = 0.0

        def sink(raw: bytes) -> Stop | None:
            nonlocal spent
            found = line_usage(raw, launch.model)
            if found is None:
                return None
            call, cost = found
            spent += cost or 0.0
            if budget is not None and call.context > budget:
                return Stop.CONTEXT
            return Stop.BUDGET if cap is not None and spent > cap else None

        return sink

    def watch_stderr(self, launch: Launch) -> Sink | None:
        """A quota refusal in opencode's log ends the launch `rate_limited`: opencode would
        retry it for as long as the provider asks, printing nothing meanwhile."""

        def sink(raw: bytes) -> Stop | None:
            return Stop.RATE_LIMITED if refusal_in_log(raw.decode("utf-8", "replace")) else None

        return sink

    def parse(self, launch: Launch, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        return parse_events(launch, self.name, stdout, exit_code, killed)

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """A launch ended on a refusal opencode only logged: the provider's words are its result."""
        if launch_result.stop is not Stop.RATE_LIMITED:
            return
        launch_result.rate_limit = launch_result.rate_limit or RateLimit(status="quota")
        words = next((w for line in stderr.splitlines() if (w := refusal_in_log(line))), "")
        launch_result.result_text = launch_result.result_text or words

    def catalogue(self) -> set[str] | None:
        """Model ids from `opencode models`, or None when it cannot be read."""
        if not shutil.which(self.binary, path=self.base_path()):
            return None
        try:
            proc = subprocess.run(
                [self.binary, "models"], capture_output=True, text=True, timeout=60, env={**self._base_env, "NO_COLOR": "1"}
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return {line.strip() for line in proc.stdout.splitlines() if re.fullmatch(r"[\w.-]+/\S+", line.strip())} or None


#: Providers opencode knows by name (the ones a gateway credential is likely to stand in
#: for); another provider name is set up as an OpenAI-compatible one.
KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "google", "openrouter", "opencode", "opencode-go"})


def _merged(base: dict, over: dict) -> dict:
    """`over` merged into `base`, objects key by key."""
    out = dict(base)
    for k, v in over.items():
        out[k] = _merged(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out
