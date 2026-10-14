import type { JsonObject, PanelInfo, TrendsView } from '@contraagent/api';
import '@contraagent/elements/segmented/define';
import { base } from '@contraagent/elements/styles';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { getLocale } from '../../core/i18n.js';
import { TREND_DAYS } from '../../core/route.js';
import { trendSections } from '../../adapters/trends.js';
import { daysBefore } from '../../lib/trends.js';
import {
  allGroups,
  customPeriod,
  exportedPeriod,
  fromLabel,
  groupLabel,
  lastDays,
  noRunsInPeriod,
  periodLabel,
  toLabel,
  trendWords,
  trendsTitle,
  zoneLabel,
} from '../../words/trends.js';
import '../lists/ca-panel-body.js';

/**
 * The trends: what the runs of a period add up to (`/api/trends`), section by section:
 * the totals, the cost of each day, each kind and each model, the subscription usage,
 * the attempts that did not complete, what was refused or not run, when runs start, and
 * the runs; then the pipeline's own trend panels. Above them, the period (the last 7,
 * 14 or 30 days, or two dates), its time zone and a run group; an export's period is
 * fixed and named instead.
 *
 * @fires ca-navigate - `{days, from, to, tz, group}`: another period, time zone or run group
 */
@customElement('ca-trends')
@localized()
export class CaTrends extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-bottom: 14px; }
      .controls label { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
      input, select { background: var(--well); border: 1px solid var(--line); color: var(--text); border-radius: 8px; font: inherit; font-size: 12px; padding: 4px 8px; }
      input:focus-visible, select:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .period { font-size: 12px; color: var(--text-2); }
      .loading { font-size: 12px; color: var(--text-muted); }
      .err { font-size: 12px; color: var(--status-failed); }
      /* wide sections span the page; the narrow ones pair up and fill each other's gaps */
      .wide { margin-bottom: 14px; }
      .pairs { columns: 2 440px; column-gap: 14px; margin-bottom: 14px; }
      .pairs > .panel { break-inside: avoid; margin-bottom: 14px; }
      .panel { display: block; }
    `,
  ];

  @property({ attribute: false }) view: TrendsView | null = null;
  /** The period: the last `days` days (0: `from` to `to`). */
  @property({ type: Number }) days = 14;
  @property() from = '';
  @property() to = '';
  /** The time zone the days are counted in. */
  @property() tz = '';
  /** Only the runs of this run group ('': every run). */
  @property() group = '';
  /** The run groups there are to choose from. */
  @property({ attribute: false }) groups: readonly string[] = [];
  /** The pipeline's trend panels (`Panel(scope="trends")`). */
  @property({ attribute: false }) panels: readonly PanelInfo[] = [];
  /** An export: its period is the one it holds. */
  @property({ type: Boolean }) exported = false;

  private go(patch: { days?: number; from?: string; to?: string; tz?: string; group?: string }): void {
    emit(this, 'ca-navigate', patch);
  }

  override render() {
    const v = this.view;
    const data = v?.data ?? null;
    const sections = data ? trendSections(data, getLocale()) : [];
    const wide = sections.filter((s) => s.wide);
    const narrow = sections.filter((s) => !s.wide);
    const order = ['totals', 'cost-by-day', 'kinds', 'models', 'usage'];
    const first = wide.filter((s) => order.includes(s.id));
    const last = wide.filter((s) => !order.includes(s.id));
    const card = (body: unknown, id: string) => html`<section class="panel" data-section=${id}><ca-panel-body .body=${body}></ca-panel-body></section>`;
    return html`<h2 class="sr">${trendsTitle()}</h2>
      ${this.controls()}
      ${v?.error ? html`<p class="err" role="alert">${msg('No answer from the monitor')} | ${v.error.message}</p>` : nothing}
      ${!data && v?.loading ? html`<p class="loading">${msg('Loading…')}</p>` : nothing}
      ${data && !sections.length ? html`<div class="blank small"><span>${noRunsInPeriod()}</span></div>` : nothing}
      ${repeat(first, (s) => s.id, (s) => html`<div class="wide">${card(s.body, s.id)}</div>`)}
      ${narrow.length ? html`<div class="pairs">${repeat(narrow, (s) => s.id, (s) => card(s.body, s.id))}</div>` : nothing}
      ${repeat(last, (s) => s.id, (s) => html`<div class="wide">${card(s.body, s.id)}</div>`)}
      ${this.trendPanels(v?.panels ?? {})}`;
  }

  /** The period, its time zone and the run group: links of the page's address. */
  private controls() {
    const data = this.view?.data;
    const period = data ? html`<span class="period">${periodLabel(data.period.from, data.period.to, data.period.tz)}</span>` : nothing;
    if (this.exported) return html`<div class="controls"><span class="meta">${exportedPeriod()}</span>${period}</div>`;
    const choice = this.days ? String(this.days) : 'dates';
    const today = data?.period.to || new Date().toISOString().slice(0, 10);
    const zones = [...new Set([this.tz, Intl.DateTimeFormat().resolvedOptions().timeZone, 'UTC'].filter(Boolean))];
    return html`<div class="controls">
      <cae-segmented label=${msg('Period')} .value=${choice}
        .options=${[...TREND_DAYS.map((n) => ({ value: String(n), label: lastDays(n) })), { value: 'dates', label: customPeriod() }]}
        @cae-change=${(e: CustomEvent<{ value: string }>) =>
          e.detail.value === 'dates'
            ? this.go({ days: 0, from: this.from || daysBefore(today, (this.days || 14) - 1), to: this.to || today })
            : this.go({ days: Number(e.detail.value), from: '', to: '' })}></cae-segmented>
      ${this.days === 0
        ? html`<label>${fromLabel()} <input type="date" .value=${this.from} max=${this.to || nothing}
              @change=${(e: Event) => this.go({ days: 0, from: (e.target as HTMLInputElement).value, to: this.to })} /></label>
            <label>${toLabel()} <input type="date" .value=${this.to} min=${this.from || nothing}
              @change=${(e: Event) => this.go({ days: 0, from: this.from, to: (e.target as HTMLInputElement).value })} /></label>`
        : nothing}
      <label>${zoneLabel()}
        <select @change=${(e: Event) => this.go({ tz: (e.target as HTMLSelectElement).value })}>
          ${zones.map((z) => html`<option value=${z} ?selected=${z === (this.tz || zones[0])}>${z}</option>`)}
        </select></label>
      ${this.groups.length > 1
        ? html`<label>${groupLabel()}
            <select @change=${(e: Event) => this.go({ group: (e.target as HTMLSelectElement).value })}>
              <option value="" ?selected=${!this.group}>${allGroups()}</option>
              ${this.groups.map((g) => html`<option value=${g} ?selected=${g === this.group}>${g}</option>`)}
            </select></label>`
        : nothing}
      ${period}
      ${this.view?.loading && data ? html`<span class="loading" aria-live="polite">${msg('Loading…')}</span>` : nothing}
    </div>`;
  }

  /** The pipeline's own trend panels, under their titles. */
  private trendPanels(bodies: Readonly<Record<string, JsonObject>>) {
    const shown = this.panels.filter((p) => p.scope === 'trends');
    if (!shown.length) return nothing;
    return html`<h3 class="sect-h">${trendWords().trendPanels}</h3>
      ${shown.map(
        (p) => html`<section class="panel wide" data-panel=${p.name}>
          <h3>${p.icon} ${p.title || p.name}${p.description ? html`<span class="r">${p.description}</span>` : nothing}</h3>
          ${bodies[p.name] ? html`<ca-panel-body .body=${bodies[p.name]}></ca-panel-body>` : html`<p class="loading">${msg('Loading…')}</p>`}
        </section>`,
      )}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-trends': CaTrends;
  }
}
