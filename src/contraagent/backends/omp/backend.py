"""oh-my-pi backend: `omp --plugin-dir <plug> -p`.

omp resolves agents and skills from the plugin dir, same bundle as
claude. `trace` defaults on (`--mode json`): per-tool-call trace in the
LaunchResult (tool_uses, session_id) and a real event stream
for the monitor, at the cost of parsing the richer wire format instead
of plain text. `trace=False` falls back to plain-text stdout, with no
usage or cost.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.base import PARENT_SESSION_ENV, OneShotBackend
from contraagent.backends.credentials import (
    Ambient,
    ApiKey,
    CredentialBase,
    CredentialBinding,
    CredentialError,
    Gateway,
    OAuthToken,
    Secret,
    Subscription,
    child_env,
)
from contraagent.backends.launch import ACCOUNT_UUID, Launch, LaunchResult, RateLimit, Stop, account_digest
from contraagent.backends.omp.classify import classify_text_result
from contraagent.backends.omp.config import (
    CATALOGUE_TIMEOUT_S,
    OmpModelChains,
    load_model_chains,
    parse_models,
)
from contraagent.backends.omp.trace import is_rate_limited, message_usage, parse_retry_after, parse_trace
from contraagent.backends.process import Sink, via_stdin

# Runtime mapping read by omp instead of Claude Code. A procedure written
# for Claude Code stays canonical; this preamble carries the substitution
# table. Callers with their own layout pass a different preamble.
OMP_PREAMBLE = """You are running under oh-my-pi (omp), not Claude Code. Read the attached
procedure with these substitutions:
- "Agent tool" / "spawn X with subagent_type" -> the task tool with `agent: X`
- "completion notification" -> asynchronous task result delivery (auto-delivered; wait on the job when blocked)
- agent definitions live in the plugin dir's agents/; skills live in the plugin's skills/ and auto-load on their triggers
"""


def _usage_reading(argv: list[str], env: dict[str, str], provider: str) -> RateLimit | None:
    """`omp usage --json`'s one report for `provider`, as a `RateLimit` reading."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)
        reports = [r for r in json.loads(proc.stdout).get("reports", []) if r.get("provider") == provider]
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return None
    if len(reports) != 1:
        return None
    account: dict[str, dict] = {}  # the account's own windows, by omp's window id
    windows: dict[str, dict] = {}  # every window, by the name a Claude Code reading gives it
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
        windows[name] = {
            "pct": round(float(fraction) * 100, 1) if isinstance(fraction, (int, float)) else None,
            "resets_at": _iso(at) if isinstance(at, (int, float)) else None,
        }
    if not account:
        return None
    meta = reports[0].get("metadata") or {}
    seen = meta.get("headersUpdatedAt") or reports[0].get("fetchedAt")  # when a request reported it
    return RateLimit(
        status="allowed" if statuses <= {"ok"} else ",".join(sorted(statuses - {"ok"})),
        five_hour_pct=(windows.get("five_hour") or {}).get("pct"),
        five_hour_resets_at=(windows.get("five_hour") or {}).get("resets_at"),
        seven_day_pct=(windows.get("seven_day") or {}).get("pct"),
        seven_day_resets_at=(windows.get("seven_day") or {}).get("resets_at"),
        observed_at=_iso(seen) if isinstance(seen, (int, float)) else None,
        account=account_digest(ACCOUNT_UUID, str(meta.get("accountId") or "")),
        windows=windows,
    )


#: omp's window ids, as Claude Code's readings name the windows.
_OMP_WINDOWS = {"5h": "five_hour", "7d": "seven_day"}


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat(timespec="seconds")


# A quota notice is a short message; a completed agent answer is not. The
# ceiling keeps a passing mention of "rate limit" inside a legitimate
# result from being read as the provider refusing the launch.
_RATE_LIMIT_MAX_SCAN = 400


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
    return _KEY_ENV.get(provider) or provider.upper().replace("-", "_").replace(".", "_") + "_API_KEY"


def plugin_extension_args(plugin_dirs) -> list[str]:
    """`-e <file>` for every extension a plugin directory declares.

    omp 18.8's `--plugin-dir` loads a directory's agents and skills but not the
    extensions its `package.json` lists under `omp.extensions`; without an explicit
    `-e` a hook the bundle declares is silently never installed (checked by running
    omp with a probe extension: `--plugin-dir` alone never loaded it). So the backend
    passes them itself.
    """
    import json

    args: list[str] = []
    for plug in plugin_dirs:
        try:
            pkg = json.loads((Path(plug) / "package.json").read_text())
        except (OSError, ValueError):
            continue
        for rel in (pkg.get("omp") or {}).get("extensions") or []:
            f = Path(plug) / rel
            if f.is_file():
                args += ["-e", str(f)]
    return args


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


