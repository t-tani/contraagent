// The line above the frame: where the layer is, the pinned unit, and a layer the run does not have.
import { msg, str } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { shortName } from '../../../adapters/graph/flow-index.js';
import { splitLayer } from '../../../adapters/graph/layer.js';
import { LOOP_SEGMENT } from '../../../adapters/graph/types.js';
import { where } from '../../../adapters/graph/words.js';
import { emit } from '../../../core/events.js';
import { go } from './actions.js';
import type { PipelineHost } from './host.js';

/** Which functions are drawn open: those the graph chooses, every one, or only those the reader opened. */
export type OpenMode = 'auto' | 'all' | 'none';

/** "Show all inside" and "Hide all inside": each sets its mode, and, pressed again, gives the choice back to the graph. */
export function openControls(mode: OpenMode, set: (m: OpenMode) => void): TemplateResult {
  const button = (m: OpenMode, label: string) =>
    html`<button type="button" class="switch" aria-pressed=${mode === m} @click=${() => set(mode === m ? 'auto' : m)}>${label}</button>`;
  return html`<span class="opens">${button('all', msg('Show all inside'))}${button('none', msg('Hide all inside'))}</span>`;
}

/**
 * Where the layer is: "Pipeline", then every level down to the one shown, auto-descended
 * levels included; a nested loop's box is a level below the box it is in. `controls`
 * (the open controls) end the line.
 */
export function crumbs(h: PipelineHost, controls: TemplateResult | null = null) {
  const segs = h.segments;
  const pinned = h.unit;
  if (!segs.length && !pinned && !controls) return nothing;
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
    ${controls ?? nothing}
  </div>`;
}

/** The layer the view route named that this run does not have. */
export function missingLine(missing: string) {
  if (!missing) return nothing;
  const segs = missing.split('/');
  const name = segs[segs.length - 1] || missing;
  return html`<div class="missing" role="status" title=${missing}>${msg(html`No layer <code>${name}</code> in this run`)}</div>`;
}
