// The run's figures for the KPI tiles, from the journal. Pure.
import { isLaunched, isPython, retries, type JournalRow } from '@contraagent/api';

/**
 * The run's figures, from the journal. Only tries that ran count: a task
 * refused before launch (`invalid_input`) has a row but is not a try, not an
 * agent session and not a failed attempt; tasks are counted by `deriveRun`.
 */
export interface Kpis {
  /** Tries that ran. */
  attempts: number;
  python: number;
  /** Agent sessions: tries an agent ran. */
  launches: number;
  /** Tries that ran and failed. */
  bad: number;
  launchWall: number;
  pythonWall: number;
  /** Tries after a task's first, and the tasks they belong to. */
  retries: number;
  retriedTasks: number;
  /** The keys of the tasks that were retried / had fix-ups (to open one directly when it is the only one). */
  retriedKeys: string[];
  fixupKeys: string[];
  /** Fix-ups (sessions resumed with check errors), and the tasks that had any. */
  fixups: number;
  fixupTasks: number;
  /** Model switches after a rate limit, and the tasks that switched. */
  switches: number;
  switchTasks: number;
}

export function kpis(journal: readonly JournalRow[]): Kpis {
  const ran = journal.filter(isLaunched);
  const py = ran.filter(isPython);
  const llm = ran.filter((e) => !isPython(e));
  const wall = (xs: readonly JournalRow[]) => xs.reduce((a, e) => a + (e.wall_s || 0), 0);
  const keys = (xs: readonly JournalRow[]) => [...new Set(xs.map((e) => e.key))];
  const tasks = (xs: readonly JournalRow[]) => keys(xs).length;
  const retried = retries(journal);
  const fixed = ran.filter((e) => (e.rounds || 1) > 1);
  const switched = ran.filter((e) => (e.hops || []).length > 1);
  return {
    attempts: ran.length,
    python: py.length,
    launches: llm.length,
    bad: ran.filter((e) => !e.ok).length,
    launchWall: wall(llm),
    pythonWall: wall(py),
    retries: retried.length,
    retriedTasks: tasks(retried),
    retriedKeys: keys(retried),
    fixupKeys: keys(fixed),
    fixups: fixed.reduce((a, e) => a + (e.rounds || 1) - 1, 0),
    fixupTasks: tasks(fixed),
    switches: switched.reduce((a, e) => a + (e.hops || []).length - 1, 0),
    switchTasks: tasks(switched),
  };
}
