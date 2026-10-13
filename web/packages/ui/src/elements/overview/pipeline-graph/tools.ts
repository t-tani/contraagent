// The row under the frame: the legend, the zoom buttons and the view switch, and the keys of the view shown.
import '@contraagent/elements/segmented/define';
import { msg } from '@lit/localize';
import { html, nothing } from 'lit';
import { parentLayer } from '../graph/layer.js';
import { showView } from './actions.js';
import type { GraphHost } from './host.js';
import { legend } from './legend.js';

/** The legend on the left, the tools at the right end of the first line, and the keys under them while the graph has the focus. */
export function foot(h: GraphHost) {
  const table = !!h.matrix || h.asTable;
  return html`<div class="foot">
    ${legend(h)}
    <div class="tools">${table ? nothing : zoomTools(h)}${viewSwitch(h, table)}</div>
    <div class="keys">${keyHints(h).map((k, i) => html`${i ? ' | ' : ''}<span>${k}</span>`)}</div>
  </div>`;
}

/** Zoom out, zoom in, and back to the whole graph (which does nothing while the whole graph shows at its own size). */
function zoomTools(h: GraphHost) {
  const pz = h.pz;
  const whole = !pz.moved && pz.fitK >= 1;
  return html`<button type="button" aria-label=${msg('Zoom out')} title=${msg('Zoom out (Ctrl + scroll)')} @click=${() => pz.zoomBy(1 / 1.25)}>−</button>
    <button type="button" aria-label=${msg('Zoom in')} title=${msg('Zoom in (Ctrl + scroll)')} @click=${() => pz.zoomBy(1.25)}>+</button>
    <button type="button" ?disabled=${whole} @click=${() => pz.showAll()}>${msg('Show all')}</button>`;
}

/**
 * The two views of a layer, at the same place in each: the graph, and the table (a loop's
 * passes, or a row per node). From a loop's passes, the graph is the layer the loop is
 * in, with its box selected.
 */
function viewSwitch(h: GraphHost, table: boolean) {
  const options = [
    { value: 'graph', label: msg('Graph', { id: 'view-graph', desc: 'Button: show the pipeline as a graph' }) },
    { value: 'table', label: msg('Table', { id: 'view-table', desc: 'Button: show the pipeline as a table' }) },
  ];
  return html`<cae-segmented class="views" .options=${options} .value=${table ? 'table' : 'graph'} label=${msg('View')}
    @cae-change=${(e: CustomEvent<{ value: string }>) => showView(h, e.detail.value === 'table' ? 'table' : 'graph')}></cae-segmented>`;
}

/** The keys of the view shown. */
function keyHints(h: GraphHost): string[] {
  const up = h.sel ? msg('Esc: clear selection') : parentLayer(h.segments, h.auto) ? msg('Esc: up a level') : '';
  const keys = h.matrix
    ? [msg('Arrow keys: marks'), msg('Enter: open'), up]
    : h.asTable
      ? [msg('Tab: next row'), msg('Enter: open'), up]
      : [msg('Tab: next node'), msg('Arrow keys: marks'), msg('Shift + arrow keys: earlier and later tasks'), msg('Enter: open'), up];
  return keys.filter(Boolean);
}
