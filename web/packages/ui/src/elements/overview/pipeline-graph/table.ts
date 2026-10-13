// A layer as a table, in the graph's frame: a row per node.
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { repeat } from 'lit/directives/repeat.js';
import { executorIcon } from '../../../words/executor.js';
import { facts, listText } from '../../../words/format.js';
import { passCount } from '../../../words/index.js';
import { FRAME_MIN, FRAME_SHARE } from '../graph/pan-zoom.js';
import type { GraphNode } from '../graph/types.js';
import { focusSelect, go, onNameKey, primary, select } from './actions.js';
import type { GraphHost } from './host.js';
import { innerIcon, loopIcon } from './icons.js';
import { doneOf, exceptions, neighbours, nodeTip, where } from './words.js';

/**
 * The layer as a table, in the graph's frame: a row per node with its status (the graph
 * node's facts: done of all, then the others by state) and the nodes it waits for, was
 * created after and feeds. A row is selected as a node is, with the same card.
 */
export function table(h: GraphHost) {
  const g = h.graph;
  const nodes = g.nodes;
  const flows = nodes.some((n) => n.type === 'flow');
  const created = [...g.edges, ...g.stubs].some((e) => e.type === 'created');
  const boxes = new Map(g.boxes.map((b) => [b.id, b]));
  const list = (xs: string[]) => listText(xs) || msg('none', { id: 'none', desc: 'An empty value' });
  // The frame keeps the graph's height when the graph of this layer was drawn (left to right); else the table's own, up to the frame's limit.
  const height =
    !h.down && h.layPath === g.path.join('/') && h.pz.frameH > 0
      ? `height:${Math.round(h.pz.frameH)}px`
      : `max-height:max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh)`;
  return html`<div class="frame tframe" style=${height} @scroll=${() => h.card.place()}
      @click=${(e: MouseEvent) => !(e.target as Element).closest('tbody tr') && select(h, '')}>
    <table class="list view">
      <thead>
        <tr>
          <th scope="col" class="fit">${flows ? msg('Kind or function') : msg('Kind')}</th>
          <th scope="col" class="fit">${msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' })}</th>
          <th scope="col">${msg('Waits for')}</th>
          ${created ? html`<th scope="col">${msg('Created after')}</th>` : nothing}
          <th scope="col">${msg('Later tasks')}</th>
        </tr>
      </thead>
      <tbody>
        ${repeat(nodes, (n) => n.id, (n) => {
          const { waits, after, feeds } = neighbours(n, g);
          const box = n.box ? boxes.get(n.box) : undefined;
          const on = h.sel === n.id;
          const icon =
            n.type === 'flow' ? innerIcon() : n.executor && n.executor !== 'mixed' ? executorIcon(n.executor === 'python') : n.executor ? html`${executorIcon(false)}${executorIcon(true)}` : nothing;
          const at = box ? msg(str`Loop at ${where(box.loop, box.file)}`) : '';
          return html`<tr class=${on ? 'sel' : ''} data-id=${n.id}
              @click=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && e.detail < 2 && select(h, n.id)}
              @dblclick=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && primary(h, { type: 'node', id: n.id, node: n })}>
            <th scope="row" class="fit">
              <span class="nm">${icon}<button type="button" class="name" title=${nodeTip(n)} aria-pressed=${on}
                @focus=${() => focusSelect(h, n.id)} @keydown=${(e: KeyboardEvent) => onNameKey(h, e, n.id)}>${n.label}</button>${box
                ? html`<button type="button" class="taskchip loopchip" title=${facts(at, passCount(box.passes))}
                    aria-label=${facts(msg(str`Passes of the loop at ${where(box.loop, box.file)}`), passCount(box.passes))}
                    @click=${() => go(h, [...g.path, box.id])}>${loopIcon(12)}${passCount(box.passes)}</button>`
                : nothing}</span>
            </th>
            <td class="fit st">${statusLine(n, h.live)}</td>
            <td class="rel">${list(waits)}</td>
            ${created ? html`<td class="rel">${list(after)}</td>` : nothing}
            <td class="rel">${list(feeds)}</td>
          </tr>`;
        })}
      </tbody>
    </table>
  </div>`;
}

/** A node's status in one row, as its node in the graph says it: "28/30 | 1 failed | 1 not started". */
export function statusLine(n: GraphNode, live: boolean) {
  const c = n.counts;
  const sep = html`<span class="sep" aria-hidden="true"> | </span>`;
  return html`<span class="n" aria-hidden="true" title=${doneOf(c)}>${c.done}/${c.total}</span><span class="sr">${doneOf(c)}</span>${exceptions(n, live).map(
    ([cls, t]) => html`${sep}<span class=${cls}>${t}</span>`,
  )}`;
}
