"""oh-my-pi backend: `omp --plugin-dir <plug> -p`.

omp resolves agents and skills from the plugin dir, same bundle as
claude. `trace` defaults on (`--mode json`): per-tool-call trace in the
LaunchResult (tool_uses, session_id) and a real event stream
for the monitor (`wire.TraceReader`). `trace=False` falls back to plain-text
stdout (`wire.TextReader`), with no usage or cost.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path
from types import ModuleType

from contraagent._internal.backends import opencode_key, plugin_files
from contraagent._internal.backends.base import PARENT_SESSION_ENV, Backend, ModelChains, preamble_in_prompt
from contraagent._internal.backends.credentials import (
    SECRET_NAME_RE,
    SENSITIVE,
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
    model_provider,
    scrubbed,
    secret_value,
)
from contraagent._internal.backends.launch import ACCOUNT_UUID, Launch, account_digest
from contraagent._internal.backends.omp import catalogue, deny
from contraagent._internal.backends.omp import wire as omp_wire
from contraagent._internal.backends.omp.config import OmpModelChains, load_model_chains
from contraagent._internal.backends.process import via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold
from contraagent._internal.dispatch.records import QuotaReading, QuotaWindow
from contraagent._internal.platform.links import links
from contraagent._internal.runs.times import iso_of

# Runtime mapping read by omp instead of Claude Code. A procedure written
# for Claude Code stays canonical; this preamble carries the substitution
# table. Callers with their own layout pass a different preamble.
OMP_PREAMBLE = """You are running under oh-my-pi (omp), not Claude Code. Read the attached
procedure with these substitutions:
- "Agent tool" / "spawn X with subagent_type" -> the task tool with `agent: X`
- "completion notification" -> asynchronous task result delivery (auto-delivered; wait on the job when blocked)
- agent definitions live in the plugin dir's agents/; skills live in the plugin's skills/ and auto-load on their triggers
"""


def _usage_reading(argv: list[str], env: dict[str, str], provider: str, cwd: Path) -> QuotaReading | None:
    """`omp usage --json`'s one report for `provider`, as a `QuotaReading`, run in `cwd`: omp
    reads the `.env` file there at start (`omp_dotenv_files`)."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd, timeout=30, encoding="utf-8", errors="replace")
        reports = [r for r in json.loads(proc.stdout).get("reports", []) if r.get("provider") == provider]
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return None
    if len(reports) != 1:
        return None
    account: dict[str, dict] = {}  # the account's own windows, by omp's window id
    windows: dict[str, QuotaWindow] = {}  # every window, by the name a Claude Code reading gives it
    statuses: set[str] = set()
    for limit in reports[0].get("limits", []):
        scope = limit.get("scope") or {}
        if not isinstance(limit.get("amount"), dict):
            continue
        window_id = str(scope.get("windowId") or "")
        name = _OMP_WINDOWS.get(window_id, window_id)
        if scope.get("tier"):  # a model's own window: named, not the account's
            name = f"{name}_{scope['tier']}"
        else:
            account[window_id] = limit
            statuses.add(str(limit.get("status") or ""))
        fraction = limit["amount"].get("usedFraction")
        at = (limit.get("window") or {}).get("resetsAt")
        windows[name] = QuotaWindow(
            pct=round(float(fraction) * 100, 1) if isinstance(fraction, (int, float)) else None,
            resets_at=iso_of(at / 1000) if isinstance(at, (int, float)) else None,
        )
    if not account:
        return None
    meta = reports[0].get("metadata") or {}
    seen = meta.get("headersUpdatedAt") or reports[0].get("fetchedAt")  # when a request reported it
    return QuotaReading.from_windows(
        windows,
        status="allowed" if statuses <= {"ok"} else ",".join(sorted(statuses - {"ok"})),
        observed_at=iso_of(seen / 1000) if isinstance(seen, (int, float)) else None,
        account=account_digest(ACCOUNT_UUID, str(meta.get("accountId") or "")),
    )


#: omp's window ids, as Claude Code's readings name the windows.
_OMP_WINDOWS = {"5h": "five_hour", "7d": "seven_day"}


#: A plugin's stop hooks for omp, in Claude Code's `hooks/hooks.json` format, relative to the
#: plugin (`contraagent plugin render` writes it): the plugin's extension, `omp/index.ts`,
#: runs them at omp's `session_stop`.
HOOKS_FILE = "omp/hooks.json"

