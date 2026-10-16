import type { PlanNode, ServiceSpan } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { statusWord } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';
import type { Tone } from '@contraagent/elements';
import { kindUnit } from '../../words/format.js';
import { serviceFacts, serviceState, serviceStateLabel, type ServiceState } from '../../words/services.js';
import { taskChip } from '../shared/task-chip.js';

const TONE: Record<ServiceState, Tone> = { running: 'running', stopped: 'done', failed: 'failed', unknown: 'muted' };

/**
 * The run's services (`Plan.services`): each start of the long-lived helper a claim
 * name stands for, one per row, with its state, its claim name, its address, when it
 * started and stopped and why, and the task whose claim started it. A service that
 * stopped when idle and started again has a row for each start.
 *
 * @fires ca-open-task - the task chip of the task that started a service was clicked
 */
@customElement('ca-services')
@localized()
export class CaServices extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
      li { display: grid; grid-template-columns: max-content 1fr; column-gap: 10px; row-gap: 2px; align-items: baseline; font-size: 12px; }
      .name { font-family: var(--mono); color: var(--text); overflow-wrap: anywhere; }
      .addr { font-family: var(--mono); color: var(--text-2); overflow-wrap: anywhere; }
      .facts { grid-column: 2; color: var(--text-2); overflow-wrap: anywhere; }
      .by { grid-column: 2; }
    `,
  ];

  /** Each start of a service, in start order (`Plan.services`). */
  @property({ attribute: false }) services: readonly ServiceSpan[] = [];
  /** The run's tasks (`Plan.nodes`): the task that started a service is named by its kind and unit. */
  @property({ attribute: false }) nodes: readonly PlanNode[] = [];
  /** Whether the run still runs: a service with no stop recorded is running only then. */
  @property({ type: Boolean }) live = false;

  override render() {
    if (!this.services.length) return html`<div class="meta">${msg('No services')}</div>`;
    const byKey = new Map(this.nodes.map((n) => [n.key, n]));
    return html`<ul>
      ${this.services.map((s) => {
        const state = serviceState(s, this.live);
        const node = s.key ? byKey.get(s.key) : undefined;
        return html`<li>
          ${statusWord({ text: serviceStateLabel(state), tone: TONE[state] })}
          <div><span class="name" title="services.jsonl">${s.name}</span>${s.address ? html` <span class="addr">${s.address}</span>` : nothing}</div>
          <div class="facts">${serviceFacts(s)}</div>
          ${s.key ? html`<div class="by">${taskChip(this, node ? kindUnit(node) : s.key, node ?? { key: s.key })}</div>` : nothing}
        </li>`;
      })}
    </ul>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-services': CaServices;
  }
}
