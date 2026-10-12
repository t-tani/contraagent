// The list filters and row facts, pure: what the tasks and journal tabs show
// for a kind, a stop and a text.
import { isBad, isLaunched, type JournalRow, type Outcome, type TaskRollup } from '@contraagent/api';

/** Tasks of `kind` (all when ''), whose slot or last stop contains `q`. */
export function filterTasks(tasks: readonly TaskRollup[], kind: string, q: string): TaskRollup[] {
  const needle = q.toLowerCase();
  return tasks.filter((t) => (!kind || t.kind === kind) && (!needle || (t.slot + t.last_stop).toLowerCase().includes(needle)));
}

/** What happened to a task, from its rollup: the same outcome words every screen uses. */
export function rollupOutcome(t: TaskRollup): Outcome {
  if (t.running) return 'running';
  if (!t.attempts) return 'waiting';
  if (t.last_stop === 'skipped') return 'skipped';
  if (t.last_stop === 'invalid_input') return 'not_started';
  if (t.last_stop === 'completed') return t.ok < t.attempts ? 'recovered' : 'done';
  return 'failed';
}

const JOURNAL_TEXT = ['key', 'unit', 'stop', 'kind', 'route', 'reason'] as const;

/** Keys of tasks that ran more than once (a retry in a new session). */
export function retriedKeys(rows: readonly JournalRow[]): Set<string> {
  const n = new Map<string, number>();
  for (const r of rows) if (isLaunched(r)) n.set(r.key, (n.get(r.key) ?? 0) + 1);
  return new Set([...n].filter(([, c]) => c > 1).map(([k]) => k));
}

/** A row whose output was sent back to the agent at least once (a fix-up in the same session). */
export const hadFixup = (r: JournalRow): boolean => (r.rounds ?? 1) > 1;

/**
 * Journal rows of `kind` with `stop` that contain `q`. Besides a stop value,
 * `stop` takes 'bad' (every attempt that did not complete), 'fixup' (attempts
 * whose output was sent back for a fix-up) and 'retried' (every row of a task
 * that ran more than once).
 */
export function filterJournal(rows: readonly JournalRow[], kind: string, stop: string, q: string): JournalRow[] {
  const needle = q.toLowerCase();
  const retried = stop === 'retried' ? retriedKeys(rows) : null;
  return rows.filter((e) => {
    if (stop === 'bad' && !isBad(e)) return false;
    if (stop === 'fixup' && !hadFixup(e)) return false;
    if (retried && !retried.has(e.key)) return false;
    if (stop && !['bad', 'fixup', 'retried'].includes(stop) && e.stop !== stop) return false;
    if (kind && e.kind !== kind) return false;
    return !needle || JOURNAL_TEXT.some((k) => String(e[k] ?? '').toLowerCase().includes(needle));
  });
}

/** Rows per stop, most frequent first. */
export function journalTally(rows: readonly JournalRow[]): [string, number][] {
  const tally = new Map<string, number>();
  for (const e of rows) tally.set(e.stop || '?', (tally.get(e.stop || '?') ?? 0) + 1);
  return [...tally.entries()].sort((a, b) => b[1] - a[1]);
}

/**
 * Per task key: how many tries ran (refusals are not tries), and the row index
 * and try number of its last successful try.
 */
export function attemptFacts(rows: readonly JournalRow[]): Map<string, { count: number; lastOk: number; lastOkTry: number }> {
  const facts = new Map<string, { count: number; lastOk: number; lastOkTry: number }>();
  rows.forEach((r, i) => {
    const f = facts.get(r.key) ?? { count: 0, lastOk: -1, lastOkTry: 0 };
    if (isLaunched(r)) f.count++;
    if (r.ok) {
      f.lastOk = i;
      f.lastOkTry = (r.attempt ?? 0) + 1;
    }
    facts.set(r.key, f);
  });
  return facts;
}
