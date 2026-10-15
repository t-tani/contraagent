import { deriveRun, type JournalRow, type LaunchEvent, type MonitorClient, type Plan, type TaskDetail, type TaskOutcome } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { emit, type RoundInfo, type RoundsChangedDetail } from '../../core/events.js';
import { TASK_VIEWS, type TaskView } from '../../core/route.js';
import { TaskDetailController } from '../../controllers/task-detail.js';
import { base } from '@contraagent/elements/styles';
import { executorIconStyles } from '../../words/executor.js';
import { contractStyles } from '../shared/contract-parts.js';
import './ca-transcript.js';
import type { CaTranscript } from './ca-transcript.js';
import { tagStyles } from '@contraagent/elements/transcript';
import { isPy, type TaskContext } from './context.js';
import { taskHeader } from './header.js';
import { noTranscript } from './panes/transcript.js';
import { inputPane, outputPane } from './panes/io.js';
import { definitionPane } from './panes/definition.js';
import { taskViewStyles } from './styles.js';

/** Each view's tab label, in the current locale (call at render time). */
const viewLabel = (): Record<TaskView, string> => ({
  transcript: msg('Transcript'),
  input: msg('Input'),
  output: msg('Output', { id: 'view-output', desc: 'Tab: the files a task wrote' }),
  definition: msg('Definition'),
});

/**
 * One task: who ran it, every finished attempt, and four views of it: the
 * transcript (live), its input (params, upstream outputs, declared inputs, the
 * prompt), its output (files against their contracts, the result, who uses it)
 * and its definition. Sends `ca-navigate` with `view` or `round`, and
 * `ca-open-task` for a linked task.
 *
 * @fires ca-navigate - `{view}` or `{round}`: another view or round of this task
 * @fires ca-open-task - `{key}`: an upstream or downstream task was clicked
 */
@customElement('ca-task-view')
@localized()
export class CaTaskView extends LitElement {
  static override styles = [base, contractStyles, tagStyles, executorIconStyles, taskViewStyles];

  @property({ attribute: false }) client!: MonitorClient;
  @property({ attribute: 'base-url' }) baseUrl = '';
  @property() run = '';
  /** A task key; null when there is no task to show. */
  @property({ attribute: false }) taskKey: string | null = null;
  @property() view: TaskView = 'transcript';
  /** The round shown, 1-based; null follows the latest. */
  @property({ attribute: false }) round: number | null = null;
  /** The run is live. */
  @property({ type: Boolean }) live = false;
  /** The whole run's journal: the subscription readings other tasks took after this one, and what happened to the tasks it reads from. Optional. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The run's plan: whether a task with no attempt is waiting or not started, and which earlier task stopped it. Optional. */
  @property({ attribute: false }) plan: Plan | null = null;
  /** Read from an export (`Info.export`): it holds no transcript. */
  @property({ type: Boolean }) exported = false;
  /** The run is a replay that also launched (`mixedReplay`): each attempt played from its recording is marked. */
  @property({ type: Boolean, attribute: 'replay-marks' }) replayMarks = false;

  private readonly detail = new TaskDetailController(this);
  @query('ca-transcript') private transcriptEl?: CaTranscript;
  @state() private launches: (LaunchEvent | null)[] = [];
  @state() private shownRound = -1;
  @state() private rounds: RoundInfo[] = [];
  /** What happened to every task of the run (`deriveRun` of `journal` and `plan`), by key. */
  private outcomes: ReadonlyMap<string, TaskOutcome> = new Map();

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('run') || changed.has('taskKey') || changed.has('client')) {
      this.detail.load(this.client, this.run, this.taskKey);
      this.launches = [];
      this.shownRound = -1;
      this.rounds = [];
    }
    this.outcomes = this.plan ? deriveRun(this.journal, this.plan).outcomes : new Map<string, TaskOutcome>();
  }

  /** The view shown: a Python task has no transcript, so it opens on its output. */
  private shownView(d: TaskDetail): TaskView {
    return this.view === 'transcript' && isPy(d) && !d.stream ? 'output' : this.view;
  }

  private revealSearch(query: string, nth: number): void {
    const at = this.transcriptEl?.revealWebSearch(query, nth);
    emit(this, 'ca-navigate', at ? { view: 'transcript', round: at.round } : { view: 'transcript' });
  }

  override render() {
    const key = this.taskKey;
    if (!key) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${msg('No task selected')}</b></div>`;
    }
    const d = this.detail.value;
    if (!d) return html`<div class="taskmeta meta"><strong>${key}</strong> ${msg('Loading…')}</div>`;
    const c: TaskContext = {
      host: this,
      run: this.run,
      detail: d,
      live: d.launches.length > 0 && this.live,
      journal: this.journal,
      plan: this.plan,
      outcomes: this.outcomes,
      launches: this.launches,
      shownRound: this.shownRound,
      rounds: this.rounds,
      exported: this.exported,
      replayMarks: this.replayMarks,
    };
    const view = this.shownView(d);
    return html`${taskHeader(c, key, (q, nth) => this.revealSearch(q, nth))} ${this.renderViews(d, view)}
      ${d.stream
        ? html`<ca-transcript .run=${this.run} .stream=${d.stream} base-url=${this.baseUrl} .client=${this.client} .live=${c.live}
            .rows=${d.rows} .round=${this.round} mode=${view === 'transcript' ? 'full' : view === 'input' ? 'tabs' : 'none'}
            @ca-rounds=${(e: CustomEvent<RoundsChangedDetail>) => {
              this.launches = e.detail.launches;
              this.shownRound = e.detail.shown;
              this.rounds = e.detail.rounds;
            }}></ca-transcript>`
        : view === 'transcript'
          ? noTranscript(c)
          : nothing}
      ${view !== 'transcript' ? html`<div class="pane">${this.renderPane(c, view)}</div>` : nothing}`;
  }

  private renderViews(d: TaskDetail, view: TaskView) {
    const io = d.io;
    const py = isPy(d) && !d.stream;
    const n: Partial<Record<TaskView, number>> = {
      input: new Set([...io.inputs.map((o) => o.path), ...io.upstream.flatMap((u) => u.outputs.map((o) => o.path))]).size + Object.keys(io.params).length,
      output: io.outputs.length,
    };
    return html`<div class="tviews" role="tablist">
      ${TASK_VIEWS.filter((id) => !(py && id === 'transcript')).map((id) => {
        const label = viewLabel()[id];
        return html`<button type="button" role="tab" aria-selected=${id === view} class="tview ${id === view ? 'sel' : ''}"
          @click=${() => emit(this, 'ca-navigate', { view: id })}>
          ${label}${n[id] ? html`<span class="badge">${n[id]}</span>` : nothing}
        </button>`;
      })}
    </div>`;
  }

  private renderPane(c: TaskContext, view: TaskView) {
    if (view === 'input') return inputPane(c);
    if (view === 'output') return outputPane(c);
    return definitionPane(c);
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-task-view': CaTaskView;
  }
}
