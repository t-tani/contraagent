import { addRow, emptySpend, isPython, taskOutcomes, type JournalRow, type Plan, type Spend, type TaskOutcome, type TaskRollup } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { facts, fmtDur, localTime, tokens, usd } from '../../lib/format.js';
import { notStartedCause, outcomeLabel } from '../../lib/labels.js';
import { base } from '../../styles/base.js';
import { filterTasks, rollupOutcome } from './filters.js';

/**
 * Every task, by kind and unit (one row per slot): what happened to it, its
 * attempts and time. A row opens the task's detail (`ca-open-task`).
 *
 * @fires ca-open-task - `{key}`: an agent task's row was clicked (its slot)
 */
@customElement('ca-task-table')
@localized()
export class CaTaskTable extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; margin-top: 4px; }
      /* the numbers sit tight together, right-aligned; the outcome comes last and takes the spare width, so no gap opens inside the row */
      .trow { display: grid; grid-template-columns: minmax(220px, 0.6fr) 64px 132px 72px 72px 128px minmax(240px, 1fr);
        column-gap: 20px; padding: 6px 12px; align-items: center; border-radius: 8px; transition: background 0.15s; cursor: pointer; }
      .trow.hd { cursor: default; }
      .trow:not(.hd):hover { background: var(--raise); }
      .trow.running { background: var(--live-a); }
      .trow.hd { align-items: end; white-space: nowrap; padding: 4px 12px 8px; color: var(--mut); font-size: 11px; border-bottom: 1px solid var(--line); border-radius: 0; margin-bottom: 4px; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .wall { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
      .wall .jdur { width: 56px; margin: 0; flex: none; }
      .grow { display: flex; align-items: center; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .grow .jdim { margin-left: 8px; }
      .cause { display: block; font-size: 11px; color: var(--mut); margin-top: 2px; white-space: normal; overflow-wrap: anywhere; }
      @media (max-width: 760px) {
        .trow { grid-template-columns: minmax(0, 1fr) 128px 90px; }
        .trow > span:nth-child(2), .trow > span:nth-child(4), .trow > span:nth-child(5), .trow > span:nth-child(6) { display: none; }
      }
    `,
  ];

  @property({ attribute: false }) tasks: TaskRollup[] = [];
  /** Only this kind ('' for all). */
  @property() kind = '';
  /** A text filter over the slot and the last stop. */
  @property() q = '';
  /** The run's journal and plan, optional: with them a task that did not start names the failed task that stopped it. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  @property({ attribute: false }) plan: Plan | null = null;

  /** Failed and not-started tasks first, the rest in their order. */
  private static rank(o: string): number {
    return o === 'failed' ? 0 : o === 'not_started' ? 1 : 2;
  }

  /** The run id: paths in a cause are shown relative to it. */
  @property() run = '';

  /** Why a task did not start: "input out/review/zeta.json is missing because review · zeta failed". */
  private cause(t: TaskRollup, outcomes: Map<string, TaskOutcome> | null): string {
    if (!outcomes) return '';
    const own = [...outcomes.values()].find((o) => o.kind === t.kind && (o.unit || '') === (t.unit || ''));
    return own ? notStartedCause(own, outcomes, this.run) : '';
  }

  /** Tokens and cost cells; '—' for a task that reported none (a Python task, one that never ran). */
  private spendCells(s: Spend | undefined) {
    if (!s?.reported) return html`<span class="num jdim">—</span><span class="num jdim">—</span>`;
    const cache = facts(msg(str`Cache read ${tokens(s.cache_read)}`), msg(str`Cache write ${tokens(s.cache_creation)}`));
    return html`<span class="num" title=${cache}>${tokens(s.input + s.output)}</span><span class="num">${usd(s.cost)}</span>`;
  }

  override render() {
    const outcomes = this.journal.length && this.plan ? taskOutcomes(this.journal, this.plan) : null;
    const rows = filterTasks(this.tasks, this.kind, this.q)
      .map((t, i) => ({ t, i, r: CaTaskTable.rank(rollupOutcome(t)) }))
      .sort((a, b) => a.r - b.r || a.i - b.i)
      .map((x) => x.t);
    if (!rows.length)
      return html`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${this.tasks.length ? msg('No tasks match the filter') : msg('No tasks')}</div>`;
    const maxWall = Math.max(1, ...rows.map((t) => t.wall_s || 0));
    // Tokens and cost per task (kind and unit), over all its attempts.
    const spend = new Map<string, Spend>();
    for (const r of this.journal) {
      const id = `${r.kind}|${r.unit ?? ''}`;
      addRow(spend.get(id) ?? spend.set(id, emptySpend()).get(id)!, r);
    }
    return html`<div class="trow hd">
        <span title=${msg('Kind · unit')}>${msg('Task')}</span><span class="num" title=${msg('Attempts that ran')}>${msg('Attempts')}</span>
        <span class="num" title=${msg('Sum over all attempts')}>${msg('Time')}</span>
        <span class="num" title=${msg('Input and output tokens, all attempts')}>${msg('Tokens')}</span>
        <span class="num" title=${msg('Reported by the coding agent')}>${msg('Cost')}</span>
        <span class="num">${msg('Last attempt ended')}</span>
        <span class="st">${msg('Status')}</span>
      </div>
      ${repeat(
        rows,
        (t) => t.slot,
        (t) => {
          const py = isPython(t);
          const outcome = rollupOutcome(t);
          // A task refused before it started (or skipped) never ran: no attempts, no time.
          const ran = outcome !== 'not_started' && outcome !== 'skipped' && outcome !== 'waiting';
          // A Python task has no transcript, but its detail shows what it was given and what it left.
          return html`<div class="trow ${t.running ? 'running' : ''} ${py ? 'py' : ''}"
            @click=${() => emit(this, 'ca-open-task', py ? { key: t.slot, view: 'output' } : { key: t.slot })}>
            <span class="grow jmono" title=${t.slot}>
              <span class="k-ic ${py ? '' : 'llm'}" title=${py ? msg('Python task') : msg('Agent task')}><span aria-hidden="true">${py ? '⚙' : '✦'}</span><span class="sr">${py ? msg('Python task') : msg('Agent task')}</span></span>${t.kind}
              ${t.unit ? html`<span class="jdim">· ${t.unit}</span>` : nothing}
            </span>
            <span class="num">${ran ? t.attempts : '—'}</span>
            <span class="num wall">${ran
              ? html`${fmtDur(t.wall_s)}<span class="jdur"><i class=${py ? '' : 'llm'}
                  style="width:${Math.max(4, Math.round((100 * t.wall_s) / maxWall))}%"></i></span>`
              : '—'}</span>
            ${this.spendCells(spend.get(`${t.kind}|${t.unit ?? ''}`))}
            <span class="num meta">${ran ? localTime(t.last_ts, true) : '—'}</span>
            <span class="st"><span class="pill o-${outcome}" title=${t.last_stop || ''}>${outcomeLabel(outcome)}</span>${outcome === 'not_started' && this.cause(t, outcomes)
              ? html`<span class="cause">${this.cause(t, outcomes)}</span>`
              : nothing}</span>
          </div>`;
        },
      )}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-task-table': CaTaskTable;
  }
}
