// The timeline's bars and lanes, from the journal and what is running. Pure.
import { isLaunched, isPython, type JournalRow } from '@contraagent/api';

/** Finished tasks older than this before the newest are left out. */
export const TIMELINE_WINDOW_MS = 6 * 3600e3;
const STEP_MS = 60e3;

/** Something running now, as the timeline draws it. */
export interface LiveBar {
  kind: string;
  cls: 'llm' | 'py';
  /** Epoch ms it started. */
  t0: number;
}

export interface TimelineBar {
  /** `py`, `llm`, `bad` (ran and failed), `idle` (a task that never started) for a finished row; `run` for a running one. */
  cls: 'py' | 'llm' | 'bad' | 'idle' | 'run';
  start: number;
  end: number;
  live: boolean;
  /** Which of its lane's stacked tracks it is drawn on: overlapping bars (a retry beside its failed try) get their own. */
  track: number;
  row?: JournalRow;
}

export interface TimelineLane {
  name: string;
  /** Any of its bars is an agent launch. */
  llm: boolean;
  bars: TimelineBar[];
  /** How many tracks its bars are stacked on (at least 1). */
  tracks: number;
}

export interface Timeline {
  t0: number;
  span: number;
  lanes: TimelineLane[];
  /** Finished tasks left out of the window. */
  hidden: number;
  live: boolean;
}

interface Placed extends Omit<TimelineBar, 'track'> {
  lane: string;
  liveCls?: 'llm' | 'py';
}

/** Every finished task as a bar on its kind's lane, running ones growing to `now`. Null when there is nothing to draw. */
export function timeline(journal: readonly JournalRow[], live: readonly LiveBar[], now: number): Timeline | null {
  const bars: Placed[] = [];
  for (const e of journal) {
    if (!e.ts) continue;
    const end = Date.parse(e.ts);
    if (Number.isNaN(end)) continue;
    const cls = !isLaunched(e) ? 'idle' : !e.ok ? 'bad' : isPython(e) ? 'py' : 'llm';
    bars.push({ lane: e.kind || '?', cls, start: end - (e.wall_s || 0) * 1000, end, live: false, row: e });
  }
  if (!bars.length && !live.length) return null;
  for (const a of live) bars.push({ lane: a.kind, cls: 'run', start: a.t0, end: now, live: true, liveCls: a.cls });
  const newest = Math.max(...bars.filter((x) => !x.live).map((x) => x.end), ...live.map((a) => a.t0));
  const vis = bars.filter((x) => x.end >= newest - TIMELINE_WINDOW_MS);
  const t0 = Math.min(...vis.map((x) => x.start));
  const t1 = live.length ? t0 + Math.ceil((now - t0 + 20e3) / STEP_MS) * STEP_MS : newest;
  const names: string[] = [];
  for (const x of [...vis].sort((a, b) => a.start - b.start)) if (!names.includes(x.lane)) names.push(x.lane);
  const lanes = names.map((name) => {
    const mine = vis.filter((x) => x.lane === name).sort((a, b) => a.start - b.start);
    // Each bar on the first track whose last bar has ended: overlapping bars do not hide each other.
    const ends: number[] = [];
    const bars = mine.map(({ cls, start, end, live: isLive, row }): TimelineBar => {
      let track = ends.findIndex((e) => e <= start);
      if (track < 0) track = ends.push(end) - 1;
      else ends[track] = end;
      return row ? { cls, start, end, live: isLive, track, row } : { cls, start, end, live: isLive, track };
    });
    return { name, llm: mine.some((x) => x.cls === 'llm' || x.liveCls === 'llm'), bars, tracks: Math.max(1, ends.length) };
  });
  return { t0, span: Math.max(1, t1 - t0), lanes, hidden: bars.length - vis.length, live: live.length > 0 };
}

/** A bar's left edge and width, in percent of the span; a live bar grows to `now`. */
export function barBox(b: TimelineBar, tl: Pick<Timeline, 't0' | 'span'>, now: number): { left: number; width: number } {
  const left = ((b.start - tl.t0) / tl.span) * 100;
  const end = b.live ? now : b.end;
  const w = ((end - b.start) / tl.span) * 100;
  return { left, width: Math.max(0.4, b.live ? Math.min(100 - left, w) : w) };
}
