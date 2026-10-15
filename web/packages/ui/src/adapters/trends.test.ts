import type { ColumnsBody, HeatmapBody, LinesBody, TableBody, TilesBody, Trends } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { trendsQuery } from '../lib/trends.js';
import { trendSections } from './trends.js';

const usage = { input: 100, output: 20, cache_read: 1000, cache_creation: 50, calls: 3 };

export const TRENDS: Trends = {
  period: { from: '2026-10-13', to: '2026-10-14', tz: 'Asia/Tokyo', days: ['2026-10-13', '2026-10-14'] },
  totals: { runs: 2, attempts: 10, ok: 9, cost_usd: 1.5, wall_s: 600, tokens: usage },
  daily: [
    { day: '2026-10-13', cost_usd: { writer: 1, triage: 0.2 }, attempts: 6, ok: 6 },
    { day: '2026-10-14', cost_usd: { triage: 0.3 }, attempts: 4, ok: 3 },
  ],
  kinds: [
    { kind: 'triage', group: 'triage', executor: 'agent', tasks: 4, tasks_ok: 3, attempts: 5, ok: 4, wall_s: 100, wall_s_median: 20, cost_usd: 0.5, tokens: usage },
    { kind: 'writer', group: 'writer', executor: 'agent', tasks: 2, tasks_ok: 2, attempts: 5, ok: 5, wall_s: 500, wall_s_median: 90, cost_usd: 1, tokens: usage },
  ],
  models: [{ agent: 'claude', model: 'sonnet', sessions: 10, calls: 30, input: 100, output: 20, cache_read: 1000, cache_creation: 50, cost_usd: 1.5, wall_s: 600 }],
  stops: [
    { stop: 'completed', attempts: 9, kinds: { triage: 4, writer: 5 } },
    { stop: 'timeout', attempts: 1, kinds: { triage: 1 } },
  ],
  denials: [],
  quota: [{ credential: 'ambient', window: 'seven_day', daily_peak: [90, null], hourly_peak: [] }],
  rests: [],
  deferred: [{ run: 'r2', ts: '2026-10-14T03:00:00+00:00', key: 'writer-x', kind: 'writer', cause: 'deadline', reason: 'deadline' }],
  deferred_causes: { deadline: 1 },
  runs: [
    { run: 'r2', run_group: 'r2', host_id: '', started_at: '2026-10-14T01:00:00+00:00', finished_at: '', last_ts: '', attempts: 4, ok: 3, cost_usd: 0.3, wall_s: 100, stub: false },
    { run: 'r1', run_group: 'r1', host_id: '', started_at: '2026-10-13T01:00:00+00:00', finished_at: '', last_ts: '', attempts: 6, ok: 6, cost_usd: 1.2, wall_s: 500, stub: false },
  ],
  starts: { weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], hours: Array.from({ length: 24 }, (_, h) => h), counts: Array.from({ length: 7 }, (_, d) => Array.from({ length: 24 }, (_, h) => (d === 1 && h === 10 ? 2 : 0))) },
  bodies: {},
  panels: [],
} as unknown as Trends;

