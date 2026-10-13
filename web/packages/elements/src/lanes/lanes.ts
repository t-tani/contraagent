import { LitElement, html, nothing, type PropertyValues, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { withDefaults } from '../core/strings.js';
import { legend, legendStyles, type LegendItem } from '../primitives/legend.js';
import { base } from '../styles/index.js';
import { barBox, fitRange, stack } from './stack.js';
import { lanesStyles } from './styles.js';
import { DEFAULT_LANES_STRINGS, type Lane, type LaneStyle, type LanesStrings, type TimeRange } from './types.js';

/** A span shorter than this shows seconds on its axis (else every tick reads the same minute). */
const SECONDS_BELOW_MS = 10 * 60e3;

/**
 * Bars on a time axis, a lane per group: each bar as long as it took, the
 * overlapping bars of a lane stacked, a running bar (`end` null) growing until
 * now and a line at now. A bar's look is its style in `barStyles`, whose
 * labels are the legend (a row per `group`). The bars grow in when they are
 * first drawn.
 *
 * Its look: `--cae-lanes-label-width` (the lanes' labels; 112px, 78px on a
 * narrow screen) and the parts.
 *
 * @tagname cae-lanes
 * @csspart axis - the times above the lanes
 * @csspart lane - each lane
 * @csspart lane-label - a lane's label
 * @csspart track - the area of a lane's bars
 * @csspart bar - each bar
 * @csspart now - the line at now, while a bar runs
 * @csspart legend - each row of the legend
 * @csspart empty - what the element shows with no bars
 * @slot empty - what the element shows with no bars, instead of `strings.empty`
 */
export class CaeLanes extends LitElement {
  static override styles = [base, legendStyles, lanesStyles];

  @property({ attribute: false }) lanes: readonly Lane[] = [];
  /** A look per style key of the bars, in legend order. */
  @property({ attribute: false }) barStyles: Readonly<Record<string, LaneStyle>> = {};
  /** The time the axis spans; null fits the bars (`fitRange`). */
  @property({ attribute: false }) range: TimeRange | null = null;
  /** Draws again every second, so the running bars and the line at now move. */
  @property({ type: Boolean }) live = false;
  /** Bars the host left out, as a note after the legend. */
  @property({ type: Number }) omitted = 0;
  /** The language of the axis' times; by default the page's (`lang`). */
  @property() locale = '';
  @property({ attribute: false }) strings: Partial<LanesStrings> = {};

  private timer: ReturnType<typeof setInterval> | null = null;
  /** The bars have been drawn once: later bars do not grow in. */
  private drawn = false;

  override connectedCallback(): void {
    super.connectedCallback();
    this.tick(this.live);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.tick(false);
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('live')) this.tick(this.live);
  }

  private tick(on: boolean): void {
    if (on && !this.timer) this.timer = setInterval(() => this.requestUpdate(), 1000);
    if (!on && this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private time(t: number, seconds: boolean): string {
    const locale = this.locale || document.documentElement.lang || undefined;
    return new Date(t).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}), hourCycle: 'h23' });
  }

  override render() {
    const s = withDefaults(DEFAULT_LANES_STRINGS, this.strings);
    const now = Date.now();
    const range = this.range ?? fitRange(this.lanes, now);
    if (!range) return html`<div part="empty"><slot name="empty">${s.empty}</slot></div>`;
    const animate = !this.drawn;
    this.drawn = true;
    const span = Math.max(1, range.end - range.start);
    const running = this.lanes.some((l) => l.bars.some((b) => b.end === null));
    const seconds = span < SECONDS_BELOW_MS;
    const nowAt = Math.min(1, (now - range.start) / span);
    return html`<div class="lanes ${animate ? 'anim' : ''}">
        <div class="axis" part="axis">${[0, 0.25, 0.5, 0.75, 1].map((k) => html`<span>${this.time(range.start + span * k, seconds)}</span>`)}</div>
        ${repeat(this.lanes, (l) => l.id, (l) => this.lane(l, range, now))}
        ${running
          ? html`<span class="now" part="now" style="left:calc(var(--label) + 8px + (100% - var(--label) - 8px) * ${nowAt.toFixed(4)})"></span>`
          : nothing}
      </div>
      ${this.legends(s)}`;
  }

  private lane(l: Lane, range: TimeRange, now: number): TemplateResult {
    const placed = stack(l.bars);
    const rows = Math.max(1, ...placed.map((p) => p.row + 1));
    return html`<div class="lane" part="lane">
      <span class="name" part="lane-label" title=${l.label}>${l.label}</span>
      <div class="track" part="track" style="--rows:${rows}">
        ${placed.map(({ bar, row }) => {
          const box = barBox(bar, range, now);
          const look = this.barStyles[bar.style];
          return html`<span class="bar ${bar.end === null ? 'running' : ''}" part="bar" data-style=${bar.style}
            data-pattern=${look?.pattern ?? 'solid'} title=${bar.label}
            style="--bar:${look?.color ?? 'var(--line2)'};--row:${row};left:${box.left.toFixed(3)}%;width:${box.width.toFixed(3)}%"></span>`;
        })}
      </div>
    </div>`;
  }

  /** A legend row per group of styles, in key order; the note of omitted bars ends the last. */
  private legends(s: LanesStrings): TemplateResult[] {
    const groups: LegendItem[][] = [];
    for (const look of Object.values(this.barStyles)) {
      const g = look.group ?? 0;
      (groups[g] ??= []).push({
        label: look.label,
        icon: html`<i data-pattern=${look.pattern ?? 'solid'} style="--bar:${look.color}"></i>`,
      });
    }
    const rows = groups.filter(Boolean);
    if (this.omitted) {
      if (!rows.length) rows.push([]);
      rows[rows.length - 1]!.push({ label: s.omitted(this.omitted) });
    }
    return rows.map((items) => legend(items));
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-lanes': CaeLanes;
  }
}
