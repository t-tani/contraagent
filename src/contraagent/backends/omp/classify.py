"""The stop-classification order shared by every text/trace-based backend.

`OmpBackend.parse()` (text mode) and `TraceReader.result()` (omp's
`--mode json` and RPC wires) each read a
finished launch's observable shape — some text, an exit code, whether
anything was seen at all — into the same decision tree. Only the
rate-limit *sniff* differs per wire format (a char-window heuristic for
plain text, a regex over an accumulated provider error message for the
event wires); the order those signals are weighed in does not, so it lives
here once.
"""

from __future__ import annotations

from contraagent.backends.launch import Stop


def classify_text_result(
    text: str, *, saw_any: bool, exit_code: int | None, killed: Stop | None, rate_limited: bool, api_status: int | None = None
) -> Stop:
    """One Stop from a finished launch's observable shape.

    Order: killed first (a limit stop outranks anything the output
    shape might suggest); then a 429/provider rate-limit signal — the
    caller's own `rate_limited` verdict (its regex/char-window heuristic
    already applied) together with a literal `api_status == 429`, which
    is structural rather than a sniff and safe to own here; then a
    nonzero exit with no text (ERROR); then nothing observed at all
    (LAUNCH_FAILED) vs. something seen but no final text (NO_OUTPUT);
    else COMPLETED.
    """
    if killed is not None:
        return killed
    if rate_limited or api_status == 429:
        return Stop.RATE_LIMITED
    if exit_code not in (0, None) and not text:
        return Stop.ERROR
    if not text:
        return Stop.LAUNCH_FAILED if not saw_any else Stop.NO_OUTPUT
    return Stop.COMPLETED
