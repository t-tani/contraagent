"""oh-my-pi backend: `omp --plugin-dir <plug> -p`.

omp resolves agents and skills from the plugin dir, same bundle as
claude. `trace` defaults on (`--mode json`): per-tool-call trace in the
LaunchResult (tool_uses, session_id) and a real event stream
for the monitor (`wire.TraceReader`). `trace=False` falls back to plain-text
stdout (`wire.TextReader`), with no usage or cost.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import ModuleType

from contraagent._internal.backends import opencode_key, plugin_files
from contraagent._internal.backends.base import PARENT_SESSION_ENV, Backend, ModelChains
from contraagent._internal.backends.credentials import (
    SECRET_NAME_RE,
    SENSITIVE,
    Ambient,
    ApiKey,
    CredentialBase,
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
from contraagent._internal.backends.omp import catalogue
from contraagent._internal.backends.omp import wire as omp_wire
from contraagent._internal.backends.omp.config import OmpModelChains, load_model_chains
from contraagent._internal.backends.process import via_stdin
from contraagent._internal.backends.refusal import Signals
from contraagent._internal.backends.wire import EventFold
from contraagent._internal.dispatch.records import QuotaReading, QuotaWindow
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


def _usage_reading(argv: list[str], env: dict[str, str], provider: str) -> QuotaReading | None:
    """`omp usage --json`'s one report for `provider`, as a `QuotaReading`."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)
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


def omp_dotenv_files(env: dict[str, str], args: tuple[str, ...] = (), cwd: Path | None = None) -> list[Path]:
    """The `.env` files omp loads at start, in the order it reads them; each one sets only the
    variables the launch's environment leaves unset or empty (omp's `pi-utils/src/env.ts`):
    the working directory's, then its agent directory's and its config root's (those of the
    profile `--profile` names), then `~/.env`."""
    home = Path(env.get("HOME") or Path.home())
    root = home / (env.get("PI_CONFIG_DIR") or ".omp")
    profile = args[args.index("--profile") + 1] if "--profile" in args and args.index("--profile") + 1 < len(args) else ""
    if profile:
        root = root / "profiles" / profile
    agent = Path(env["PI_CODING_AGENT_DIR"]).expanduser() if env.get("PI_CODING_AGENT_DIR") and not profile else root / "agent"
    return [(cwd or Path.cwd()) / ".env", agent / ".env", root / ".env", home / ".env"]


def provider_vars(provider: str) -> frozenset[str]:
    """The variables omp reads `provider`'s key and endpoint from (`omp --help`)."""
    own = {provider_key_env(provider), provider_base_url_env(provider)}
    if provider == "anthropic":
        own |= {"ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_CUSTOM_HEADERS"}
    return frozenset(own)


def dotenv_credentials(env: dict[str, str], args: tuple[str, ...] = (), names: frozenset[str] | None = None) -> dict[str, Path]:
    """The variables omp would take from a `.env` file because the launch's environment
    leaves them unset, each with the file it comes from: `names`, or by default every
    credential variable (those `scrubbed` removes)."""
    found: dict[str, Path] = {}
    for f in omp_dotenv_files(env, args):
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


def prompt_args(launch: Launch) -> list[str]:
    """The system prompt and the tools: `Launch.system_prompt` replaces omp's own
    (`--system-prompt`), `Launch.tools == ()` turns every tool off (`--no-tools`, and
    `--no-lsp` for the language-server tools, which `--no-tools` leaves), a tuple of
    names keeps only those (`--tools`). Values ride in one element: a role's text may
    start with `-`."""
    a: list[str] = []
    if launch.system_prompt is not None:
        a.append(f"--system-prompt={launch.system_prompt}")
    if launch.append_system_prompt is not None:
        a.append(f"--append-system-prompt={launch.append_system_prompt}")
    if launch.tools == ():
        a += ["--no-tools", "--no-lsp"]
    elif launch.tools is not None:
        a.append(f"--tools={','.join(launch.tools)}")
    return a


