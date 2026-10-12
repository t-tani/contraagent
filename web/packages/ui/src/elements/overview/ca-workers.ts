import { liveActivities, type Procs } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { starts } from '../../lib/clock.js';
import { base } from '../../styles/base.js';
import '../shared/ca-elapsed.js';

/**
 * What runs now: one card per running task (an agent session opens its
 * transcript), the rest idle, up to the number of tasks the run runs at once
 * (`max_concurrent`). Sends `ca-open-task`.
 *
 * @fires ca-open-task - `{key}`: a running agent launch was clicked
 */
@customElement('ca-workers')
@localized()
export class CaWorkers extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .wks { display: grid; grid-template-columns: repeat(var(--n, 3), minmax(0, 1fr)); gap: 10px; }
      @media (max-width: 900px) { .wks { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      .wk { border-radius: 11px; padding: 10px 12px; border: 1px solid var(--line); background: rgba(255, 255, 255, 0.02); min-width: 0;
        position: relative; overflow: hidden; }
      .wk.py { border-color: rgba(148, 163, 184, 0.35); }
      .wk.llm { border-color: rgba(167, 139, 250, 0.45); background: var(--llm-a); cursor: pointer; }
      .wk.idle { opacity: 0.45; border-style: dashed; }
      .wk-top { display: flex; align-items: center; gap: 8px; min-width: 0; }
      .wk-top b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .wk-ic { width: 24px; height: 24px; border-radius: 7px; flex: none; display: grid; place-items: center; background: var(--raise); font-size: 12px; }
      .wk.llm .wk-ic { color: var(--llm); }
      .wk.py .wk-ic { color: var(--muted); }
      .wk-el { margin-left: auto; font-family: var(--mono); font-size: 11.5px; color: var(--live); }
      .wk-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; overflow: hidden; }
      .wk-bar i { position: absolute; top: 0; bottom: 0; width: 30%; background: linear-gradient(90deg, transparent, var(--live), transparent);
        animation: scan 1.8s linear infinite; }
      .wk.llm .wk-bar i { background: linear-gradient(90deg, transparent, var(--llm), transparent); }
    `,
  ];

  @property({ attribute: false }) procs: Procs | null = null;
  /** The run is live; when not, every slot is idle. */
  @property({ type: Boolean }) live = false;

  override render() {
    const work = this.live ? liveActivities(this.procs) : [];
    const max = Math.max(this.procs?.max_workers || 1, work.length);
    const free = Array.from({ length: max - work.length }, (_, i) => i);
    return html`<div class="wks" style="--n:${Math.min(max, 6)}">
      ${repeat(
        work,
        (a) => a.id,
        (a) => html`<div class="wk ${a.cls}"
          @click=${a.key ? () => emit(this, 'ca-open-task', { key: a.key }) : nothing}>
          <div class="wk-top"><span class="wk-ic" title=${a.cls === 'llm' ? msg('Agent task') : msg('Python task')}><span aria-hidden="true">${a.cls === 'llm' ? '✦' : '⚙'}</span><span class="sr">${a.cls === 'llm' ? msg('Agent task') : msg('Python task')}</span></span><b>${a.kind}</b>
            <ca-elapsed class="wk-el" .since=${starts.at(a.id, a.ageS)}></ca-elapsed></div>
          <div class="meta">${a.detail}</div>
          <div class="wk-bar"><i></i></div>
        </div>`,
      )}
      ${free.map(
        () => html`<div class="wk idle"><div class="wk-top"><b>${msg('Idle')}</b></div>
          <div class="meta">${msg('No task')}</div></div>`,
      )}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-workers': CaWorkers;
  }
}
