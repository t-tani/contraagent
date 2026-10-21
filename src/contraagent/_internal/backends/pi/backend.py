"""pi backend: `pi --mode json -p`, one process per launch.

pi (pi.dev) is the coding agent omp was forked from; its `--mode json` wire is the
same agent events (`wire.py`). A launch runs with an agent directory of contraagent's
own (`agent_dir.py`) and with every discovery turned off by flag
(`ISOLATION_ARGS`), so the agent sees only what the task gives it: its plugins'
skills (`--skill`), hook extensions (`-e`) and MCP servers (`mcp.ts`), its role file
attached to the prompt, and the call file.

Credentials: pi picks the provider from the model (`provider/model`) and, for that
provider, a login in `auth.json`, then the provider's key variable. `ambient` and a
`subscription` link the logins of a pi agent directory (the user's own, or the
subscription's `config_dir`); an `api_key` or an `oauth_token` is the only key the
child sees, with no logins at all; a `gateway` is a provider of its own in the
directory's `models.json`, spoken to over the OpenAI chat-completions API.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from contraagent._internal.backends import opencode_key, plugin_files
from contraagent._internal.backends.base import DENY_POINTER, PARENT_SESSION_ENV, Backend, preamble_in_prompt
from contraagent._internal.backends.credentials import (
    Ambient,
    ApiKey,
    Credential,
    CredentialBinding,
    CredentialError,
    Gateway,
    OAuthToken,
    Subscription,
    check_provider,
    child_env,
    key_var,
    model_id,
    model_provider,
    secret_value,
)
from contraagent._internal.backends.launch import Launch
from contraagent._internal.backends.opencode_key import OpencodeKeyAccount
from contraagent._internal.backends.pi import agent_dir, catalogue
from contraagent._internal.backends.pi import wire as pi_wire
from contraagent._internal.backends.pi.login import pi_login
from contraagent._internal.backends.process import via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold

#: Every discovery pi does at startup turned off: extensions (the built-in ones too, MCP
#: among them), skills, prompt templates, themes, `AGENTS.md`/`CLAUDE.md`, and a project's
#: `.pi/` files. Explicit `--skill` and `-e` paths still load (checked against pi 1.2.0).
ISOLATION_ARGS = ("--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve")


#: The extension that registers a plugin's MCP servers (`.mcp.json`, named by
#: `MCP_CONFIG_ENV`), loaded with pi's built-in MCP support.
MCP_EXTENSION = Path(__file__).resolve().parent / "mcp.ts"
MCP_CONFIG_ENV = "CONTRAAGENT_PI_MCP_CONFIG"
#: Added to every launch: no request to pi.dev for the latest version.
DEFAULT_ENV = {"PI_SKIP_VERSION_CHECK": "1"}
#: pi's own variables for its directories, which the launch sets itself.
PI_DIR_ENV = ("PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR")
#: Providers whose key variable is not `<PROVIDER>_API_KEY` (from `pi --help`).
_KEY_ENV = {
    "opencode": "OPENCODE_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
    "google": "GEMINI_API_KEY",
    "github-copilot": "COPILOT_GITHUB_TOKEN",
    "huggingface": "HF_TOKEN",
    "azure": "AZURE_OPENAI_API_KEY",
    "vercel-ai-gateway": "AI_GATEWAY_API_KEY",
}


def provider_key_env(provider: str) -> str:
    """The variable pi reads a provider's API key from."""
    return key_var(provider, _KEY_ENV)


def plugin_args(plugin_dirs) -> list[str]:
    """`--skill <plugin>/skills` for every plugin with skills, and `-e <file>` for every
    extension its `package.json` lists under `pi.extensions` (the hooks `contraagent
    plugin render` writes for pi)."""
    args: list[str] = []
    for plug in plugin_dirs:
        root = Path(plug)
        if (root / "skills").is_dir():
            args += ["--skill", str(root / "skills")]
        for f in plugin_files.extensions(root, "pi"):
            args += ["-e", str(f)]
    return args


