"""Backend interface: one headless CLI behind argv / env / run.

A Backend builds the child argv, the child env, and runs one launch to
completion. Most CLIs are one-shot: spawn, capture, parse raw output
into a LaunchResult after the fact — that shared "spawn, capture, classify"
loop and the `parse()` contract it calls live on `OneShotBackend`, not
on `Backend` itself, since a backend driving a live stream or an
interactive RPC exchange (claude, the omp RPC variant) builds its
LaunchResult as it goes and has no post-hoc parse step at all.
"""

from __future__ import annotations

import abc
import dataclasses
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Protocol

from contraagent.backends.credentials import Ambient, CredentialBase, CredentialBinding, CredentialError
from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.backends.process import LaunchError, Sink, run_process

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
    # The reasoning-depth values this CLI accepts for `Launch.effort`, read off
    # the installed CLI rather than guessed (`claude --help | grep effort`,
    # `omp --help | grep thinking`). The vocabularies differ, so a value valid
    # for one aborts the other; re-check after a CLI upgrade. None: not checked.
    effort_levels: tuple[str, ...] | None = None

    def __init__(self, binary: str = "", base_env: dict[str, str] | None = None):
        if binary:
            self.binary = binary
        self._base_env = dict(os.environ if base_env is None else base_env)

    def base_path(self) -> str | None:
        """PATH the child binary is resolved against."""
        return self._base_env.get("PATH")

    @abc.abstractmethod
    def argv(self, launch: Launch) -> list[str]:
        """Build the child argv. Variable-length options go last."""

    @abc.abstractmethod
    def env(self, launch: Launch) -> dict[str, str]:
        """Build the child environment over the captured base.

        May raise `CredentialError` for a credential that cannot be used:
        `run()` maps it to LAUNCH_FAILED. Never falls back to another one.
        """

    @abc.abstractmethod
    def run(self, launch: Launch) -> LaunchResult:
        """Run one launch to completion and return its LaunchResult."""

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

    def attest(self, launch_result: LaunchResult, credential: CredentialBase) -> str | None:
        """After a launch: a reason when the agent reports using a different credential than
        `credential`, else None. Default: the agent reports nothing to check against."""
        return None

    def catalogue(self) -> set[str] | None:
        """Provider-qualified model ids this agent advertises, or None.

        The cheap half of a preflight: a model name that is not in the
        agent's own list is a typo, and finding that out from the list
        costs one local read instead of one failed launch. None means
        "this agent publishes no list" — a different answer from an empty
        set, and the caller falls back to probing.

        Implementations own their own CLI's output format, which is the
        whole reason this lives on the backend: the table omp prints is
        omp's, and a caller that parsed it would be omp-specific by
        accident.
        """
        return None

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
        """Second look at a parsed LaunchResult, now that stderr exists.

        `parse` only ever sees stdout, and CLIs do not agree on where
        they report a refusal: omp prints `429 Go usage limit exceeded`
        on stderr while stdout holds a spinner line, so a stdout-only
        classifier calls that an ordinary error and the run keeps
        launching into a blown quota. May rewrite `launch_result.stop`.
        Default is a no-op — most agents have nothing to add.
        """
        return None


class OneShotBackend(Backend):
    """A `Backend` that runs to completion, then parses raw output.

    Covers every CLI without a live wire to drive as it runs: spawn,
    capture stdout/stderr, and turn the finished result into a LaunchResult
    after the fact. `OmpBackend`'s text/trace modes are the one real
    case today; a backend that instead has to see its own output as it
    streams (claude, the omp RPC variant) implements `run()` itself
    directly on `Backend` and never gains a `parse()` method at all.
    """

    @abc.abstractmethod
    def parse(self, launch: Launch, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """Turn raw process output into a LaunchResult."""

    def watch(self, launch: Launch) -> Sink | None:
        """A reader of the launch's output, one line at a time as it arrives; a `Stop`
        it returns ends the launch there (a budget the CLI cannot enforce itself).
        Default: none."""
        return None

    def run(self, launch: Launch) -> LaunchResult:
        """Run one launch to completion and return its LaunchResult."""
        t0 = time.monotonic()
        try:
            argv = self.argv(launch)
        except CredentialError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                credential=launch.credential.label,
                stderr_tail=f"credential: {exc}",
            )
        if not shutil.which(self.binary, path=self.base_path()):
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                argv=argv,
                stderr_tail=f"{self.binary} not on PATH",
            )
        try:
            out, err, exit_code, killed = run_process(argv, self.env(launch), launch, sink=self.watch(launch))
        except LaunchError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                argv=argv,
                stderr_tail=str(exc),
            )
        except CredentialError as exc:
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=Stop.LAUNCH_FAILED,
                ok=False,
                model=launch.model,
                argv=argv,
                credential=launch.credential.label,
                stderr_tail=f"credential: {exc}",
            )
        launch_result = self.parse(launch, out, exit_code, killed)
        launch_result.argv = argv
        launch_result.credential = launch.credential.label
        launch_result.wall_s = time.monotonic() - t0
        # What the parser read from stdout (a provider's error) stays, with stderr after it.
        launch_result.stderr_tail = "\n".join(x for x in (launch_result.stderr_tail, err) if x)
        self.reclassify(launch_result, err)
        apply_attestation(self, launch_result, launch)
        return launch_result


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
