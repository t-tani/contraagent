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

import json
import re

from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.backends.omp.classify import classify_text_result
from contraagent.backends.omp.trace import STREAM_FWD, TraceReader, is_rate_limited

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
#: `message_update` kinds (`assistantMessageEvent.type`), from pi's `docs/json.md`.
KNOWN_UPDATES = {
    "start",
    "done",
    "error",
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "toolcall_start",
    "toolcall_delta",
    "toolcall_end",
}

#: A provider's status at the head of pi's `errorMessage` (`429 {...}`, `400 Bad Request`).
_STATUS_RE = re.compile(r"^\s*(\d{3})\b")
#: Anthropic's answer to a subscription login with no extra usage left, given with status
#: 400: `You're out of extra usage`, `Third-party apps now draw from your extra usage`.
_EXTRA_USAGE_RE = re.compile(r"out of extra usage|draw from your extra usage", re.IGNORECASE)


def is_quota_refusal(text: str) -> bool:
    """A provider message that says the account's quota is spent."""
    return is_rate_limited(text) or bool(_EXTRA_USAGE_RE.search(text))


class PiTraceReader(TraceReader):
    """omp's `TraceReader`, reading pi's events and pi's refusals."""

    agent = "pi"
    known_events = KNOWN_EVENTS
    known_updates = KNOWN_UPDATES

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
            m = _STATUS_RE.match(str(frame.get("errorMessage") or ""))
            self.api_status = int(m.group(1)) if m else None

    def classify(self, text: str, *, exit_code: int | None, killed: Stop | None) -> Stop:
        """The last assistant message decides. A refusal it reports comes first: a quota
        (429, or its words under any status) is `rate_limited`, 401/403 `auth_failed`, any
        other `api_error`; pi exits 0 after one, so the exit says nothing. A message that
        ends the turn (`stop`) completes the launch, with or without text: a model that
        has written its output file may end on an empty message."""
        if killed is not None:
            return killed
        if self.api_status == 429 or is_quota_refusal(self.api_error):
            return Stop.RATE_LIMITED
        if self.api_error and not text:
            return Stop.AUTH_FAILED if self.api_status in (401, 403) else Stop.API_ERROR
        if self.stop_reason == "stop" and exit_code in (0, None):
            return Stop.COMPLETED
        return classify_text_result(text, saw_any=self.saw_any, exit_code=exit_code, killed=None, rate_limited=False)


def parse_events(launch: Launch, agent: str, stdout: bytes, exit_code: int | None, killed: Stop | None) -> LaunchResult:
    """A finished launch's `--mode json` lines, folded."""
    reader = PiTraceReader()
    for raw in stdout.split(b"\n"):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            reader.feed(ev)
    return reader.result(launch, agent, exit_code=exit_code, killed=killed)