describe('trendSections', () => {
  const sections = trendSections(TRENDS, 'en');
  const by = (id: string) => sections.find((s) => s.id === id)?.body;

  it('gives a section for each fact the period has, and none for a fact it lacks', () => {
    expect(sections.map((s) => s.id)).toEqual(['totals', 'cost-by-day', 'kinds', 'models', 'usage', 'outcomes', 'deferred', 'starts', 'runs']);
    expect(trendSections({ ...TRENDS, totals: { ...TRENDS.totals, runs: 0 } }, 'en')).toEqual([]);
  });

  it('counts partly done tasks and attempts apart, in a column only when the period has them', () => {
    const cols = (b: unknown) => (b as TableBody).columns.map((c) => c.id);
    expect(cols(by('kinds'))).not.toContain('partial');
    expect(cols(by('runs'))).not.toContain('partial');
    const t = {
      ...TRENDS,
      totals: { ...TRENDS.totals, partial: 1 },
      kinds: TRENDS.kinds.map((k, i) => (i ? k : { ...k, tasks_ok: 2, tasks_partial: 1 })),
      runs: TRENDS.runs.map((r, i) => (i ? r : { ...r, partial: 1 })),
    } as Trends;
    const s = trendSections(t, 'en');
    const body = (id: string) => s.find((x) => x.id === id)?.body as TableBody;
    expect(cols(body('kinds'))).toContain('partial');
    expect(body('kinds').rows.map((r) => [r['kind'], r['partial']])).toEqual([['writer', 0], ['triage', 1]]);
    expect(body('runs').rows.map((r) => r['partial'])).toEqual([1, 0]);
    expect((s[0]?.body as TilesBody).tiles.find((x) => x.id === 'attempts')?.sub).toEqual([['Passed 90%', '1 partly done']]);
  });

  it('stacks the cost of each day by kind, the costliest kind first, a day without it empty', () => {
    const c = by('cost-by-day') as ColumnsBody;
    expect(c.x).toEqual(['Oct 13', 'Oct 14']);
    expect(c.stacked).toBe(true);
    expect(c.series.map((s) => [s.name, s.values])).toEqual([
      ['writer', [1, null]],
      ['triage', [0.2, 0.3]],
    ]);
  });

  it('writes the totals in words, an average of the days that cost anything', () => {
    const tiles = (by('totals') as TilesBody).tiles;
    expect(tiles.map((t) => [t.label, t.value])).toEqual([
      ['Runs', '2'],
      ['Attempts', '10'],
      ['Cost', '$1.50'],
      ['Tokens', '1.2k'],
      ['Time', '10m 00s'],
    ]);
    expect(tiles[1]!.sub).toEqual([['Passed 90%']]);
    expect(tiles[2]!.sub).toEqual([['$0.750 a day']]);
  });

  it('marks a kind with a task that did not pass, and lists the kinds by cost', () => {
    const t = by('kinds') as TableBody;
    expect(t.rows.map((r) => [r['kind'], r['_tone'] ?? null])).toEqual([
      ['writer', null],
      ['triage', 'attention'],
    ]);
  });

  it('draws utilization as fractions, a day with no reading empty, and run starts on a weekday grid', () => {
    expect((by('usage') as LinesBody).series[0]).toMatchObject({ name: 'default | weekly', values: [0.9, null] });
    const h = by('starts') as HeatmapBody;
    expect(h.y[0]).toBe('Mon');
    expect(h.values[1]![10]).toBe(2);
    expect(h.values[0]![0]).toBeNull();
  });

  it("names a model's own window, and the account when one identity was of two", () => {
    const quota = [
      { credential: 'sub', account: 'aaaaaa111111', window: 'seven_day', daily_peak: [50, 60], hourly_peak: [] },
      { credential: 'sub', account: 'bbbbbb222222', window: 'seven_day_opus', daily_peak: [10, 20], hourly_peak: [] },
      { credential: 'other', account: 'cccccc333333', window: 'five_hour', daily_peak: [5, 5], hourly_peak: [] },
    ];
    const rests = [{ ts: '2026-10-14T02:00:00+00:00', credential: 'sub', account: 'bbbbbb222222', event: 'start', run: 'r2' }];
    const s = trendSections({ ...TRENDS, quota, rests }, 'en');
    const names = (s.find((x) => x.id === 'usage')!.body as LinesBody).series.map((x) => x.name);
    expect(names).toEqual(['sub | account aaaaaa | weekly', 'sub | account bbbbbb | weekly (opus)', 'other | 5-hour']);
    expect((s.find((x) => x.id === 'rests')!.body as TableBody).rows[0]).toMatchObject({ identity: 'sub | account bbbbbb' });
  });

  it('says why a task was not run, in words', () => {
    expect((by('deferred') as TableBody).rows[0]).toMatchObject({ task: 'writer-x', cause: 'Past the deadline' });
  });
});

describe('trendsQuery', () => {
  const now = new Date('2026-10-14T20:00:00Z'); // already the 15th in Tokyo

  it('asks for the last days, today included, in the time zone', () => {
    expect(trendsQuery({ days: 7, from: '', to: '', tz: 'Asia/Tokyo', group: '' }, now)).toEqual({ from: '2026-10-09', to: '2026-10-15', tz: 'Asia/Tokyo' });
    expect(trendsQuery({ days: 14, from: '', to: '', tz: 'UTC', group: 'nightly' }, now)).toEqual({ from: '2026-10-01', to: '2026-10-14', tz: 'UTC', run_group: 'nightly' });
  });

  it('asks for two dates as they are', () => {
    expect(trendsQuery({ days: 0, from: '2026-09-01', to: '2026-09-30', tz: 'UTC', group: '' }, now)).toEqual({ from: '2026-09-01', to: '2026-09-30', tz: 'UTC' });
  });
});
