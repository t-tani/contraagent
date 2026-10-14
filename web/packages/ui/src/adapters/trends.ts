// The trends (`/api/trends`) as the typed bodies `ca-panel-body` draws, in the UI's words:
// built from the raw numbers, never from the English `Trends.bodies`.
import type { Trends, TypedPanelBody } from '@contraagent/api';
import { credentialLabel } from '../words/credential.js';
import { fmtDur, tokenCount, usd } from '../words/format.js';
import { windowName } from '../words/quota.js';
import { deferredText } from '../words/rests.js';
import { stopLabel } from '../words/stop.js';
import { dayLabel, modelName, passedShare, perDay, restEvent, trendWords, usageLine, weekdayLabels } from '../words/trends.js';

/** The sections of the trends, one body each, in the order a reader checks them: their key and their body. */
export interface TrendSection {
  id: string;
  body: TypedPanelBody;
  /** The section spans the page's width (a chart over the days, a wide table). */
  wide?: boolean;
}

const tokensOf = (t: { input?: number; output?: number; cache_read?: number; cache_creation?: number }): number =>
  (t.input ?? 0) + (t.output ?? 0) + (t.cache_read ?? 0) + (t.cache_creation ?? 0);

/** The trends as sections; empty when no run worked in the period. */
export function trendSections(t: Trends, locale?: string): TrendSection[] {
  if (!t.totals.runs) return [];
  const w = trendWords();
  const days = t.period.days.map((d) => dayLabel(d, locale));
  const out: TrendSection[] = [];

  const tot = t.totals;
  const spent = t.daily.filter((d) => Object.keys(d.cost_usd).length).length;
  out.push({
    id: 'totals',
    wide: true,
    body: {
      type: 'tiles',
      collapsed: false,
      tiles: [
        { id: 'runs', label: w.runs, value: String(tot.runs), sub: [] },
        { id: 'attempts', label: w.attempts, value: String(tot.attempts), sub: [[passedShare(tot.attempts ? `${Math.round((tot.ok / tot.attempts) * 100)}%` : '—')]] },
        { id: 'cost', label: w.cost, value: tot.cost_usd == null ? '—' : usd(tot.cost_usd), sub: spent && tot.cost_usd != null ? [[perDay(usd(tot.cost_usd / spent))]] : [] },
        { id: 'tokens', label: w.tokens, value: tokenCount(tokensOf(tot.tokens)), sub: [[`${w.input} ${tokenCount(tot.tokens.input)} | ${w.output} ${tokenCount(tot.tokens.output)}`]] },
        { id: 'time', label: w.time, value: fmtDur(tot.wall_s), sub: [] },
      ],
    },
  });

  // Cost by day, stacked by kind (or group): a magnitude over time, parts of each day's whole.
  const series = [...new Set(t.daily.flatMap((d) => Object.keys(d.cost_usd)))];
  const byCost = series
    .map((s) => ({ s, total: t.daily.reduce((a, d) => a + (d.cost_usd[s] ?? 0), 0) }))
    .sort((a, b) => b.total - a.total)
    .map((x) => x.s);
  out.push({
    id: 'cost-by-day',
    wide: true,
    body: {
      type: 'columns',
      collapsed: false,
      title: w.costByDay,
      x: days,
      unit: 'usd',
      stacked: true,
      series: byCost.map((s) => ({ name: s, values: t.daily.map((d) => d.cost_usd[s] ?? null) })),
    },
  });

  out.push({
    id: 'kinds',
    wide: true,
    body: {
      type: 'table',
      collapsed: false,
      title: w.kinds,
      columns: [
        { id: 'kind', label: w.kind },
        ...(t.kinds.some((k) => k.group && k.group !== k.kind) ? [{ id: 'group', label: w.group }] : []),
        { id: 'tasks', label: w.tasks, align: 'end' as const, format: 'number' as const },
        { id: 'passed', label: w.tasksPassed, align: 'end' as const, format: 'pct' as const },
        { id: 'attempts', label: w.attempts, align: 'end' as const, format: 'number' as const },
        { id: 'median', label: w.medianTime, align: 'end' as const, format: 'duration' as const },
        { id: 'wall', label: w.totalTime, align: 'end' as const, format: 'duration' as const },
        { id: 'tokens', label: w.tokens, align: 'end' as const, format: 'tokens' as const },
        { id: 'cost', label: w.cost, align: 'end' as const, format: 'usd' as const, bar: true },
      ],
      rows: [...t.kinds]
        .sort((a, b) => (b.cost_usd ?? 0) - (a.cost_usd ?? 0) || b.attempts - a.attempts)
        .map((k) => ({
          kind: k.kind,
          group: k.group,
          tasks: k.tasks,
          passed: k.tasks ? k.tasks_ok / k.tasks : null,
          attempts: k.attempts,
          median: k.wall_s_median,
          wall: k.wall_s,
          tokens: tokensOf(k.tokens),
          cost: k.cost_usd,
          ...(k.tasks_ok < k.tasks ? { _tone: 'attention' as const } : {}),
        })),
    },
  });

  if (t.models.length) {
    out.push({
      id: 'models',
      wide: true,
      body: {
        type: 'table',
        collapsed: false,
        title: w.models,
        columns: [
          { id: 'model', label: w.model },
          { id: 'sessions', label: w.sessions, align: 'end', format: 'number' },
          { id: 'calls', label: w.calls, align: 'end', format: 'number' },
          { id: 'input', label: w.input, align: 'end', format: 'tokens' },
          { id: 'output', label: w.output, align: 'end', format: 'tokens' },
          { id: 'cache_read', label: w.cacheRead, align: 'end', format: 'tokens' },
          { id: 'cache_write', label: w.cacheWrite, align: 'end', format: 'tokens' },
          { id: 'cost', label: w.cost, align: 'end', format: 'usd', bar: true },
          { id: 'wall', label: w.time, align: 'end', format: 'duration' },
        ],
        rows: t.models.map((m) => ({
          model: modelName(m.agent, m.model),
          sessions: m.sessions,
          calls: m.calls,
          input: m.input,
          output: m.output,
          cache_read: m.cache_read,
          cache_write: m.cache_creation,
          cost: m.cost_usd,
          wall: m.wall_s,
        })),
      },
    });
  }

  // The utilization of each identity and window: a level over time, one line each.
  if (t.quota.length) {
    out.push({
      id: 'usage',
      wide: true,
      body: {
        type: 'lines',
        collapsed: false,
        title: w.usage,
        x: days,
        unit: 'pct',
        series: t.quota.map((q) => ({
          name: usageLine(credentialLabel(q.credential) || q.credential, windowName(q.window)),
          values: q.daily_peak.map((p) => (p == null ? null : p / 100)),
        })),
      },
    });
  }

  const bad = t.stops.filter((s) => s.stop !== 'completed' && s.stop !== 'skipped');
  if (bad.length) {
    out.push({
      id: 'outcomes',
      body: {
        type: 'table',
        collapsed: false,
        title: w.outcomes,
        columns: [
          { id: 'outcome', label: w.outcome },
          { id: 'attempts', label: w.attempts, align: 'end', format: 'number', bar: true },
          { id: 'kinds', label: w.kinds },
        ],
        rows: bad.map((s) => ({
          outcome: stopLabel(s.stop),
          attempts: s.attempts,
          kinds: Object.entries(s.kinds)
            .sort((a, b) => b[1] - a[1])
            .map(([k, n]) => `${k} ${n}`)
            .join(' | '),
          _tone: 'failed' as const,
        })),
      },
    });
  }

  if (t.denials.length) {
    out.push({
      id: 'denials',
      body: {
        type: 'table',
        collapsed: false,
        title: w.denials,
        columns: [
          { id: 'tool', label: w.tool },
          { id: 'count', label: w.calls, align: 'end', format: 'number', bar: true },
          { id: 'kinds', label: w.kinds },
        ],
        rows: t.denials.map((d) => ({
          tool: d.tool,
          count: d.count,
          kinds: Object.entries(d.kinds)
            .map(([k, n]) => `${k} ${n}`)
            .join(' | '),
        })),
      },
    });
  }

  if (t.deferred.length) {
    out.push({
      id: 'deferred',
      body: {
        type: 'table',
        collapsed: false,
        title: w.deferred,
        columns: [
          { id: 'when', label: w.when, format: 'datetime' },
          { id: 'task', label: w.task },
          { id: 'cause', label: w.cause },
          { id: 'run', label: w.run },
        ],
        rows: [...t.deferred]
          .sort((a, b) => b.ts.localeCompare(a.ts))
          .map((d) => ({
            when: d.ts,
            task: d.key,
            cause: deferredText({ cause: d.cause }, d.reason),
            run: d.run,
            _tone: 'attention' as const,
          })),
      },
    });
  }

  if (t.rests.length) {
    out.push({
      id: 'rests',
      body: {
        type: 'table',
        collapsed: false,
        title: w.rests,
        columns: [
          { id: 'when', label: w.when, format: 'datetime' },
          { id: 'identity', label: w.identity },
          { id: 'event', label: w.event },
          { id: 'run', label: w.run },
        ],
        rows: [...t.rests]
          .sort((a, b) => (b.ts ?? '').localeCompare(a.ts ?? ''))
          .map((r) => ({ when: r.ts, identity: credentialLabel(r.credential) || r.credential || '—', event: restEvent(r.event), run: r.run })),
      },
    });
  }

  // When runs start: counts on a weekday × hour grid, one hue light to dark.
  if (t.starts.counts.some((row) => row.some((n) => n > 0))) {
    out.push({
      id: 'starts',
      wide: true,
      body: {
        type: 'heatmap',
        collapsed: false,
        title: w.starts,
        x: t.starts.hours.map((h) => String(h).padStart(2, '0')),
        y: weekdayLabels(locale),
        values: t.starts.counts.map((row) => row.map((n) => n || null)),
        unit: 'number',
      },
    });
  }

  out.push({
    id: 'runs',
    wide: true,
    body: {
      type: 'table',
      collapsed: false,
      title: w.runs,
      columns: [
        { id: 'run', label: w.run },
        { id: 'started', label: w.started, format: 'datetime' },
        { id: 'attempts', label: w.attempts, align: 'end', format: 'number' },
        { id: 'passed', label: w.passed, align: 'end', format: 'pct' },
        { id: 'cost', label: w.cost, align: 'end', format: 'usd', bar: true },
        { id: 'wall', label: w.time, align: 'end', format: 'duration' },
      ],
      rows: t.runs.map((r) => ({
        run: r.run,
        started: r.started_at || null,
        attempts: r.attempts,
        passed: r.attempts ? r.ok / r.attempts : null,
        cost: r.cost_usd,
        wall: r.wall_s,
        ...(r.ok < r.attempts ? { _tone: 'attention' as const } : {}),
      })),
    },
  });
  return out;
}
