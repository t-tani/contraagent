// What the live feed of one run folds into, and the questions the views ask of it.
// Pure: no I/O, no clock unless passed in.
import { runActivity } from './derive.js';
import type {
  CursorView,
  Forecast,
  JournalRow,
  JsonObject,
  Outputs,
  Plan,
  Procs,
  RunFeedMessage,
  RunSummary,
} from './types.js';

/** The newest rows kept; older ones drop off the front. */
export const JOURNAL_CAP = 4000;

export interface RunState {
  /** Finished attempts in arrival order, at most `JOURNAL_CAP`. */
  journal: JournalRow[];
  /** Null until the first `procs` message. */
  procs: Procs | null;
  plan: Plan;
  outputs: Outputs;
  /** Null until the first `forecast` message (an export written before it has none). */
  forecast: Forecast | null;
  /** Null for a run that keeps no cursor. */
  cursor: CursorView | null;
  panels: Record<string, JsonObject>;
  /** The feed's replay is over (`ready`): a journal row after this is new. */
  ready: boolean;
}

export function emptyRunState(): RunState {
  return {
    journal: [],
    procs: null,
    plan: { nodes: [], groups: [], flow_calls: [] },
    outputs: { contracts: [], tally: { valid: 0, invalid: 0, refused: 0, pending: 0, failed: 0, running: 0 } },
    forecast: null,
    cursor: null,
    panels: {},
    ready: false,
  };
}

/** A feed message, or the feed (re)connecting: the server then replays the journal from the start. */
export type RunAction = RunFeedMessage | { event: 'connected' };

/** Fold a batch of actions into the state. The journal is copied once per batch, not per row. */
export function reduceRun(state: RunState, actions: readonly RunAction[]): RunState {
  let next = state;
  let rows: JournalRow[] | null = null;
  const flush = () => {
    if (!rows) return;
    const all = next.journal.concat(rows);
    next = { ...next, journal: all.length > JOURNAL_CAP ? all.slice(all.length - JOURNAL_CAP) : all };
    rows = null;
  };
  for (const a of actions) {
    if (a.event === 'journal') {
      (rows ??= []).push(a.data);
      continue;
    }
    flush();
    switch (a.event) {
      case 'connected':
        next = { ...next, journal: [], ready: false };
        break;
      case 'ready':
        next = { ...next, ready: true };
        break;
      case 'procs':
        next = { ...next, procs: a.data };
        break;
      case 'plan':
        next = { ...next, plan: a.data };
        break;
      case 'outputs':
        next = { ...next, outputs: a.data };
        break;
      case 'forecast':
        next = { ...next, forecast: a.data };
        break;
      case 'cursor':
        next = { ...next, cursor: a.data };
        break;
      default:
        next = { ...next, panels: { ...next.panels, [a.event.slice('panel:'.length)]: a.data } };
    }
  }
  flush();
  return next;
}

// --- selectors ----------------------------------------------------------------

/**
 * A finished attempt that neither completed, nor was partial (ok, its output a placeholder),
 * nor was skipped, nor was cancelled (no flow call waited for it any longer: no failure).
 */
export const isBad = (row: { stop?: string | undefined }): boolean =>
  !!row.stop && row.stop !== 'completed' && row.stop !== 'partial' && row.stop !== 'skipped' && row.stop !== 'cancelled';

/** A Python task (the journal, plan and contracts say who executed it). */
export const isPython = (x: { executor?: string | undefined }): boolean => x.executor === 'python';

/**
 * Which start of the run each of one task's journal rows (in journal order) belongs
 * to, 0 for the first start that ran it: a resumed run numbers a task's attempts
 * from 0 again, so a row whose attempt is not above the one before it begins the
 * next start that ran the task.
 */
export function runStarts(rows: readonly { attempt?: number | null | undefined }[]): number[] {
  let start = 0;
  return rows.map((r, i) => {
    const before = rows[i - 1];
    if (before && (r.attempt ?? 0) <= (before.attempt ?? 0)) start++;
    return start;
  });
}

/** A stable identity for a journal row. */
export const rowId = (row: JournalRow): string => `${row.ts}|${row.key}`;

export const runRow = (runs: readonly RunSummary[], run: string): RunSummary | undefined =>
  runs.find((r) => r.run === run);

/** The run's process is alive (by the feed, or by the run list): `runActivity` is `running`. */
export const isRunLive = (state: RunState, summary: RunSummary | undefined): boolean =>
  runActivity(summary, !!state.procs?.alive) === 'running';

/** Something running right now: an agent launch or a Python task. */
export interface Activity {
  /** `llm` for an agent launch, `py` for a Python task. */
  cls: 'llm' | 'py';
  /** Stable across updates: the task key, prefixed by kind of activity. */
  id: string;
  kind: string;
  /** The unit; '' for a task of the whole run. */
  unit: string;
  detail: string;
  /** Seconds it has run, as of the procs message. */
  ageS: number;
  /** The task key, for an agent launch (it has a transcript). */
  key: string;
}

export function liveActivities(procs: Procs | null): Activity[] {
  if (!procs) return [];
  return [
    ...procs.launches.map(
      (c): Activity => ({
        cls: 'llm',
        id: `c:${c.key}`,
        kind: c.kind || 'task',
        unit: c.unit || '',
        detail: [c.unit, c.model || c.role].filter(Boolean).join(' | '),
        ageS: c.age_s,
        key: c.key,
      }),
    ),
    ...procs.python_tasks.map(
      (p): Activity => ({
        cls: 'py',
        id: `p:${p.key}`,
        kind: p.kind || 'task',
        unit: p.unit || '',
        detail: p.unit || 'Python',
        ageS: p.age_s,
        key: '',
      }),
    ),
  ];
}
