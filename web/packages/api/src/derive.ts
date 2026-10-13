// Everything the views count and list about a run's tasks, derived once per
// state change: the outcomes, the rows, the counts and the problems. Every view
// reads `deriveRun(journal, plan)`, so "N of M tasks done" and every cause read
// the same on every screen. Pure; memoized on the identity of its inputs.
import { isLaunched, outcomeCounts, problems, taskOutcomes, taskRows } from './outcomes.js';
import type { Outcome, Problems, TaskOutcome, TaskRow } from './outcomes.js';
import type { HostSummary, JournalRow, Plan, PlanNode, RunSummary } from './types.js';

export interface RunCounts extends Record<Outcome, number> {
  total: number;
  /** done + recovered: "N of M tasks done" in every view. */
  doneTotal: number;
  /** done + recovered + skipped: nothing is left to do. */
  finished: number;
}

/** Tries (journal rows that ran) and rows of tasks that never started (a refusal, a skip). */
export interface TryCounts {
  tries: number;
  notStarted: number;
}

export interface RunDerived {
  /** Every task of the run, by key: the plan joined with the journal. */
  outcomes: ReadonlyMap<string, TaskOutcome>;
  /** The same tasks as rows, in plan order. */
  rows: readonly TaskRow[];
  counts: RunCounts;
  problems: Problems;
  /** The tasks' kinds, sorted. */
  kinds: readonly string[];
  tries: TryCounts;
}

const NO_PLAN: Plan = { nodes: [], groups: [] };

/** Run state replaces the journal and the plan arrays on every change (`reduceRun`), so their identity is the key. */
const memo = new WeakMap<readonly JournalRow[], WeakMap<Plan, RunDerived>>();

/**
 * What the views show about a run's tasks. Without a plan, the tasks are the
 * journal's only. The same `journal` and `plan` objects give the same result object.
 */
export function deriveRun(journal: readonly JournalRow[], plan: Plan | null | undefined = NO_PLAN): RunDerived {
  const p = plan ?? NO_PLAN;
  let byPlan = memo.get(journal);
  if (!byPlan) memo.set(journal, (byPlan = new WeakMap()));
  let d = byPlan.get(p);
  if (!d) byPlan.set(p, (d = derive(journal, p)));
  return d;
}

function derive(journal: readonly JournalRow[], plan: Plan): RunDerived {
  const outcomes = taskOutcomes(journal, plan);
  const c = outcomeCounts(outcomes);
  return {
    outcomes,
    rows: taskRows(outcomes, plan),
    counts: { ...c, doneTotal: c.done + c.recovered, finished: c.done + c.recovered + c.skipped },
    problems: problems(outcomes),
    kinds: [...new Set([...outcomes.values()].map((t) => t.kind))].sort(),
    tries: tryCounts(journal),
  };
}

/** Tries (journal rows that ran) and rows of tasks that never started: the one way the UI counts them. */
export function tryCounts(journal: readonly JournalRow[]): TryCounts {
  const tries = journal.filter(isLaunched).length;
  return { tries, notStarted: journal.length - tries };
}

export interface Progress {
  total: number;
  /** Plan state `done`: done and done after retrying. */
  done: number;
  skipped: number;
  /** Finished (done and skipped) out of all, in percent. */
  pct: number;
}

/** How far a run is, from the plan's groups. */
export function progress(plan: Plan): Progress {
  const total = plan.groups.reduce((a, g) => a + g.total, 0);
  const done = plan.groups.reduce((a, g) => a + g.done, 0);
  const skipped = plan.groups.reduce((a, g) => a + g.skipped, 0);
  return { total, done, skipped, pct: Math.round((100 * (done + skipped)) / Math.max(1, total)) };
}

/** How a run's tasks ended, from the plan: for a run that is over, in place of a progress bar. */
export function result(plan: Plan): { done: number; skipped: number; failed: number; notStarted: number; left: number } {
  const count = (...states: PlanNode['state'][]) => plan.nodes.filter((n) => states.includes(n.state)).length;
  return { done: count('done'), skipped: count('skipped'), failed: count('failed'), notStarted: count('blocked'), left: count('pending', 'running') };
}

/** How long a run took, wall clock: from its start to its last activity (null when unknown). */
export function elapsedS(r: Pick<RunSummary, 'started_at' | 'last_ts'> | undefined): number | null {
  const a = Date.parse(r?.started_at ?? '');
  const b = Date.parse(r?.last_ts ?? '');
  return Number.isNaN(a) || Number.isNaN(b) ? null : Math.max(0, (b - a) / 1000);
}

// --- a run's process and its host ----------------------------------------------

/**
 * A run's process, as every view names it: `running`; `unresponsive`, its host
 * last reported it alive and has stopped reporting (a hub only), so whether it
 * still runs is not known; or `stopped`.
 */
export type RunActivity = 'running' | 'unresponsive' | 'stopped';

/** What a run's process is doing, from the run list and (when its feed is open) the feed's `procs.alive`. */
export function runActivity(summary: Pick<RunSummary, 'running' | 'unresponsive'> | undefined, alive = false): RunActivity {
  if (alive || summary?.running) return 'running';
  return summary?.unresponsive ? 'unresponsive' : 'stopped';
}

/** The host that drives a run, from the host list. */
export const hostOf = (hosts: readonly HostSummary[] | undefined, summary: Pick<RunSummary, 'host_id'> | undefined): HostSummary | undefined =>
  summary?.host_id ? hosts?.find((h) => h.host_id === summary.host_id) : undefined;

/** A run's name without its host: a hub names a run `<run_id>@<host_id>`; any other name as it is. */
export function runIdOf(r: Pick<RunSummary, 'run' | 'host_id'>): string {
  const tail = r.host_id ? `@${r.host_id}` : '';
  return tail && r.run.endsWith(tail) && r.run.length > tail.length ? r.run.slice(0, -tail.length) : r.run;
}

/** One host's runs. */
export interface HostGroup {
  hostId: string;
  /** The host as the host list has it; undefined for a host the list does not have yet. */
  host: HostSummary | undefined;
  runs: RunSummary[];
}

const ACTIVITY_ORDER: Record<RunActivity, number> = { running: 0, unresponsive: 1, stopped: 2 };

/**
 * Runs by host, in the host list's order (then the host ids it does not have,
 * sorted): in each, the running runs, then those whose host stopped reporting,
 * then the rest, each in the order given (the run list's: most recent first).
 */
export function hostGroups(runs: readonly RunSummary[], hosts: readonly HostSummary[] = []): HostGroup[] {
  const by = new Map<string, RunSummary[]>();
  for (const r of runs) {
    const id = r.host_id ?? '';
    let list = by.get(id);
    if (!list) by.set(id, (list = []));
    list.push(r);
  }
  const order = [...hosts.map((h) => h.host_id).filter((id) => by.has(id)), ...[...by.keys()].filter((id) => !hosts.some((h) => h.host_id === id)).sort()];
  return order.map((hostId) => ({
    hostId,
    host: hosts.find((h) => h.host_id === hostId),
    runs: by.get(hostId)!.map((r, i) => [r, i] as const).sort(([a, i], [b, j]) => ACTIVITY_ORDER[runActivity(a)] - ACTIVITY_ORDER[runActivity(b)] || i - j).map(([r]) => r),
  }));
}
