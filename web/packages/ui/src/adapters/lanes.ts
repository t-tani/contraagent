// The timeline (`ca-timeline`) as the lanes of `<cae-lanes>`: every attempt as
// a bar as long as it took, on its kind's lane, the running ones growing until
// now. Pure.
import { isLaunched, isPython, runRelative, type JournalRow, type TaskOutcome } from '@contraagent/api';
import type { Lane, LaneBar, LaneStyle } from '@contraagent/elements/lanes';
import { msg, str } from '@lit/localize';
import { getLocale } from '../core/i18n.js';
import { clockFormat } from '../words/clock-format.js';
import { facts, fmtDur, kindUnit } from '../words/format.js';
import { modelSwitch, notStartedCause, stopLabel } from '../words/index.js';

/** Finished tasks older than this before the newest are left out. */
export const TIMELINE_WINDOW_MS = 6 * 3600e3;

/** Something running now, as the timeline draws it. */
export interface LiveBar {
  kind: string;
  cls: 'llm' | 'py';
  /** Epoch ms it started. */
  t0: number;
}

/** A bar's look: `py`, `llm`, `bad` (ran and failed), `idle` (a task that never started), `run` (running). */
export type LaneStyleKey = 'py' | 'llm' | 'bad' | 'idle' | 'run';

export interface TimelineLanes {
  lanes: Lane[];
  /** Finished tasks left out of the window. */
  omitted: number;
}

// The same text as `toLocaleTimeString` with these options, from a format made once.
const hhmmss = (t: number) => clockFormat(getLocale(), false).format(new Date(t));

/**
 * The bars' looks and the legend: who ran it is an identity cue (Python
 * neutral, an agent violet), on the first row; failed and running are
 * statuses, each with a pattern besides the colour, on the second.
 */
export function laneStyles(): Record<LaneStyleKey, LaneStyle> {
  return {
    py: { label: msg('Python task'), color: 'var(--meter)' },
    llm: { label: msg('Agent task'), color: 'var(--agent)' },
    run: { label: msg('running'), color: 'var(--status-running)', pattern: 'striped', group: 1 },
    bad: { label: msg('failed'), color: 'var(--status-failed)', pattern: 'hatched', group: 1 },
    idle: { label: msg('not started'), color: 'var(--line2)', pattern: 'outline', group: 1 },
  };
}

/** A finished row's tooltip, one item per line: its name, how it ended, its time, its model, why it failed. */
function rowLabel(e: JournalRow, end: number, outcomes: ReadonlyMap<string, TaskOutcome>, run: string): string {
  // A task that never ran: its name and why, and no time, end or model.
  if (!isLaunched(e)) {
    const t = outcomes.get(e.key);
    const cause = e.stop === 'invalid_input' && t ? notStartedCause(t, outcomes, run) : '';
    return [kindUnit(e), cause ? msg(str`Not started: ${cause}`) : stopLabel(e.stop, e.reason), e.key].join('\n');
  }
  const sw = modelSwitch(e.hops, null, e.skipped_hops);
  const reason = e.reason && !e.ok ? runRelative(e.reason, run) : '';
  // One item per line: a task's name holds a `·` of its own.
  return [
    kindUnit(e),
    facts(stopLabel(e.stop), fmtDur(e.wall_s), msg(str`ended ${hhmmss(end)}`)),
    sw ? msg(str`Model switch: ${sw}`) : e.model ? msg(str`Model ${e.model}`) : '',
    reason,
    e.key,
  ]
    .filter(Boolean)
    .join('\n');
}

type FinishedBar = { lane: string; bar: LaneBar & { end: number } };

/** The finished bars last made for a journal, and what else they were made from. */
const made = new WeakMap<readonly JournalRow[], { outcomes: ReadonlyMap<string, TaskOutcome>; run: string; locale: string; bars: FinishedBar[] }>();

/** Each finished row's bar, on its lane: made again only when the journal, the outcomes, the run or the language changed. */
function finishedBars(journal: readonly JournalRow[], outcomes: ReadonlyMap<string, TaskOutcome>, run: string): readonly FinishedBar[] {
  const locale = getLocale();
  const had = made.get(journal);
  if (had && had.outcomes === outcomes && had.run === run && had.locale === locale) return had.bars;
  const bars: FinishedBar[] = [];
  journal.forEach((e, i) => {
    if (!e.ts) return;
    const end = Date.parse(e.ts);
    if (Number.isNaN(end)) return;
    const style: LaneStyleKey = !isLaunched(e) ? 'idle' : !e.ok ? 'bad' : isPython(e) ? 'py' : 'llm';
    bars.push({ lane: e.kind || '?', bar: { id: `j${i}`, style, start: end - (e.wall_s || 0) * 1000, end, label: rowLabel(e, end, outcomes, run) } });
  });
  made.set(journal, { outcomes, run, locale, bars });
  return bars;
}

/**
 * Every finished task as a bar on its kind's lane, in order of first start,
 * and the running ones (`end` null); finished tasks that ended more than six
 * hours before the newest are left out. Null when there is nothing to draw.
 */
export function lanesFromJournal(
  journal: readonly JournalRow[],
  live: readonly LiveBar[],
  outcomes: ReadonlyMap<string, TaskOutcome>,
  run: string,
): TimelineLanes | null {
  const bars = finishedBars(journal, outcomes, run);
  if (!bars.length && !live.length) return null;
  let newest = -Infinity;
  for (const x of bars) newest = Math.max(newest, x.bar.end);
  for (const a of live) newest = Math.max(newest, a.t0);
  const vis: { lane: string; bar: LaneBar }[] = bars.filter((x) => x.bar.end >= newest - TIMELINE_WINDOW_MS);
  const omitted = bars.length - vis.length;
  live.forEach((a, i) => vis.push({ lane: a.kind, bar: { id: `live${i}`, style: 'run', start: a.t0, end: null, label: `${a.kind}\n${msg('running')}` } }));
  const lanes = new Map<string, LaneBar[]>();
  for (const { lane, bar } of [...vis].sort((a, b) => a.bar.start - b.bar.start)) (lanes.get(lane) ?? lanes.set(lane, []).get(lane)!).push(bar);
  return { lanes: [...lanes].map(([name, bs]) => ({ id: name, label: name, bars: bs })), omitted };
}
