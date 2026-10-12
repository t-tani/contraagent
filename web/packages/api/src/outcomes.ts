// What happened to each task, in the terms a reader asks about: did it finish,
// fail, never start, or fail and then recover; and for a problem, which task
// caused it. Folded from the journal (finished attempts) and the plan (every
// queued task and what it waits for). Pure.
import type { JournalRow, Plan, PlanNode } from './types.js';

/**
 * - `done`: its last attempt completed, first time.
 * - `recovered`: it failed at least once, then its last attempt completed.
 * - `failed`: it ran and its last attempt failed.
 * - `not_started`: it never ran: an input was missing or off-contract, or it waits behind a task that failed.
 * - `running`, `waiting` (queued, not started yet), `skipped`.
 */
export type Outcome = 'done' | 'recovered' | 'failed' | 'not_started' | 'running' | 'waiting' | 'skipped';

export interface TaskOutcome {
  key: string;
  kind: string;
  unit: string;
  executor: 'agent' | 'python';
  outcome: Outcome;
  /** Its journal rows, oldest first (a refusal included). */
  attempts: JournalRow[];
  /** The rows of tries that actually ran (`isLaunched`), oldest first. */
  tries: JournalRow[];
  /** For a task that did not start: the failed task upstream that stopped it, if one is known. */
  cause: string | null;
}

const isOk = (r: JournalRow) => r.ok;

/**
 * The row is a real try: the task ran. A task refused before launch
 * (`invalid_input`) or skipped also gets a journal row, but never ran: it is
 * not a try, not an agent session, and not a failed attempt.
 */
export const isLaunched = (r: JournalRow): boolean => r.stop !== 'invalid_input' && r.stop !== 'skipped';

function outcomeOf(node: PlanNode | undefined, attempts: JournalRow[]): Outcome {
  if (node?.state === 'running') return 'running';
  const last = attempts[attempts.length - 1];
  if (!last) return node?.state === 'blocked' ? 'not_started' : 'waiting';
  if (last.stop === 'skipped') return 'skipped';
  if (last.stop === 'invalid_input') return 'not_started';
  if (isOk(last)) return attempts.some((a) => !isOk(a)) ? 'recovered' : 'done';
  return 'failed';
}

/** Every task of the run (from the plan, and from the journal for tasks the plan does not list), by key. */
export function taskOutcomes(journal: readonly JournalRow[], plan: Plan): Map<string, TaskOutcome> {
  const rows = new Map<string, JournalRow[]>();
  for (const r of journal) {
    let list = rows.get(r.key);
    if (!list) rows.set(r.key, (list = []));
    list.push(r);
  }
  const nodes = new Map(plan.nodes.map((n) => [n.key, n]));
  const keys = [...new Set([...plan.nodes.map((n) => n.key), ...rows.keys()])];
  const out = new Map<string, TaskOutcome>();
  for (const key of keys) {
    const node = nodes.get(key);
    const attempts = rows.get(key) ?? [];
    const first = attempts[0];
    out.set(key, {
      key,
      kind: node?.kind ?? first?.kind ?? '',
      unit: node?.unit ?? first?.unit ?? '',
      executor: node?.executor ?? first?.executor ?? 'agent',
      outcome: outcomeOf(node, attempts),
      attempts,
      tries: attempts.filter(isLaunched),
      cause: null,
    });
  }
  // A task that did not start: follow what it waits for to the task that actually failed.
  const rootOf = (key: string, seen: Set<string>): string | null => {
    for (const dep of nodes.get(key)?.after ?? []) {
      if (seen.has(dep)) continue;
      seen.add(dep);
      const d = out.get(dep);
      if (d?.outcome === 'failed') return dep;
      if (d?.outcome === 'not_started') {
        const r = rootOf(dep, seen);
        if (r) return r;
      }
    }
    return null;
  };
  for (const t of out.values()) if (t.outcome === 'not_started') t.cause = rootOf(t.key, new Set());
  return out;
}

export interface Problem {
  /** The task that failed. */
  task: TaskOutcome;
  /** The tasks that did not start because of it. */
  stopped: TaskOutcome[];
}

/**
 * What is wrong with the run, causes first: each failed task with the tasks
 * it stopped, then tasks that did not start for a reason of their own (an
 * input that was never produced by a task). Tasks that recovered are not problems.
 */
export function problems(outcomes: ReadonlyMap<string, TaskOutcome>): { failed: Problem[]; notStarted: TaskOutcome[] } {
  const failed = new Map<string, Problem>();
  for (const t of outcomes.values()) if (t.outcome === 'failed') failed.set(t.key, { task: t, stopped: [] });
  const notStarted: TaskOutcome[] = [];
  for (const t of outcomes.values()) {
    if (t.outcome !== 'not_started') continue;
    const p = t.cause ? failed.get(t.cause) : undefined;
    if (p) p.stopped.push(t);
    else notStarted.push(t);
  }
  const lastTs = (t: TaskOutcome) => t.attempts[t.attempts.length - 1]?.ts ?? '';
  return {
    failed: [...failed.values()].sort((a, b) => lastTs(b.task).localeCompare(lastTs(a.task))),
    notStarted,
  };
}

/** How many tasks the run has, and how they ended. */
export function outcomeCounts(outcomes: ReadonlyMap<string, TaskOutcome>): Record<Outcome, number> & { total: number } {
  const c = { done: 0, recovered: 0, failed: 0, not_started: 0, running: 0, waiting: 0, skipped: 0, total: 0 };
  for (const t of outcomes.values()) {
    c[t.outcome]++;
    c.total++;
  }
  return c;
}
