// Parts of the monitor's header: the name, what is running now, and the
// connection to the monitor server.
import type { Activity } from '@contraagent/api';
import { msg } from '@lit/localize';
import { html, nothing, type TemplateResult } from 'lit';
import { kindUnit } from '../../words/format.js';
import { taskChip } from '../shared/task-chip.js';

/**
 * The brand mark (braces around a spark, the favicon's drawing) and the monitor's title.
 * The braces take the text colour and the spark goes from the accent to the agent colour,
 * so the mark follows the theme; the gradient's id is unique in the element's shadow root.
 */
export const brand = (title: string): TemplateResult =>
  html`<div class="brand">
    <svg viewBox="12 12 96 96" aria-hidden="true">
      <defs>
        <linearGradient id="brand-spark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" class="spark-a" />
          <stop offset="1" class="spark-b" />
        </linearGradient>
      </defs>
      <g class="logo-braces" fill="none" stroke-width="14" stroke-linecap="round" stroke-linejoin="round">
        <path d="M48 22 C36 22 36 30 36 38 L36 50 C36 56 32 60 26 60 C32 60 36 64 36 70 L36 82 C36 90 36 98 48 98" />
        <path d="M72 22 C84 22 84 30 84 38 L84 50 C84 56 88 60 94 60 C88 60 84 64 84 70 L84 82 C84 90 84 98 72 98" />
      </g>
      <g class="logo-spark">
        <path d="M60 45 C61.6 56 64 58.4 75 60 C64 61.6 61.6 64 60 75 C58.4 64 56 61.6 45 60 C56 58.4 58.4 56 60 45 Z"
          fill="url(#brand-spark)" transform="translate(60 60) scale(1.15) translate(-60 -60)" />
      </g>
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