#: What a task agent may see beyond its plugin and call file: nothing (`isolation/config.yml`).
ISOLATION = Path(__file__).resolve().parent / "isolation"


def isolation_args() -> list[str]:
    """omp's discovery of project and user files (AGENTS.md, CLAUDE.md, skills, rules,
    hooks, MCP servers, ...) turned off, all but the `--plugin-dir` plugin."""
    return ["--config", str(ISOLATION / "config.yml")]


#: The omp profile isolated launches run in: it holds no stored login.
ISOLATED_PROFILE = "contraagent-isolated"
#: Providers for which omp uses nothing but what the launch gives it, in a profile with no
#: stored logins (checked against the real CLI: an anthropic or openai-codex login stays in its
#: own profile; litellm without a key in the environment is not contacted at all).
PROFILE_ISOLATED_PROVIDERS = frozenset({"anthropic", "openai-codex", "litellm"})
#: A subscription's provider (whose login it is) to the omp provider of that login's models:
#: a ChatGPT login (`provider = "openai"`, as for codex) is omp's `openai-codex`, its models
#: `openai-codex/<model>`; omp's `openai` is the API platform, reached with an API key.
LOGIN_PROVIDERS = {"openai": "openai-codex"}
#: Providers whose key variable is not `<PROVIDER>_API_KEY` (from `omp --help`).
_KEY_ENV = {
    "opencode-zen": "OPENCODE_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
    "google": "GEMINI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "azure-openai": "AZURE_OPENAI_API_KEY",
}


def provider_base_url_env(provider: str) -> str:
    """The variable omp reads a provider's endpoint from (`LITELLM_BASE_URL`, `OPENAI_BASE_URL`, ...)."""
    return provider.upper().replace("-", "_").replace(".", "_") + "_BASE_URL"


def provider_key_env(provider: str) -> str:
    """The variable omp reads a provider's API key from."""
    return key_var(provider, _KEY_ENV)


def omp_dotenv_files(env: dict[str, str], args: tuple[str, ...], cwd: Path) -> list[Path]:
    """The `.env` files omp loads at start, in the order it reads them; each one sets only the
    variables the launch's environment leaves unset or empty (omp's `pi-utils/src/env.ts`):
    the one of `cwd`, the directory omp runs in, then its agent directory's and its config
    root's (those of the profile `--profile` names), then `~/.env`."""
    home = Path(env.get("HOME") or Path.home())
    root = home / (env.get("PI_CONFIG_DIR") or ".omp")
    profile = args[args.index("--profile") + 1] if "--profile" in args and args.index("--profile") + 1 < len(args) else ""
    if profile:
        root = root / "profiles" / profile
    agent = Path(env["PI_CODING_AGENT_DIR"]).expanduser() if env.get("PI_CODING_AGENT_DIR") and not profile else root / "agent"
    return [Path(cwd) / ".env", agent / ".env", root / ".env", home / ".env"]


def provider_vars(provider: str) -> frozenset[str]:
    """The variables omp reads `provider`'s key and endpoint from (`omp --help`)."""
    own = {provider_key_env(provider), provider_base_url_env(provider)}
    if provider == "anthropic":
        own |= {"ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_CUSTOM_HEADERS"}
    return frozenset(own)


def dotenv_credentials(env: dict[str, str], args: tuple[str, ...], cwd: Path, names: frozenset[str] | None = None) -> dict[str, Path]:
    """The variables omp, run in `cwd`, would take from a `.env` file because the launch's
    environment leaves them unset, each with the file it comes from: `names`, or by default
    every credential variable (those `scrubbed` removes)."""
    found: dict[str, Path] = {}
    for f in omp_dotenv_files(env, args, cwd):
        for name, value in opencode_key.dotenv(f).items():
            wanted = name in names if names is not None else (name in SENSITIVE or SECRET_NAME_RE.search(name))
            if wanted and value and not env.get(name) and name not in found:
                found[name] = f
    return found


