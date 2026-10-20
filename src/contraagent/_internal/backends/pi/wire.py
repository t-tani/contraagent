"""pi's event wire (`pi --mode json`): the reader that folds it into a `LaunchResult`.

omp is a fork of pi and sends the same agent events, so `PiTraceReader` is omp's
`TraceReader` with pi's own list of events and pi's way of reporting a provider's
refusal: an assistant `message_end` whose `stopReason` is `error`, its `errorMessage`
the provider's status and body (`400 {"type":"error",...}`), on an exit status of 0.
The monitor renders the wire with omp's `normalize_event`, which reads these events
alike.

Tested on recordings of a real pi (`tests/fixtures/pi/<version>/`).
"""

from __future__ import annotations

import re

from contraagent._internal.backends.credentials import Ambient, Subscription
from contraagent._internal.backends.launch import Launch, LaunchResult, Stop
from contraagent._internal.backends.omp import wire as omp_wire
from contraagent._internal.backends.omp.wire import STREAM_FWD, TraceReader
from contraagent._internal.backends.refusal import QUOTA_RE, Ending, Signals

#: The monitor reads pi's events as omp's.
normalize_event = omp_wire.normalize_event

#: How pi words a refusal: a quota in the provider's words under any status, Anthropic's
#: answer to a subscription login with no extra usage left among them (given with status
#: 400: `You're out of extra usage`, `Third-party apps now draw from your extra usage`); the
#: provider's status at the head of `errorMessage` (`429 {...}`, `400 Bad Request`).
SIGNALS = Signals(
    quota=re.compile(f"{QUOTA_RE.pattern}|out of extra usage|draw from your extra usage", re.IGNORECASE),
    status=re.compile(r"^\s*(\d{3})\b"),
    stderr_stops=frozenset(),
)

#: What an `auth_failed` launch on a pi login adds to its reason (`agent_dir`): pi takes the
#: lock for a refresh beside the `auth.json` of the directory it runs with, so a pi run on
#: the user's own directory at the same time does not wait for a launch's refresh.
SHARED_LOGIN = (
    "pi refreshes a login under a lock beside auth.json in the agent directory it runs with; "
    "a pi the user runs on the same login at the same time takes another lock, and when the "
    "provider replaces the refresh token at each refresh, one of the two is left with a token "
    "that no longer works. Log in again with pi, and do not run pi yourself on this login while "
    "contraagent runs it."
)

#: The event types `pi --mode json` sends (`AgentSessionEvent` and the session header,
#: checked against pi 1.2.0's `docs/json.md` and the recordings in `tests/fixtures/pi/`).
#: A type outside this set is counted in `LaunchResult.unread_events`.
KNOWN_EVENTS = STREAM_FWD | {
    "session",
    "agent_settled",
    "queue_update",
    "entry_appended",
    "session_info_changed",
    "thinking_level_changed",
    "compaction_start",
    "compaction_end",
    "summarization_retry_scheduled",
    "summarization_retry_attempt_start",
    "summarization_retry_finished",
}
#: `message_update` kinds (`assistantMessageEvent.type`), from pi's `docs/json.md`: omp's but `image_end`.
KNOWN_UPDATES = omp_wire.KNOWN_UPDATES - {"image_end"}


class PiTraceReader(TraceReader):
    """omp's `TraceReader`, reading pi's events and pi's refusals."""

    agent = "pi"
    known_events = frozenset(KNOWN_EVENTS)
    known_updates = frozenset(KNOWN_UPDATES)
    signals = SIGNALS

    def __init__(self) -> None:
        super().__init__()
        #: The `stopReason` of the latest assistant message (`stop`, `length`, `toolUse`, `error`, `aborted`).
        self.stop_reason = ""

    def _message_end(self, ev: dict) -> None:
        super()._message_end(ev)
        message = ev.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            self.stop_reason = str(message.get("stopReason") or "")

    def _error(self, frame: dict) -> None:
        super()._error(frame)
        if self.api_status is None:
            self.api_status = SIGNALS.status_in(str(frame.get("errorMessage") or ""))

    def result(self, launch: Launch, agent: str, *, exit_code: int | None, killed: Stop | None) -> LaunchResult:
        """omp's, and, for an `auth_failed` launch on the logins of a pi agent directory
        (`ambient`, `subscription`), `SHARED_LOGIN` after the provider's words."""
        r = super().result(launch, agent, exit_code=exit_code, killed=killed)
        if r.stop is Stop.AUTH_FAILED and isinstance(launch.credential, (Ambient, Subscription)):
            r.stderr_tail = "\n".join(x for x in (r.stderr_tail, SHARED_LOGIN) if x)
        return r

    def ending(self, *, exit_code: int | None, killed: Stop | None) -> Ending:
        """The last assistant message decides. A refusal it reports comes first: a quota
        (429, or its words under any status) is `rate_limited`, 401/403 `auth_failed`, any
        other `api_error`; pi exits 0 after one, so the exit says nothing. A message that
        ends the turn (`stop`) completes the launch, with or without text: a model that
        has written its output file may end on an empty message."""
        e = super().ending(exit_code=exit_code, killed=killed)
        e.failed = bool(self.api_error) and not e.text
        e.completed = self.stop_reason == "stop" and exit_code in (0, None)
        return e
