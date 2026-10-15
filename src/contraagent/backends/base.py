"""The `Backend` interface: one headless coding-agent CLI behind argv, env and `run`.

`Backend.run` is one template for every CLI: prepare the launch, check the binary, take
the readings the agent offers before a launch (`usage_reading`), run the process while
its reader (`fold`, an `EventFold` of `wire.py`) reads every line as it arrives and a
`LimitsWatch` ends it on the budgets the CLI cannot enforce, fold what was read into a
`LaunchResult`, stamp it (argv, credential, start, wall time, CLI version, context
window), take a second look at stderr (`reclassify`) and check the credential the agent
reports (`attest`). A backend supplies its argv, env and reader; one that does not drive
a plain process (the omp RPC exchange) overrides `exchange` alone. A backend that plays
replies instead of running a CLI (`contraagent.testing.StubAgent`) overrides `run`.
"""

from __future__ import annotations

import abc
import atexit
import dataclasses
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Protocol

from contraagent.backends.credentials import Ambient, CredentialBase, CredentialBinding, CredentialError
from contraagent.backends.launch import Launch, LaunchResult, RateLimit, Stop
from contraagent.backends.process import LaunchError, Sink, run_process
from contraagent.backends.refusal import Signals, quota_refusal
from contraagent.backends.wire import EventFold, LimitsWatch
from contraagent.runs.times import now_iso

#: Variables that tie a process to a Claude Code session that started contraagent
#: (a coding agent running the pipeline): its id, its messaging socket and token.
#: Left in place, a task agent joins that session (a Claude child uses no tools
#: and returns raw tool-call text as its body, observed live). Removed from every launch.
PARENT_SESSION_ENV = (
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_BRIDGE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDECODE",
    "CLAUDE_EFFORT",
    "AI_AGENT",
    "CLAUDE_PID",
)


class ModelChains(Protocol):
    """What `Backend.model_chains` reports: an agent's own model-level failover
    configuration, as far as a preflight needs to describe it."""

    def describe(self, model: str) -> str:
        """One line saying what the agent does after `model` is refused, and where that is set."""
        ...