def session_args(launch: Launch) -> list[str]:
    """Where pi keeps this launch's session, and which one it continues.

    Ephemeral (`--no-session`) unless the run may resume it: then it is saved under the
    launch's own `session_dir`, and a resume names its id (`--session`), which pi's
    session header gives, or takes the latest there (`--continue`)."""
    if launch.session_dir is None:
        return ["--no-session"]
    Path(launch.session_dir).mkdir(parents=True, exist_ok=True)
    a = ["--session-dir", str(launch.session_dir)]
    if launch.resume:
        a += ["--session", launch.resume]
    elif launch.resume is not None:
        a += ["--continue"]
    return a


def prompt_args(backend: Backend, launch: Launch) -> list[str]:
    """The system prompt and the tools: `Launch.system_prompt` replaces pi's own,
    `Launch.tools == ()` turns every tool off (`--no-tools`), a tuple of names keeps only
    those (`--tools`). pi has no `--flag=value` form; it reads the argument after a
    value flag as its value (checked against pi 1.2.0).

    The system prompt and `append_system_prompt` are written to files of the launch's
    scratch directory (`Backend._text_file`), and the flags name those files: pi reads a
    value that names a file as that file's text, in UTF-8 (`resolvePromptInput` of its
    `core/resource-loader.js`, pi 1.2.0)."""
    a: list[str] = []
    if launch.system_prompt is not None:
        a += ["--system-prompt", str(backend._text_file(launch, "system-prompt.md", launch.system_prompt))]
    if launch.append_system_prompt is not None:
        a += ["--append-system-prompt", str(backend._text_file(launch, "append-system-prompt.md", launch.append_system_prompt))]
    if launch.tools == ():
        a.append("--no-tools")
    elif launch.tools is not None:
        a += ["--tools", ",".join(launch.tools)]
    denied = [_PI_TOOLS.get(rule, rule.lower()) for rule in launch.limits.disallowed_tools]
    if denied and launch.tools != ():
        a += ["--exclude-tools", ",".join(dict.fromkeys(denied))]
    return a


#: Claude Code's tool names (`Limits.disallowed_tools`) as pi's (`pi --help`).
_PI_TOOLS = {
    "Read": "read",
    "Bash": "bash",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Write": "write",
    "Grep": "grep",
    "Glob": "find",
    "LS": "ls",
}


