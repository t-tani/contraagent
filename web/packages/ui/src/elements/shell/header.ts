// Parts of the monitor's header: the name, what is running now, and the
// connection to the monitor server.
import type { Activity } from '@contraagent/api';
import { msg } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { kindUnit } from '../../words/format.js';
import { taskChip } from '../shared/task-chip.js';

/** The logo and the monitor's title. */
export const brand = (title: string): TemplateResult =>
  html`<div class="brand">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle class="logo-ring" cx="12" cy="12" r="9.5" fill="none" stroke-width="1.5" stroke-dasharray="4 3" />
      <circle class="logo-core" cx="12" cy="12" r="4" />
    </svg>
    <span title=${title}>${title}</span>
  </div>`;

/** The tasks running now, the first three by name; each chip opens its task (sent from `host`). */
export const nowLine = (host: EventTarget, acts: readonly Activity[]): TemplateResult =>
  html`<span class="nowline">${acts.length
    ? msg(html`Running ${acts.slice(0, 3).map((a) => taskChip(host, kindUnit(a), { key: a.key }))}${acts.length > 3 ? html` <span>+${acts.length - 3}</span>` : nothing}`)
    : nothing}</span>`;

/** Whether the feed is connected: a dot, with its words as its accessible name and its tooltip. */
export const connection = (connected: boolean): TemplateResult => {
  const words = connected ? msg('Connected to the monitor server') : msg('Not connected to the monitor server');
  return html`<span role="img" aria-label=${words} title=${words}><span class="live-dot ${connected ? '' : 'off'}"></span></span>`;
};
