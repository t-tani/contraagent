import type { Forecast, ForecastEntry } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { expectedByNode, forecastShown, notInPlan } from './forecast.js';
import { layerGraph } from './graph/layer.js';
import { F, ft, planOf } from './graph/plans.fixture.js';

const entry = (group: string, flow: string[], remaining: number): ForecastEntry => ({
  kind: group, group, flow, passes: [], expected: remaining, created: 0, remaining, wall_s: remaining, cost_usd: null,
});
const forecast = (entries: ForecastEntry[]): Forecast => ({
  flow: 'm.top', earlier_run: 'top-1', earlier_finished_at: '', entries, wall_s: 0, cost_usd: null,
  remaining: entries.reduce((a, e) => a + e.remaining, 0),
});

describe('the forecast on the graph', () => {
  const plan = planOf([
    ft('prepare-a', 'a', 'prepare', 'done', [F('m.top')]),
    ft('review-a', 'a', 'review', 'done', [F('m.top'), F('m.one')], { flow_call: '0.1' }),
  ]);

  it('gives a kind node its own group in its layer, and a function node what is created in it or below it', () => {
    const f = forecast([entry('prepare', ['m.top'], 2), entry('review', ['m.top', 'm.one'], 3), entry('note', ['m.top', 'm.one', 'm.two'], 1)]);
    const top = layerGraph(plan, ['m.top']);
    const ids = Object.fromEntries(expectedByNode(f, top));
    expect(ids).toEqual({ 'kind:prepare': 2, 'flow:m.one': 4 });
    expect(Object.fromEntries(expectedByNode(f, layerGraph(plan, ['m.top', 'm.one'])))).toEqual({ 'kind:review': 3 });
  });

  it('names the groups the plan has no task of yet, and shows nothing without an earlier run or with nothing left', () => {
    const f = forecast([entry('prepare', ['m.top'], 2), entry('report', ['m.top'], 1)]);
    expect(notInPlan(f, plan)).toEqual([{ group: 'report', remaining: 1 }]);
    expect(forecastShown(f)).toBe(true);
    expect(forecastShown({ ...f, earlier_run: '' })).toBe(false);
    expect(forecastShown(forecast([]))).toBe(false);
  });
});