class PiBackend(OpencodeKeyAccount, Backend):
    """Headless pi: `pi --mode json -p`.

    Every launch turns pi's discovery off by flag (`--no-extensions`, `--no-skills`,
    `--no-prompt-templates`, `--no-themes`, `--no-context-files`) and runs with an agent
    directory of contraagent's own (`PI_CODING_AGENT_DIR`, under `~/.cache/contraagent/pi/`):
    its settings (no project trust, no cache warming, no telemetry) and links to the
    user's logins (`auth.json`), custom providers (`models.json`), model catalogue and
    `fd` and `rg`, and nothing else of theirs. Launches made alike share one directory,
    so they refresh one OAuth login once.

    No text of the task is on the command line: `Launch.system_prompt` and
    `append_system_prompt` are files of the launch's scratch directory (`prompt_args`),
    the attached files are named by path (`@<file>`), and `Launch.preamble` is the head of
    the prompt, which goes over stdin past `STDIN_THRESHOLD` characters. pi sends the
    attached files and the prompt as one first message.
    """

    name = "pi"
    binary = "pi"
    effort_levels: tuple[str, ...] | None = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
    thinking: str = "medium"
    # pi has no named-agent mechanism: the task's role file rides along as an attached file.
    needs_inline_role_file = True
    # `--no-tools`, `--system-prompt` (`prompt_args`); the agent directory and
    # `ISOLATION_ARGS` already keep every setting, skill and MCP server out.
    light_launch = True
    wire: ModuleType | None = pi_wire
    signals: Signals = pi_wire.SIGNALS
    # pi's CLI has no cost cap: the cost of each API call, as its `message_end` reports it, summed.
    watched_limits: frozenset[str] = frozenset({"max_budget_usd"})

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """pi denies whole tools (`--exclude-tools`), not a pattern of what a tool is given."""
        patterned = [rule for rule in denied if "(" in rule]
        return f"pi cannot hold {', '.join(patterned)}: it denies whole tools only {DENY_POINTER}" if patterned else None

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None, thinking: str = "medium", agent_dirs: Path | None = None):
        super().__init__(binary, base_env)
        self.thinking = thinking
        #: Where the agent directories are made (`agent_dir.default_root`).
        self.agent_dirs: Path = agent_dirs or agent_dir.default_root(self._base_env)

    def fold(self, launch: Launch) -> EventFold:
        """Stdout is the `--mode json` event stream."""
        return pi_wire.PiTraceReader()

    # --- the account and its usage ---------------------------------------------

    def billed_key(self, credential: Credential, model: str) -> tuple[str, str]:
        """The OpenCode key a launch of `model` as `credential` bills and its endpoint ('' for
        opencode.ai's), as pi picks it: the binding's key variable, else pi's own login, else
        (`ambient`) `OPENCODE_API_KEY`. ('', '') for another provider."""
        provider = model_provider(model) or getattr(credential, "provider", "")
        if not opencode_key.is_opencode(provider):
            return "", ""
        if isinstance(credential, Gateway):
            token = credential.token.resolve(self._base_env) if credential.token is not None else ""
            return token, credential.endpoint(self._base_env)
        if isinstance(credential, ApiKey):
            return credential.key.resolve(self._base_env), ""
        source = agent_dir.default_source(self._base_env)
        home = Path(credential.config_dir).expanduser() if isinstance(credential, Subscription) and credential.config_dir else source
        login = pi_login(home, provider) or {}
        stored = login.get("key")
        key = stored if isinstance(stored, str) else ""
        if not key and isinstance(credential, Subscription):
            key = opencode_key.stored_key(provider, self._base_env)
        if not key and isinstance(credential, Ambient):
            key = opencode_key.env_key(self._base_env)
        return key, ""

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): for `ambient` the parent's, for any other
        credential every other one removed; in both, pi's agent directory is the launch's
        own (`agent_dir`). Raises `CredentialError` (LAUNCH_FAILED) when it cannot bind."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        mcp = {MCP_CONFIG_ENV: str(launch.mcp_config)} if launch.mcp_config and launch.tools != () else {}
        return child_env(
            self._base_env, launch.credential, binding, {**launch.env, **mcp}, drop=PARENT_SESSION_ENV + PI_DIR_ENV, defaults=DEFAULT_ENV
        )

    # --- credentials -------------------------------------------------------

    def bind_credential(
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """With `env` None a check only: nothing is read and no directory is made."""
        c = credential
        source = agent_dir.default_source(self._base_env if env is None else env)
        if isinstance(c, Ambient):
            return self._binding(
                {},
                env,
                source,
                logins=True,
                link_models=True,
                isolated=False,
                isolation=f"ambient: the logins and custom providers of pi agent directory {source}",
            )
        provider = getattr(c, "provider", "")
        check_provider(c, model, provider)

        match c:
            case Subscription():
                home = Path(c.config_dir).expanduser() if c.config_dir else source
                if opencode_key.is_opencode(provider) and env is not None and pi_login(home, provider) is None:
                    # pi holds no OpenCode login here: opencode's own, as the key pi reads
                    # after its logins. One login serves pi, opencode and omp alike.
                    key = opencode_key.stored_key(provider, env)
                    if key:
                        return self._binding(
                            {opencode_key.KEY_VAR: key},
                            env,
                            home,
                            logins=(home / "auth.json").is_file(),
                            isolated=c.isolate,
                            isolation=f"opencode's stored {provider} login (pi agent directory {home} holds none)",
                        )
                if env is not None and not (home / "auth.json").is_file():
                    raise CredentialError(f"no pi logins in {home} (auth.json): run pi and /login {provider} there")
                return self._binding(
                    {},
                    env,
                    home,
                    logins=True,
                    isolated=c.isolate,
                    isolation=f"the {provider} login in pi agent directory {home}",
                )
            case ApiKey():
                out = {provider_key_env(provider): secret_value(c.key, env)}
            case OAuthToken() if provider == "anthropic":
                out = {"ANTHROPIC_OAUTH_TOKEN": secret_value(c.token, env)}
            case Gateway():
                key_var = provider_key_env(provider)
                entry: dict = {"baseUrl": c.endpoint(env), "api": "openai-completions", "apiKey": f"${key_var}" if c.token else "none"}
                if c.headers:
                    entry["headers"] = dict(c.headers)
                if model_provider(model) == provider:
                    entry["models"] = [{"id": model_id(model)}]
                out = {key_var: secret_value(c.token, env)} if c.token is not None else {}
                return self._binding(
                    out,
                    env,
                    source,
                    models={"providers": {provider: entry}},
                    isolated=c.isolate,
                    isolation=f"pi provider {provider} at the gateway, with no logins",
                )
            case _:
                for_provider = f" for {provider}" if provider else ""
                raise CredentialError(f"pi cannot use {c.type} credentials{for_provider} (not wired here)")
        return self._binding(out, env, source, isolated=c.isolate, isolation=f"{', '.join(out)} only, with no pi logins")

    def _binding(
        self,
        out: dict[str, str],
        env: dict[str, str] | None,
        source: Path,
        *,
        logins: bool = False,
        models: dict | None = None,
        link_models: bool = False,
        isolated: bool,
        isolation: str,
    ) -> CredentialBinding:
        """The binding, with the agent directory made when this is not a check (`env` set)."""
        if env is not None:
            made = agent_dir.make(self.agent_dirs, source, logins=logins, models=models, link_models=link_models)
            out = {**out, "PI_CODING_AGENT_DIR": str(made)}
        return CredentialBinding(out, isolated=isolated, isolation=isolation)

    def read_models(self) -> dict[str, int | None] | None:
        """Model ids from `pi --list-models`, or None when it cannot be read. pi lists the
        models of the providers it has a credential for, read from the user's own agent
        directory. Each window is the one that directory's model files list
        (`agent_dir.windows`, exact; the list's own `context` column is rounded), None
        for a model they do not list."""
        out = self.run_catalogue(*catalogue.ARGS, env=DEFAULT_ENV)
        listed = catalogue.parse_models(out) if out is not None else None
        if not listed:
            return None
        known = agent_dir.windows(agent_dir.default_source(self._base_env))
        return {model: known.get(model) for model in sorted(listed)}

    def _as_launched(self, launch: Launch) -> Launch:
        """The preamble at the head of the prompt (`preamble_in_prompt`): on pi's command line
        it would be a message of its own, which pi sends as a turn before the prompt's."""
        return preamble_in_prompt(super()._as_launched(launch))

    def argv(self, launch: Launch) -> list[str]:
        launch = self._as_launched(launch)
        # `effort` is the neutral name for reasoning depth; pi spells it `--thinking`.
        a = [self.binary, "--mode", "json", "-p", "--thinking", launch.effort or self.thinking, *ISOLATION_ARGS]
        a += plugin_args(launch.plugin_dirs)
        if launch.mcp_config and launch.tools != ():
            a += ["-e", "builtin:mcp", "-e", str(MCP_EXTENSION)]
        a += prompt_args(self, launch)
        if launch.model:
            a += ["--model", launch.model]
        a += session_args(launch)
        # Everything after `--` is the prompt, so a prompt starting with `-` is not read as
        # an option.
        a.append("--")
        a += [f"@{f}" for f in launch.context_files]
        # Past `STDIN_THRESHOLD` the prompt goes on stdin, which pi puts before the attached
        # files in the first message (`via_stdin`).
        if not via_stdin(launch):
            a.append(launch.prompt)
        return a
