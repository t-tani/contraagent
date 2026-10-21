// The list filters and row facts, pure: what the tasks and journal tabs show
// for a kind, a stop and a text.
import { isBad, isLaunched, retries, type JournalRow, type Outcome, type TaskRow } from '@contraagent/api';

/** Tasks of `kind` (all when ''), whose kind, unit, claims, key or last stop contains `q`. */
export function filterTasks(tasks: readonly TaskRow[], kind: string, q: string): TaskRow[] {
  const needle = q.toLowerCase();
  return tasks.filter(
    (t) => (!kind || t.kind === kind) && (!needle || `${t.kind} ${t.unit} ${(t.claims ?? []).join(' ')} ${t.key} ${t.last_stop}`.toLowerCase().includes(needle)),
  );
}

/** Failed first, then not started, partly done, running and waiting; the rest after them. */
const RANK: Partial<Record<Outcome, number>> = { failed: 0, not_started: 1, partial: 2, running: 3, waiting: 4 };

/** The tasks list's order: by `RANK`, then the latest journal row first, then plan order. */
export function sortTasks(tasks: readonly TaskRow[]): TaskRow[] {
  return tasks
    .map((t, i) => ({ t, i }))
    .sort((a, b) => (RANK[a.t.outcome] ?? 9) - (RANK[b.t.outcome] ?? 9) || b.t.last_ts.localeCompare(a.t.last_ts) || a.i - b.i)
    .map((x) => x.t);
}

const JOURNAL_TEXT = ['key', 'unit', 'stop', 'kind', 'route', 'reason'] as const;

/** Keys of tasks that were retried: a try ran after one that ran and failed (`retries`). */
export const retriedKeys = (rows: readonly JournalRow[]): Set<string> => new Set(retries(rows).map((r) => r.key));

/**
 * The corrections of an attempt: each time its output's failed checks went back to the
 * agent session, by the stop hook within a round (`hook_errors`) or in a correction
 * round (`rounds` after the first). `max_corrections` bounds this count.
 */
export const correctionCount = (r: Pick<JournalRow, 'rounds' | 'hook_errors'>): number =>
  Math.max((r.rounds ?? 1) - 1, 0) + (r.hook_errors ?? []).length;

/** A row whose output was sent back to the agent at least once (a correction). */
export const hadFixup = (r: JournalRow): boolean => correctionCount(r) > 0;

/**
 * Journal rows of `kind` with `stop` that contain `q`. Besides a stop value,
 * `stop` takes 'bad' (every attempt that did not complete), 'fixup' (attempts
 * whose output was sent back for a fix-up), 'retried' (every row of a task
 * retried after a failed try, `retries`) and 'replayed' (attempts played from
 * their recordings, `JournalRow.replayed`).
 */
export function filterJournal(rows: readonly JournalRow[], kind: string, stop: string, q: string): JournalRow[] {
  const needle = q.toLowerCase();
  const retried = stop === 'retried' ? retriedKeys(rows) : null;
  return rows.filter((e) => {
    if (stop === 'bad' && !isBad(e)) return false;
    if (stop === 'fixup' && !hadFixup(e)) return false;
    if (retried && !retried.has(e.key)) return false;
    if (stop === 'replayed' && !e.replayed) return false;
    if (stop && !['bad', 'fixup', 'retried', 'replayed'].includes(stop) && e.stop !== stop) return false;
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
