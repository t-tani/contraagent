"""The hub's retention on a schedule (`Pruner`) and the words a `PruneReport` is written in.

`contraagent hub --retain-days N` runs a `Pruner` beside the server; `contraagent hub
prune` runs `Hub.prune` once and prints its report (`report_table`, `report_json`).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta

from contraagent._internal.hub.core import Hub, PruneReport

log = logging.getLogger(__name__)

#: Hours between prunes (`--prune-every`) by default, and for a retention shorter than
#: `SHORT_RETENTION_DAYS`.
PRUNE_EVERY_HOURS = 24.0
SHORT_PRUNE_EVERY_HOURS = 1.0
SHORT_RETENTION_DAYS = 7.0
#: Seconds after the server starts before the first prune.
FIRST_PRUNE_AFTER_S = 300.0
#: The reasons `Hub.prune` keeps an old run, in the order a report lists them.
KEPT_REASONS = ("live", "unresponsive", "no activity")


def default_prune_every(retain_days: float) -> float:
    """The hours between prunes for a retention of `retain_days`."""
    return SHORT_PRUNE_EVERY_HOURS if retain_days < SHORT_RETENTION_DAYS else PRUNE_EVERY_HOURS


def _kept_counts(report: PruneReport) -> Counter[str]:
    counts = Counter({reason: 0 for reason in KEPT_REASONS})
    counts.update(report.kept_runs.values())
    return counts


def report_line(report: PruneReport, swept: int | None = None) -> str:
    """One log line: what was removed and what old was kept, as counts; `swept`, the orphan
    segment objects `SegmentedStreamLogs.sweep` deleted, when it ran."""
    kept = " ".join(f"{reason.replace(' ', '-')}={n}" for reason, n in _kept_counts(report).items())
    line = (
        f"prune{' (dry run)' if report.dry_run else ''} cutoff={report.cutoff}"
        f" | removed runs={len(report.runs)} transcripts={len(report.transcripts)} segments={len(report.segments)}"
        f" blobs={len(report.blobs)} blob_bytes={report.blob_bytes} heartbeats={len(report.heartbeats)}"
        f" | kept runs: {kept} | kept heartbeats={len(report.kept_heartbeats)}"
    )
    return line if swept is None else f"{line} | swept segments={swept}"


def report_json(report: PruneReport) -> str:
    return json.dumps(dataclasses.asdict(report), indent=2)


def _size(n: int) -> str:
    size, unit = float(n), "B"
    for bigger in ("KiB", "MiB", "GiB"):
        if size < 1024:
            break
        size, unit = size / 1024, bigger
    return f"{n} B" if unit == "B" else f"{size:.1f} {unit}"


def report_table(report: PruneReport) -> str:
    """The report for a terminal: a count per kind, then the names."""
    removed = "Would remove" if report.dry_run else "Removed"
    rows = [
        (f"{removed}: runs", len(report.runs), ""),
        (f"{removed}: transcripts of runs no longer held", len(report.transcripts), ""),
        (f"{removed}: segments", len(report.segments), ""),
        (f"{removed}: blobs", len(report.blobs), _size(report.blob_bytes)),
        (f"{removed}: heartbeats", len(report.heartbeats), ""),
        *((f"Kept old runs: {reason}", n, "") for reason, n in _kept_counts(report).items()),
        ("Kept old heartbeats", len(report.kept_heartbeats), ""),
    ]
    width = max(len(r[0]) for r in rows)
    lines = [f"Cutoff: {report.cutoff}" + (" (dry run: nothing removed)" if report.dry_run else ""), ""]
    lines += [f"{label:<{width}}  {n:>6}  {extra}".rstrip() for label, n, extra in rows]
    named = [
        ("Runs", report.runs),
        ("Transcripts of runs no longer held", [f"{name} (run uid {uid})" for name, uid in report.transcripts]),
        ("Heartbeats", report.heartbeats),
        ("Kept old runs", [f"{name} ({why})" for name, why in sorted(report.kept_runs.items())]),
        ("Kept old heartbeats", [f"{host} ({why})" for host, why in sorted(report.kept_heartbeats.items())]),
    ]
    for title, names in named:
        if names:
            lines += ["", f"{title}:", *(f"  {n}" for n in names)]
    return "\n".join(lines) + "\n"


class Pruner:
    """A thread that calls `hub.prune(older_than=...)` every `every_s` seconds, the first time
    `first_after_s` after `start`, and then the transcript store's `sweep` when it has one.

    Each round logs one line (`report_line`). An exception is logged and the next round
    retries. `stop` ends the thread after the round it is in; call it before the transcript
    store's `shutdown`. `now` gives the time `Hub.prune` reckons from (default: the current
    time)."""

    def __init__(
        self,
        hub: Hub,
        *,
        older_than: timedelta,
        every_s: float,
        first_after_s: float = FIRST_PRUNE_AFTER_S,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.hub = hub
        self.older_than = older_than
        self.every_s = every_s
        self.first_after_s = first_after_s
        self.now = now
        self.rounds = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="hub-prune")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def _loop(self) -> None:
        delay = self.first_after_s
        while not self._stop.wait(delay):
            self.run_once()
            delay = self.every_s

    def run_once(self) -> PruneReport | None:
        """One round: prune, then sweep; the report, or None when the prune failed."""
        self.rounds += 1
        report: PruneReport | None = None
        try:
            report = self.hub.prune(older_than=self.older_than, now=self.now() if self.now else None)
        except Exception:
            log.exception("prune failed; the next one is in %gh", self.every_s / 3600)
        swept: int | None = None
        sweep = getattr(self.hub.streams, "sweep", None)
        if sweep is not None:
            try:
                swept = len(sweep())
            except Exception:
                log.exception("sweep of orphan segment objects failed; the next one is in %gh", self.every_s / 3600)
        if report is not None:
            log.info("%s", report_line(report, swept))
        elif swept is not None:
            log.info("swept segments=%d", swept)
        return report
