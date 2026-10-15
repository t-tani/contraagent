"""Shared vocabulary for headless coding-agent launches.

Stop, Limits, Launch, Usage, QuotaRefusal, and LaunchResult are backend-neutral; a launch's
quota readings are `QuotaReading`s and its totals a `TokenUsage` (`dispatch.records`).
Per-CLI argv, env and wire readers live in `backends/<agent>/`; the Backend ABC
and its run template in `backends/base.py`; what every wire reader shares in
`backends/wire.py`; the subprocess loop in `backends/process.py`; the provider
identity in `backends/credentials.py`.
They hold the per-call usage accounting, the stop taxonomy, and the
telemetry record.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contraagent._internal.backends.credentials import AMBIENT, Credential
from contraagent._internal.dispatch.records import OtherModel, QuotaReading, TokenUsage
from contraagent._internal.runs.files import append_lines

# Prompt text beyond this size goes over stdin, not argv
# (Linux caps one argv element at 128KB; stdin takes 10MB).
STDIN_THRESHOLD = 60_000


class Stop(str, enum.Enum):
    """Why one launch ended: exactly one per launch. A task's result (`TaskResult.stop`)
    holds one of these too, or one of a task's own: `partial` (a Python task's
    placeholder output, ok), `skipped` (a resume skipped it), `deferred` (not launched)
    or `duplicate_key` (not queued: a task with the same key was in flight).

    `completed`: ran to the end (`ok` still decides success). `timeout`: past `Limits.timeout_s`,
    killed. `max_turns`: the coding agent stopped on its turn cap. `budget`: it stopped on
    its cost cap (`max_budget_usd`). `context_budget`: one API call's input passed
    `Limits.context_budget`. `stalled`: no transcript line for `Limits.stall_s`.
    `auth_failed`: a 401 or 403; a retry cannot fix the credential. `api_error`: the agent
    reported an API error (not a 429, a 401 or a refusal). `rate_limited`: a 429 or a
    usage-limit message. `refused`: a safety refusal. `aborted`: stopped in the middle of a
    tool call. `denied`: more permission denials than `Limits.max_denials`. `error`: a
    nonzero exit with no result (a Python task: it raised). `no_output`: the process ended
    with no result line. `launch_failed`: the program is missing or the launch could not
    be set up. `invalid_output`: the output was still off-contract after every round.
    `invalid_input`: an input the task reads is off-contract; nothing was launched.
    `credential_mismatch`: the agent reported another credential than the one chosen.
    """

    COMPLETED = "completed"  # Ran to the end (`ok` still decides success)
    TIMEOUT = "timeout"  # Past `Limits.timeout_s`; the wrapper killed it
    MAX_TURNS = "max_turns"  # CLI stopped on `--max-turns`
    BUDGET = "budget"  # CLI stopped on `--max-budget-usd`
    CONTEXT = "context_budget"  # One call's input passed `Limits.context_budget`
    STALLED = "stalled"  # No stream output for `Limits.stall_s`
    AUTH_FAILED = "auth_failed"  # 401/403 — retrying cannot fix the credential
    API_ERROR = "api_error"  # `is_error` result (minus 429/401/refusal)
    RATE_LIMITED = "rate_limited"  # 429 or usage-limit copy
    REFUSED = "refused"  # Safety refusal
    ABORTED = "aborted"  # Mid-tool abort (`terminal_reason` aborted_*)
    DENIED = "denied"  # Permission denials past `Limits.max_denials`
    ERROR = "error"  # Nonzero exit with no result text (generic failure)
    NO_OUTPUT = "no_output"  # Process ended with no result line
    LAUNCH_FAILED = "launch_failed"  # Missing binary or broken launch setup
    INVALID_OUTPUT = "invalid_output"  # Output file still off-contract after every resume
    INVALID_INPUT = "invalid_input"  # An input the task reads is off-contract; nothing was launched
    CREDENTIAL_MISMATCH = "credential_mismatch"  # The agent reports a different credential than the one chosen


@dataclass(frozen=True)
class Limits:
    """The budget of one launch: the turn, time, cost and stall caps that stop it.

    `timeout_s` / `max_turns` / `max_budget_usd` go to the CLI.
    `context_budget` (per-call input ceiling: resident + accumulated reads)
    and `stall_s` are enforced by the wrapper watching the stream.
    `context_warn_pct` stops nothing: a launch whose peak context
    (`LaunchResult.peak_context`) passes that % of `context_budget` is
    recorded as warned (`JournalRow.context_warned`); it needs a `context_budget`.
    `disallowed_tools` becomes `--disallowedTools` (patterns like
    `Bash(git push:*)` allowed). Past `max_denials` permission denials the
    wrapper stops: a denied model burns calls working around with
    mkdir/cat/python3 (13 observed).
    """

    timeout_s: float = 600.0
    max_turns: int | None = None
    max_budget_usd: float | None = None
    context_budget: int | None = None
    context_warn_pct: int | None = None
    stall_s: float | None = None
    disallowed_tools: tuple[str, ...] = ()
    # Stop after this many stream `permission_denied` events. None never stops.
    max_denials: int | None = None

    def __post_init__(self) -> None:
        if self.context_warn_pct is not None:
            if (
                isinstance(self.context_warn_pct, bool)
                or not isinstance(self.context_warn_pct, int)
                or not 1 <= self.context_warn_pct <= 99
            ):
                raise ValueError(f"context_warn_pct = {self.context_warn_pct!r} is not a whole percent from 1 to 99")
            if not self.context_budget:
                raise ValueError("context_warn_pct needs a context_budget: it is a percent of it")

    def context_warned(self, peak_context: int | None) -> bool:
        """Whether a launch with this `peak_context` passed `context_warn_pct`% of
        `context_budget`; False without them or without a peak context."""
        if peak_context is None or not self.context_budget or not self.context_warn_pct:
            return False
        return peak_context * 100 > self.context_warn_pct * self.context_budget


@dataclass(frozen=True)
class Launch:
    """One backend invocation's launch options. Immutable.

    `role` is the role the coding agent runs as (`agents/<role>.md` in a
    plugin): Claude Code gets it as `--agent <role>`, omp as an attached file.
    `tools` None keeps the CLI default; a tuple narrows via `--tools`
    (empty tuple = no tools). `settings` is a file path or JSON string;
    `setting_sources` None means the backend's own default (Claude Code: `""`,
    no settings files: a role comes from the plugin, not `.claude/agents/`). `stream_path` keeps raw stream-json lines for
    later inspection. `permission_prompts="none"` (default, CLI >= 2.1.259)
    tells the model not to retry denied calls under headless `-p`.
    `prompt_via_stdin` None sends over stdin past `STDIN_THRESHOLD`
    (argv caps one element at 128KB; stdin takes 10MB). `session_id`
    pins the UUID so records and sessions can be joined. `fallback_model`
    covers overload.

    `resume` continues an earlier session instead of starting one: a
    session id for claude (`--resume`), and for omp the id when known,
    else the lone session under `session_dir` (`--continue`). omp prints
    no session id in text mode, so a launch that may need resuming gets
    its own `session_dir` and the directory is the handle.
    """

    prompt: str
    label: str = ""
    role: str | None = None
    model: str = ""
    effort: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    tools: tuple[str, ...] | None = None
    allowed_tools: tuple[str, ...] = ()
    json_schema: dict[str, Any] | None = None
    settings: str | None = None
    setting_sources: str | None = None
    mcp_config: str | None = None
    strict_mcp: bool = True
    persist_session: bool = False
    exclude_dynamic_sections: bool = False
    limits: Limits = field(default_factory=Limits)
    credential: Credential = AMBIENT
    cwd: Path = field(default_factory=Path.cwd)
    env: dict[str, str] = field(default_factory=dict)
    stream_path: Path | None = None
    permission_prompts: str | None = "none"
    permission_mode: str | None = None
    prompt_via_stdin: bool | None = None
    plugin_dirs: tuple[str, ...] = ()
    preamble: str | None = None
    context_files: tuple[str, ...] = ()
    session_id: str | None = None
    fallback_model: str | None = None
    resume: str | None = None
    session_dir: Path | None = None


@dataclass
class CallUsage:
    """One API call's token counts. Same `message.id` stream lines count once."""

    model: str
    input: int
    cache_read: int
    cache_creation: int
    output: int

    @property
    def context(self) -> int:
        """Whole input sent to the model on this call (resident + reads)."""
        return self.input + self.cache_read + self.cache_creation


