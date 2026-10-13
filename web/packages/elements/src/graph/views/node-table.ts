// The graph as a table, in its frame: a row per node.
import { html, nothing } from 'lit';
import { repeat } from 'lit/directives/repeat.js';
import { FRAME_MIN, FRAME_SHARE } from '../../core/frame.js';
import type { GraphHost } from '../host.js';
import { cycleIcon, innerIcon } from '../icons.js';
import type { EdgeStyle, GraphInput, GraphNode } from '../types.js';
import { notes } from './dag.js';

/** The names of the nodes `n` is joined to: by a solid edge, by a dashed one, and the later ones. */
export function neighbours(
  n: GraphNode,
  g: Pick<GraphInput, 'edges' | 'stubs'>,
  nodes: ReadonlyMap<string, GraphNode>,
  inCluster: (label: string) => string,
): { solid: string[]; dashed: string[]; later: string[] } {
  const label = (id: string) => {
    const x = nodes.get(id);
    return !x ? id : x.cluster ? inCluster(x.label) : x.label;
  };
  const into = (style: EdgeStyle) => [
    ...g.stubs.filter((s) => s.to === n.id && s.style === style).map((s) => s.label),
    ...g.edges.filter((e) => e.to === n.id && e.style === style).map((e) => label(e.from)),
  ];
  return { solid: into('solid'), dashed: into('dashed'), later: [...new Set(g.edges.filter((e) => e.from === n.id).map((e) => label(e.to)))] };
}

/**
 * The graph as a table, in its frame: a row per node with its status (the node's
 * count and notes) and the nodes it is joined to. A row is selected as a node is,
 * with the same card.
 */
export function nodeTable(h: GraphHost) {
  const g = h.graph;
  const w = h.strings;
  const dashed = [...g.edges, ...g.stubs].some((e) => e.style === 'dashed');
  const list = (xs: string[]) => w.list(xs) || w.none;
  // The frame keeps the drawing's height when the drawing of this graph was laid out (left to right); else the table's own, up to the frame's limit.
  const height = !h.down && h.laidOut && h.pz.frameH > 0 ? `height:${Math.round(h.pz.frameH)}px` : `max-height:max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh)`;
  const rows = h.arr.drawn.map((id) => h.nodes.get(id)).filter((n): n is GraphNode => !!n);
  return html`<div class="frame tframe" part="frame" style=${height} @scroll=${() => h.card.place()}
      @click=${(e: MouseEvent) => !(e.target as Element).closest('tbody tr') && h.select(null)}>
    <table class="list view" part="table">
      <thead>
        <tr>
          <th scope="col" class="fit">${w.nameHeader}</th>
          <th scope="col" class="fit">${w.statusHeader}</th>
          <th scope="col">${w.solidHeader}</th>
          ${dashed ? html`<th scope="col">${w.dashedHeader}</th>` : nothing}
          <th scope="col">${w.laterHeader}</th>
        </tr>
      </thead>
      <tbody>
        ${repeat(rows, (n) => n.id, (n) => {
          const nb = neighbours(n, g, h.nodes, w.inCluster);
          const box = n.cluster ? h.clusters.get(n.cluster) : undefined;
          const on = h.selected === n.id;
          const icons = html`${(n.icons ?? []).map((x) => h.renderIcon(x))}${n.drill ? innerIcon() : nothing}`;
          return html`<tr class=${on ? 'sel' : ''} part="row" data-id=${n.id}
              @click=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && e.detail < 2 && h.select(n.id)}
              @dblclick=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && h.act(n.id)}>
            <th scope="row" class="fit">
              <span class="nm">${icons}<button type="button" class="name" title=${n.tip ?? nothing} aria-pressed=${on}
                @focus=${() => h.focusSelect(n.id)} @keydown=${(e: KeyboardEvent) => {
                  if (e.key !== 'Enter') return;
                  e.preventDefault();
                  h.act(n.id);
                }}>${n.label}</button>${box?.drill
                ? html`<button type="button" class="taskchip loopchip" title=${box.chipTip ?? nothing} aria-label=${box.chipLabel ?? nothing}
                    @click=${() => h.drill(box.id)}>${box.cycle ? cycleIcon(12) : nothing}${box.note ?? box.label}</button>`
                : nothing}</span>
            </th>
            <td class="fit st">${statusLine(n)}</td>
            <td class="rel">${list(nb.solid)}</td>
            ${dashed ? html`<td class="rel">${list(nb.dashed)}</td>` : nothing}
            <td class="rel">${list(nb.later)}</td>
          </tr>`;
        })}
      </tbody>
    </table>
  </div>`;
}

/** A node's status in one row, as its node in the graph says it: "28/30 | 1 failed | 1 not started". */
export function statusLine(n: GraphNode) {
  const sep = html`<span class="sep" aria-hidden="true"> | </span>`;
  const p = n.progress;
  return html`${p ? html`<span class="n" aria-hidden="true" title=${p.label}>${p.done}/${p.total}</span><span class="sr">${p.label}</span>` : nothing}${notes(n).map(
    (x, i) => html`${p || i ? sep : nothing}${x}`,
  )}`;
}
