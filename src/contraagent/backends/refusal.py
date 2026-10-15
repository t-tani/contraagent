"""How a launch ended: one ladder of stops for every coding agent, read from what its wire said.

Each coding agent words a provider's refusal its own way, so each wire module holds its
`Signals`: the patterns of a quota refusal, a refused credential and a safety refusal in
the provider's words, and how its process ends when it has said nothing. What its reader
observed is an `Ending`; `classify_stop` weighs it in one order for every agent:

    killed by a limit -> quota (429) -> refused credential (401/403) -> safety refusal
    -> abort -> the agent's own cap -> any other API error -> the agent says it is done
    -> a nonzero exit with no answer -> nothing seen at all -> no answer -> completed

The steps from the refused credential to the API error apply only when the agent reports
that the session ended on an error (`Ending.failed`).

A refusal can also be printed only on stderr (omp's text mode, a CLI that dies at start):
`Backend.reclassify` reads it there, for the stops `Signals.stderr_stops` names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from contraagent.backends.launch import RateLimit, Stop

#: A quota refusal in a provider's words, as omp, pi and opencode pass them on.
QUOTA_RE = re.compile(
    r"usage limit exceeded|rate[_ -]?limit|too many requests|quota (?:exceeded|exhausted)|insufficient_quota",
    re.IGNORECASE,
)
_RETRY_AFTER_RE = re.compile(r"retry-after-ms=(\d+)|retry[_ -]?after[\"':= ]+(\d+(?:\.\d+)?)", re.IGNORECASE)

#: The stops a quota refusal on stderr turns into `rate_limited`: the failed ones. A launch
#: that produced its answer stays completed even if stderr mentions a limit (the agent retried
#: internally, and failing over would discard an answer already paid for).
FAILED_STOPS = frozenset({Stop.ERROR, Stop.NO_OUTPUT, Stop.API_ERROR})


def is_rate_limited(text: str, pattern: re.Pattern[str] = QUOTA_RE) -> bool:
    """Whether `text` words a quota refusal (`pattern`: a coding agent's own, else `QUOTA_RE`)."""
    return bool(pattern.search(text or ""))


def parse_retry_after(text: str) -> float | None:
    """The provider's own stated cool-off, in seconds.

    opencode-go answers a blown quota with `retry-after-ms=313534000`: three and a half
    days. Without it the router probes the primary on a timer and burns a launch per probe
    to learn the same thing; with it, one 429 buys a real schedule. Absent or unparsable:
    None, and the router falls back to its configured interval.
    """
    m = _RETRY_AFTER_RE.search(text or "")
    if not m:
        return None
    if m.group(1):
        return int(m.group(1)) / 1000.0
    try:
        return float(m.group(2))
    except (TypeError, ValueError):
        return None


def quota_refusal(words: str = "") -> RateLimit:
    """The reading of a launch refused for its quota, with the cool-off its words state."""
    return RateLimit(status="quota", retry_after_s=parse_retry_after(words))


@dataclass(frozen=True)
class Signals:
    """How one coding agent's wire says a launch was refused, and how its silence reads."""

    #: A quota refusal in the provider's words.
    quota: re.Pattern[str] = QUOTA_RE
    #: A refused credential in the provider's words (beside a 401/403 status).
    auth: re.Pattern[str] | None = None
    #: A safety refusal in the provider's words.
    refusal: re.Pattern[str] | None = None
    #: A provider's HTTP status inside its words (`429 {...}`, `status 401`).
    status: re.Pattern[str] | None = None
    #: True when a provider status, where the wire gives one, decides a quota refusal alone:
    #: its words are read only when it gives none.
    status_decides: bool = False
    #: True when a process that printed nothing failed to start if it exited nonzero, and had
    #: no output if it exited 0. Else a nonzero exit with no answer is an error, and nothing
    #: seen a launch failure.
    silence_is_startup: bool = False
    #: True when a nonzero exit with no answer, after the agent printed something, is an error;
    #: False reads it as no output.
    nonzero_exit_is_error: bool = True
    #: The stops a quota refusal on stderr turns into `rate_limited` (`Backend.reclassify`).
    stderr_stops: frozenset[Stop] = field(default=FAILED_STOPS)

    def quota_in(self, text: str) -> bool:
        return is_rate_limited(text, self.quota)

    def auth_in(self, text: str) -> bool:
        return bool(self.auth is not None and text and self.auth.search(text))

    def refusal_in(self, text: str) -> bool:
        return bool(self.refusal is not None and text and self.refusal.search(text))

    def status_in(self, text: str) -> int | None:
        """The first HTTP status `status` finds in `text`, or None."""
        m = self.status.search(text or "") if self.status is not None else None
        found = next((g for g in m.groups() if g), None) if m else None
        return int(found) if found else None


@dataclass
class Ending:
    """What a reader observed at the end of a launch, as `classify_stop` weighs it."""

    #: The limit the wrapper ended the launch on (timeout, stall, budget, ...), if it did.
    killed: Stop | None = None
    #: The process's exit status; None with no process exit to weigh (an RPC exchange).
    exit_code: int | None = None
    #: Whether the reader saw anything of the wire at all.
    saw_any: bool = False
    #: The agent's answer: its final text.
    text: str = ""
    #: The provider's words about a failure (or the text a refusal is looked for in).
    error: str = ""
    #: The provider's HTTP status, when the wire states one.
    status: int | None = None
    #: The agent reports that the session ended on an error.
    failed: bool = False
    #: The wire says the credential was refused, a safety refusal, an abort, in its own terms.
    auth: bool = False
    refused: bool = False
    aborted: bool = False
    #: The agent stopped on its own cap (`max_turns`, `budget`).
    capped: Stop | None = None
    #: The agent says the turn ended normally.
    completed: bool = False


def classify_stop(e: Ending, signals: Signals) -> Stop:
    """One stop from what a launch's wire said, in one order for every coding agent."""
    if e.killed is not None:
        return e.killed
    words_decide = not (signals.status_decides and e.status is not None)
    if e.status == 429 or (words_decide and signals.quota_in(e.error)):
        return Stop.RATE_LIMITED
    if e.failed:
        if e.status in (401, 403) or e.auth or signals.auth_in(e.error):
            return Stop.AUTH_FAILED
        if e.refused or signals.refusal_in(e.error):
            return Stop.REFUSED
        if e.aborted:
            return Stop.ABORTED
        if e.capped is not None:
            return e.capped
        return Stop.API_ERROR
    if e.completed:
        return Stop.COMPLETED
    if not e.saw_any and signals.silence_is_startup:
        return Stop.NO_OUTPUT if e.exit_code == 0 else Stop.LAUNCH_FAILED
    if e.exit_code not in (0, None) and not e.text and signals.nonzero_exit_is_error:
        return Stop.ERROR
    if not e.text:
        return Stop.NO_OUTPUT if e.saw_any else Stop.LAUNCH_FAILED
    return Stop.COMPLETED
