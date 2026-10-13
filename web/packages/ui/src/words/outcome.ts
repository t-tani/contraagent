// A task's outcome in words: its status, a count of tasks in a state, a plan
// state. The code's terms (`recovered`, `blocked`) stay in the data and in
// tooltips; the words are the reader's (AGENTS.md "Words the UI shows").
import { planOutcome, type Outcome, type PlanNode } from '@contraagent/api';
import { msg, str } from '@lit/localize';

/** What happened to a task. */
export function outcomeLabel(o: Outcome): string {
  switch (o) {
    case 'done':
      return msg('done', { id: 'outcome-done', desc: 'The status of a task: done' });
    case 'recovered':
      return msg('done after retrying');
    case 'failed':
      return msg('failed');
    case 'not_started':
      return msg('not started');
    case 'running':
      return msg('running');
    case 'waiting':
      return msg('waiting');
    case 'skipped':
      return msg('skipped');
  }
}

/** What happened to a task, in a run that is `live` or over: a task still waiting when the run ended is "not run". */
export const taskStatusLabel = (o: Outcome, live: boolean): string => (o === 'waiting' && !live ? msg('not run') : outcomeLabel(o));

/** A plan node's state (the task matrix, progress by kind). */
export const planStateLabel = (s: PlanNode['state']): string => outcomeLabel(planOutcome(s));

/**
 * How many tasks are in a state, number first: "3 failed", "2 not started".
 * A count only: a cause ("review · zeta failed") has its own message.
 * `not_run`: waiting when the run ended.
 */
export function stateCount(s: Outcome | 'not_run', n: number): string {
  switch (s) {
    case 'done':
      return msg(str`${n} done`);
    case 'recovered':
      return msg(str`${n} done after retrying`);
    case 'failed':
      return msg(str`${n} failed`);
    case 'not_started':
      return msg(str`${n} not started`);
    case 'running':
      return msg(str`${n} running`);
    case 'waiting':
      return msg(str`${n} waiting`);
    case 'skipped':
      return msg(str`${n} skipped`);
    case 'not_run':
      return msg(str`${n} not run`);
  }
}