def plugin_extension_args(plugin_dirs) -> list[str]:
    """`-e <file>` for every extension a plugin directory declares.

    omp 18.8's `--plugin-dir` loads a directory's agents and skills but not the
    extensions its `package.json` lists under `omp.extensions`; without an explicit
    `-e` a hook the bundle declares is silently never installed (checked by running
    omp with a probe extension: `--plugin-dir` alone never loaded it). So the backend
    passes them itself.
    """
    return [a for plug in plugin_dirs for f in plugin_files.extensions(plug, "omp") for a in ("-e", str(f))]


def deny_args(launch: Launch) -> list[str]:
    """`-e` of contraagent's own extension that denies the task's `disallowed_tools` (`deny`),
    for a launch that denies a tool and has tools at all; its rules are in the environment
    (`deny.env`)."""
    return deny.args(launch.limits.disallowed_tools) if launch.tools != () else []


def session_args(launch: Launch) -> list[str]:
    """Where omp keeps this launch's session, and which one to continue.

    A known id resumes exactly that session. Without one (text mode
    prints none) `--continue` takes the latest under `session_dir`, which
    is unambiguous because the directory belongs to this launch alone.
    """
    a: list[str] = []
    if launch.session_dir is not None:
        Path(launch.session_dir).mkdir(parents=True, exist_ok=True)
        # A saved session is otherwise titled by a model call — spend on
        # the run's own quota for a label nobody reads.
        a += ["--session-dir", str(launch.session_dir), "--no-title"]
    if launch.resume:
        a += ["--resume", launch.resume]
    elif launch.resume is not None and launch.session_dir is not None:
        a += ["--continue"]
    return a


def prompt_args(backend: Backend, launch: Launch) -> list[str]:
    """The system prompt and the tools: `Launch.system_prompt` replaces omp's own
    (`--system-prompt`), `Launch.tools == ()` turns every tool off (`--no-tools`, and
    `--no-lsp` for the language-server tools, which `--no-tools` leaves), a tuple of
    names keeps only those (`--tools`).

    The system prompt and `append_system_prompt` are written to files of the launch's
    scratch directory (`Backend._text_file`), and the flags name those files: omp reads a
    value with no line break as the path of a file and takes the file's text, and keeps
    the value as the text itself only when no such file can be read (omp 18.9.1,
    `--system-prompt` and `--append-system-prompt` in its `main.ts`)."""
    a: list[str] = []
    if launch.system_prompt is not None:
        a.append(f"--system-prompt={backend._text_file(launch, 'system-prompt.md', launch.system_prompt)}")
    if launch.append_system_prompt is not None:
        a.append(f"--append-system-prompt={backend._text_file(launch, 'append-system-prompt.md', launch.append_system_prompt)}")
    if launch.tools == ():
        a += ["--no-tools", "--no-lsp"]
    elif launch.tools is not None:
        a.append(f"--tools={','.join(launch.tools)}")
    return a