@dataclass
class Usage:
    """A launch's API calls as its coding agent reported them (`CallUsage`, one per call),
    and the output total of its result; `totals()` sums them as a `TokenUsage`.

    `resident` is the first call's input (what was loaded before the task
    started); `peak_context` the largest input of one call (context at its most grown).
    A call's input is `CallUsage.context`: fresh input, cache read and cache write.

    The stream's `assistant` `output_tokens` are running fragments (live
    reading: 7 streamed vs 271 in result for one launch). Output totals
    come from the result's `usage`; per-call inputs come from the stream.
    """

    calls: list[CallUsage] = field(default_factory=list)
    output_total: int = 0

    @property
    def resident(self) -> int:
        return self.calls[0].context if self.calls else 0

    @property
    def peak_context(self) -> int:
        return max((c.context for c in self.calls), default=0)

    @property
    def context_total(self) -> int:
        """All calls' inputs summed (rereads included)."""
        return sum(c.context for c in self.calls)

    def totals(self, context_window: int | None = None) -> TokenUsage | None:
        """The calls summed: the output the larger of the calls' and the result's total;
        `resident` and `peak_context` None without a call; `context_window` the one the
        coding agent reported (`LaunchResult.context_window`). None when the launch
        reported no API call and no output."""
        if not (self.calls or self.output_total):
            return None
        return TokenUsage(
            input=sum(c.input for c in self.calls),
            output=max(sum(c.output for c in self.calls), self.output_total),
            cache_read=sum(c.cache_read for c in self.calls),
            cache_creation=sum(c.cache_creation for c in self.calls),
            calls=len(self.calls),
            resident=self.resident if self.calls else None,
            peak_context=self.peak_context if self.calls else None,
            context_window=context_window,
        )

    def as_dict(self) -> dict[str, Any]:
        """The usage as `launches.jsonl` records it: the totals, with the result's own
        output total (`output_total`) and every call's input summed (`context_total`)."""
        t = self.totals() or TokenUsage()
        return {
            "n_calls": t.calls,
            "resident": t.resident or 0,
            "peak_context": t.peak_context or 0,
            "context_total": self.context_total,
            "input": t.input,
            "cache_read": t.cache_read,
            "cache_creation": t.cache_creation,
            "output_total": self.output_total,
        }


