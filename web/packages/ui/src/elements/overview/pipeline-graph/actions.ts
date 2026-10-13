// What the pipeline graph does: the events it sends for a selection, a layer, a
// task, and the focus it puts back.
import { emit } from '../../../core/events.js';
import { parentLayer } from '../graph/layer.js';
import { selected, type Selected } from '../graph/selection.js';
import { LOOP_SEGMENT, type GraphMark, type GraphNode } from '../graph/types.js';
import type { GraphHost } from './host.js';

/** Select a node, a loop box or a mark (by its selection id); '' clears the selection. */
export function select(h: GraphHost, id: string): void {
  if (id !== h.sel) emit(h.el, 'ca-navigate', { sel: id });
}

/** Focus moved by the reader selects what it is on; focus put back does not. */
export function focusSelect(h: GraphHost, id: string): void {
  if (!h.card.quiet) select(h, id);
}

/** Go to a layer (its segments; [] for the layer the graph opens on), with a unit highlighted or not. */
export function go(h: GraphHost, segments: readonly string[], unit = h.unit): void {
  const layer = segments.join('/');
  emit(h.el, 'ca-navigate', { layer: layer === h.auto.join('/') ? '' : layer, unit });
}

/** The Tasks tab, filtered to a kind node's kind. */
export function tasksOf(h: GraphHost, n: GraphNode): void {
  emit(h.el, 'ca-navigate', { tab: 'tasks', kind: n.kinds.length === 1 ? n.kinds[0] : '' });
}

/** Open a mark: a task (on its input when it did not start, a Python task on its output), or a flow call's function. */
export function open(h: GraphHost, m: GraphMark): void {
  if (m.flow) return go(h, [...h.graph.path, m.flow], m.unit || h.unit);
  const t = h.links.byKey.get(m.key);
  emit(h.el, 'ca-open-task', m.state === 'blocked' ? { key: m.key, view: 'input' } : t?.executor === 'python' ? { key: m.key, view: 'output' } : { key: m.key });
}

/** What a double click or Enter does: a mark opens its task (or its flow call's function), a function node or a loop box opens inside, a kind node its tasks. */
export function primary(h: GraphHost, s: Selected): void {
  if (s.type === 'mark') return open(h, s.mark);
  if (s.type === 'box') return go(h, [...h.segments, s.box.id]);
  if (s.node.type === 'flow') return go(h, [...h.graph.path, s.node.name]);
  tasksOf(h, s.node);
}

/** Enter on a node's or a box's name: its primary action (Space selects it, as a click does). */
export function onNameKey(h: GraphHost, e: KeyboardEvent, id: string): void {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const s = selected(h.graph, h.matrix, id);
  if (s) primary(h, s);
}

/** The graph or the table; from a loop's passes, the graph is the layer the loop is in, with its box selected. */
export function showView(h: GraphHost, v: 'graph' | 'table'): void {
  if (v === 'table') {
    if (!h.matrix) h.asTable = true;
    return;
  }
  h.asTable = false;
  if (!h.matrix) return;
  const box = h.segments[h.segments.length - 1] ?? '';
  const up = parentLayer(h.segments, h.auto) ?? [];
  const auto = h.auto.join('/');
  emit(h.el, 'ca-navigate', { layer: up.join('/') === auto ? '' : up.join('/'), unit: h.unit, sel: box });
}

/** After going up a level: the focus on the node or the loop box it came from (`from`), else on the first item; it does not select. */
export function restoreFocus(h: GraphHost, from: string): void {
  const root = h.root;
  let el: HTMLElement | null = null;
  if (from.startsWith(LOOP_SEGMENT)) el = root.querySelector<HTMLElement>(`.box[data-box="${CSS.escape(from)}"] > .hd .name`);
  else if (from) {
    const n = h.graph.nodes.find((x) => x.type === 'flow' && x.name === from);
    if (n) el = root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(n.id)}"] [tabindex="0"]`);
  }
  h.card.focusQuietly(el ?? root.querySelector<HTMLElement>('.mark[tabindex="0"], .node .name, .crumbs button'));
}