class OmpBackend(Backend):
    """Headless oh-my-pi: `omp -p` with text output.

    Every launch runs with contraagent's own config overlay (`--config`): each discovery
    provider is off but `claude-plugins`, which loads the task's `--plugin-dir`, so omp
    reads no AGENTS.md, CLAUDE.md, `.omp/`, `.claude/` or other tools' context files,
    skills, rules, hooks, tools or MCP servers; the overlay's directory, which holds no
    plugins, is the agent's `CLAUDE_CONFIG_DIR`, so the user's installed Claude Code
    plugins are not loaded either. omp takes MCP servers from the plugin's `.mcp.json`
    only: a launch with servers of its own (`Launch.mcp_config`, another file) loads a
    copy of the plugin whose `.mcp.json` holds them.

    No text of the task is on the command line: `Launch.system_prompt` and
    `append_system_prompt` are files of the launch's scratch directory (`prompt_args`),
    the attached files are named by path (`@<file>`), and `Launch.preamble` is the head of
    the prompt, which goes over stdin past `STDIN_THRESHOLD` (`via_stdin`). omp sends the
    attached files and the prompt as one first message. `OmpRpcBackend` sends the
    preamble, the attached files and the prompt as one message over stdin.

    A plugin's extension (`omp/index.ts`, `-e` from its `package.json`) runs its tool
    hooks and, at omp's `session_stop`, the stop hooks of `omp/hooks.json`: one that exits
    2 continues the session with what it said (`stop_hooks_file`). `Limits.max_turns` (its
    turns, `turn_start` to `turn_end`) and `Limits.max_budget_usd` are counted from the
    event stream (`watched_limits`).

    `Limits.disallowed_tools` loads contraagent's own extension (`-e .../omp/deny.ts`),
    with its rules as JSON in `CONTRAAGENT_OMP_DENY`. It takes a tool denied whole out of
    the tools the model is offered and blocks a call a rule denies before it runs. Claude
    Code's names become omp's tools:

        Bash               bash; a pattern holds each command of the line, the parts
                           between `&&`, `||`, `;`, `|` and `&`: `git push:*` is `git push`
                           alone or followed by more words, `npm * build` any words for
                           the `*`, anything else the command exactly
        Read               read; a pattern holds the path read
        Write              write; a pattern holds the path written
        Edit, MultiEdit    edit and ast_edit; a pattern holds the path of edit and write,
                           and denies ast_edit whole (it edits every file its glob finds)
        Glob               glob and find
        Grep               grep and ast_grep
        WebSearch          web_search
        Agent, Task        task
        TodoWrite          todo
        WebFetch           read of an http(s) URL; `WebFetch(domain:example.com)`: of that
                           host or one under it
        Skill              read of a `skill://` URL; `Skill(name)`: of that skill
        mcp__s__t          omp's name of that MCP tool (`mcp__s_t`); `mcp__s`, `mcp__s__*`:
                           every tool of server `s`
        another name       omp's tool of that name, in lower case (`Eval` is `eval`)

    A path pattern is Claude Code's: `//` starts an absolute path, `~/` one in the home
    directory, anything else is from the launch's directory; `*` matches within one part
    of a path, `**` across parts, and `secrets/**` the directory and all under it. A
    pattern of another tool (`Glob(src/**)`, `Agent(explore)`, `WebFetch(https://...)`)
    cannot be held: the route is refused (`tool_deny_problem`).
    """

    name = "omp"
    binary = "omp"
    effort_levels: tuple[str, ...] | None = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "auto")
    thinking: str = "medium"
    trace: bool = True

    # retry.fallbackChains, on by default — but configured in omp's own
    # config rather than on argv, so the caller reports what is set
    # instead of writing it per launch.
    native_model_chain = True
    drivable_model_chain = False
    # omp has no named-agent mechanism of its own: the task's role file
    # (`agents/<role>.md`) rides along as an attached context file instead.
    needs_inline_role_file = True
    # `--no-tools`, `--system-prompt` (`prompt_args`); the isolation config already
    # turns off every settings, skill and MCP discovery, and a light launch loads no plugin.
    light_launch = True
    wire: ModuleType | None = omp_wire
    signals: Signals = omp_wire.SIGNALS
    # A line of text mode's stream is its plain-text narration.
    plaintext_stream = True
    # omp's CLI has no cost cap and no turn cap: the cost of each API call, as its
    # `message_end` reports it, summed, and its `turn_start` events counted (trace mode;
    # text mode reports neither).
    watched_limits: frozenset[str] = frozenset({"max_budget_usd", "max_turns"})
    # The plugin's Stop hooks, in Claude Code's format, which the plugin's extension
    # (`omp/index.ts`) runs at omp's `session_stop`: one that exits 2 continues the session.
    stop_hooks_file: str | None = HOOKS_FILE

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """omp denies tools in an extension of contraagent's own (`deny`): whole tools, and
        patterns of a command (`Bash`), a path (`Read`, `Write`, `Edit`), a domain
        (`WebFetch(domain:...)`) or a skill (`Skill`); a pattern of another tool it cannot."""
        return deny.problem(denied)

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None, thinking: str = "medium", trace: bool = True):
        super().__init__(binary, base_env)
        self.thinking = thinking
        self.trace = trace
        self._chains: dict[Path, OmpModelChains] = {}  # by the directory omp runs in
        self._accounts: dict[tuple[str, str, Path], str] = {}  # (credential, provider, directory) -> its account
        self._catalogues: dict[Path, set[str] | None] = {}  # by the directory omp runs in
        self._catalogues_lock = threading.Lock()

    def fold(self, launch: Launch) -> EventFold:
        """Stdout is the json event stream (trace) or the answer (text)."""
        return omp_wire.TraceReader() if self.trace else omp_wire.TextReader()

    def usage_reading(self, launch: Launch) -> QuotaReading | None:
        """The 5-hour and weekly usage of the account `launch` runs as, as Claude Code reports it:
        what the account's latest request reported in its response headers, which omp keeps
        and `omp usage --json` prints (no request of its own). None for a model with no
        provider prefix, an account omp reports no usage for, or several accounts of that
        provider (which one a launch uses is omp's choice). Asked in `Launch.cwd`, whose `.env`
        omp reads."""
        provider = model_provider(launch.model)
        if not provider:
            return None
        cwd = Path(launch.cwd)
        try:
            binding = self._bind_credential_in(cwd, launch.credential, launch.model, env=self._base_env, label=launch.label)
            env = child_env(self._base_env, launch.credential, binding, {})
        except CredentialError:
            return None
        reading = _usage_reading([self.binary, *binding.args, "usage", "--json", "--provider", provider], env, provider, cwd)
        if reading is not None and opencode_key.is_opencode(provider):
            # omp names no account for an OpenCode key: the key itself does.
            reading.account = reading.account or opencode_key.account_of_key(self._opencode_key(binding, env, cwd))
        return reading

    def account(self, credential: Credential, model: str = "") -> str:
        """The account omp's usage report names for the model's provider (`metadata.accountId`,
        from `omp usage --json`, which reads what omp kept of the account's last response).
        Asked once per credential, provider and directory in this process, here in this
        process's current directory; for a launch, contraagent asks in the directory it runs
        in (`Launch.cwd`), whose `.env` omp reads. '' when omp reports none."""
        return self._account_in(Path.cwd(), credential, model)

    def _account_in(self, cwd: Path, credential: Credential, model: str = "") -> str:
        provider = model_provider(model)
        if not provider:
            return ""
        where = Path(cwd)
        if opencode_key.is_opencode(provider):
            # Read locally, as opencode and pi read it: the key omp would send (`_opencode_key`).
            try:
                binding = self._bind_credential_in(where, credential, model, env=self._base_env)
                env = child_env(self._base_env, credential, binding, {})
            except CredentialError:
                return ""
            return opencode_key.account_of_key(self._opencode_key(binding, env, where))
        key = (credential.label, provider, where.resolve())
        if key not in self._accounts:
            launch = Launch(prompt="", label=f"account-{credential.label}", model=model, credential=credential, cwd=where)
            reading = self.usage_reading(launch)
            self._accounts[key] = reading.account if reading is not None else ""
        return self._accounts[key]

    def _opencode_key(self, binding: CredentialBinding, env: dict[str, str], cwd: Path) -> str:
        """The OpenCode key omp, run in `cwd`, sends: `OPENCODE_API_KEY` of the launch's
        environment, else the first of omp's `.env` files that sets it (`omp_dotenv_files`).
        A login stored in omp's own profile is not read here ('' then)."""
        files = omp_dotenv_files(env, binding.args, cwd)
        return opencode_key.env_key(env) or next(
            (v for f in files if (v := opencode_key.dotenv(f).get(opencode_key.KEY_VAR, "").strip())),
            "",
        )

    def model_chains(self, cwd: Path | None = None) -> ModelChains:
        """omp's `retry` settings as omp reports them in `cwd` (`load_model_chains`), asked once
        per directory.

        `cwd` is the directory omp is launched in (`Launch.cwd`): omp reads the project's
        `<cwd>/.omp/config.yml` there, so two directories can give two answers. None: this
        process's current directory. The preflight asks for the run's working directory
        (`Pipeline(cwd=)`).
        """
        where = (Path(cwd) if cwd is not None else Path.cwd()).resolve()
        if where not in self._chains:
            self._chains[where] = load_model_chains(self._base_env, where, self.binary)
        return self._chains[where]

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's as it is for `ambient`; for any
        other credential, every other one removed and the chosen one applied last.
        Raises `CredentialError` (LAUNCH_FAILED) when it cannot bind."""
        binding = self._bind_credential_in(Path(launch.cwd), launch.credential, launch.model, env=self._base_env, label=launch.label)
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=(*PARENT_SESSION_ENV, deny.DENY_ENV))
        rules = deny.env(launch.limits.disallowed_tools, Path(launch.cwd)) if deny_args(launch) else {}
        return {**env, "CLAUDE_CONFIG_DIR": str(ISOLATION), **rules}

    # --- credentials -------------------------------------------------------
    #
    # omp picks the provider from the model (`provider/model`) and that provider's
    # credential from, in order, an env var (`<PROVIDER>_API_KEY`; for Anthropic
    # `ANTHROPIC_OAUTH_TOKEN` outranks `ANTHROPIC_API_KEY`, per `omp --help`) and the
    # logins stored in its profile (`--profile`, `~/.omp/profiles/<name>`). Every
    # credential variable is removed first. Isolation runs the launch in a profile
    # with no stored logins (`ISOLATED_PROFILE`). Checked against the real CLI: an
    # Anthropic login does not reach another profile, but an opencode-go login
    # does (omp keeps it outside its profiles), so isolation is claimed only for
    # the providers in `PROFILE_ISOLATED_PROVIDERS`. omp also fills an unset variable from
    # the `.env` file of the directory it runs in (`omp_dotenv_files`), so a launch is bound
    # in its own directory (`Launch.cwd`).

    def bind_credential(
        self, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """As bound for a launch in this process's current directory, whose `.env` omp reads;
        for a launch, contraagent binds in the directory it runs in (`Launch.cwd`)."""
        return self._bind_credential_in(Path.cwd(), credential, model, env=env, label=label)

    def _bind_credential_in(
        self, cwd: Path, credential: Credential, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and omp's default profile")
        where = Path(cwd)
        provider = getattr(c, "provider", "")
        if isinstance(c, Subscription):
            provider = LOGIN_PROVIDERS.get(provider, provider)
        check_provider(c, model, provider, named=getattr(c, "provider", ""))

        match c:
            case Subscription():
                args = ("--profile", c.profile) if c.profile else ()
                isolation = f"the {provider} login in omp profile {c.profile or 'default'}"
                # A key omp fills in from a .env file outranks the stored login.
                back = dotenv_credentials(scrubbed(env or self._base_env), args, where, provider_vars(provider)) if c.isolate else {}
                if back:
                    isolation += "; omp reads " + ", ".join(f"{n} from {f}" for n, f in sorted(back.items()))
                return CredentialBinding(args=args, isolated=c.isolate and not back, isolation=isolation)
            case ApiKey():
                out = {provider_key_env(provider): secret_value(c.key, env)}
            case Gateway():
                # omp reads `<PROVIDER>_BASE_URL` beside the key (checked against the real CLI for
                # litellm: the key goes as `Authorization: Bearer`, models are discovered from the
                # gateway's /model/info and /models).
                out = {provider_base_url_env(provider): c.endpoint(env)}
                if c.token is not None:
                    out[provider_key_env(provider)] = secret_value(c.token, env)
                if c.headers:
                    if provider != "anthropic":
                        raise CredentialError(f"omp sends custom headers only to an anthropic endpoint, not {provider}")
                    out["ANTHROPIC_CUSTOM_HEADERS"] = c.header_lines()
            case OAuthToken() if provider == "anthropic":
                out = {"ANTHROPIC_OAUTH_TOKEN": secret_value(c.token, env)}
            case _:
                raise CredentialError(
                    f"omp cannot use {c.type} credentials" + (f" for {provider}" if provider else "") + " (not wired here)"
                )
        if not c.isolate:
            return CredentialBinding(out, isolation="omp's default profile stays visible")
        verified = provider in PROFILE_ISOLATED_PROVIDERS
        args = ("--profile", ISOLATED_PROFILE)
        isolation = (
            f"omp profile {ISOLATED_PROFILE}: no stored logins"
            if verified
            else f"omp profile {ISOLATED_PROFILE}, but omp may still use a {provider} login it keeps outside its profiles"
        )
        # omp fills an unset variable from its `.env` files: a key there comes back.
        # Names only, so it holds for a check (`env` None) too: no secret is read.
        back = dotenv_credentials({**scrubbed(env or self._base_env), **out}, args, where, provider_vars(provider))
        if back:
            verified = False
            isolation += "; omp reads " + ", ".join(f"{n} from {f}" for n, f in sorted(back.items()))
        return CredentialBinding(out, args=args, isolated=verified, isolation=isolation)

    def read_models(self) -> dict[str, int | None] | None:
        """Model ids and their context windows from `omp models --json` (`catalogue`), or
        None when it cannot be read. omp lists a window for each model (`contextWindow`): exact.

        A local registry read, no network: it took ~1s here. Worth it because the
        failure it removes is a model typo that otherwise costs one launch each and
        reads as a generic error, and omp's `-p` stream names the model but not its
        window. None (not an empty dict) on any failure, so a missing binary or a
        changed format defers to the live probe instead of reporting every model as
        unknown.
        """
        out = self.run_catalogue(*catalogue.ARGS)
        return (catalogue.parse_models(out) or None) if out is not None else None

    def _catalogue_in(self, cwd: Path) -> set[str] | None:
        """omp lists the models of each provider it has a key for, and it reads keys from
        the `.env` file of the directory it runs in (`omp_dotenv_files`): the list is read
        in `cwd`, once per directory."""
        where = Path(cwd).resolve()
        with self._catalogues_lock:
            if where not in self._catalogues:
                out = self._run_catalogue_in(where, *catalogue.ARGS)
                listed = (catalogue.parse_models(out) or None) if out is not None else None
                self._catalogues[where] = set(listed) if listed is not None else None
            return self._catalogues[where]

    def _loaded_plugin_dirs(self, launch: Launch) -> tuple[str, ...]:
        """The plugin directories omp is given (`--plugin-dir`). omp takes MCP servers from a
        plugin's `.mcp.json` alone, so a launch whose `mcp_config` is another file gets, in
        place of its first plugin, a copy of it in a scratch directory: a link to each of
        that plugin's files and folders, and `mcp_config` as its `.mcp.json` (with no plugin,
        a plugin of that file alone)."""
        dirs = tuple(launch.plugin_dirs)
        if not launch.mcp_config or launch.tools == ():
            return dirs
        given = Path(launch.mcp_config).resolve()
        if dirs and (Path(dirs[0]) / ".mcp.json").resolve() == given:
            return dirs
        mirror = self.scratch(launch.label, "plugin")
        shutil.rmtree(mirror, ignore_errors=True)  # a launch before it, of the same task
        mirror.mkdir(parents=True)
        if dirs:
            for entry in Path(dirs[0]).iterdir():
                if entry.name != ".mcp.json":
                    links.link(entry.resolve(), mirror / entry.name)
        else:
            (mirror / ".claude-plugin").mkdir()
            (mirror / ".claude-plugin" / "plugin.json").write_text(
                json.dumps({"name": "mcp", "version": "0.0.0"}), encoding="utf-8", newline="\n"
            )
        shutil.copyfile(given, mirror / ".mcp.json")
        return (str(mirror), *dirs[1:])

    def _as_launched(self, launch: Launch) -> Launch:
        """The preamble at the head of the prompt (`preamble_in_prompt`): on omp's command
        line it would be a message of its own, which omp sends before the prompt's."""
        return preamble_in_prompt(super()._as_launched(launch))

    def argv(self, launch: Launch) -> list[str]:
        launch = self._as_launched(launch)
        a = [self.binary]
        for plug in self._loaded_plugin_dirs(launch):
            a += ["--plugin-dir", plug]
        a += plugin_extension_args(launch.plugin_dirs)
        a += deny_args(launch)
        # `effort` is the neutral name for reasoning depth; omp spells it
        # `--thinking` and Claude Code spells it `--effort`. The launch
        # value wins so a per-task effort reaches the CLI — before this,
        # `Launch.effort` was read only by the claude backend and an
        # --omp-only run silently ignored it. `self.thinking` stays as the
        # constructor default for a launch that sets no effort.
        a += ["-p", "--thinking", launch.effort or self.thinking, "--approval-mode", "yolo", *isolation_args()]
        a += prompt_args(self, launch)
        if self.trace:
            a += ["--mode", "json"]
        if launch.model:
            a += ["--model", launch.model]
        a += self._bind_credential_in(Path(launch.cwd), launch.credential, launch.model, label=launch.label).args
        a += session_args(launch)
        a += [f"@{f}" for f in launch.context_files]
        # A prompt over the per-argument limit cannot go on argv at all:
        # execve fails with E2BIG before omp ever starts, which the caller
        # sees as a 0-second launch_failed with no stderr. via_stdin says
        # the prompt is already being fed on the pipe, so it must not also
        # ride along as an argument. Claude Code has always done this.
        if not via_stdin(launch):
            a.append(launch.prompt)
        return a
