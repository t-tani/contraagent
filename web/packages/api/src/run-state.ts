// What the live feed of one run folds into, and the questions the views ask of it.
// Pure: no I/O, no clock unless passed in.
import type {
  CursorView,
  JournalRow,
  JsonObject,
  Outputs,
  Plan,
  Procs,
  RunFeedMessage,
  RunSummary,
  TaskRollup,
} from './types.js';

/** The newest rows kept; older ones drop off the front. */
export const JOURNAL_CAP = 4000;

export interface RunState {
  /** Finished attempts in arrival order, at most `JOURNAL_CAP`. */
  journal: JournalRow[];
  tasks: TaskRollup[];
  /** Null until the first `procs` message. */
  procs: Procs | null;
  plan: Plan;
  outputs: Outputs;
  /** Null for a run that keeps no cursor. */
  cursor: CursorView | null;
  panels: Record<string, JsonObject>;
  /** The feed's replay is over (`ready`): a journal row after this is new. */
  ready: boolean;
}

export function emptyRunState(): RunState {
  return {
    journal: [],
    tasks: [],
    procs: null,
    plan: { nodes: [], groups: [], flow_calls: [] },
    outputs: { contracts: [], tally: { valid: 0, invalid: 0, refused: 0, pending: 0, failed: 0, running: 0 } },
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
      case 'tasks':
        next = { ...next, tasks: a.data };
        break;
      case 'plan':
        next = { ...next, plan: a.data };
        break;
      case 'outputs':
        next = { ...next, outputs: a.data };
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

/** A finished attempt that neither completed nor was skipped. */
export const isBad = (row: { stop?: string | undefined }): boolean =>
  !!row.stop && row.stop !== 'completed' && row.stop !== 'skipped';

/** A Python task (the journal, plan, rollup and contracts say who executed it). */
export const isPython = (x: { executor?: string | undefined }): boolean => x.executor === 'python';

/** A stable identity for a journal row. */
export const rowId = (row: JournalRow): string => `${row.ts}|${row.key}`;

export const runRow = (runs: readonly RunSummary[], run: string): RunSummary | undefined =>
  runs.find((r) => r.run === run);

/** The run's process is alive (by the feed, or by the run list). */
export const isRunLive = (state: RunState, summary: RunSummary | undefined): boolean =>
  !!state.procs?.alive || !!summary?.running;

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

/** The task to open by default: a running one, else the most recent with a transcript. */
export function latestSlot(tasks: readonly TaskRollup[]): string | null {
  const llm = tasks.filter((t) => !isPython(t));
  const running = llm.find((t) => t.running);
  if (running) return running.slot;
  const last = llm.filter((t) => t.last_ts).sort((a, b) => b.last_ts.localeCompare(a.last_ts))[0];
  return last?.slot ?? null;
}