class Backend(abc.ABC):
    """One headless CLI. Subclasses define argv, env, and how to run."""

    name: str = ""
    binary: str = ""
    # True when this agent can retry a different model inside one launch —
    # model-level failover, a different axis from the Router's agent-level
    # one. The two compose rather than compete: the agent exhausts its own
    # models first, and only a refusal that survives reaches the Router.
    native_model_chain: bool = False
    # True when `native_model_chain` can be driven per launch, which is
    # what decides whether the caller fills it in. Claude Code takes
    # --fallback-model on argv, so yes. omp's equivalent
    # (retry.fallbackChains, default on) lives in its own config file and
    # is the operator's to set, so the caller reads and reports it
    # instead of writing it.
    drivable_model_chain: bool = False
    # True when this agent needs the task's role file (`agents/<role>.md`)
    # inlined into the prompt/context files rather than resolved via its own
    # --agent flag. Only omp today: it has no named-agent mechanism of its
    # own, so the caller attaches the file directly.
    needs_inline_role_file: bool = False
    # True when this agent runs a light launch as asked: `Launch.tools == ()` turns
    # every tool off, `Launch.system_prompt` replaces its own system prompt, and it
    # loads no settings, skills or MCP servers it was not given. A kind declared with
    # `agent_task(tools=())` is refused on an agent without it (routing).
    light_launch: bool = False
    # True when the cost a resumed launch reports (`LaunchResult.cost_usd`) is the
    # session's so far, the earlier launches of the session included, not that launch's
    # alone. A fix-up round resumes the session, so its cost replaces the rounds' total
    # rather than adding to it (`contracts.fold_spend`). Measured per CLI: Claude Code's
    # `total_cost_usd` is the session's; omp reports each launch's own.
    cost_is_session_total: bool = False
    # The reasoning-depth values this CLI accepts for `Launch.effort`, read off
    # the installed CLI rather than guessed (`claude --help | grep effort`,
    # `omp --help | grep thinking`). The vocabularies differ, so a value valid
    # for one aborts the other; re-check after a CLI upgrade. None: not checked.
    effort_levels: tuple[str, ...] | None = None
    #: The module that reads this agent's wire (`<agent>/wire.py`): the monitor renders its
    #: stream files with that module's `normalize_event` (`streams.py`). None: no stream format.
    wire: ModuleType | None = None
    #: True when a line of its stream that is not JSON is the agent's own plain-text narration
    #: (omp's text mode), rendered with the wire's `normalize_text_line`.
    plaintext_stream: bool = False
    #: How this agent's wire words a refusal; `reclassify` reads stderr with it.
    signals: Signals = Signals(stderr_stops=frozenset())
    #: The `Limits` fields this agent leaves to the wrapper (`LimitsWatch`): `context_budget`,
    #: `max_budget_usd`, `max_turns`. The others it is given on its command line or has none of.
    watched_limits: frozenset[str] = frozenset()
    #: How long the agent may take to list its models (`read_models`), in seconds.
    catalogue_timeout_s: float = 30.0

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None):
        if binary:
            self.binary = binary
        self._base_env = dict(os.environ if base_env is None else base_env)

    def base_path(self) -> str | None:
        """PATH the child binary is resolved against."""
        return self._base_env.get("PATH")

    @classmethod
    def tool_deny_problem(cls, denied: tuple[str, ...]) -> str | None:
        """Why this coding agent cannot keep a launch from the tools `denied`
        (`Limits.disallowed_tools`, Claude Code's names and patterns: `WebFetch`,
        `Bash(rm:*)`), or None when it can. The routing check refuses a route whose
        agent cannot (`[tasks.<kind>].disallowed_tools`). By default it cannot."""
        return f"{cls.name} has no way to deny a tool" if denied else None

    @abc.abstractmethod
    def argv(self, launch: Launch) -> list[str]:
        """Build the child argv. Variable-length options go last."""

    @abc.abstractmethod
    def env(self, launch: Launch) -> dict[str, str]:
        """Build the child environment over the captured base.

        May raise `CredentialError` for a credential that cannot be used:
        `run()` maps it to LAUNCH_FAILED. Never falls back to another one.
        """

    # --- one launch ---------------------------------------------------------

    def prepare(self, launch: Launch) -> Launch:
        """`launch` as this agent runs it (codex writes attached files into the prompt). May
        raise `OSError` for a file it cannot read: the launch fails. Default: as it is."""
        return launch

    def fold(self, launch: Launch) -> EventFold:
        """A new reader of this agent's wire for `launch`. A backend that runs a CLI supplies
        one; one that overrides `run` needs none."""
        raise NotImplementedError(f"{type(self).__name__} supplies no reader (fold) and does not override run")

    def usage_reading(self, launch: Launch) -> RateLimit | None:
        """The utilization of the account `launch` bills, read before it starts, where the agent
        reports it outside its stream (omp's `omp usage`, OpenCode Go's usage route); first in
        `LaunchResult.rate_limits`. Default: none."""
        return None

    def watch_stderr(self, launch: Launch) -> Sink | None:
        """A reader of stderr, one line at a time, for a CLI that reports something only there
        (opencode's log of a refusal it keeps retrying); a `Stop` it returns ends the launch.
        Default: none."""
        return None

    def exchange(
        self, launch: Launch, argv: list[str], env: dict[str, str], fold: EventFold, watch: LimitsWatch
    ) -> tuple[bytes, str, int | None, Stop | None]:
        """Run the process to its end, each stdout line to `fold` and then `watch`; their first
        `Stop` ends it. Returns stdout, the stderr tail, the exit status and the kill reason.
        Raises `LaunchError` when the process cannot start."""

        def sink(raw: bytes) -> Stop | None:
            return fold.feed_line(raw) or watch()

        return run_process(argv, env, launch, sink=sink, stderr_sink=self.watch_stderr(launch))

    def run(self, launch: Launch) -> LaunchResult:
        """Run one launch to completion and return its LaunchResult (the template above)."""
        started_at = now_iso()
        t0 = time.monotonic()
        reading = self.usage_reading(launch)
        result = self._run(launch, started_at, t0)
        if reading is not None:
            result.rate_limits.insert(0, reading)
        return result

    def _run(self, launch: Launch, started_at: str, t0: float) -> LaunchResult:
        argv: list[str] = []
        try:
            try:
                launch = self.prepare(launch)
            except OSError as exc:
                return self.launch_failed(launch, f"attached file: {exc}", started_at=started_at, t0=t0)
            argv = self.argv(launch)
            env = self.env(launch)
        except CredentialError as exc:
            return self.launch_failed(launch, f"credential: {exc}", argv=argv, started_at=started_at, t0=t0)
        if not shutil.which(self.binary, path=self.base_path()):
            return self.launch_failed(launch, f"{self.binary} not on PATH", argv=argv, started_at=started_at, t0=t0)
        fold = self.fold(launch)
        try:
            _, stderr, exit_code, killed = self.exchange(launch, argv, env, fold, LimitsWatch(launch.limits, self.watched_limits, fold))
        except LaunchError as exc:
            return self.launch_failed(launch, str(exc), argv=argv, started_at=started_at, t0=t0)
        result = fold.result(launch, self.name, exit_code=exit_code, killed=killed)
        result.argv = argv
        result.credential = launch.credential.label
        result.started_at = started_at
        result.wall_s = time.monotonic() - t0
        result.cli_version = result.cli_version or self.version()
        if result.context_window is None and result.model:
            result.context_window = self.context_window(result.model)
        # What the reader took from the wire (a provider's words) stays, with stderr after it.
        result.stderr_tail = "\n".join(x for x in (result.stderr_tail, stderr) if x)[-2000:]
        self.reclassify(result, stderr)
        apply_attestation(self, result, launch)
        return result

    def launch_failed(
        self, launch: Launch, why: str, *, argv: list[str] | None = None, started_at: str = "", t0: float | None = None
    ) -> LaunchResult:
        """The result of a launch that never ran: `why` is its reason."""
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            stop=Stop.LAUNCH_FAILED,
            ok=False,
            started_at=started_at,
            wall_s=time.monotonic() - t0 if t0 is not None else 0.0,
            cli_version=self.version(),
            argv=list(argv or []),
            model=launch.model,
            credential=launch.credential.label,
            stderr_tail=why,
        )

    # --- what the CLI says about itself ---------------------------------------

    def version(self) -> str:
        """The version `<binary> --version` prints (its first `1.2.3`-like word), asked once;
        '' when the binary is missing or prints none."""
        own: dict = vars(self)
        if own.get("_version") is None:
            own["_version"] = cli_version(self.binary, self._base_env)
        return own["_version"]

    def run_catalogue(self, *args: str, env: dict[str, str] | None = None) -> str | None:
        """What `<binary> <args>` prints when it lists the agent's models, within
        `catalogue_timeout_s`; None when the binary is missing, fails or takes longer."""
        if not shutil.which(self.binary, path=self.base_path()):
            return None
        try:
            proc = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                timeout=self.catalogue_timeout_s,
                env={**self._base_env, **(env or {}), "NO_COLOR": "1"},
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout if proc.returncode == 0 else None

    # --- scratch directories ------------------------------------------------

    def scratch_parent(self) -> Path | None:
        """Where this backend's scratch root is made; None: the system's temporary directory."""
        return None

    def scratch(self, label: str, which: str, create: bool = True) -> Path:
        """A directory per launch label and purpose (a resumed launch keeps its label, and so
        its directory), under one root this process removes at exit."""
        own: dict = vars(self)
        if own.get("_scratch_root") is None:
            parent = self.scratch_parent()
            if parent is not None:
                parent.mkdir(parents=True, exist_ok=True)
            own["_scratch_root"] = Path(tempfile.mkdtemp(prefix=f"contraagent-{self.name}-", dir=parent))
            atexit.register(shutil.rmtree, own["_scratch_root"], True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in label) or "launch"
        d = own["_scratch_root"] / safe / which
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """How this agent authenticates as `credential` for a launch of `model`.

        Raises `CredentialError` when it cannot (an unsupported type, a provider
        the model does not use). With `env` None this is a check only and no
        secret is read; with the parent environment the secrets are resolved.
        `label` keys any per-launch state (an isolated config directory). The
        default supports only `ambient`: whatever the agent loads by itself.
        """
        if isinstance(credential, Ambient):
            return CredentialBinding(isolation="ambient: whatever the agent loads by default")
        raise CredentialError(f"{self.name} cannot use {credential.type} credentials")

    def account(self, credential: CredentialBase, model: str = "") -> str:
        """The account a launch of `model` as `credential` bills, as `account_digest`: the
        same value for the same account, never the secret or anything it can be turned
        back into. '' when this agent cannot tell (the default). Read from local state only
        (a login file, the credential's own secret), except where the agent offers no other
        way; cheap enough to ask once per credential per run."""
        return ""

    def attest(self, launch_result: LaunchResult, credential: CredentialBase) -> str | None:
        """After a launch: a reason when the agent reports using a different credential than
        `credential`, else None. Default: the agent reports nothing to check against."""
        return None

    def read_models(self) -> dict[str, int | None] | None:
        """The agent's own model catalogue, read once (`models`): each provider-qualified
        model id it lists, with the context window it lists for that model (tokens; None
        where it lists none). None when the agent publishes no catalogue or it cannot be
        read, never an exception. Default: no catalogue.

        Implementations own their own CLI's output format, which is the whole reason this
        lives on the backend: the list omp prints is omp's, and a caller that parsed it
        would be omp-specific by accident."""
        return None

    def models(self) -> dict[str, int | None] | None:
        """`read_models()`, read on the first call and kept for the backend's life: one
        local read per backend per run, however many launches ask."""
        own: dict = vars(self)
        with own.setdefault("_models_lock", threading.Lock()):
            if "_models" not in own:
                own["_models"] = self.read_models()
            return own["_models"]

    def catalogue(self) -> set[str] | None:
        """Provider-qualified model ids this agent advertises (`models`), or None.

        The cheap half of a preflight: a model name that is not in the
        agent's own list is a typo, and finding that out from the list
        costs one local read instead of one failed launch. None means
        "this agent publishes no list" — a different answer from an empty
        set, and the caller falls back to probing.
        """
        listed = self.models()
        return set(listed) if listed is not None else None

    def context_window(self, model: str) -> int | None:
        """The context window the agent's catalogue (`models`) lists for `model`, the
        model a launch ran on as it was launched (`window_of`); None when it lists none.
        Fills `LaunchResult.context_window` when the launch's stream reports none."""
        return window_of(self.models() or {}, model)

    def resumable(self, launch: Launch) -> Launch:
        """`launch`, adjusted so the session it starts can be resumed.

        Called before the first launch of a run that may need a second
        turn. Default: an omp-style per-launch `session_dir` — omp prints
        no session id in text mode, so the directory is the only handle,
        and a fresh one per launch keeps `--continue` from picking up a
        concurrent task's session.
        """
        if launch.session_dir is not None:
            return launch
        return dataclasses.replace(launch, session_dir=Path(tempfile.mkdtemp(prefix=f"{self.name}-session-")))

    def resumed(self, launch: Launch, prior: LaunchResult, prompt: str) -> Launch | None:
        """The launch that sends `prompt` as the next turn of `prior`'s session.

        None when the session cannot be found again. The task context
        (preamble, attached files) was delivered on the first turn and is
        already in the transcript, so it is not sent twice.
        """
        if launch.session_dir is None and not prior.session_id:
            return None
        return dataclasses.replace(
            launch, prompt=prompt, resume=prior.session_id or "", preamble=None, context_files=(), prompt_via_stdin=None
        )

    def discard_session(self, launch: Launch, session_id: str) -> None:
        """Delete a session `resumable` kept only so it could be resumed.

        `launch` is the caller's, from before `resumable`. Default no-op:
        omp's session lives in a scratch `session_dir` the caller removes.
        """
        return None

    def model_chains(self, cwd: Path | None = None) -> ModelChains | None:
        """This agent's own model-level failover chain, if it has one.

        None means the agent has nothing to report — most agents drive
        model failover through `native_model_chain`/`drivable_model_chain`
        instead, with no separate config to read. omp is the one
        exception: its `retry.fallbackChains` lives in its own config
        file, so it overrides this to read and describe it.
        """
        return None

    def reclassify(self, launch_result: LaunchResult, stderr: str) -> None:
        """Second look at a launch's result, now that its stderr is whole.

        CLIs do not agree on where they report a refusal: omp prints `429 Go usage limit
        exceeded` on stderr while stdout holds a spinner line, and a CLI that dies at start
        prints only there. A failed launch (`signals.stderr_stops`) whose stderr words a quota
        refusal (`signals.quota`) is `rate_limited`, which is in the failover path; read from
        stdout alone it is an ordinary error, and a run keeps launching into a blown quota.
        """
        sig = self.signals
        if launch_result.stop not in sig.stderr_stops or not sig.quota_in(stderr):
            return
        launch_result.stop = Stop.RATE_LIMITED
        launch_result.ok = False
        if launch_result.rate_limit is None:
            launch_result.rate_limit = quota_refusal(stderr)


