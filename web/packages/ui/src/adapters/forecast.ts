// The forecast (`Forecast`: the tasks a run is expected to create and has not yet, from
// the run of its flow that finished last before it) on the pipeline graph: how many
// more tasks each kind node is expected to have, and the kinds the plan has no task of yet.
import type { Forecast, ForecastEntry, Plan } from '@contraagent/api';
import type { LayerModel } from './graph/types.js';

const sameLayer = (a: readonly string[], b: readonly string[]): boolean => a.length === b.length && a.every((x, i) => x === b[i]);

/**
 * The tasks each node of a layer is expected to have beyond its own, by node id: for a
 * kind node, the `remaining` of the forecast's entries of its group created in its
 * layer's function; for a function node, those of every entry created in that function
 * or below it. Of several nodes of one group or function in one layer (one per loop),
 * the first in the layer's order takes them.
 */
export function expectedByNode(forecast: Forecast | null | undefined, m: Pick<LayerModel, 'nodes'>): Map<string, number> {
  const out = new Map<string, number>();
  for (const e of forecast?.entries ?? []) {
    if (!e.remaining) continue;
    const n = m.nodes.find((x) =>
      x.type === 'kind'
        ? x.name === e.group && sameLayer(x.layer, e.flow)
        : e.flow.length > x.layer.length && sameLayer(x.layer, e.flow.slice(0, x.layer.length)) && e.flow[x.layer.length] === x.name,
    );
    if (n) out.set(n.id, (out.get(n.id) ?? 0) + e.remaining);
  }
  return out;
}

/** The forecast's entries of a kind or a function the plan has no task of yet, by group: what the graph has no node for. */
export function notInPlan(forecast: Forecast | null | undefined, plan: Pick<Plan, 'nodes'>): { group: string; remaining: number }[] {
  const have = new Set(plan.nodes.map((n) => `${n.group}\u0000${(n.flow ?? []).map((f) => f.function).join('\u0000')}`));
  const by = new Map<string, number>();
  for (const e of forecast?.entries ?? []) {
    if (!e.remaining || have.has(`${e.group}\u0000${e.flow.join('\u0000')}`)) continue;
    by.set(e.group, (by.get(e.group) ?? 0) + e.remaining);
  }
  return [...by].map(([group, remaining]) => ({ group, remaining }));
}

/** The forecast has something to show: an earlier run, and tasks it expects that this run has not created. */
export const forecastShown = (forecast: Forecast | null | undefined): forecast is Forecast & { entries: ForecastEntry[] } =>
  !!forecast?.earlier_run && forecast.remaining > 0;