#: The sources of an account digest: an Anthropic account's UUID (a Claude Code login,
#: omp's usage report), or the secret a credential authenticates with (a token, a key).
ACCOUNT_UUID = "anthropic-account"
ACCOUNT_SECRET = "secret"


def account_digest(kind: str, value: str) -> str:
    """A short digest that tells an account apart and cannot be turned back into `value`:
    SHA-256 over a fixed prefix, the source's `kind` (`ACCOUNT_UUID`, `ACCOUNT_SECRET`) and
    the value, cut to 12 hex digits. A UUID and a token of one account give different
    digests: an account is compared only with one from the same source. '' for an empty
    value."""
    if not value:
        return ""
    return hashlib.sha256(f"contraagent account\0{kind}\0{value}".encode()).hexdigest()[:12]


@dataclass(frozen=True)
class QuotaRefusal:
    """A launch refused for its quota (a 429, `Stop.RATE_LIMITED`): the cool-off the
    provider stated, in seconds, or None. A blown opencode-go quota answers
    `retry-after-ms=313534000`; honouring it is the difference between one 429 and a launch
    per probe until the quota returns."""

    retry_after_s: float | None = None


#: Web search queries kept per launch (`LaunchResult.web_queries`).
WEB_QUERIES_MAX = 50


def note_web_query(queries: list[str], query: object) -> None:
    """Append one web search's query, whitespace folded and cut at 200 characters,
    while `queries` holds fewer than `WEB_QUERIES_MAX`."""
    text = " ".join(str(query or "").split())[:200]
    if text and len(queries) < WEB_QUERIES_MAX:
        queries.append(text)


