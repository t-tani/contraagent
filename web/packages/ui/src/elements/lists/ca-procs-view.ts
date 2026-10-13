import type { Procs } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { starts } from '@contraagent/elements';
import { facts, kindUnit } from '../../words/format.js';
import { base } from '@contraagent/elements/styles';
import '@contraagent/elements/count/define';
import './ca-proc-tree.js';

/**
 * A live run's processes: each coding-agent launch (opens its transcript with
 * `ca-open-task`), each Python task, and the process tree.
 *
 * @fires ca-open-task - `{key}`: a launch was clicked
 */
@customElement('ca-procs-view')
@localized()
export class CaProcsView extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .cmd { word-break: break-all; }
    `,
  ];

  @property({ attribute: false }) procs: Procs | null = null;

  /** Open a launch's task. A launch's row opens it on a click; its name is the button for the keyboard. */
  private open(key: string): void {
    emit(this, 'ca-open-task', { key });
  }


  override render() {
    const p = this.procs;
    if (!p?.alive) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">⚙</span><b>${facts(msg('No processes'), msg('run not running'))}</b></div>`;
    }
    const pys = p.python_tasks;
    return html`<div class="g12">
      <section class="panel c12">
        <h3 title=${msg('One per task (Backend.run)')}>${msg('Agent sessions running')} <span class="r">${p.launches.length}</span></h3>
        ${p.launches.length
          ? repeat(
              p.launches,
              (c) => c.key,
              (c) => html`<div class="fl" @click=${(e: MouseEvent) => !(e.target as Element).closest('button') && this.open(c.key)}>
                <button type="button" class="fl-name jmono" @click=${() => this.open(c.key)}>${kindUnit(c)}</button>
                <span class="meta">${facts(msg(str`PID ${c.pid}`), msg(str`Model ${c.model || '—'}`), c.role ? msg(str`Role ${c.role}`) : '')} |
                  <cae-elapsed .since=${starts.at(`c:${c.key}`, c.age_s)}></cae-elapsed></span>
                <div class="meta mono cmd">${(c.full_cmd || msg('In the pipeline process')).slice(0, 400)}</div>
              </div>`,
            )
          : html`<div class="meta">${msg('No agent sessions')}</div>`}
      </section>
      ${pys.length
        ? html`<section class="panel c12">
            <h3 title=${msg('Functions in the pipeline process')}>${msg('Python tasks running')} <span class="r">${pys.length}</span></h3>
            ${repeat(
              pys,
              (pt) => pt.key,
              (pt) => html`<div class="fl">
                <b class="jmono">${kindUnit(pt)}</b>
                <span class="meta">${msg(str`PID ${pt.pid}`)} | <cae-elapsed .since=${starts.at(`p:${pt.key}`, pt.age_s)}></cae-elapsed></span>
              </div>`,
            )}
          </section>`
        : nothing}
      <section class="panel c12"><h3>${msg('Process tree')}</h3><ca-proc-tree .procs=${p}></ca-proc-tree></section>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-procs-view': CaProcsView;
  }
}
