// What the pipeline graph does: the events it sends for a selection, a layer and a task.
import { emit } from '../../../core/events.js';
import { parentLayer } from '../../../adapters/graph/layer.js';
import type { Selected } from '../../../adapters/graph/selection.js';
import type { GraphNode, LayerMark } from '../../../adapters/graph/types.js';
import type { PipelineHost } from './host.js';

/** Select a node, a loop box or a mark (by its selection id); '' clears the selection. */
export function select(h: PipelineHost, id: string): void {
  if (id !== h.sel) emit(h.el, 'ca-navigate', { sel: id });
}

/** Go to a layer (its segments; [] for the layer the graph opens on), with a unit highlighted or not. */
export function go(h: PipelineHost, segments: readonly string[], unit = h.unit): void {
  const layer = segments.join('/');
  emit(h.el, 'ca-navigate', { layer: layer === h.auto.join('/') ? '' : layer, unit });
}

/** The Tasks tab, filtered to a kind node's kind. */
export function tasksOf(h: PipelineHost, n: GraphNode): void {
  emit(h.el, 'ca-navigate', { tab: 'tasks', kind: n.kinds.length === 1 ? n.kinds[0] : '' });
}

/** Open a mark: a task (on its input when it did not start, a Python task on its output), or a flow call's function. */
export function open(h: PipelineHost, m: LayerMark): void {
  if (m.flow) return go(h, [...h.graph.path, m.flow], m.unit || h.unit);
  const t = h.links.byKey.get(m.key);
  emit(h.el, 'ca-open-task', m.state === 'blocked' ? { key: m.key, view: 'input' } : t?.executor === 'python' ? { key: m.key, view: 'output' } : { key: m.key });
}

/** What a double click or Enter does: a mark opens its task (or its flow call's function), a function node or a loop box opens inside, a kind node its tasks. */
export function primary(h: PipelineHost, s: Selected): void {
  if (s.type === 'mark') return open(h, s.mark);
  if (s.type === 'box') return go(h, [...h.segments, s.box.id]);
  if (s.node.type === 'flow') return go(h, [...h.graph.path, s.node.name]);
  tasksOf(h, s.node);
}

/** "Graph" in a loop's passes: the layer the loop is in, with its box selected. */
export function leavePasses(h: PipelineHost): void {
  const box = h.segments[h.segments.length - 1] ?? '';
  const up = parentLayer(h.segments, h.auto) ?? [];
  const auto = h.auto.join('/');
  emit(h.el, 'ca-navigate', { layer: up.join('/') === auto ? '' : up.join('/'), unit: h.unit, sel: box });
}
