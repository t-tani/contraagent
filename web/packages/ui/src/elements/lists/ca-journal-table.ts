import { deriveRun, isBad, isLaunched, isPython, rowId, type JournalRow, type Plan } from '@contraagent/api';
import '@contraagent/elements/data-table/define';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import { stopTone, type Tone } from '../../lib/tone.js';
import { toneAttr } from '@contraagent/elements';
import { markOf } from '@contraagent/elements/primitives';
import { base, meterStyles } from '@contraagent/elements/styles';
import { executorIconStyles } from '../../words/executor.js';
import { tableStrings } from '../../words/table.js';
import { replayedTip } from '../../words/run-line.js';
import { retryTip } from '../../words/attempts.js';
import { correctionTip } from '../../words/contract.js';
import { filterJournal, hadFixup, journalTally, retriedKeys } from '../../adapters/filters.js';
import { journalColumns, shortStop } from '../../adapters/journal-columns.js';

/** The look of the rows and of what their cells draw, inside `<cae-data-table>`. */
const CELLS = [
  meterStyles,
  executorIconStyles,
  css`
    caption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    tr { column-gap: 12px; row-gap: 2px; padding: 7px 12px; border-bottom: 1px solid var(--line); font-size: 12px; min-width: 980px; }
    th, td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    tbody [data-col='outcome'], tbody [data-col='agent'], tbody [data-col='tokens'], tbody [data-col='reason'] { white-space: normal; }
    /* a cell takes the size of the one line it draws, so the line sits where it did as the cell itself */
    tbody [data-col='ended'], tbody [data-col='task'] { font-family: var(--mono); font-size: 11.5px; }
    thead { position: sticky; top: 0; z-index: 1; }
    thead tr { color: var(--text-muted); font-size: 11px; background: var(--bg); }
    tbody tr[data-key]:hover { background: var(--card); }
    tbody tr[data-executor='python'] { opacity: 0.85; }
    tbody tr[data-executor='python']:hover, tbody tr[data-executor='python'][data-tone='failed'] { opacity: 1; }
    tbody tr[data-ran='false'] { opacity: 0.8; }
    tbody tr[data-fresh] { animation: rowin 1.6s var(--ease); }
    tr.empty { min-width: 0; }
    tr.empty td { font-size: var(--font-size-sm); }
    .jwhy { color: var(--text-2); overflow-wrap: anywhere; }
    .later { color: var(--status-done); }
    .nw { white-space: nowrap; }
    .unread { color: var(--status-attention); }
    .two { display: flex; flex-direction: column; line-height: 1.35; }
    /* the status mark stays beside its word, the lines under it align with the word */
    .jstop.two { display: grid; grid-template-columns: auto minmax(0, 1fr); align-content: center; }
    .jstop.two > * { grid-column: 2; }
    .jstop.two::before { grid-row: 1; }
    .two .sub { color: var(--text-muted); font-size: 11px; white-space: normal; overflow-wrap: anywhere; }
    [data-col='tokens'] .two > span { white-space: nowrap; }
    .sub .q { color: var(--text-2); font-family: var(--mono); white-space: nowrap; }
    .jstop .sub { font-weight: 400; }
    .cost { font-variant-numeric: tabular-nums; color: var(--text-2); }
  `,
];

/**
 * The run's history: every finished attempt, newest first (`journal.jsonl`),
 * with a chip per outcome that filters by it (`ca-filter`). A row opens the
 * task's detail, with a click or with Enter.
 *
 * @fires ca-filter - `{stop}`: a chip was toggled: a stop value, 'fixup' or 'retried' ('' clears)
 * @fires ca-open-task - `{key}`: an attempt's row was opened (its task's key; a Python task with `view: 'output'`)
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
  /** The pipeline's own journal columns (`RunSummary.row_extras`): a column each. */
  @property({ attribute: false }) extras: readonly string[] = [];
  /** The run is a replay that also launched (`mixedReplay`): each attempt played from its recording is marked, and counted in a filter. */
  @property({ type: Boolean, attribute: 'replay-marks' }) replayMarks = false;

  /** The counts of the rows, and the rows shown: for the rows (and filter) they were made from. */
  private counts: { rows: JournalRow[]; replayMarks: boolean; fixups: number; retried: number; replayed: number; tally: ReturnType<typeof journalTally> } | null = null;
  private shown: { rows: JournalRow[]; kind: string; stop: string; q: string; shown: JournalRow[] } | null = null;

  private open(rows: readonly JournalRow[], id: string): void {
    const e = rows.find((r) => rowId(r) === id);
    if (e) emit(this, 'ca-open-task', isPython(e) ? { key: e.key, view: 'output' } : { key: e.key });
  }

  override render() {
    const s = this.shown;
    const rows = s && s.rows === this.rows && s.kind === this.kind && s.stop === this.stop && s.q === this.q ? s.shown : filterJournal(this.rows, this.kind, this.stop, this.q).reverse();
    this.shown = { rows: this.rows, kind: this.kind, stop: this.stop, q: this.q, shown: rows };
    if (this.counts?.rows !== this.rows || this.counts.replayMarks !== this.replayMarks) {
      this.counts = {
        rows: this.rows,
        replayMarks: this.replayMarks,
        fixups: this.rows.filter(hadFixup).length,
        retried: retriedKeys(this.rows).size,
        replayed: this.replayMarks ? this.rows.filter((r) => r.replayed).length : 0,
        tally: journalTally(this.rows),
      };
    }
    const { fixups, retried, replayed, tally } = this.counts;
    const chip = (k: string, label: string, n: number, tip: string, tone: Tone = 'neutral') =>
      html`<button type="button" class="jchip ${this.stop === k ? 'on' : ''}" data-tone=${toneAttr(tone)} data-mark=${markOf(tone) ?? nothing}
        aria-pressed=${this.stop === k} title=${tip}
        @click=${() => emit(this, 'ca-filter', { stop: this.stop === k ? '' : k })}>${label} <b>${n}</b></button>`;
    const columns = journalColumns({ run: this.run, outcomes: deriveRun(this.rows, this.plan).outcomes, journal: this.rows, rows, extras: this.extras, replayMarks: this.replayMarks });
    return html`<div class="jtally">
        ${tally.map(([k, c]) => chip(k, shortStop(k), c, k, stopTone(k)))}
        ${fixups ? chip('fixup', msg('attempts with corrections'), fixups, correctionTip()) : nothing}
        ${retried ? chip('retried', msg('tasks retried'), retried, retryTip()) : nothing}
        ${replayed ? chip('replayed', msg('attempts replayed'), replayed, replayedTip()) : nothing}
      </div>
      <cae-data-table
        .columns=${columns}
        .rows=${rows}
        .rowKey=${rowId}
        .rowTone=${(e: JournalRow) => (isLaunched(e) && isBad(e) ? 'failed' : undefined)}
        .rowAttrs=${(e: JournalRow) => ({
          'data-executor': isPython(e) ? 'python' : 'agent',
          ...(isLaunched(e) ? {} : { 'data-ran': 'false' }),
          ...(this.fresh.has(rowId(e)) ? { 'data-fresh': '' } : {}),
        })}
        .cellStyles=${CELLS}
        .caption=${msg('History')}
        .strings=${tableStrings(msg('No finished attempts'))}
        @cae-activate=${(e: CustomEvent<{ id: string }>) => this.open(rows, e.detail.id)}
      ></cae-data-table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-journal-table': CaJournalTable;
  }
}
