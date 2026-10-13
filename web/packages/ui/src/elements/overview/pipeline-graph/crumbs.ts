// The line above the frame: where the layer is, the pinned unit, and a layer the run does not have.
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { emit } from '../../../core/events.js';
import { shortName } from '../graph/flow-index.js';
import { splitLayer } from '../graph/layer.js';
import { LOOP_SEGMENT } from '../graph/types.js';
import { go } from './actions.js';
import type { GraphHost } from './host.js';
import { where } from './words.js';

/**
 * Where the layer is: "Pipeline", then every level down to the one shown, auto-descended
 * levels included; a nested loop's box is a level below the box it is in.
 */
export function crumbs(h: GraphHost) {
  const segs = h.segments;
  const pinned = h.unit;
  if (!segs.length && !pinned) return nothing;
  const { path, loop } = splitLayer(segs);
  const levels = [
    ...path.map((fn, i) => ({ name: shortName(fn), tip: fn, to: path.slice(0, i + 1) })),
    // A loop by where it is: two loops one in the other are told apart.
    ...(loop ? loop.slice(LOOP_SEGMENT.length).split('.') : []).map((line, i, lines) => {
      const id = LOOP_SEGMENT + lines.slice(0, i + 1).join('.');
      const file = h.graph.boxes.find((b) => b.id === id)?.file || h.matrix?.box.file || '';
      const known = /^\d+$/.test(line);
      return {
        name: known ? msg(str`Loop at ${where(line, file)}`) : msg('Loop'),
        tip: known && file ? `${file}:${line}` : '',
        to: [...path, id],
      };
    }),
  ];
  return html`<div class="bar">
    ${segs.length
      ? html`<nav aria-label=${msg('Pipeline layer')}>
          <ol class="crumbs">
            <li><button type="button" @click=${() => go(h, [])}>${msg('Pipeline')}</button></li>
            ${levels.map((l, i) => {
              const last = i === levels.length - 1;
              return html`<li><span class="sep" aria-hidden="true">›</span>
                ${last
                  ? html`<span aria-current="page" title=${l.tip || nothing}>${l.name}</span>`
                  : html`<button type="button" title=${l.tip || nothing} @click=${() => go(h, l.to)}>${l.name}</button>`}</li>`;
            })}
          </ol>
        </nav>`
      : nothing}
    ${pinned
      ? html`<span class="pin">${msg(str`Unit: ${pinned}`)}
          <button type="button" class="switch" @click=${() => emit(h.el, 'ca-navigate', { unit: '' })}>${msg('Clear highlight')}</button></span>`
      : nothing}
  </div>`;
}

/** The layer the route named that this run does not have. */
export function missingLine(missing: string) {
  if (!missing) return nothing;
  const segs = missing.split('/');
  const name = segs[segs.length - 1] || missing;
  return html`<div class="missing" role="status" title=${missing}>${msg(html`No layer <code>${name}</code> in this run`)}</div>`;
}
