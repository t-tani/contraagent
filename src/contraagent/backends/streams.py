"""Stream-event normalizer, dispatching on the stream format.

Every backend (`claude`, `omp`, `omp-rpc`, `opencode`, `pi`, `codex`) writes raw
per-launch lines to `launch.stream_path`, in four distinct wire
vocabularies: omp's/omp-rpc's/pi's `--mode json`/RPC shapes
(`assistantMessageEvent`/`toolCall`/`toolResult`/...), claude's own
`--output-format stream-json` shapes (Anthropic Messages API events),
opencode's `run --format json` parts (`step_finish`/`tool_use`/`text`/...) and
codex's `exec --json` items.
This module gives them a single call site: look up the stream format's own
`normalize_event`, in its own module (`backends/claude/stream.py`,
`backends/omp/trace.py`, `backends/opencode/wire.py`, `backends/codex/wire.py`),
and use its output as-is.

Every per-backend `normalize_event` emits the *same* renderable
shape (`message_update`/`tool_execution_start`/`notice`/...) that
a monitor UI already understands, so adding a backend
here needs no frontend change.

omp only writes `--mode json` events when launched with `--trace`; most
real tasks run without it and their stdout is plain text.
`_PLAINTEXT_FALLBACK` wraps such a line into the same renderable shape, so
a non-JSON line is shown rather than dropped.

Nothing in `backends/claude/stream.py`, `backends/omp/trace.py`, `backends/opencode/wire.py`
or `backends/codex/wire.py` imports this
module back — they are leaves this module depends on, never the reverse.
"""

from __future__ import annotations

import json

from contraagent.backends.claude import stream as claude_stream
from contraagent.backends.codex import wire as codex_wire
from contraagent.backends.omp import trace as omp_trace
from contraagent.backends.opencode import wire as opencode_wire

_NORMALIZERS = {
    "claude": claude_stream.normalize_event,
    "omp": omp_trace.normalize_event,
    # omp-rpc's NDJSON frames reuse the same message_update/toolCall/
    # tool_execution_end shapes trace mode's --mode json does (confirmed
    # against `backends/omp/rpc.py`'s own _Accumulator.feed()/_update()); its
    # RPC-only protocol frames (ready, negotiate_protocol, rpc_chunk,
    # response, prompt_result, session_stats/stats) aren't in
    # omp_trace.STREAM_FWD, so they're already dropped with no extra
    # code needed. Disclosed gap: a large payload split across several
    # rpc_chunk frames is invisible here (each chunk is a base64
    # fragment, meaningless alone) even though _Accumulator reassembles
    # it correctly for the real LaunchResult -- live reassembly would need
    # state carried across calls, which this one-line-at-a-time
    # normalizer does not keep.
    "omp-rpc": omp_trace.normalize_event,
    "opencode": opencode_wire.normalize_event,
    # pi sends the agent events omp was forked from (`backends/pi/wire.py`).
    "pi": omp_trace.normalize_event,
    # `codex exec --json`: always JSON, so no plain-text fallback.
    "codex": codex_wire.normalize_event,
}

# Backends that can run with trace off (omp's --mode json defaults on
# via OmpBackend.trace, but a task can still opt out): a non-JSON line
# from one of these is the agent's own plain-text narration, not noise,
# and renders as ordinary assistant text instead of being dropped.
# claude's --output-format stream-json is always JSON, so it carries no
# entry here -- a non-JSON claude line is genuinely unexpected input.
_PLAINTEXT_FALLBACK = {
    "omp": omp_trace.normalize_text_line,
}


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
    return name if name in _NORMALIZERS else "omp"


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
    normalize = _NORMALIZERS.get(format)
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
        fallback = _PLAINTEXT_FALLBACK.get(format)
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


def read_stream(format: str, stream_path, start: int = 0):
    """Yield `(next_offset, event)` for each renderable line of a launch's stream file.

    The live view of a running task: every backend appends raw lines to
    `launch.stream_path` as the agent works, and a viewer polls this with
    the last offset it saw to get only the new events. `start` is a byte
    offset; a partial trailing line (the agent is mid-write) is left for
    the next call. Lines that normalize to nothing are skipped.
    """
    with open(stream_path, "rb") as f:
        f.seek(start)
        offset = start
        for raw in f:
            if not raw.endswith(b"\n"):
                return
            offset += len(raw)
            for ev in normalize_stream_line(format, raw.decode("utf-8", "replace").rstrip("\n")):
                yield offset, ev
