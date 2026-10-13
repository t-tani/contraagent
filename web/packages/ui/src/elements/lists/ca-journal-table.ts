import { deriveRun, isBad, isLaunched, isPython, rowId, type JournalRow, type Plan, type TaskOutcome } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { facts, fmtDur, kindUnit, localTime, sentence, tokenCount, unreadEvents, usd } from '../../lib/format.js';
import { attemptLabel, correctionsText, credentialLabel, credentialTip, modelSwitch, notStartedCause, outcomeLabel, runRelative, stopLabel } from '../../lib/labels.js';
import { stopTone, type Tone } from '../../lib/tone.js';
import { markOf, statusWord } from '../../lib/status.js';
import { accountReading, readingShort } from '../../lib/quota-format.js';
import { base } from '../../styles/base.js';
import { attemptFacts, filterJournal, hadFixup, journalTally, retriedKeys } from './filters.js';

// Each row is its own grid, so every track is fixed or a share of the width, never content-sized:
// time compact, outcome and task a small share, agent a little more, the numbers tight and fixed, the reason most of the rest.
const COLS = 'grid-template-columns:64px minmax(130px,0.8fr) minmax(150px,0.7fr) minmax(150px,1fr) 92px 60px 76px minmax(200px,2.2fr)';

/**
 * The run's history: every finished attempt, newest first (`journal.jsonl`),
 * with a chip per outcome that filters by it (`ca-filter`). A row opens the
 * task's detail.
 *
 * @fires ca-filter - `{stop}`: a chip was toggled: a stop value, 'fixup' or 'retried' ('' clears)
 * @fires ca-open-task - `{key}`: an agent task's row was clicked
 */
