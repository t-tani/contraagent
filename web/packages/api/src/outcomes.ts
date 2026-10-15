// What happened to each task, in the terms a reader asks about: did it finish,
// fail, never start, or fail and then recover; and for a problem, which task
// caused it. Folded from the journal (finished attempts) and the plan (every
// queued task and what it waits for). Pure.
import type { DeferralCause, JournalRow, Plan, PlanNode, TaskState } from './types.js';

/**
 * - `done`: its last attempt completed, first time.
 * - `recovered`: a try that ran failed at least once, then its last attempt completed.
 * - `partial`: its last attempt was partial (stop `partial`): ok, its output a placeholder; not done, not failed.
 * - `failed`: it ran and its last attempt failed.
 * - `not_started`: it never ran: an input was missing or off-contract, or it waits behind a task that failed.
 * - `running`, `waiting` (queued, not started yet), `skipped`.
 */
export type Outcome = 'done' | 'recovered' | 'partial' | 'failed' | 'not_started' | 'running' | 'waiting' | 'skipped';

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
  /** For a task the queue deferred (never launched): why, as the run recorded it; '' when it was not. */
  deferred: string;
  /** The same as data, for words of a reader's language; null when it was not deferred, or the run recorded no cause. */
  deferredCause: DeferralCause | null;
  /** For a task deferred by a flow call's own deadline (`time_box`): that flow call's function (`module.qualname`); '' otherwise. */
  deferredIn: string;
}

/** The function of the flow call whose own deadline (`time_box`) deferred a task (`cause.flow_call`); '' for the run's deadline or another cause. */
export function deferredIn(plan: Pick<Plan, 'flow_calls'> | null | undefined, cause: DeferralCause | null | undefined): string {
  const id = cause?.flow_call;
  return id ? (plan?.flow_calls?.find((c) => c.id === id)?.function ?? '') : '';
}

const isOk = (r: JournalRow) => r.ok;

/**
 * The row is a real try: the task ran. A task refused before launch
 * (`invalid_input`) or skipped also gets a journal row, but never ran: it is
 * not a try, not an agent session, and not a failed attempt.
 */
export const isLaunched = (r: JournalRow): boolean => r.stop !== 'invalid_input' && r.stop !== 'skipped';

/**
 * A task's outcome from its plan node (if any) and its journal rows, oldest
 * first. `recovered` needs a try that ran and failed: a refusal before launch
 * (`invalid_input`) is not a failed attempt, so "not started, then done" is `done`.
 */
export function outcomeOf(node: Pick<PlanNode, 'state'> | undefined, attempts: readonly JournalRow[]): Outcome {
  if (node?.state === 'running') return 'running';
  const last = attempts[attempts.length - 1];
  if (!last) return node?.state === 'blocked' ? 'not_started' : 'waiting';
  if (last.stop === 'skipped') return 'skipped';
  if (last.stop === 'invalid_input') return 'not_started';
  if (last.stop === 'partial') return 'partial';
  if (isOk(last)) return attempts.some((a) => isLaunched(a) && !isOk(a)) ? 'recovered' : 'done';
  return 'failed';
}

/**
 * The retries in `journal`, oldest first: the tries that ran (`isLaunched`)
 * after an earlier try of the same task ran and failed, as in `recovered`. A
 * try after a refusal (`invalid_input`) is not a retry.
 */
export function retries(journal: readonly JournalRow[]): JournalRow[] {
  const failed = new Set<string>();
  const out: JournalRow[] = [];
  for (const r of journal) {
    if (!isLaunched(r)) continue;
    if (failed.has(r.key)) out.push(r);
    if (!isOk(r)) failed.add(r.key);
  }
  return out;
}

/**
 * A plan node's state as an outcome: `blocked` is `not_started` and `pending`
 * is `waiting`. Plan state `done` covers both `done` and `recovered`.
 */
export function planOutcome(state: TaskState): Outcome {
  switch (state) {
    case 'blocked':
      return 'not_started';
    case 'pending':
      return 'waiting';
    default:
      return state;
  }
}

/** Nothing is left to do for the task in this run: done, done after retrying, partial (its later tasks run on its output), or skipped. */
export const isFinished = (o: Outcome): boolean => o === 'done' || o === 'recovered' || o === 'partial' || o === 'skipped';

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
      deferred: node?.deferred ?? '',
      deferredCause: node?.deferred_cause ?? null,
      deferredIn: deferredIn(plan, node?.deferred_cause),
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

