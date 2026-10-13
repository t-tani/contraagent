import { deriveRun, isLaunched, liveActivities, runRelative, type JournalRow, type Plan, type Procs } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { starts } from '../../core/clock.js';
import { getLocale } from '../../core/i18n.js';
import { facts, fmtDur, kindUnit } from '../../words/format.js';
import { modelSwitch, notStartedCause, stopLabel } from '../../words/index.js';
import { base, legendStyles } from '../../styles/index.js';
import { barBox, timeline, type TimelineBar } from './timeline-model.js';

const hhmm = (t: number) => new Date(t).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const hhmmss = (t: number) =>
  new Date(t).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
/** A span shorter than this shows seconds on its axis (else every tick reads the same minute). */
const SECONDS_BELOW_MS = 10 * 60e3;

/**
 * Every finished attempt as a bar as long as it took, on its kind's lane, the
 * running ones growing until now (the last six hours of the run).
 */
@customElement('ca-timeline')
@localized()
export class CaTimeline extends LitElement {
  static override styles = [
    base,
    legendStyles,
    css`
      :host { display: block; }
      .tl { position: relative; }
      .tl-axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; color: var(--text-muted); margin: 0 0 6px 120px; }
      .tl-row { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 8px; align-items: center; min-height: 24px; padding: 4px 0; }
      .nm { font-size: 11.5px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .tl-lane { position: relative; height: calc(var(--tracks, 1) * 14px + 2px); border-radius: 4px;
        background: repeating-linear-gradient(90deg, color-mix(in srgb, var(--text) 5%, transparent) 0 1px, transparent 1px 10%); }
      .tl-bar { position: absolute; top: calc(var(--track, 0) * 14px + 2px); height: 12px; border-radius: 4px; min-width: 3px; cursor: default;
        transform-origin: left center; transition: width 1s linear; }
      .tl.anim .tl-bar:not(.run) { animation: growx 0.6s var(--ease) both; }
      /* who ran it is an identity cue (Python neutral, an agent violet); failed and running are statuses,
         each with a pattern of its own besides the colour (failed: fine hatching; running: moving stripes) */
      .tl-bar.py, .legend i.py { background: var(--meter); }
      .tl-bar.llm, .legend i.llm { background: var(--agent); }
      .tl-bar.bad, .legend i.bad { background: repeating-linear-gradient(135deg, var(--status-failed) 0 3px,
        color-mix(in srgb, var(--status-failed) 55%, var(--bg)) 3px 5px); }
      .tl-bar.idle, .legend i.idle { background: none; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .tl-bar.run, .legend i.run { background: repeating-linear-gradient(45deg, var(--status-running) 0 6px,
        color-mix(in srgb, var(--status-running) 60%, var(--bg)) 6px 12px); background-size: 17px 17px; }
      .tl-bar.run { animation: stripes 0.8s linear infinite; box-shadow: 0 0 12px color-mix(in srgb, var(--status-running) 45%, transparent); }
      .tl-bar:hover { filter: brightness(1.2); }
      .tl-now { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--status-running); border-radius: 2px; box-shadow: 0 0 10px var(--status-running); }
      .legend { margin-top: 10px; }
      .legend + .legend { margin-top: 4px; }
      @media (max-width: 760px) {
        .tl-row { grid-template-columns: 78px minmax(0, 1fr); }
        .tl-axis { margin-left: 86px; }
      }
    `,
  ];

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The run's plan: with the journal, why a task did not start, as the tasks list says it. Optional. */
  @property({ attribute: false }) plan: Plan | null = null;
  @property({ attribute: false }) procs: Procs | null = null;
  /** The run is live: its running tasks are drawn, growing every second. */
  @property({ type: Boolean }) live = false;
  /** The run drawn; the bars grow in when a run is first drawn, not on every update. */
  @property() run = '';

  private drawnRun: string | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('live')) this.tick(this.live);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.tick(this.live);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.tick(false);
  }

  /** Repaint every second while live, so the running bars and the now line move. */
  private tick(on: boolean): void {
    if (on && !this.timer) this.timer = setInterval(() => this.requestUpdate(), 1000);
    if (!on && this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  override render() {
    const now = Date.now();
    const live = this.live
      ? liveActivities(this.procs).map((a) => ({ kind: a.kind, cls: a.cls, t0: starts.at(a.id, a.ageS, now) }))
      : [];
    const tl = timeline(this.journal, live, now);
    if (!tl)
      return html`<div class="blank" style="padding:28px"><span class="ic" aria-hidden="true">⏱</span>${this.live
        ? msg('No finished attempts yet')
        : msg('No finished attempts')}</div>`;
    const animate = this.drawnRun !== this.run;
    this.drawnRun = this.run;
    const { outcomes } = deriveRun(this.journal, this.plan);
    const tip = (lane: string, b: TimelineBar) => {
      const e = b.row;
      if (!e) return `${lane}\n${msg('running')}`;
      // A task that never ran: its name and why, and no time, end or model.
      if (!isLaunched(e)) {
        const t = outcomes.get(e.key);
        const cause = e.stop === 'invalid_input' && t ? notStartedCause(t, outcomes, this.run) : '';
        return [kindUnit(e), cause ? msg(str`Not started: ${cause}`) : stopLabel(e.stop, e.reason), e.key].join('\n');
      }
      const sw = modelSwitch(e.hops);
      const reason = e.reason && !e.ok ? runRelative(e.reason, this.run) : '';
      // One item per line: a task's name holds a `·` of its own.
      return [
        kindUnit(e),
        facts(stopLabel(e.stop), fmtDur(e.wall_s), msg(str`ended ${hhmmss(b.end)}`)),
        sw ? msg(str`Model switch: ${sw}`) : e.model ? msg(str`Model ${e.model}`) : '',
        reason,
        e.key,
      ]
        .filter(Boolean)
        .join('\n');
    };
    const nowAt = Math.min(1, (now - tl.t0) / tl.span);
    const tick = tl.span < SECONDS_BELOW_MS ? hhmmss : hhmm;
    return html`<div class="tl ${animate ? 'anim' : ''}">
        <div class="tl-axis">${[0, 0.25, 0.5, 0.75, 1].map((k) => html`<span>${tick(tl.t0 + tl.span * k)}</span>`)}</div>
        ${repeat(
          tl.lanes,
          (l) => l.name,
          (l) => html`<div class="tl-row">
            <span class="nm" title=${l.name}>${l.name}</span>
            <div class="tl-lane" style="--tracks:${l.tracks}">
              ${l.bars.map((b) => {
                const box = barBox(b, tl, now);
                return html`<span class="tl-bar ${b.cls}" style="--track:${b.track};left:${box.left.toFixed(3)}%;width:${box.width.toFixed(3)}%" title=${tip(l.name, b)}></span>`;
              })}
            </div>
          </div>`,
        )}
        ${tl.live ? html`<span class="tl-now" style="left:calc(120px + (100% - 120px) * ${nowAt.toFixed(4)})"></span>` : nothing}
      </div>
      <div class="legend">
        <span><i class="py"></i>${msg('Python task')}</span><span><i class="llm"></i>${msg('Agent task')}</span>
      </div>
      <div class="legend">
        <span><i class="run"></i>${msg('running')}</span><span><i class="bad"></i>${msg('failed')}</span>
        <span><i class="idle"></i>${msg('not started')}</span>
        ${tl.hidden ? html`<span>${tl.hidden === 1 ? msg('1 older attempt not shown') : msg(str`${tl.hidden} older attempts not shown`)}</span>` : nothing}
      </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-timeline': CaTimeline;
  }
}
