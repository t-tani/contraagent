// The trends page's request, from where the monitor is (its view route).
import type { PanelInfo, RunSummary, TrendsQuery } from '@contraagent/api';
import type { ViewRoute } from '../core/view-route.js';

/** The browser's time zone (an IANA name), `UTC` when it names none. */
export const browserZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

/** Today in time zone `tz`, YYYY-MM-DD. */
export function todayIn(tz: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
  } catch {
    return now.toISOString().slice(0, 10);
  }
}

/** The calendar day `n` days before `day` (YYYY-MM-DD). */
export function daysBefore(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

/** What `/api/trends` is asked for on the trends page: the view route's period, time zone and run group. */
export function trendsQuery(r: Pick<ViewRoute, 'days' | 'from' | 'to' | 'tz' | 'group'>, now: Date = new Date()): TrendsQuery {
  const tz = r.tz || browserZone();
  const period =
    r.days === 0 && r.from && r.to
      ? { from: r.from, to: r.to }
      : (() => {
          const to = todayIn(tz, now);
          return { from: daysBefore(to, Math.max(1, r.days) - 1), to };
        })();
  return { ...period, tz, ...(r.group ? { run_group: r.group } : {}) };
}

/** The run groups of the runs, each once, in the order the runs list them. */
export const runGroups = (runs: readonly RunSummary[]): string[] => [...new Set(runs.map((r) => r.run_group).filter((g): g is string => !!g))];

/** The tabs of the trends page: '' (the trends, with the trends panels of no `tab`), then each panel's `tab` once, in the order the first of its panels comes; only '' when no panel names one. */
export const trendsTabs = (panels: readonly PanelInfo[]): string[] => [
  '',
  ...new Set(panels.filter((p) => p.scope === 'trends' && p.tab).map((p) => p.tab!)),
];