@dataclass
class LaunchResult:
    """The result of one launch (one `Backend.run`).

    `ok` means "ran to the end and is not hollow". The only
    `COMPLETED`-yet-not-ok shape is hollow: the agent ended after one turn
    without calling a tool, having written tool calls out as text instead
    (`Bash(...)`, `Write(...)`), so nothing it describes was done. A launch whose
    final message is its output (`OutputContract.from_message`) and passes its
    checks is not hollow: `run_until_valid` clears it.
    """

    label: str
    #: The coding agent that ran it (its registered `Backend` name).
    agent: str = ""
    stop: Stop = Stop.LAUNCH_FAILED
    ok: bool = False
    started_at: str = ""
    wall_s: float = 0.0
    exit_code: int | None = None
    cli_version: str = ""
    argv: list[str] = field(default_factory=list)
    model: str = ""
    credential: str = "ambient"
    api_key_source: str = ""
    session_id: str = ""
    num_turns: int | None = None
    duration_api_ms: int | None = None
    result_text: str = ""
    structured_output: dict[str, Any] | list[Any] | None = None
    cost_usd: float | None = None
    usage: Usage = field(default_factory=Usage)
    #: What the launch spent on models other than its own, by model, as the coding agent
    #: reports it. Their cost is in `cost_usd`; their tokens are not in `usage`.
    other_models: dict[str, OtherModel] = field(default_factory=dict)
    #: Every quota reading the launch received, oldest first (Claude Code sends one when a
    #: session starts or resumes; omp's is read at the launch's start).
    quota: list[QuotaReading] = field(default_factory=list)
    #: Set when the launch was refused for its quota, with the cool-off the provider stated.
    quota_refusal: QuotaRefusal | None = None
    permission_denials: list[dict[str, Any]] = field(default_factory=list)
    tool_uses: dict[str, int] = field(default_factory=dict)
    #: The queries of the web searches the agent made (Claude Code `WebSearch`, omp
    #: `web_search`), in call order; kept without a transcript too.
    web_queries: list[str] = field(default_factory=list)
    hollow: bool = False
    #: Event types the backend's reader does not know, with their counts: the coding
    #: agent sends something newer than the reader (omp's `KNOWN_EVENTS`).
    unread_events: dict[str, int] = field(default_factory=dict)
    # From `system/init`: resolved model (`--agent`/fallback may change it),
    # tool count, load failures.
    init_model: str = ""
    init_tools: int = 0
    init_errors: list[dict[str, Any]] = field(default_factory=list)
    # From `system/api_retry`: retry count and per-cause classification.
    api_retries: int = 0
    retry_errors: dict[str, int] = field(default_factory=dict)
    stderr_tail: str = ""
    raw_result: dict[str, Any] = field(default_factory=dict)
    # Output-file contract (`contraagent._internal.contracts.contract`): rounds spent (1 when
    # the first answer was on-contract; None when the launch carried no
    # contract), and the errors of each round that failed its checks, in
    # order: each was sent back as the next round, and when the launch
    # ended `INVALID_OUTPUT` the last is what still stood.
    rounds: int | None = None
    round_errors: list[list[str]] = field(default_factory=list)
    #: What each round cost on its own, in order (None for a round that reported no cost):
    #: `cost_usd` is their sum. Empty without a contract.
    round_costs: list[float | None] = field(default_factory=list)
    #: True when the output was taken out of a final message that wrapped it
    #: (`OutputContract.unwrap`); the whole message is kept beside the output file.
    unwrapped: bool = False
    #: What the plugin's stop hook sent back within the launch, before the agent
    #: ended its turn (Claude Code): one list of errors per time it objected.
    hook_errors: list[list[str]] = field(default_factory=list)
    #: The `Limits.context_budget` the launch ran under, and whether its peak context passed
    #: `Limits.context_warn_pct`% of it (`Limits.context_warned`; over folded rounds and
    #: hops, whether any did). Set by the runner, which knows the limits.
    context_budget: int | None = None
    context_warned: bool = False
    #: The context window of the model the launch ran on (tokens of one API call's input),
    #: as the coding agent reports it: in its stream, else in its model catalogue for the
    #: model as launched (`Backend.context_window`); None when it reports none. Over folded
    #: rounds and hops, the window of the launch whose call is the peak context (`fold_spend`).
    context_window: int | None = None

    @property
    def peak_context(self) -> int | None:
        """The launch's peak context: the largest input of one API call, its fresh input,
        cache read and cache write summed (`CallUsage.context`, as `Usage.resident` is the
        first call's). Over the rounds and hops `fold_spend` carried in, the largest of
        them. None when the coding agent's stream reported no API call."""
        return self.usage.peak_context if self.usage.calls else None

    @property
    def context_pct(self) -> float | None:
        """The peak context as % of `context_window`; None when either is unknown."""
        peak = self.peak_context
        if peak is None or not self.context_window:
            return None
        return round(100.0 * peak / self.context_window, 1)

    def as_dict(self) -> dict[str, Any]:
        d = {
            "ts": self.started_at,
            "label": self.label,
            "wall_s": round(self.wall_s, 1),
            "stop": self.stop.value,
            "ok": self.ok,
            "exit": self.exit_code,
            "agent": self.agent,
            "cli_version": self.cli_version,
            "argv": _short_argv(self.argv),
            "model": self.model,
            "session_id": self.session_id,
            "num_turns": self.num_turns,
            "duration_api_ms": self.duration_api_ms,
            "cost_usd": self.cost_usd,
            "usage": self.usage.as_dict(),
            "context_window": self.context_window,
            "context_pct": self.context_pct,
            "rate_limit": self._rate_limit(),
            "permission_denials": len(self.permission_denials),
            # What was denied (tool + input head): finds allow-list holes in logs.
            "denied": [
                {"tool": str(d.get("tool_name") or ""), "input": json.dumps(d.get("tool_input") or {}, ensure_ascii=False)[:160]}
                for d in self.permission_denials[:10]
            ],
            "tool_uses": dict(self.tool_uses),
            "hollow": self.hollow,
            "tool_args": {k: list(v)[:5] for k, v in (self.raw_result.get("tool_args") or {}).items()}
            if isinstance(self.raw_result, dict)
            else {},
            "web_queries": list(self.web_queries),
            "unread_events": dict(self.unread_events),
            "init_model": self.init_model,
            "init_tools": self.init_tools,
            "init_errors": self.init_errors,
            "api_retries": self.api_retries,
            "retry_errors": dict(self.retry_errors),
            "result_head": self.result_text[:200],
            "stderr_tail": self.stderr_tail[-300:],
            "rounds": self.rounds,
            "round_errors": [errors[:10] for errors in self.round_errors],
            "round_costs": list(self.round_costs),
            "unwrapped": self.unwrapped,
            "hook_errors": [errors[:10] for errors in self.hook_errors],
            "context_budget": self.context_budget,
            "context_warned": self.context_warned,
        }
        return d

    def _rate_limit(self) -> dict[str, Any] | None:
        """The latest quota reading and the quota refusal, as `launches.jsonl` records them
        in one: the reading's fields with the refusal's `retry_after_s`; `status` `quota`
        for a refusal with no reading."""
        reading = self.quota[-1] if self.quota else None
        if reading is None and self.quota_refusal is None:
            return None
        r = reading or QuotaReading(status="quota")
        return {
            "status": r.status,
            "five_hour_pct": r.five_hour_pct,
            "five_hour_resets_at": r.five_hour_resets_at,
            "seven_day_pct": r.seven_day_pct,
            "seven_day_resets_at": r.seven_day_resets_at,
            "retry_after_s": self.quota_refusal.retry_after_s if self.quota_refusal is not None else None,
            "observed_at": r.observed_at,
            "credential": r.credential,
            "account": r.account,
            "status_window": r.status_window,
            "threshold_pct": r.threshold_pct,
            "overage_status": r.overage_status,
            "overage_disabled_reason": r.overage_disabled_reason,
            "using_overage": r.using_overage,
            "windows": {k: w.model_dump(mode="json") for k, w in r.windows.items()},
            "extra": dict(r.extra),
        }

    def record(self, path: Path) -> None:
        """Append the telemetry line. Creates parent dirs."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        append_lines(path, [json.dumps(self.as_dict(), ensure_ascii=False)])


def _short_argv(argv: list[str]) -> list[str]:
    """Prompt bodies truncate to 200 chars (the element after `-p`)."""
    out = list(argv)
    for i, a in enumerate(out[:-1]):
        if a == "-p" and len(out[i + 1]) > 200:
            out[i + 1] = out[i + 1][:200] + "…"
    return out
