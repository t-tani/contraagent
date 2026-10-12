// What the coding agents spent: tokens and cost, summed per attempt, task, kind
// and run from the journal. A row without usage or cost (a Python task, a task
// that never started, an agent that reports none) adds nothing and is not
// counted as zero. Pure.
import type { JournalRow } from './types.js';

export interface Spend {
  input: number;
  output: number;
  /** Input served from the prompt cache. */
  cache_read: number;
  /** Input written to the prompt cache. */
  cache_creation: number;
  /** API calls. */
  calls: number;
  /** USD as the coding agents report it; null when no row reported a cost. */
  cost: number | null;
  /** Rows that reported tokens or a cost. */
  reported: number;
}

export const emptySpend = (): Spend => ({ input: 0, output: 0, cache_read: 0, cache_creation: 0, calls: 0, cost: null, reported: 0 });

/** Every token of a spend: input, output and both cache kinds. */
export const totalTokens = (s: Spend): number => s.input + s.output + s.cache_read + s.cache_creation;

/** Add one row's usage and cost to `s` (in place); returns `s`. */
export function addRow(s: Spend, r: JournalRow): Spend {
  const u = r.usage;
  if (!u && (r.cost_usd === null || r.cost_usd === undefined)) return s;
  if (u) {
    s.input += u.input ?? 0;
    s.output += u.output ?? 0;
    s.cache_read += u.cache_read ?? 0;
    s.cache_creation += u.cache_creation ?? 0;
    s.calls += u.calls ?? 0;
  }
  if (r.cost_usd !== null && r.cost_usd !== undefined) s.cost = (s.cost ?? 0) + r.cost_usd;
  s.reported++;
  return s;
}

/** The spend of some rows; null when none of them reported any. */
export function spendOf(rows: readonly JournalRow[]): Spend | null {
  const s = emptySpend();
  for (const r of rows) addRow(s, r);
  return s.reported ? s : null;
}

/** One row's spend; null when it reported none. */
export const rowSpend = (r: JournalRow): Spend | null => spendOf([r]);

export interface SpendGroup {
  /** A task key, or a kind. */
  id: string;
  kind: string;
  unit: string;
  spend: Spend;
  /** Fraction (0..1) of the run's reported cost; null when the run reported none. */
  share: number | null;
}

function group(journal: readonly JournalRow[], idOf: (r: JournalRow) => string): SpendGroup[] {
  const by = new Map<string, SpendGroup>();
  const total = emptySpend();
  for (const r of journal) {
    addRow(total, r);
    const id = idOf(r);
    let g = by.get(id);
    if (!g) by.set(id, (g = { id, kind: r.kind, unit: r.unit ?? '', spend: emptySpend(), share: null }));
    addRow(g.spend, r);
  }
  const out = [...by.values()].filter((g) => g.spend.reported);
  for (const g of out) g.share = total.cost ? (g.spend.cost ?? 0) / total.cost : null;
  // Most expensive first; by tokens when no cost was reported.
  return out.sort((a, b) => (b.spend.cost ?? 0) - (a.spend.cost ?? 0) || totalTokens(b.spend) - totalTokens(a.spend));
}

/** Spend per task (key), most expensive first. */
export const spendByTask = (journal: readonly JournalRow[]): SpendGroup[] => group(journal, (r) => r.key);

/** Spend per kind, most expensive first. */
export const spendByKind = (journal: readonly JournalRow[]): SpendGroup[] =>
  group(journal, (r) => r.kind).map((g) => ({ ...g, unit: '' }));
