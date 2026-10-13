import { addRow, deriveRun, emptySpend, isPython, type JournalRow, type Plan, type Spend, type TaskOutcome, type TaskRow } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { facts, fmtDur, localTime, tokenCount, usd } from '../../words/format.js';
import { notStartedCause, passLabel, taskStatusLabel, waitCause } from '../../words/index.js';
import { base } from '../../styles/base.js';
import { filterTasks, sortTasks } from './filters.js';

/**
 * Every task of the run, one row each (`deriveRun(...).rows`: the plan joined with the
 * journal, so a task that never ran is a row too): what happened to it, its
 * attempts, time, tokens and cost. A row opens the task's detail (`ca-open-task`).
 *
 * @fires ca-open-task - `{key}`: a task's row was clicked (its key; a Python task with `view: 'output'`)
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
      .trow.running { background: var(--status-running-bg); }
      .trow.hd { align-items: end; white-space: nowrap; padding: 4px 12px 8px; color: var(--text-muted); font-size: 11px; border-bottom: 1px solid var(--line); border-radius: 0; margin-bottom: 4px; }
      .num { text-align: right; font-variant-numeric: tabular-nums; }
      .wall { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
      .wall .jdur { width: 56px; margin: 0; flex: none; }
      .grow { display: flex; align-items: center; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .grow .jdim { margin-left: 8px; }
      .pass { margin-left: 8px; font-size: 11px; color: var(--text-muted); }
      .cause { display: block; font-size: 11px; color: var(--text-muted); margin-top: 2px; white-space: normal; overflow-wrap: anywhere; }
      @media (max-width: 760px) {
        .trow { grid-template-columns: minmax(0, 1fr) 128px 90px; }
        .trow > span:nth-child(2), .trow > span:nth-child(4), .trow > span:nth-child(5), .trow > span:nth-child(6) { display: none; }
      }
    `,
  ];

  /** The run's journal and plan: the tasks are the plan's, what happened to them the journal's. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  @property({ attribute: false }) plan: Plan | null = null;
  /** Only this kind ('' for all). */
  @property() kind = '';
  /** A text filter over the kind, unit, key and last stop. */
  @property() q = '';
  /** The run is running: a task that has not started is waiting; in a run that is over, it did not run. */
  @property({ type: Boolean }) live = false;
  /** The run id: paths in a cause are shown relative to it. */
  @property() run = '';

  /** Why a task that never ran did not run: what stopped it, or the earlier tasks it waits for; '' when unknown. */
  private cause(t: TaskRow, outcomes: ReadonlyMap<string, TaskOutcome>): string {
    if (t.outcome === 'not_started') return notStartedCause(t, outcomes, this.run);
    if (t.outcome === 'waiting') return waitCause(t.waits_for.map((k) => outcomes.get(k) ?? { kind: k }));
    return '';
  }

  /** Tokens and cost cells: 'none' for a task that never ran, '—' for one that reported none (a Python task). */
  private spendCells(ran: boolean, s: Spend | undefined) {
    if (!ran) return html`<span class="num jdim">${msg('none', { id: 'none', desc: 'An empty value' })}</span><span class="num jdim">${msg('none', { id: 'none', desc: 'An empty value' })}</span>`;
    if (!s?.reported) return html`<span class="num jdim">—</span><span class="num jdim">—</span>`;
    const cache = facts(msg(str`Cache read ${tokenCount(s.cache_read)}`), msg(str`Cache write ${tokenCount(s.cache_creation)}`));
    return html`<span class="num" title=${cache}>${tokenCount(s.input + s.output)}</span><span class="num">${usd(s.cost)}</span>`;
  }

  override render() {
    const d = this.plan ? deriveRun(this.journal, this.plan) : null;
    const all = d?.rows ?? [];
    const rows = sortTasks(filterTasks(all, this.kind, this.q));
    if (!rows.length)
      return html`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${all.length ? msg('No tasks match the filter') : msg('No tasks')}</div>`;
    const outcomes: ReadonlyMap<string, TaskOutcome> = d?.outcomes ?? new Map();
    // A kind and unit with more than one task (a loop's passes): each row names its pass.
    const per = new Map<string, number>();
    for (const t of all) per.set(`${t.kind}|${t.unit}`, (per.get(`${t.kind}|${t.unit}`) ?? 0) + 1);
    const maxWall = Math.max(1, ...rows.map((t) => t.wall_s));
    // Tokens and cost per task, over all its attempts.
    const spend = new Map<string, Spend>();
    for (const r of this.journal) addRow(spend.get(r.key) ?? spend.set(r.key, emptySpend()).get(r.key)!, r);
    return html`<div class="trow hd">
        <span title=${msg('Kind · unit')}>${msg('Task')}</span><span class="num" title=${msg('Attempts that ran')}>${msg('Attempts')}</span>
        <span class="num" title=${msg('Sum over all attempts')}>${msg('Time')}</span>
        <span class="num" title=${msg('Input and output tokens, all attempts')}>${msg('Tokens')}</span>
        <span class="num" title=${msg('Reported by the coding agent')}>${msg('Cost')}</span>
        <span class="num">${msg('Last attempt ended')}</span>
        <span class="st">${msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' })}</span>
      </div>
      ${repeat(
        rows,
        (t) => t.key,
        (t) => {
          const py = isPython(t);
          const running = t.outcome === 'running';
          // A task that has not run (refused, skipped, waiting) has no attempts and no time.
          const ran = t.tries.length > 0;
          const cause = this.cause(t, outcomes);
          const pass = t.pass !== null && (per.get(`${t.kind}|${t.unit}`) ?? 0) > 1 ? t.pass : null;
          // A Python task has no transcript, but its detail shows what it was given and what it left.
          return html`<div class="trow ${running ? 'running' : ''} ${py ? 'py' : ''}"
            @click=${() => emit(this, 'ca-open-task', py ? { key: t.key, view: 'output' } : { key: t.key })}>
            <span class="grow jmono" title=${t.key}>
              <span class="k-ic ${py ? '' : 'llm'}" title=${py ? msg('Python task') : msg('Agent task')}><span aria-hidden="true">${py ? '⚙' : '✦'}</span><span class="sr">${py ? msg('Python task') : msg('Agent task')}</span></span>${t.kind}
              ${t.unit ? html`<span class="jdim">· ${t.unit}</span>` : nothing}${pass !== null ? html`<span class="pass">${passLabel(pass)}</span>` : nothing}
            </span>
            <span class="num">${t.tries.length}</span>
            <span class="num wall">${ran
              ? html`${fmtDur(t.wall_s)}<span class="jdur"><i class=${py ? '' : 'llm'}
                  style="width:${Math.max(4, Math.round((100 * t.wall_s) / maxWall))}%"></i></span>`
              : html`<span class="jdim">${msg('none', { id: 'none', desc: 'An empty value' })}</span><span class="jdur" style="visibility:hidden"></span>`}</span>
            ${this.spendCells(ran, spend.get(t.key))}
            <span class="num meta">${ran ? localTime(t.tries[t.tries.length - 1]?.ts, true) : msg('none', { id: 'none', desc: 'An empty value' })}</span>
            <span class="st"><span class="pill o-${t.outcome}" title=${t.last_stop}>${taskStatusLabel(t.outcome, this.live)}</span>${cause
              ? html`<span class="cause">${cause}</span>`
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