@customElement('ca-journal-table')
@localized()
export class CaJournalTable extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .jtally { display: flex; flex-wrap: wrap; gap: 8px; padding: 2px 0 12px; }
      .jchip { border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; font-size: 11.5px; color: var(--text-muted);
        cursor: pointer; transition: all 0.15s; background: none; }
      .jchip b { color: var(--text); }
      .jchip:hover { border-color: var(--line2); color: var(--text); }
      .jchip.on { background: var(--accent-bg); border-color: var(--accent); color: var(--text); }
      /* a stop's chip: marked by its status (data-mark: done quiet with a ✓, a failure red with a ✕, not started ◌) */
      .jchip[data-tone='failed'], .jchip[data-tone='attention'] { color: var(--tone); border-color: color-mix(in srgb, var(--tone) 40%, transparent); }
      .table { overflow-x: auto; }
      .jrow { display: grid; column-gap: 12px; row-gap: 2px; padding: 7px 12px; border-bottom: 1px solid var(--line); font-size: 12px; align-items: center; min-width: 980px; }
      .jrow > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
      .jrow > span.jstop { white-space: normal; }
      .jrow:hover { background: var(--card); }
      .jrow.hd { color: var(--text-muted); font-size: 11px; position: sticky; top: 0; background: var(--bg); z-index: 1; }
      .jrow.bad { background: color-mix(in srgb, var(--status-failed) 6%, transparent); box-shadow: inset 3px 0 0 var(--status-failed); }
      .jrow.py { opacity: 0.85; }
      .jrow.py:hover, .jrow.py.bad { opacity: 1; }
      .jrow.fresh { animation: rowin 1.6s var(--ease); }
      .jrow.agent { cursor: pointer; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .jwhy { color: var(--text-2); white-space: normal !important; overflow-wrap: anywhere; }
      .later { color: var(--status-done); }
      .nw { white-space: nowrap; }
      .jrow.notrun { opacity: 0.8; }
      .unread { color: var(--status-attention); }
      .two { display: flex; flex-direction: column; line-height: 1.35; }
      /* the status mark stays beside its word, the lines under it align with the word */
      .jstop.two { display: grid; grid-template-columns: auto minmax(0, 1fr); align-content: center; }
      .jstop.two > * { grid-column: 2; }
      .jstop.two::before { grid-row: 1; }
      .two .sub { color: var(--text-muted); font-size: 11px; white-space: normal; overflow-wrap: anywhere; }
      .num.two > span { white-space: nowrap; }
      .jrow > span.two { white-space: normal; }
      .sub .q { color: var(--text-2); font-family: var(--mono); white-space: nowrap; }
      .jstop .sub { font-weight: 400; }
      .cost { font-variant-numeric: tabular-nums; text-align: right; color: var(--text-2); }
    `,
  ];

  @property({ attribute: false }) rows: JournalRow[] = [];
  /** The run's plan: with the rows, why a task did not start, as the tasks list says it. Optional. */
  @property({ attribute: false }) plan: Plan | null = null;
  /** Rows (by `rowId`) that just arrived: they flash once. */
  @property({ attribute: false }) fresh: ReadonlySet<string> = new Set();
  @property() kind = '';
  /** A stop; 'bad' (every attempt that did not complete), 'fixup' (output sent back) or 'retried' (tasks retried after a failed try). */
  @property() stop = '';
  @property() q = '';
  /** The run id: paths inside the run directory are shown relative to it. */
  @property() run = '';

  /** What happened to each task (`deriveRun`): a refused row names its cause in words. */
  private outcomes: ReadonlyMap<string, TaskOutcome> = new Map();

  override render() {
    this.outcomes = deriveRun(this.rows, this.plan).outcomes;
    const rows = filterJournal(this.rows, this.kind, this.stop, this.q).reverse();
    const maxWall = Math.max(1, ...rows.map((e) => e.wall_s || 0));
    const facts = attemptFacts(this.rows);
    const index = new Map(this.rows.map((r, i) => [r, i]));
    const fixups = this.rows.filter(hadFixup).length;
    const retried = retriedKeys(this.rows).size;
    const chip = (k: string, label: string, n: number, tip: string, tone: Tone = '') =>
      html`<button type="button" class="jchip ${this.stop === k ? 'on' : ''}" data-tone=${tone || nothing} data-mark=${markOf(tone) ?? nothing}
        aria-pressed=${this.stop === k} title=${tip}
        @click=${() => emit(this, 'ca-filter', { stop: this.stop === k ? '' : k })}>${label} <b>${n}</b></button>`;
    return html`<div class="jtally">
        ${journalTally(this.rows).map(([k, c]) => chip(k, this.shortStop(k), c, k, stopTone(k)))}
        ${fixups ? chip('fixup', msg('attempts with corrections'), fixups, msg('Attempts with at least one correction')) : nothing}
        ${retried ? chip('retried', msg('tasks retried'), retried, msg('Tasks retried after a failed attempt')) : nothing}
      </div>
      <div class="table">
      <div class="jrow hd" style=${COLS}>
        <span>${msg('Ended')}</span><span>${msg('Task')}</span>
        <span title=${msg('How the attempt ended (stop)')}>${msg('Outcome')}</span>
        <span>${msg('Agent, model, identity')}</span>
        <span class="num" title=${msg('Input / output tokens, then cache read / cache write')}>${msg('Tokens')}</span>
        <span class="num" title=${msg('Reported by the coding agent')}>${msg('Cost')}</span>
        <span class="num">${msg('Time')}</span><span>${msg('Reason')}</span>
      </div>
      ${repeat(rows, rowId, (e) => {
        const f = facts.get(e.key);
        const later = !e.ok && isLaunched(e) && (f?.lastOk ?? -1) > (index.get(e) ?? 0) ? (f?.lastOkTry ?? 0) : 0;
        return this.row(e, maxWall, (f?.count ?? 1) > 1, later);
      })}
      </div>
      ${rows.length ? nothing : html`<div class="meta" style="padding:8px">${msg('No finished attempts')}</div>`}`;
  }

  /** A stop as a short column label: a task that never ran is just "not started"; the cause goes to the reason. */
  private shortStop(stop: string | null | undefined): string {
    return stop === 'invalid_input' ? outcomeLabel('not_started') : stopLabel(stop);
  }

  /**
   * What the reason column says: the model switch, then (for a row that failed
   * or never ran) the reason, run-relative, then the attempt that later did the task.
   */
  private reason(e: JournalRow, ran: boolean, laterTry: number) {
    const sw = modelSwitch(e.hops);
    const run = this.run || e.run_id || '';
    const own = this.outcomes.get(e.key);
    const cause = e.stop === 'invalid_input' && own ? notStartedCause({ attempts: [e], cause: null }, this.outcomes, run) : '';
    const why = cause ? sentence(cause) : (!e.ok || !ran) && e.reason ? runRelative(e.reason, run) : '';
    const later = laterTry ? msg(str`The task was done on attempt ${laterTry}`) : '';
    if (!sw && !why && !later) return html`<span class="jdim">—</span>`;
    return html`${sw ? html`<span class="nw" title=${msg('Model switch')}>${sw}</span><br />` : nothing}${why ? html`${why}<br />` : nothing}${later
      ? html`<span class="later">${later}</span>`
      : nothing}`;
  }

  /** The identity the attempt authenticated as; both when a model switch changed it. */
  private identity(e: JournalRow) {
    const ids = [...new Set([...(e.hops ?? []).map((h) => h.credential), e.credential].filter(Boolean))];
    if (!ids.length) return nothing;
    // The subscription usage the attempt's first session started at, when the agent reported one.
    const start = (e.quota ?? [])[0];
    const tip = start ? msg(str`Usage at session start (account-wide): ${accountReading(start)}`) : '';
    // The reading belongs to one account: name it when the row has more than one, or a different one.
    const own = start && ids.length === 1 && (start.credential ?? '') === ids[0];
    const shown = start ? (own ? readingShort(start) : accountReading(start)) : '';
    const tips = [tip, ...ids.map(credentialTip)].filter(Boolean).join('\n');
    return html`<span class="sub" title=${tips || nothing}>${ids.map((c) => credentialLabel(c)).join(' → ')}${start ? html` <span class="q">${shown}</span>` : nothing}</span>`;
  }

  /** Tokens (input / output, then cache read / write) and cost; '—' for a row that reported none. */
  private spend(e: JournalRow) {
    const u = e.usage;
    const hops = e.hops ?? [];
    const perHop =
      hops.length > 1
        ? hops.map((h) => facts(h.model || h.route || '—', credentialLabel(h.credential) || '—', usd(h.cost_usd), stopLabel(h.stop))).join('\n')
        : '';
    return html`<span class="num two">${u
        ? html`<span>${tokenCount(u.input)} / ${tokenCount(u.output)}</span><span class="sub">${tokenCount(u.cache_read)} / ${tokenCount(u.cache_creation)}</span>`
        : html`<span class="jdim">—</span>`}</span>
      <span class="cost" title=${perHop || msg('Reported by the coding agent')}>${usd(e.cost_usd)}</span>`;
  }

  private row(e: JournalRow, maxWall: number, numbered: boolean, laterTry: number) {
    const ran = isLaunched(e);
    // A refusal is not a failure of this task: it never ran, because an input was missing.
    const bad = ran && isBad(e);
    const py = isPython(e);
    const sw = modelSwitch(e.hops);
    const corrections = ran ? correctionsText((e.rounds ?? 1) - 1) : '';
    const kindName = py ? msg('Python task') : msg('Agent task');
    const cls = `jrow${bad ? ' bad' : ''}${ran ? '' : ' notrun'}${py ? ' py' : ' agent'}${this.fresh.has(rowId(e)) ? ' fresh' : ''}`;
    return html`<div class=${cls} style=${COLS}
      @click=${() => emit(this, 'ca-open-task', py ? { key: e.key, view: 'output' } : { key: e.key })}>
      <span class="jmono" title=${localTime(e.ts, true)}>${localTime(e.ts)}</span>
      <span class="jmono" title=${e.key}><span title=${kindName}><span aria-hidden="true">${py ? '⚙' : '✦'}</span><span class="sr">${kindName}</span></span>
        ${kindUnit(e)}</span>
      ${statusWord(
        html`<span class="nw">${this.shortStop(e.stop)}</span>${(numbered && ran) || corrections
          ? html`<span class="sub">${facts(numbered && ran ? attemptLabel(e.attempt) : '', corrections)}</span>`
          : nothing}`,
        stopTone(e.stop),
        { cls: 'two', title: e.stop },
      )}
      <span class="jmono jdim two" title=${facts(e.route, sw) || nothing}>${ran
        ? html`<span>${[e.agent, e.model].filter(Boolean).join(' / ') || '—'}</span>${this.identity(e)}`
        : '—'}</span>
      ${this.spend(e)}
      <span class="num">${ran
        ? html`${fmtDur(e.wall_s)}<span class="jdur"><i class=${bad ? 'bad' : py ? '' : 'llm'}
            style="width:${Math.max(2, Math.round((100 * (e.wall_s || 0)) / maxWall))}%"></i></span>`
        : '—'}</span>
      <span class="jwhy" title=${e.reason || nothing}>${this.reason(e, ran, laterTry)}${unreadEvents([e])
        ? html` <span class="unread nw" title=${msg(str`Event types from the coding agent that this contraagent version does not recognize: ${unreadEvents([e])}`)}
            ><span aria-hidden="true">⚠</span> ${msg('Unrecognized events')}</span
          >`
        : nothing}</span>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-journal-table': CaJournalTable;
  }
}
