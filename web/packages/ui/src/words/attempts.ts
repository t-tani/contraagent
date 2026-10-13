// Attempts and corrections, as the reader counts them.
import { runStarts } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, localTime } from './format.js';

/** The attempt as the reader counts it: "Attempt 1", "Attempt 2" ... (`JournalRow.attempt` is 0-based). */
export const attemptLabel = (attempt: number | null | undefined): string => msg(str`Attempt ${(attempt ?? 0) + 1}`);

/**
 * The names of one task's attempts that ran (its journal rows in order): "Attempt 1",
 * and "Attempt 1 | resumed run" for an attempt of a later start of the run (`runStarts`).
 * Where two names are still the same (a run resumed more than once), each also gets
 * the time its attempt ended.
 */
export function attemptNames(rows: readonly { attempt?: number | null | undefined; ts: string }[]): string[] {
  const starts = runStarts(rows);
  const names = rows.map((r, i) => (starts[i] ? facts(attemptLabel(r.attempt), msg('resumed run')) : attemptLabel(r.attempt)));
  return names.map((n, i) => (names.indexOf(n) === names.lastIndexOf(n) ? n : facts(n, localTime(rows[i]?.ts))));
}

/** `1 correction`, `3 corrections`; '' for none. */
export function correctionsText(n: number): string {
  if (n <= 0) return '';
  return n === 1 ? msg('1 correction') : msg(str`${n} corrections`);
}
