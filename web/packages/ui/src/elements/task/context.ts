// What the parts of `ca-task-view` (its header and its panes) render from: the
// task's detail, the run around it and what its transcript reported, plus the
// facts they share about the task.
import {
  inputProblems,
  isLaunched,
  isPython,
  outcomeOf,
  runRelative,
  type JournalRow,
  type LaunchEvent,
  type Outcome,
  type Plan,
  type TaskDetail,
  type TaskOutcome,
  type UpstreamTask,
} from '@contraagent/api';
import { html } from 'lit';
import { emit, type RoundInfo } from '../../core/events.js';
import { kindUnit } from '../../words/format.js';
import { correctionsText, inputCause, notStartedCause } from '../../words/index.js';
import { type Producer } from '../../words/contract.js';

export interface TaskContext {
  /** The element: it sends the events. */
  host: HTMLElement;
  run: string;
  detail: TaskDetail;
  /** The task is running now. */
  live: boolean;
  /** The whole run's journal; may be empty. */
  journal: JournalRow[];
  plan: Plan | null;
  /** What happened to every task of the run, by key (empty without a plan). */
  outcomes: ReadonlyMap<string, TaskOutcome>;
  /** From the transcript: each round's launch, the round shown, the rounds. */
  launches: (LaunchEvent | null)[];
  shownRound: number;
  rounds: RoundInfo[];
}

/** A Python task: it runs in the pipeline's process, so it has no agent session and no transcript. */
export const isPy = (d: TaskDetail): boolean => isPython(d.io) || d.rows.some(isPython);

/** The coding agent ran for this task at least once. */
export const hadSession = (d: TaskDetail): boolean => !isPy(d) && (!!d.stream || d.launches.length > 0 || d.rows.some(isLaunched));

/** The task's state in the run: running, waiting, not started, done ... */
export const stateOf = (c: TaskContext): Outcome =>
  c.live ? 'running' : (c.outcomes.get(c.detail.key)?.outcome ?? outcomeOf(undefined, c.detail.rows));

/** The earlier task that writes `path`, by the task's own upstream list. */
export const writerOf = (c: TaskContext, path: string): UpstreamTask | undefined =>
  c.detail.io.upstream.find((u) => u.outputs.some((o) => o.path === path));

/** For a contract card: who writes a file, and what happened to that task. */
export const producerOf =
  (c: TaskContext) =>
  (path: string): Producer | undefined => {
    const u = writerOf(c, path);
    if (!u) return undefined;
    const o = u.outputs.find((x) => x.path === path);
    return { name: kindUnit(u), written: !!o?.file.exists, outcome: c.outcomes.get(u.key)?.outcome };
  };

/**
 * Why a task did not start, as a phrase after "Not started: ": the input its
 * refusal names and why it is not ready, or the earlier task that failed; '' when unknown.
 */
export function notStartedWhy(c: TaskContext): string {
  const d = c.detail;
  const own = c.outcomes.get(d.key) ?? { attempts: d.rows, cause: null };
  const cause = notStartedCause(own, c.outcomes, c.run, (path) => writerOf(c, path)?.key);
  if (cause) return cause;
  // A task the plan does not list (no outcomes): name the earlier task by its upstream entry.
  const p = inputProblems(d.rows[d.rows.length - 1]?.reason)[0];
  const w = p ? writerOf(c, p.path) : undefined;
  return p ? inputCause(runRelative(p.path, c.run), p.problem, w ? { name: kindUnit(w) } : undefined) : '';
}

/** The earlier task a task that did not start waits for: the one its refusal names, or the failed one upstream. */
export function culprit(c: TaskContext): { key: string; kind: string; unit: string; executor?: string } | undefined {
  const d = c.detail;
  const p = inputProblems(d.rows[d.rows.length - 1]?.reason)[0];
  const byKey = p?.producer ? c.outcomes.get(p.producer) : undefined;
  if (byKey) return byKey;
  const w = p ? writerOf(c, p.path) : undefined;
  if (w) return w;
  const cause = c.outcomes.get(d.key)?.cause;
  return cause ? c.outcomes.get(cause) : undefined;
}

/** `N corrections` for a journal row whose attempt needed them ('' when none). */
export const correctionsOf = (r: { rounds?: number | null }): string => correctionsText((r.rounds || 1) - 1);

/** A task's name as a link that sends `ca-open-task`. */
export const taskLink = (c: TaskContext, u: { key: string; kind: string; unit: string }) =>
  html`<a class="lnk" href="#" @click=${(e: Event) => {
    e.preventDefault();
    emit(c.host, 'ca-open-task', { key: u.key });
  }}>${kindUnit(u)}</a>`;
