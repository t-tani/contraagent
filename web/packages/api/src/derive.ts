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
  /** done + recovered + partial + skipped + cancelled: nothing is left to do. */
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
    counts: { ...c, doneTotal: c.done + c.recovered, finished: c.done + c.recovered + c.partial + c.skipped + c.cancelled },
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
  /** Plan state `partial`: ok, the output a placeholder. */
  partial: number;
  skipped: number;
  /** Plan state `cancelled`: no flow call waited for it any longer. */
  cancelled: number;
  /** Finished (done, partial, skipped and cancelled) out of all, in percent. */
  pct: number;
}

/** How far a run is, from the plan's groups. */
export function progress(plan: Plan): Progress {
  const total = plan.groups.reduce((a, g) => a + g.total, 0);
  const done = plan.groups.reduce((a, g) => a + g.done, 0);
  const partial = plan.groups.reduce((a, g) => a + (g.partial ?? 0), 0);
  const skipped = plan.groups.reduce((a, g) => a + g.skipped, 0);
  const cancelled = plan.groups.reduce((a, g) => a + (g.cancelled ?? 0), 0);
  return { total, done, partial, skipped, cancelled, pct: Math.round((100 * (done + partial + skipped + cancelled)) / Math.max(1, total)) };
}

/** How a run's tasks ended, from the plan: for a run that is over, in place of a progress bar. */
export function result(plan: Plan): { done: number; partial: number; skipped: number; cancelled: number; failed: number; notStarted: number; left: number } {
  const count = (...states: PlanNode['state'][]) => plan.nodes.filter((n) => states.includes(n.state)).length;
  return {
    done: count('done'),
    partial: count('partial'),
    skipped: count('skipped'),
    cancelled: count('cancelled'),
    failed: count('failed'),
    notStarted: count('blocked'),
    left: count('pending', 'running'),
  };
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
  const n = r.run.length - (r.host_id?.length ?? 0) - 1;
  return r.host_id && n > 0 && r.run.endsWith(`@${r.host_id}`) ? r.run.slice(0, n) : r.run;
}

/** One host's runs. */
export interface HostGroup {
  hostId: string;
  /** The host as the host list has it; undefined for a host the list does not have yet. */
  host: HostSummary | undefined;
  runs: RunSummary[];
}

const ACTIVITY_ORDER: RunActivity[] = ['running', 'unresponsive', 'stopped'];

/**
 * Runs by host, in the host list's order (then the host ids it does not have,
 * sorted): in each, the running runs, then those whose host stopped reporting,
 * then the rest, each in the order given (the run list's: most recent first).
 */
export function hostGroups(runs: readonly RunSummary[], hosts: readonly HostSummary[] = []): HostGroup[] {
  const ids = [...new Set(runs.map((r) => r.host_id ?? ''))];
  const known = hosts.map((h) => h.host_id);
  const rank = (r: RunSummary) => ACTIVITY_ORDER.indexOf(runActivity(r));
  return [...known.filter((id) => ids.includes(id)), ...ids.filter((id) => !known.includes(id)).sort()].map((hostId) => ({
    hostId,
    host: hosts.find((h) => h.host_id === hostId),
    // A stable sort: equal runs keep the order given.
    runs: runs.filter((r) => (r.host_id ?? '') === hostId).sort((a, b) => rank(a) - rank(b)),
  }));
}
