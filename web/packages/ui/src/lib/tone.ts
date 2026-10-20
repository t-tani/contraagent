// Which status colour (`Tone`, from @contraagent/elements) run data takes. A
// colour means a status, and only where that status applies: totals and
// measures stay neutral, a count of a problem takes the problem's colour only
// when it is above 0, and a whole is never coloured by its worst part (a run's
// dot is the exception: it is the run's own status). An element shows its tone
// as `data-tone` (none for neutral); the rules are in the elements' styles.
import type { ContractStatus, Outcome, RunActivity, Stop } from '@contraagent/api';
import { markOf, type Mark, type Tone } from '@contraagent/elements';

export type { Tone };

/** The tone of a count of a problem: the problem's tone above 0, neutral at 0 (a 0 is not good news to colour). */
export function problemTone(n: number, tone: Exclude<Tone, 'neutral'>): Tone {
  return n > 0 ? tone : 'neutral';
}

/**
 * A run's own status: running; attention when its host stopped reporting (a hub);
 * then how it ended: failed (a task failed), attention (tasks not started, or
 * partly done), done; neutral before it has tasks.
 */
export function runTone(activity: RunActivity, tasks: { total: number; failed: number; not_started: number; partial?: number } | undefined): Tone {
  if (activity === 'running') return 'running';
  if (activity === 'unresponsive') return 'attention';
  if (!tasks?.total) return 'neutral';
  if (tasks.failed) return 'failed';
  if (tasks.not_started || tasks.partial) return 'attention';
  return 'done';
}

/**
 * The tone of each stop. A `Record` over the generated `Stop` type: a stop the
 * schema adds fails type-checking here until it has a tone.
 */
const STOP_TONE: Readonly<Record<Stop, Tone>> = {
  completed: 'done',
  partial: 'attention',
  invalid_input: 'attention',
  skipped: 'muted',
  cancelled: 'muted',
  timeout: 'failed',
  max_turns: 'failed',
  budget: 'failed',
  context_budget: 'failed',
  stalled: 'failed',
  auth_failed: 'failed',
  api_error: 'failed',
  rate_limited: 'failed',
  refused: 'failed',
  aborted: 'failed',
  denied: 'failed',
  error: 'failed',
  no_output: 'failed',
  launch_failed: 'failed',
  invalid_output: 'failed',
  credential_mismatch: 'failed',
};

/** Every stop contraagent writes (`JournalRow.stop`), in schema order. */
export const ALL_STOPS = Object.keys(STOP_TONE) as readonly Stop[];

/** Whether a journal row's `stop` is one contraagent writes (a domain may write its own). */
export const isStop = (stop: string | null | undefined): stop is Stop => stop != null && Object.hasOwn(STOP_TONE, stop);

/** How one attempt ended (a journal row's `stop`), as a tone: a stop it does not know is a failure. */
export function stopTone(stop: string | null | undefined): Tone {
  return isStop(stop) ? STOP_TONE[stop] : 'failed';
}

/** What happened to a task, as a tone. */
export function outcomeTone(o: Outcome): Tone {
  switch (o) {
    case 'done':
    case 'recovered':
      return 'done';
    case 'failed':
      return 'failed';
    case 'partial':
    case 'not_started':
      return 'attention';
    case 'running':
      return 'running';
    case 'waiting':
    case 'skipped':
    case 'cancelled':
      return 'muted';
  }
}

/** A checked file's status, as a tone; neutral without one. */
export function contractTone(s: ContractStatus | null | undefined): Tone {
  switch (s) {
    case 'valid':
      return 'done';
    case 'invalid':
    case 'failed':
      return 'failed';
    case 'refused':
      return 'attention';
    case 'running':
      return 'running';
    case 'pending':
      return 'muted';
    case null:
    case undefined:
      return 'neutral';
  }
}

/** The mark of a task's outcome: a waiting task is ◌ too, though muted. */
export const outcomeMark = (o: Outcome): Mark | null => (o === 'waiting' ? 'pending' : markOf(outcomeTone(o)));
