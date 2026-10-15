"""Stream-event normalizer, dispatching on the stream format.

Every backend writes raw per-launch lines to `launch.stream_path`, in its own wire
vocabulary: omp's/omp-rpc's/pi's `--mode json`/RPC shapes
(`assistantMessageEvent`/`toolCall`/`toolResult`/...), claude's own
`--output-format stream-json` shapes (Anthropic Messages API events),
opencode's `run --format json` parts (`step_finish`/`tool_use`/`text`/...) and
codex's `exec --json` items. A stream format is a registered coding agent's name: its
`Backend.wire` module's `normalize_event` renders its lines, and with
`Backend.plaintext_stream` its `normalize_text_line` renders a line that is not JSON (omp's
text mode narrates in plain text). `register_normalizer` adds a format of its own.

Every `normalize_event` emits the *same* renderable shape
(`message_update`/`tool_execution_start`/`notice`/...) that a monitor UI already
understands, so adding a backend needs no frontend change.

omp-rpc's RPC-only protocol frames (ready, negotiate_protocol, rpc_chunk, response,
prompt_result, session_stats/stats) are not in omp's `STREAM_FWD`, so its normalizer drops
them. A large payload split across several rpc_chunk frames is not shown (each chunk is a
base64 fragment, meaningless alone), though the backend's reader reassembles it.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from contraagent.backends import backend_class

#: Stream formats a caller registered (`register_normalizer`), and their plain-text readers.
_NORMALIZERS: dict[str, Callable] = {}
_PLAINTEXT_FALLBACK: dict[str, Callable] = {}


def _normalizers(format: str) -> tuple[Callable | None, Callable | None]:
    """The event normalizer and the plain-text one of stream format `format`."""
    if format in _NORMALIZERS:
        return _NORMALIZERS[format], _PLAINTEXT_FALLBACK.get(format)
    cls = backend_class(format)
    wire = cls.wire if cls is not None else None
    if wire is None:
        return None, None
    return wire.normalize_event, (wire.normalize_text_line if cls is not None and cls.plaintext_stream else None)


def register_normalizer(format: str, normalize_event, plaintext=None) -> None:
    """Teach the monitor to render a custom `Backend`'s stream, as stream format `format`
    (usually the coding agent's name).

    `normalize_event(dict) -> dict | list[dict] | None` maps one parsed JSON event to the
    renderable shape (a list when one line holds several) (`message_update` / `tool_execution_start` / `notice` ...),
    or `{"type": "skip"}`. `plaintext(str) -> dict | None` handles a line that
    is not JSON (an agent that narrates in plain text); omit it to drop those.
    """
    _NORMALIZERS[format] = normalize_event
    if plaintext is not None:
        _PLAINTEXT_FALLBACK[format] = plaintext


def resolve_format(agent: str, aliases: dict[str, str] | None = None) -> str:
    """The stream format of coding agent `agent`: its alias, else its own name when a
    normalizer is registered, else `omp` — the lenient one, which renders
    plain-text narration instead of dropping it. A monitor process is not the
    process that registered a custom agent's normalizer, so an unknown name
    must degrade to something readable rather than to an empty transcript."""
    name = (aliases or {}).get(agent, agent)
    return name if _normalizers(name)[0] is not None else "omp"


# Upper bound on the prompt we hand the client from a launch marker, even
# if an older/larger marker exists on disk. `backends/process.py` already caps what
# it writes (`_MARKER_PROMPT_CAP`); this is the same ceiling applied on the
# read side so one line can never balloon a response.
_LAUNCH_PROMPT_CAP = 200_000


def _launch_event(ev: dict) -> dict:
    """A `launch` marker (written by `contraagent.backends.process.write_launch_marker`
    at the head of each invocation's stream append) passed through to the
    client, backend-agnostically. It is neither backend's wire vocabulary --
    `run_process` writes it for every backend alike -- so it is recognized
    here in the shared dispatcher, ahead of the per-backend normalizer that
    would otherwise drop it as unknown. Carries the exact argv, the submitted
    prompt (capped), the cwd, and a launch timestamp; the monitor uses it both
    as the per-invocation tab boundary and as the source of the command-line
    and prompt header each tab shows."""
    prompt = str(ev.get("prompt") or "")
    out: dict = {
        "type": "launch",
        "ts": ev.get("ts"),
        "argv": [str(a) for a in (ev.get("argv") or [])],
        "cwd": str(ev.get("cwd") or ""),
        "prompt": prompt[:_LAUNCH_PROMPT_CAP],
    }
    # Carry through the writer's own truncation count, plus any extra we trim
    # here, so the UI can honestly say how much of the prompt it is not showing.
    extra = max(0, len(prompt) - _LAUNCH_PROMPT_CAP)
    trunc = int(ev.get("prompt_truncated") or 0) + extra
    if trunc:
        out["prompt_truncated"] = trunc
    return out


def normalize_stream_line(format: str, raw_line: str) -> list[dict]:
    """The renderable events of one stream line, in order: none, one, or (a format whose
    one line holds a tool call and its result, opencode's) several.

    A line gives none for: an unrecognized `format` name, a blank `raw_line`,
    unparsable input in a format with no plaintext fallback, or an event the
    format's own `normalize_event` marks as `{"type": "skip"}` (its
    forward-set membership check, or an event shape it has nothing renderable
    to say about).
    """
    normalize, fallback = _normalizers(format)
    if normalize is None:
        return []
    line = raw_line.strip()
    if not line:
        return []
    try:
        ev = json.loads(line)
    except ValueError:
        ev = None
    if not isinstance(ev, dict):
        shown = fallback(line) if fallback else None
        return [shown] if shown else []
    # The launch marker is shared across backends (`run_process` writes it for
    # all of them), so it is handled here rather than in a per-backend
    # normalizer, which would see an unknown `type` and skip it.
    if ev.get("type") == "launch":
        return [_launch_event(ev)]
    out = normalize(ev)
    events = out if isinstance(out, list) else [out]
    return [e for e in events if e is not None and e.get("type") != "skip"]
