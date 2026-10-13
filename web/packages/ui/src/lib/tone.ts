// Which status colour a value takes. A colour means a status, and only where
// that status applies: totals and measures stay neutral (''), a count of a
// problem takes the problem's colour only when it is above 0, and a whole is
// never coloured by its worst part (a run's dot is the exception: it is the
// run's own status). The classes are `t-<tone>`, `dot <tone>`, `kpi <tone>`.

/** A status colour, or '' for the neutral text colour. */
export type Tone = 'failed' | 'attention' | 'done' | 'running' | 'muted' | '';

/** The tone of a count of a problem: the problem's tone above 0, neutral at 0 (a 0 is not good news to colour). */
export function problemTone(n: number, tone: Exclude<Tone, ''>): Tone {
  return n > 0 ? tone : '';
}

/** A run's own status: running, failed (a task failed), attention (only tasks not started), done; '' before it has tasks. */
export function runTone(running: boolean, tasks: { total: number; failed: number; not_started: number } | undefined): Tone {
  if (running) return 'running';
  if (!tasks?.total) return '';
  if (tasks.failed) return 'failed';
  if (tasks.not_started) return 'attention';
  return 'done';
}

/** How one attempt ended (a journal row's `stop`), as a tone: every stop but these four is a failure. */
export function stopTone(stop: string | null | undefined): Tone {
  switch (stop) {
    case 'completed':
      return 'done';
    case 'invalid_input':
      return 'attention';
    case 'skipped':
      return 'muted';
    case 'running':
      return 'running';
    default:
      return 'failed';
  }
}
