// A subscription's utilization as the coding agent reported it. Claude Code
// sends a reading when a session starts or resumes, never when it ends; every
// reading is account-wide (parallel tasks and anything else on the account
// share it). So a try has readings at its session starts, and the closest
// reading after it ended is whatever session started next. Pure.
import type { JournalRow, QuotaReading } from './types.js';

/** A reading, and the row (try) it came with. */
export interface SourcedReading {
  reading: QuotaReading;
  key: string;
  attempt: number;
}

const at = (r: QuotaReading): number => Date.parse(r.observed_at ?? '');

const usable = (r: QuotaReading): boolean =>
  !Number.isNaN(at(r)) && (r.five_hour_pct != null || r.seven_day_pct != null);

/** Every reading of the run, oldest first. */
export function runReadings(journal: readonly JournalRow[]): SourcedReading[] {
  const out: SourcedReading[] = [];
  for (const row of journal) {
    for (const reading of row.quota ?? []) {
      if (usable(reading)) out.push({ reading, key: row.key, attempt: row.attempt ?? 0 });
    }
  }
  return out.sort((a, b) => at(a.reading) - at(b.reading));
}

/** One account's utilization over the run (readings belong to the credential that reported them). */
export interface AccountUsage {
  credential: string;
  first: QuotaReading;
  last: QuotaReading;
}

/** Per account, the run's first and last reading; the account with the highest weekly use first. */
export function runAccounts(journal: readonly JournalRow[]): AccountUsage[] {
  const by = new Map<string, QuotaReading[]>();
  for (const { reading } of runReadings(journal)) {
    const c = reading.credential ?? '';
    let list = by.get(c);
    if (!list) by.set(c, (list = []));
    list.push(reading);
  }
  const out: AccountUsage[] = [];
  for (const [credential, list] of by) {
    const first = list[0];
    const last = list[list.length - 1];
    if (first && last) out.push({ credential, first, last });
  }
  return out.sort((a, b) => (b.last.seven_day_pct ?? 0) - (a.last.seven_day_pct ?? 0));
}

export interface TryQuota {
  /** The try's first reading: usage when its (first) session started. */
  start: QuotaReading | null;
  /** The first reading of the same account received after the try ended (`row.ts`), if any. */
  next: QuotaReading | null;
}

/** One try's readings: at its start, and the next one observed after it ended. */
export function tryQuota(row: JournalRow, readings: readonly SourcedReading[]): TryQuota {
  const own = (row.quota ?? []).filter(usable).sort((a, b) => at(a) - at(b));
  const ended = Date.parse(row.ts);
  const start = own[0] ?? null;
  const account = start?.credential ?? '';
  const next =
    start === null || Number.isNaN(ended)
      ? undefined
      : readings.find((r) => at(r.reading) > ended && (r.reading.credential ?? '') === account);
  return { start, next: next?.reading ?? null };
}