export interface Problems {
  /** Failed tasks, the latest first, each with the tasks it stopped. */
  failed: Problem[];
  /** Tasks that did not start for a reason of their own. */
  notStarted: TaskOutcome[];
  /** Partial tasks: ok, their output a placeholder. */
  partial: TaskOutcome[];
  /** Tasks done after retrying. */
  recovered: TaskOutcome[];
}

/**
 * What is wrong with the run, causes first: each failed task with the tasks
 * it stopped, then tasks that did not start for a reason of their own (an
 * input that was never produced by a task). Tasks that recovered are not
 * problems: they are listed apart, after them.
 */
export function problems(outcomes: ReadonlyMap<string, TaskOutcome>): Problems {
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
    partial: [...outcomes.values()].filter((t) => t.outcome === 'partial'),
    recovered: [...outcomes.values()].filter((t) => t.outcome === 'recovered'),
  };
}

/** How many tasks the run has, and how they ended. */
export function outcomeCounts(outcomes: ReadonlyMap<string, TaskOutcome>): Record<Outcome, number> & { total: number } {
  const c = { done: 0, recovered: 0, partial: 0, failed: 0, not_started: 0, running: 0, waiting: 0, skipped: 0, total: 0 };
  for (const t of outcomes.values()) {
    c[t.outcome]++;
    c.total++;
  }
  return c;
}

/**
 * One task of the run as a list shows it: what happened to it (`TaskOutcome`)
 * and what its tries add up to. A task that never ran has no tries: `wall_s` 0,
 * `last_ts` and `last_stop` ''.
 */
export interface TaskRow extends TaskOutcome {
  /** Its loop pass (the innermost loop of its flow path), from 1; null outside a loop. */
  pass: number | null;
  /** Time of its tries, summed, in seconds. */
  wall_s: number;
  /** When its last journal row was written; '' for none. */
  last_ts: string;
  /** The stop of its last journal row; '' for none. */
  last_stop: string;
  /** A waiting task: the keys of the earlier tasks it waits for that have not finished, in plan order. */
  waits_for: string[];
  /** The names it holds while it runs (`claims`); empty for none. */
  claims: string[];
  /** Its task call's `priority`: a tie-breaker in the queue's order; 0 by default. */
  priority: number;
}

/** The innermost loop pass of a plan node's flow path; null outside a loop (a pass not counted reads as the first). */
export function loopPass(node: Pick<PlanNode, 'flow'> | undefined): number | null {
  const frames = Array.isArray(node?.flow) ? node.flow : [];
  for (let i = frames.length - 1; i >= 0; i--) {
    const loops = frames[i]?.loops ?? [];
    const inner = loops[loops.length - 1];
    if (inner) return typeof inner.pass === 'number' && inner.pass >= 1 ? inner.pass : 1;
  }
  return null;
}

/**
 * Every task of the run, one row each, from its outcomes (`taskOutcomes`): the
 * plan joined with the journal, so a task that never ran (waiting, not started)
 * is a row too. In plan order. Views read them from `deriveRun(...).rows`.
 */
export function taskRows(outcomes: ReadonlyMap<string, TaskOutcome>, plan: Plan): TaskRow[] {
  const nodes = new Map(plan.nodes.map((n) => [n.key, n]));
  return [...outcomes.values()].map((t) => {
    const last = t.attempts[t.attempts.length - 1];
    const node = nodes.get(t.key);
    return {
      ...t,
      pass: loopPass(node),
      wall_s: t.tries.reduce((s, r) => s + (r.wall_s || 0), 0),
      last_ts: last?.ts ?? '',
      last_stop: last?.stop ?? '',
      waits_for:
        t.outcome === 'waiting' ? (node?.after ?? []).filter((d) => !isFinished(outcomes.get(d)?.outcome ?? 'waiting')) : [],
      claims: node?.claims ?? [],
      priority: node?.priority ?? 0,
    };
  });
}

/** The task to open by default: a running agent task, else the agent task that ran last (it has a transcript); never a Python task. Its key, or null. */
export function latestTask(rows: readonly TaskRow[]): string | null {
  const agent = rows.filter((t) => t.executor !== 'python');
  const running = agent.find((t) => t.outcome === 'running');
  if (running) return running.key;
  const ran = (t: TaskRow) => t.tries[t.tries.length - 1]?.ts ?? '';
  const last = agent.filter(ran).sort((a, b) => ran(b).localeCompare(ran(a)))[0];
  return last?.key ?? null;
}