class OmpBackend(Backend):
    """Headless oh-my-pi: `omp -p` with text output."""

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
    # omp's CLI has no cost cap: the cost of each API call, as its `message_end` reports it,
    # summed (trace mode; text mode reports none).
    watched_limits: frozenset[str] = frozenset({"max_budget_usd"})

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None, thinking: str = "medium", trace: bool = True):
        super().__init__(binary, base_env)
        self.thinking = thinking
        self.trace = trace
        self._chains: OmpModelChains | None = None
        self._accounts: dict[tuple[str, str], str] = {}  # (credential, provider) -> its account

    def fold(self, launch: Launch) -> EventFold:
        """Stdout is the json event stream (trace) or the answer (text)."""
        return omp_wire.TraceReader() if self.trace else omp_wire.TextReader()

    def usage_reading(self, launch: Launch) -> QuotaReading | None:
        """The 5-hour and weekly usage of the account `launch` runs as, as Claude Code reports it:
        what the account's latest request reported in its response headers, which omp keeps
        and `omp usage --json` prints (no request of its own). None for a model with no
        provider prefix, an account omp reports no usage for, or several accounts of that
        provider (which one a launch uses is omp's choice)."""
        provider = model_provider(launch.model)
        if not provider:
            return None
        try:
            binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
            env = child_env(self._base_env, launch.credential, binding, {})
        except CredentialError:
            return None
        reading = _usage_reading([self.binary, *binding.args, "usage", "--json", "--provider", provider], env, provider)
        if reading is not None and opencode_key.is_opencode(provider):
            # omp names no account for an OpenCode key: the key itself does.
            reading.account = reading.account or opencode_key.account_of_key(self._opencode_key(binding, env))
        return reading

    def account(self, credential: CredentialBase, model: str = "") -> str:
        """The account omp's usage report names for the model's provider (`metadata.accountId`,
        from `omp usage --json`, which reads what omp kept of the account's last response).
        Asked once per credential and provider in this process; '' when omp reports none."""
        provider = model_provider(model)
        if not provider:
            return ""
        if opencode_key.is_opencode(provider):
            # Read locally, as opencode and pi read it: the key omp would send (`_opencode_key`).
            try:
                binding = self.bind_credential(credential, model, env=self._base_env)
                env = child_env(self._base_env, credential, binding, {})
            except CredentialError:
                return ""
            return opencode_key.account_of_key(self._opencode_key(binding, env))
        key = (credential.label, provider)
        if key not in self._accounts:
            reading = self.usage_reading(Launch(prompt="", label=f"account-{credential.label}", model=model, credential=credential))
            self._accounts[key] = reading.account if reading is not None else ""
        return self._accounts[key]

    def _opencode_key(self, binding: CredentialBinding, env: dict[str, str]) -> str:
        """The OpenCode key omp sends: `OPENCODE_API_KEY` of the launch's environment, else the
        first of omp's `.env` files that sets it (`omp_dotenv_files`). A login stored in omp's
        own profile is not read here ('' then)."""
        return opencode_key.env_key(env) or next(
            (v for f in omp_dotenv_files(env, binding.args) if (v := opencode_key.dotenv(f).get(opencode_key.KEY_VAR, "").strip())),
            "",
        )

    def model_chains(self, cwd: Path | None = None) -> ModelChains:
        """omp's configured `retry:` block, read once per backend.

        `cwd` is the directory omp will be launched in, which is what
        decides the project file — not the reader's own directory. The
        driver passes its repo root, matching `Launch.cwd`.
        """
        if self._chains is None:
            self._chains = load_model_chains(self._base_env, cwd or Path.cwd())
        return self._chains

    def env(self, launch: Launch) -> dict[str, str]:
        """The child environment (`child_env`): the parent's as it is for `ambient`; for any
        other credential, every other one removed and the chosen one applied last.
        Raises `CredentialError` (LAUNCH_FAILED) when it cannot bind."""
        binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
        env = child_env(self._base_env, launch.credential, binding, launch.env, drop=PARENT_SESSION_ENV)
        return {**env, "CLAUDE_CONFIG_DIR": str(ISOLATION)}

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
    # the providers in `PROFILE_ISOLATED_PROVIDERS`.

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        c = credential
        if isinstance(c, Ambient):
            return CredentialBinding(isolation="ambient: the host's environment and omp's default profile")
        provider = getattr(c, "provider", "")
        if isinstance(c, Subscription):
            provider = LOGIN_PROVIDERS.get(provider, provider)
        check_provider(c, model, provider, named=getattr(c, "provider", ""))

        match c:
            case Subscription():
                args = ("--profile", c.profile) if c.profile else ()
                isolation = f"the {provider} login in omp profile {c.profile or 'default'}"
                # A key omp fills in from a .env file outranks the stored login.
                back = dotenv_credentials(scrubbed(env or self._base_env), args, provider_vars(provider)) if c.isolate else {}
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
        back = dotenv_credentials({**scrubbed(env or self._base_env), **out}, args, provider_vars(provider))
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

    def argv(self, launch: Launch) -> list[str]:
        a = [self.binary]
        for plug in launch.plugin_dirs:
            a += ["--plugin-dir", plug]
        a += plugin_extension_args(launch.plugin_dirs)
        # `effort` is the neutral name for reasoning depth; omp spells it
        # `--thinking` and Claude Code spells it `--effort`. The launch
        # value wins so a per-task effort reaches the CLI — before this,
        # `Launch.effort` was read only by the claude backend and an
        # --omp-only run silently ignored it. `self.thinking` stays as the
        # constructor default for a launch that sets no effort.
        a += ["-p", "--thinking", launch.effort or self.thinking, "--approval-mode", "yolo", *isolation_args()]
        a += prompt_args(launch)
        if self.trace:
            a += ["--mode", "json"]
        if launch.model:
            a += ["--model", launch.model]
        a += self.bind_credential(launch.credential, launch.model, label=launch.label).args
        a += session_args(launch)
        if launch.preamble:
            a.append(launch.preamble)
        a += [f"@{f}" for f in launch.context_files]
        # A prompt over the per-argument limit cannot go on argv at all:
        # execve fails with E2BIG before omp ever starts, which the caller
        # sees as a 0-second launch_failed with no stderr. via_stdin says
        # the prompt is already being fed on the pipe, so it must not also
        # ride along as an argument. Claude Code has always done this.
        if not via_stdin(launch):
            a.append(launch.prompt)
        return a