class ResumeById:
    """Session resume for an agent that reports its session's id (Claude Code, Codex): the
    session only has to be kept, and a resume names it."""

    def resumable(self, launch: Launch) -> Launch:
        """The agent reports its session id; it only has to keep the session where a resume
        finds it (`persist_session`)."""
        return dataclasses.replace(launch, persist_session=True)

    def resumed(self, launch: Launch, prior: LaunchResult, prompt: str) -> Launch | None:
        if not prior.session_id or not launch.persist_session:
            return None
        return dataclasses.replace(
            launch, prompt=prompt, resume=prior.session_id, session_id=None, preamble=None, context_files=(), prompt_via_stdin=None
        )


_VERSION_RE = re.compile(r"\d+(?:\.\d+)+[\w.+-]*")


def cli_version(binary: str, env: dict[str, str]) -> str:
    """The first `1.2.3`-like word `<binary> --version` prints (`2.1.296 (Claude Code)`,
    `codex-cli 0.162.1`, `omp/18.9.1`); '' when it is missing or prints none."""
    exe = shutil.which(binary, path=env.get("PATH"))
    if not exe:
        return ""
    try:
        p = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30, env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = _VERSION_RE.search(p.stdout or "")
    return m.group(0) if m else ""


#: The reasoning suffix a model selector may carry (`model:high`), dropped by `window_of`.
_THINKING_SUFFIXES = frozenset({"off", "minimal", "low", "medium", "high", "xhigh", "max"})


def window_of(windows: dict[str, int | None], model: str) -> int | None:
    """The context window `windows` (`Backend.models`) lists for `model`: its
    provider-qualified id, the same with a reasoning suffix (`:high`) dropped, or a bare
    id that every provider listing it gives one window. None when none is listed."""
    if model in windows:
        return windows[model]
    head, sep, tail = model.rpartition(":")
    if sep and tail in _THINKING_SUFFIXES and head in windows:
        return windows[head]
    if "/" in model:
        return None
    found = {w for key, w in windows.items() if key.rpartition("/")[2] == model}
    return found.pop() if len(found) == 1 else None


def apply_attestation(backend: Backend, launch_result: LaunchResult, launch: Launch) -> None:
    """Fail a launch whose agent reports a different credential than the one chosen.

    The call has already been made by then; what this prevents is the result
    being used as if it had been made under the chosen contract.
    """
    reason = backend.attest(launch_result, launch.credential)
    if reason:
        launch_result.stop = Stop.CREDENTIAL_MISMATCH
        launch_result.ok = False
        launch_result.stderr_tail = f"credential mismatch: {reason}\n{launch_result.stderr_tail}"[-2000:]
