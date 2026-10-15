import { deriveRun, isPython, type JournalRow, type Plan, type TaskRow } from '@contraagent/api';
import '@contraagent/elements/data-table/define';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import { base, meterStyles } from '@contraagent/elements/styles';
import { executorIconStyles } from '../../words/executor.js';
import { tableStrings } from '../../words/table.js';
import { filterTasks, sortTasks } from '../../adapters/filters.js';
import { taskColumns } from '../../adapters/task-columns.js';

/** The look of the rows and of what their cells draw, inside `<cae-data-table>`. */
const CELLS = [
  meterStyles,
  executorIconStyles,
  css`
    caption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    /* the numbers sit tight together, right-aligned; the status comes last and takes the spare width, so no gap opens inside the row */
    tr { column-gap: 20px; padding: 6px 12px; }
    tbody tr { border-bottom: 0; border-radius: 8px; transition: background 0.15s; }
    thead tr { align-items: end; white-space: nowrap; padding: 4px 12px 8px; margin-bottom: 4px; }
    tbody [data-col='ended'] { font-size: var(--font-size-sm); }
    .wall { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
    .wall .jdur { width: 56px; margin: 0; flex: none; }
    .grow { display: flex; align-items: center; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .grow .jdim { margin-left: 8px; }
    .pass { margin-left: 8px; font-size: 11px; color: var(--text-muted); }
    .cause { display: block; font-size: 11px; color: var(--text-muted); margin-top: 2px; white-space: normal; overflow-wrap: anywhere; }
    /* a narrow table (its container is <cae-data-table>): the task, its status and its time */
    @container (max-width: 760px) {
      tr { grid-template-columns: minmax(0, 1fr) 128px 90px; }
      [data-col='attempts'], [data-col='tokens'], [data-col='cost'], [data-col='ended'] { display: none; }
    }
  `,
];

/**
 * Every task of the run, one row each (`deriveRun(...).rows`: the plan joined with the
 * journal, so a task that never ran is a row too): what happened to it, its
 * attempts, time, tokens and cost. A row opens the task's detail (`ca-open-task`),
 * with a click or with Enter.
 *
 * @fires ca-open-task - `{key}`: a task's row was opened (its key; a Python task with `view: 'output'`)
 */
@customElement('ca-task-table')
@localized()
export class CaTaskTable extends LitElement {
  static override styles = [base, css`:host { display: block; margin-top: 4px; }`];

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

  private open(rows: readonly TaskRow[], key: string): void {
    const t = rows.find((r) => r.key === key);
    // A Python task has no transcript, but its detail shows what it was given and what it left.
    if (t) emit(this, 'ca-open-task', isPython(t) ? { key, view: 'output' } : { key });
  }

  override render() {
    const d = this.plan ? deriveRun(this.journal, this.plan) : null;
    const all = d?.rows ?? [];
    const rows = sortTasks(filterTasks(all, this.kind, this.q));
    if (!rows.length)
      return html`<div class="blank"><span class="ic" aria-hidden="true">≡</span>${all.length ? msg('No tasks match the filter') : msg('No tasks')}</div>`;
    const columns = taskColumns({ run: this.run, live: this.live, outcomes: d?.outcomes ?? new Map(), all, rows, journal: this.journal });
    return html`<cae-data-table
      .columns=${columns}
      .rows=${rows}
      .rowKey=${(t: TaskRow) => t.key}
      .rowTone=${(t: TaskRow) => (t.outcome === 'running' ? 'running' : undefined)}
      .rowAttrs=${(t: TaskRow) => ({ 'data-executor': isPython(t) ? 'python' : 'agent' })}
      .cellStyles=${CELLS}
      .caption=${msg('Tasks', { id: 'tab-tasks', desc: 'Tab: the list of tasks' })}
      .strings=${tableStrings(msg('No tasks'))}
      @cae-activate=${(e: CustomEvent<{ id: string }>) => this.open(rows, e.detail.id)}
    ></cae-data-table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-task-table': CaTaskTable;
  }
}