class OmpBackend(OneShotBackend):
    """Headless oh-my-pi: `omp -p` with text output."""

    name = "omp"
    binary = "omp"
    effort_levels = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "auto")
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

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None, thinking: str = "medium", trace: bool = True):
        super().__init__(binary, base_env)
        self.thinking = thinking
        self.trace = trace
        self._chains: OmpModelChains | None = None
        self._accounts: dict[tuple[str, str], str] = {}  # (credential, provider) -> its account

    def run(self, launch: Launch) -> LaunchResult:
        """One launch, with the account's usage at its start, as Claude Code reports it: what
        the account's latest request reported in its response headers, which omp keeps and
        `omp usage` prints (no request of its own)."""
        reading = self.usage_reading(launch)
        result = self._launch(launch)
        if reading is not None:
            result.rate_limits.insert(0, reading)
        return result

    def _launch(self, launch: Launch) -> LaunchResult:
        return super().run(launch)

    def watch(self, launch: Launch) -> Sink | None:
        """`max_budget_usd`, which omp's CLI has no flag for: the cost of each API call,
        as its `message_end` reports it, summed; past the cap the launch ends `budget`."""
        cap = launch.limits.max_budget_usd
        if not self.trace or cap is None:
            return None
        spent = 0.0

        def sink(raw: bytes) -> Stop | None:
            nonlocal spent
            found = message_usage(raw)
            spent += (found[1] or 0.0) if found is not None else 0.0
            return Stop.BUDGET if spent > cap else None

        return sink

    def usage_reading(self, launch: Launch) -> RateLimit | None:
        """The 5-hour and weekly usage of the account `launch` runs as, from `omp usage --json`:
        None for a model with no provider prefix, an account omp reports no usage for, or
        several accounts of that provider (which one a launch uses is omp's choice)."""
        provider = launch.model.split("/", 1)[0] if "/" in launch.model else ""
        if not provider:
            return None
        try:
            binding = self.bind_credential(launch.credential, launch.model, env=self._base_env, label=launch.label)
            env = child_env(self._base_env, launch.credential, binding, {})
        except CredentialError:
            return None
        return _usage_reading([self.binary, *binding.args, "usage", "--json", "--provider", provider], env, provider)

    def account(self, credential: CredentialBase, model: str = "") -> str:
        """The account omp's usage report names for the model's provider (`metadata.accountId`,
        from `omp usage --json`, which reads what omp kept of the account's last response).
        Asked once per credential and provider in this process; '' when omp reports none."""
        provider = model.split("/", 1)[0] if "/" in model else ""
        if not provider:
            return ""
        key = (credential.label, provider)
        if key not in self._accounts:
            reading = self.usage_reading(Launch(prompt="", label=f"account-{credential.label}", model=model, credential=credential))
            self._accounts[key] = reading.account if reading is not None else ""
        return self._accounts[key]

    def model_chains(self, cwd: Path | None = None) -> OmpModelChains:
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
        model_provider = model.split("/", 1)[0] if "/" in model else ""
        if model_provider and provider and provider != model_provider:
            named = getattr(c, "provider", "")
            what = provider if named == provider else f"{provider} (its {named} login)"
            raise CredentialError(f"model {model} is a {model_provider} model; credential {c.label} is for {what}")

        def secret(s: Secret) -> str:
            return s.resolve(env) if env is not None else "<unresolved>"

        match c:
            case Subscription():
                args = ("--profile", c.profile) if c.profile else ()
                return CredentialBinding(
                    args=args, isolated=c.isolate, isolation=f"the {provider} login in omp profile {c.profile or 'default'}"
                )
            case ApiKey():
                out = {provider_key_env(provider): secret(c.key)}
            case Gateway():
                # omp reads `<PROVIDER>_BASE_URL` beside the key (checked against the real CLI for
                # litellm: the key goes as `Authorization: Bearer`, models are discovered from the
                # gateway's /model/info and /models).
                out = {provider_base_url_env(provider): c.endpoint(env)}
                if c.token is not None:
                    out[provider_key_env(provider)] = secret(c.token)
                if c.headers:
                    if provider != "anthropic":
                        raise CredentialError(f"omp sends custom headers only to an anthropic endpoint, not {provider}")
                    out["ANTHROPIC_CUSTOM_HEADERS"] = c.header_lines()
            case OAuthToken() if provider == "anthropic":
                out = {"ANTHROPIC_OAUTH_TOKEN": secret(c.token)}
            case _:
                raise CredentialError(
                    f"omp cannot use {c.type} credentials" + (f" for {provider}" if provider else "") + " (not wired here)"
                )
        if not c.isolate:
            return CredentialBinding(out, isolation="omp's default profile stays visible")
        verified = provider in PROFILE_ISOLATED_PROVIDERS
        return CredentialBinding(
            out,
            args=("--profile", ISOLATED_PROFILE),
            isolated=verified,
            isolation=(
                f"omp profile {ISOLATED_PROFILE}: no stored logins"
                if verified
                else f"omp profile {ISOLATED_PROFILE}, but omp may still use a {provider} login it keeps outside its profiles"
            ),
        )

    def catalogue(self) -> set[str] | None:
        """Model ids from `omp models`, or None when it cannot be read.

        A local registry read, no network: it took ~1.7s here. Worth the
        second because the failure it removes is a model typo that
        otherwise costs one launch each and reads as a generic error.
        None (not an empty set) on any failure, so a missing binary or a
        changed table format defers to the live probe instead of
        reporting every model as unknown.
        """
        import subprocess

        if not shutil.which(self.binary, path=self.base_path()):
            return None
        try:
            proc = subprocess.run(
                [self.binary, "models"],
                capture_output=True,
                text=True,
                timeout=CATALOGUE_TIMEOUT_S,
                env={**self._base_env, "NO_COLOR": "1"},
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return parse_models(proc.stdout) or None

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

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """A quota refusal on stderr is a rate limit, not an error.

        In text mode omp keeps stdout for the answer and reports the
        provider refusal on stderr — `429 Go usage limit exceeded` beside
        a `Working...` spinner line. Classified from stdout alone that
        reads as a generic failure, which is not in the failover path, so
        a run keeps launching into a dead quota. This is the exact shape
        that cost a run 644 tasks at two seconds each.

        The rpc backend inherits this, but does not rely on it: there a
        refusal arrives as an `errorStatus` frame, which its accumulator
        reads directly.
        """
        # A launch that produced its answer stays COMPLETED even if
        # stderr mentions a limit: omp retries internally, and failing
        # over would discard an answer already paid for. A blown quota
        # never answers, so the failed stops are the ones worth re-reading.
        if launch_result.stop not in (Stop.ERROR, Stop.NO_OUTPUT, Stop.API_ERROR):
            return
        text = stderr or ""
        if not is_rate_limited(text):
            return
        launch_result.stop = Stop.RATE_LIMITED
        launch_result.ok = False
        launch_result.rate_limit = RateLimit(status="quota", retry_after_s=parse_retry_after(text))

    def parse(self, launch: Launch, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """Stdout is the result (text) or the json event stream (trace)."""
        if self.trace:
            return parse_trace(launch, self.name, stdout, exit_code, killed)
        text = stdout.decode("utf-8", "replace").strip()
        # Nonzero exit is the authoritative signal. A zero exit still
        # counts when the whole stdout is a short notice, which is what
        # a quota refusal looks like — an agent that produced a real
        # answer is never 400 characters long.
        rate_limited = is_rate_limited(text) and (exit_code not in (0, None) or len(text) <= _RATE_LIMIT_MAX_SCAN)
        # Text mode has no separate "nothing ran at all" signal distinct
        # from "ran and said nothing": saw_any=True keeps empty text on
        # NO_OUTPUT rather than LAUNCH_FAILED, same as before this call
        # went through the shared classifier.
        stop = classify_text_result(text, saw_any=True, exit_code=exit_code, killed=killed, rate_limited=rate_limited)
        if stop is Stop.RATE_LIMITED:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=stop,
                ok=False,
                exit_code=exit_code,
                model=launch.model,
                result_text=text,
                rate_limit=RateLimit(status="quota", retry_after_s=parse_retry_after(text)),
            )
        if stop is Stop.COMPLETED:
            return LaunchResult(
                label=launch.label, agent=self.name, stop=stop, ok=True, exit_code=exit_code, result_text=text, model=launch.model
            )
        return LaunchResult(label=launch.label, agent=self.name, stop=stop, ok=False, exit_code=exit_code, model=launch.model)
