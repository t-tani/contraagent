import {
  deriveRun,
  isLaunched,
  isPython,
  outcomeOf,
  runReadings,
  runStarts,
  spendOf,
  tryQuota,
  type JournalRow,
  type LaunchEvent,
  type MonitorClient,
  type Outcome,
  type Plan,
  type SourcedReading,
  type Spend,
  type TaskDetail,
  type TaskOutcome,
  type UpstreamTask,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { emit } from '../../events.js';
import { facts, fmtDur, kindUnit, localTime, tokens, unreadEvents, usd } from '../../lib/format.js';
import {
  attemptLabel,
  attemptNames,
  correctionsText,
  credentialLabel,
  credentialTip,
  inputCause,
  inputProblems,
  modelSwitch,
  notStartedCause,
  outcomeLabel,
  runRelative,
  stopLabel,
} from '../../lib/labels.js';
import { accountReading, readingShort, readingTip } from '../../lib/quota-format.js';
import { stopTone, type Tone } from '../../lib/tone.js';
import { TASK_VIEWS, type TaskView } from '../../route.js';
import { base } from '../../styles/base.js';
import '../shared/ca-definition.js';
import '../shared/ca-json-tree.js';
import '../shared/ca-markdown.js';
import { contractStyles, ioFileCard, statusLabel, statusWhy, type Producer } from '../shared/contract-parts.js';
import { inputView, notPassed, type EarlierTask, type InputFile } from './inputs.js';
import { taskChip } from '../shared/task-chip.js';
import './ca-transcript.js';
import type { CaTranscript, RoundsChangedDetail } from './ca-transcript.js';
import { roundLabel, roundWhy } from './rounds.js';
import { agentLabel, checkMessage, launchWho, type RoundInfo, type Who } from './transcript-model.js';
import { whoChips, whoStyles } from './who.js';

/** Each view's tab label, in the current locale (call at render time). */
const viewLabel = (): Record<TaskView, string> => ({
  transcript: msg('Transcript'),
  input: msg('Input'),
  output: msg('Output'),
  definition: msg('Definition'),
});

/** `N corrections` for a journal row whose attempt needed them ('' when none). */
const correctionsOf = (r: { rounds?: number | null }): string => correctionsText((r.rounds || 1) - 1);

/** Keys of `TaskDetail` the header shows itself; any other key (a `task_detail` callback's) is shown as JSON. */
const SHOWN_KEYS = new Set(['key', 'rows', 'launches', 'stream', 'task_detail_error', 'definition', 'io']);

const emptyDetail = (key: string): TaskDetail => ({
  key,
  rows: [],
  launches: [],
  definition: null,
  io: { params: {}, inputs: [], outputs: [], executor: 'agent', upstream: [], downstream: [] },
  stream: null,
});

const pill = (s: string, label = s) => html`<span class="pill p-${s}">${label}</span>`;
/** The pill class of a stop's tone (`stopTone`). */
const STOP_PILL: Partial<Record<Tone, string>> = { done: 'completed', attention: 'invalid_input', muted: 'skipped', running: 'running', failed: 'error' };
const valueText = (v: unknown): string => (typeof v === 'string' ? v : JSON.stringify(v) ?? String(v));
const sameJson = (a: unknown, b: unknown): boolean => {
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
};

/** The status mark and the word a screen reader says for it. */
const mark = (ok: boolean) =>
  html`<span aria-hidden="true">${ok ? '✓' : '✕'}</span><span class="sr">${ok ? msg('passed') : msg('failed')}</span>`;


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
  static override styles = [
    base,
    contractStyles,
    whoStyles,
    css`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      .taskmeta { flex: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
        border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; color: var(--text-2); }
      .tm-head { display: flex; gap: 12px; align-items: center; }
      .tm-av { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-size: 16px; flex: none;
        background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
      .tm-av.py { background: var(--raise); color: var(--text-muted); box-shadow: none; }
      .tm-name { font-size: 15px; font-weight: 600; color: var(--text); display: flex; gap: 8px; align-items: center; }
      .verdict { font-size: 12.5px; color: var(--text); margin-top: 2px; }
      .verdict.failed { color: var(--status-failed); }
      .verdict.attention { color: var(--status-attention); }
      .verdict.mut { color: var(--text-muted); }
      .whos { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
      .runchips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
      .who.ident { color: var(--text-2); font-family: var(--mono); font-weight: 500; }
      .spend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 6px; font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
      .spend b { color: var(--text); font-weight: 600; }
      .spend.quota { flex-direction: column; gap: 0; }
      .usage-wrap { overflow-x: auto; margin: 4px 0 12px; }
      /* sized to its content (a full-width table spreads a few numbers far apart); the wrap scrolls when it is wider */
      .usage { width: auto; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
      .usage th { text-align: right; font-weight: 600; color: var(--text-muted); font-size: 10.5px; white-space: nowrap;
        padding: 6px 14px; border-bottom: 1px solid var(--line2); vertical-align: bottom; }
      .usage td { text-align: right; padding: 8px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: baseline; }
      .usage th:first-child, .usage td:first-child { padding-left: 4px; }
      .usage td.l.jmono { font-size: 12px; }
      /* the subscription readings wrap at a narrow width rather than push the table past the edge */
      .usage td.l:not(:first-child):not(.jmono) { white-space: normal; min-width: 12ch; }
      .usage th.l, .usage td.l { text-align: left; }
      .usage tr.hop td { padding-top: 4px; padding-bottom: 4px; color: var(--text-muted); }
      .usage tr.hop td:first-child { padding-left: 28px; }
      .runchip { font-size: 11px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line2); color: var(--text-2); }
      .runchip.ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
      .runchip.bad { border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); color: var(--status-failed); background: var(--status-failed-bg); }
      .io-fold { margin-top: 6px; }
      .io-fold > summary, .launch > summary { cursor: pointer; color: var(--text-muted); }
      .searches { margin: 4px 0 0; padding-left: 22px; }
      .unread { color: var(--status-attention); margin-top: 4px; }
      .qlink { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; text-align: left; font: inherit; }
      .qlink:hover { text-decoration: underline; }

      .tviews { flex: none; display: flex; gap: 4px; margin: 2px 0 8px; border-bottom: 1px solid var(--line); }
      .tview { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 6px 14px; cursor: pointer; }
      .tview:hover { color: var(--text-2); }
      .tview.sel { color: var(--text); border-bottom-color: var(--accent); }
      .tview .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); }

      .pane { flex: 1 1 auto; min-height: 0; overflow: auto; }
      .upstream { margin-bottom: 12px; }
      .up-hd { display: flex; align-items: center; gap: 10px; margin: 2px 0 6px; }
      .down { display: flex; flex-wrap: wrap; gap: 8px; }
      .notrans { flex: 1 1 auto; border: 1px solid var(--line); border-radius: 14px; }
      details.upstream > summary { cursor: pointer; list-style: none; }
      details.upstream > summary::-webkit-details-marker { display: none; }
      .params td { vertical-align: top; }
      .from { color: var(--text-muted); white-space: nowrap; }
    `,
  ];


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

  @state() private detail: TaskDetail | null = null;
  @query('ca-transcript') private transcriptEl?: CaTranscript;
  @state() private launches: (LaunchEvent | null)[] = [];
  @state() private shownRound = -1;
  @state() private rounds: RoundInfo[] = [];
  private token = 0;
  /** What happened to every task of the run (`deriveRun` of `journal` and `plan`), by key. */
  private outcomes: ReadonlyMap<string, TaskOutcome> = new Map();

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('run') || changed.has('taskKey') || changed.has('client')) void this.fetch();
    this.outcomes = this.plan ? deriveRun(this.journal, this.plan).outcomes : new Map<string, TaskOutcome>();
  }

  private async fetch(): Promise<void> {
    const token = ++this.token;
    this.detail = null;
    this.launches = [];
    this.shownRound = -1;
    this.rounds = [];
    const { run, taskKey } = this;
    if (!run || !taskKey || !this.client) return;
    let d: TaskDetail;
    try {
      d = await this.client.task(run, taskKey);
    } catch {
      d = emptyDetail(taskKey);
    }
    if (token === this.token) this.detail = d;
  }

  private openTask(e: Event, key: string): void {
    e.preventDefault();
    emit(this, 'ca-open-task', { key });
  }

  /** A Python task: it runs in the pipeline's process, so it has no agent session and no transcript. */
  private isPy(d: TaskDetail): boolean {
    return isPython(d.io) || d.rows.some(isPython);
  }

  /** The coding agent ran for this task at least once. */
  private hadSession(d: TaskDetail): boolean {
    return !this.isPy(d) && (!!d.stream || d.launches.length > 0 || d.rows.some(isLaunched));
  }

  /** The view shown: a Python task has no transcript, so it opens on its output. */
  private shownView(d: TaskDetail): TaskView {
    return this.view === 'transcript' && this.isPy(d) && !d.stream ? 'output' : this.view;
  }

  /** The task's state in the run: running, waiting, not started, done ... */
  private stateOf(d: TaskDetail, live: boolean): Outcome {
    return live ? 'running' : (this.outcomes.get(d.key)?.outcome ?? outcomeOf(undefined, d.rows));
  }

  /** The earlier task that writes `path`, by the task's own upstream list. */
  private writerOf(path: string): UpstreamTask | undefined {
    return this.detail?.io.upstream.find((u) => u.outputs.some((o) => o.path === path));
  }

  /** For a contract card: who writes a file, and what happened to that task. */
  private producerOf = (path: string): Producer | undefined => {
    const u = this.writerOf(path);
    if (!u) return undefined;
    const o = u.outputs.find((x) => x.path === path);
    return { name: kindUnit(u), written: !!o?.file.exists, outcome: this.outcomes.get(u.key)?.outcome };
  };

  /**
   * Why a task did not start, as a phrase after "Not started: ": the input its
   * refusal names and why it is not ready, or the earlier task that failed; '' when unknown.
   */
  private notStartedCause(d: TaskDetail): string {
    const own = this.outcomes.get(d.key) ?? { attempts: d.rows, cause: null };
    const cause = notStartedCause(own, this.outcomes, this.run, (path) => this.writerOf(path)?.key);
    if (cause) return cause;
    // A task the plan does not list (no outcomes): name the earlier task by its upstream entry.
    const p = inputProblems(d.rows[d.rows.length - 1]?.reason)[0];
    const w = p ? this.writerOf(p.path) : undefined;
    return p ? inputCause(runRelative(p.path, this.run), p.problem, w ? { name: kindUnit(w) } : undefined) : '';
  }

  /** The earlier task a task that did not start waits for: the one its refusal names, or the failed one upstream. */
  private culprit(d: TaskDetail): { key: string; kind: string; unit: string; executor?: string } | undefined {
    const p = inputProblems(d.rows[d.rows.length - 1]?.reason)[0];
    const byKey = p?.producer ? this.outcomes.get(p.producer) : undefined;
    if (byKey) return byKey;
    const w = p ? this.writerOf(p.path) : undefined;
    if (w) return w;
    const cause = this.outcomes.get(d.key)?.cause;
    return cause ? this.outcomes.get(cause) : undefined;
  }

  private link(u: { key: string; kind: string; unit: string }) {
    return html`<a class="lnk" href="#" @click=${(e: Event) => this.openTask(e, u.key)}>${kindUnit(u)}</a>`;
  }

  override render() {
    const key = this.taskKey;
    if (!key) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${msg('No task selected')}</b></div>`;
    }
    const d = this.detail;
    if (!d) return html`<div class="taskmeta meta"><strong>${key}</strong> ${msg('Loading…')}</div>`;
    const taskLive = d.launches.length > 0 && this.live;
    const view = this.shownView(d);
    return html`${this.renderMeta(key, d, taskLive)} ${this.renderViews(d, view)}
      ${d.stream
        ? html`<ca-transcript .run=${this.run} .stream=${d.stream} base-url=${this.baseUrl} .client=${this.client} .live=${taskLive}
            .rows=${d.rows} .round=${this.round} mode=${view === 'transcript' ? 'full' : view === 'input' ? 'tabs' : 'none'}
            @rounds-changed=${(e: CustomEvent<RoundsChangedDetail>) => {
              this.launches = e.detail.launches;
              this.shownRound = e.detail.shown;
              this.rounds = e.detail.rounds;
            }}></ca-transcript>`
        : view === 'transcript'
          ? this.noTranscript(d, taskLive)
          : nothing}
      ${view !== 'transcript' ? html`<div class="pane">${this.renderPane(d, view, taskLive)}</div>` : nothing}`;
  }

  /** Why there is no transcript: the task's state, or a transcript that was not saved. */
  private noTranscript(d: TaskDetail, live: boolean) {
    const state = this.stateOf(d, live);
    if (state === 'not_started') {
      // The cause is in the verdict above; here, the state and the earlier task to open.
      const up = this.culprit(d);
      return html`<div class="blank notrans"><span class="ic" aria-hidden="true">⊘</span><b>${facts(msg('No transcript'), outcomeLabel(state))}</b>
        ${up ? html`<span>${msg('Earlier task')} ${taskChip(this, kindUnit(up), up)}</span>` : nothing}</div>`;
    }
    if (this.hadSession(d)) {
      return html`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${msg('No transcript')}</b>
        <span>${msg('Transcript not saved (keep_transcripts = false)')}</span></div>`;
    }
    return html`<div class="blank notrans"><span class="ic" aria-hidden="true">✦</span><b>${facts(msg('No transcript'), outcomeLabel(state))}</b></div>`;
  }

  /** One line under the title: what happened to the task, in words, and its look (`failed`, `attention`, `mut`). */
  private verdict(d: TaskDetail, live: boolean): [text: string, look: string] {
    const rows = d.rows;
    const tries = rows.filter(isLaunched);
    const last = rows[rows.length - 1];
    const state = this.stateOf(d, live);
    switch (state) {
      case 'running':
        return [msg('Running'), ''];
      case 'waiting':
        return [msg('Waiting'), 'mut'];
      case 'skipped':
        return [msg('Skipped'), 'mut'];
      case 'not_started': {
        const cause = this.notStartedCause(d);
        return [cause ? msg(str`Not started: ${cause}`) : msg('Not started'), 'attention'];
      }
      case 'failed': {
        const why = runRelative(last?.reason, this.run) || stopLabel(last?.stop);
        return [tries.length > 1 ? msg(str`Failed on all ${tries.length} attempts: ${why}`) : msg(str`Failed: ${why}`), 'failed'];
      }
      default:
        break;
    }
    if (!last) return [outcomeLabel(state), ''];
    const fails = tries.filter((r) => !r.ok);
    if (fails.length) {
      const why = runRelative(fails[0]?.reason, this.run) || stopLabel(fails[0]?.stop);
      return [
        fails.length === 1
          ? msg(str`Done on attempt ${tries.length} after 1 failed attempt. First failure: ${why}`)
          : msg(str`Done on attempt ${tries.length} after ${fails.length} failed attempts. First failure: ${why}`),
        '',
      ];
    }
    const corrections = (last.rounds || 1) - 1 + (last.hook_errors ?? []).length;
    if (corrections > 0) {
      const errors = [...(last.hook_errors ?? []).flat(), ...(last.round_errors ?? []).flat(), ...this.rounds.flatMap((r) => r.rejectedWith)];
      const first = errors[0] ? checkMessage(runRelative(errors[0], this.run)) : '';
      if (!first) return [corrections === 1 ? msg('Done after 1 correction') : msg(str`Done after ${corrections} corrections`), ''];
      return [
        corrections === 1
          ? msg(str`Done after 1 correction. First failed check: ${first}`)
          : msg(str`Done after ${corrections} corrections. First failed check: ${first}`),
        '',
      ];
    }
    const sw = modelSwitch(last.hops);
    if (sw) return [msg(str`Done after a model switch: ${sw}`), ''];
    return [msg('Done'), ''];
  }

  /** The model of the latest round, as its launch named it (`--model`). */
  private streamModel(): string {
    for (let i = this.launches.length - 1; i >= 0; i--) {
      const l = this.launches[i];
      const m = l ? launchWho(l).model : '';
      if (m) return m;
    }
    return '';
  }

  private renderMeta(key: string, d: TaskDetail, live: boolean) {
    const { rows, launches } = d;
    const py = this.isPy(d);
    const session = this.hadSession(d);
    const byTs = rows.slice().sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
    const lastRow = byTs[byTs.length - 1];
    const lc0 = launches[0];
    const who: Who = {
      agent: agentLabel(lc0?.cmd ? lc0.cmd.split(' ')[0] : lastRow?.agent),
      // The journal may not name the model (an agent that does not report it): fall back to the one the transcript shows.
      model: lc0?.model || lastRow?.model || this.streamModel(),
      role: lc0?.role || '',
    };
    const otherModels = session ? [...new Set(byTs.map((r) => r.model).filter((x): x is string => !!x && x !== who.model))] : [];
    const first = rows[0];
    const tries = rows.filter(isLaunched);
    const extras = Object.entries(d).filter(([k]) => !SHOWN_KEYS.has(k));
    const [verdict, look] = this.verdict(d, live);
    const kindName = py ? msg('Python task') : msg('Agent task');
    const node = this.plan?.nodes.find((n) => n.key === d.key);
    return html`<div class="taskmeta">
      <div class="tm-head">
        <span class="tm-av ${py ? 'py' : ''}" title=${kindName}><span aria-hidden="true">${py ? '⚙' : '✦'}</span><span class="sr">${kindName}</span></span>
        <div style="min-width:0">
          <div class="tm-name" title=${key}>${first ? kindUnit(first) : node ? kindUnit(node) : key.replace(/^python:/, '')} ${live ? pill('running', msg('running')) : nothing}</div>
          <div class="verdict ${look}">${verdict}</div>
          ${session
            ? html`<div class="whos">
                ${whoChips(who)}${this.identityChip(tries)}
                ${otherModels.length
                  ? html`<span class="meta">${otherModels.length === 1
                      ? msg(str`Earlier attempts used model ${otherModels[0] ?? ''}`)
                      : msg(str`Earlier attempts used models ${otherModels.join(', ')}`)}</span>`
                  : nothing}
              </div>`
            : nothing}
          ${launches.length
            ? html`<div class="meta">${launches.length === 1 ? msg('1 agent session running') : msg(str`${launches.length} agent sessions running`)}</div>`
            : nothing}
          ${this.spendLine(spendOf(rows))}
          ${this.quotaLine(tries)}
        </div>
      </div>
      ${tries.length ? html`<div class="runchips">${attemptNames(tries).map((name, i) => this.runChip(tries[i] as JournalRow, name, session))}</div>` : nothing}
      ${this.searchFold(tries)}
      ${unreadEvents(tries)
        ? html`<div class="meta unread" title=${msg('Event types from the coding agent that this contraagent version does not recognize')}>
            <span aria-hidden="true">⚠</span> ${msg(str`Unrecognized events: ${unreadEvents(tries)}`)}
          </div>`
        : nothing}
      ${d.task_detail_error ? html`<div class="meta v-bad">${msg(str`The task_detail callback failed: ${d.task_detail_error ?? ''}`)}</div>` : nothing}
      ${launches.map(
        (lc) => html`<details class="launch">
          <summary>${facts(msg(str`Process ${lc.pid ?? '—'}`), lc.key || '')}</summary>
          <div class="meta">${facts(msg(str`Plugin ${lc.plugin || msg('none')}`), msg(str`Model ${lc.model || '—'}`), msg(str`Role ${lc.role || msg('none')}`))}</div>
        </details>`,
      )}
      ${extras.map(
        ([k, v]) => html`<details class="io-fold"><summary>${k}</summary><ca-json-tree .value=${v}></ca-json-tree></details>`,
      )}
    </div>`;
  }

  /** The identities the task's attempts authenticated as (each hop's, when a model switch changed it). */
  private identityChip(tries: JournalRow[]) {
    const ids = [...new Set(tries.flatMap((r) => [...(r.hops ?? []).map((h) => h.credential), r.credential]).filter((x): x is string => !!x))];
    return ids.length
      ? html`<span class="who ident" title=${[msg('What the coding agent authenticated as: an account or an API key (credential)'), ...ids.map(credentialTip)]
            .filter(Boolean)
            .join('\n')}
          ><span class="who-l">${msg('identity')}</span>${ids.map(credentialLabel).join(', ')}</span
        >`
      : nothing;
  }

  /** The queries of the web searches the task's attempts made, in call order; each opens its card in the transcript. */
  private searchFold(tries: JournalRow[]) {
    const queries = tries.flatMap((r) => r.web_queries ?? []);
    const seen = new Map<string, number>();
    return queries.length
      ? html`<details class="io-fold">
          <summary>${queries.length === 1 ? msg('1 web search') : msg(str`${queries.length} web searches`)}</summary>
          <ol class="meta searches">
            ${queries.map((q) => {
              const nth = seen.get(q) ?? 0;
              seen.set(q, nth + 1);
              return html`<li><button class="qlink jmono" @click=${() => this.revealSearch(q, nth)}>
                ${q}
              </button></li>`;
            })}
          </ol>
        </details>`
      : nothing;
  }

  private revealSearch(query: string, nth: number): void {
    const at = this.transcriptEl?.revealWebSearch(query, nth);
    emit(this, 'ca-navigate', at ? { view: 'transcript', round: at.round } : { view: 'transcript' });
  }

  /** The task's spend over all its attempts: cost, then tokens. Nothing when none was reported. */
  private spendLine(s: Spend | null) {
    if (!s) return nothing;
    return html`<div class="spend">
      <b title=${msg('Reported by the coding agent')}>${usd(s.cost)}</b>
      <span>${msg(str`Tokens: ${tokens(s.input)} input, ${tokens(s.output)} output, ${tokens(s.cache_read)} cache read, ${tokens(s.cache_creation)} cache write`)}</span>
      <span>${s.calls === 1 ? msg('1 API call') : msg(str`${s.calls} API calls`)}</span>
    </div>`;
  }

  /** The task's subscription usage: at its first session start, and the next reading the run took after it ended. */
  private quotaLine(tries: JournalRow[]) {
    const readings = runReadings(this.journal.length ? this.journal : tries);
    const first = tries[0];
    const last = tries[tries.length - 1];
    const start = first ? tryQuota(first, readings).start : null;
    if (!start || !last) return nothing;
    const next = tryQuota(last, readings).next;
    // The identity chip names the account; both readings are that account's.
    return html`<div class="spend quota">
      <span title=${readingTip(start)}>${msg(str`Usage at session start: ${readingShort(start)}`)}</span>
      ${next ? html`<span title=${readingTip(next)}>${msg(str`Usage after this task: ${readingShort(next)}`)}</span>` : nothing}
    </div>`;
  }

  /** One finished attempt: how it ended, how long, its cost; the rest (when, corrections, model, model switch) in its tooltip. */
  private runChip(r: JournalRow, name: string, session: boolean) {
    const ok = r.ok;
    const reason = runRelative(r.reason, this.run);
    const sw = modelSwitch(r.hops);
    const tip = [
      msg(str`Ended ${localTime(r.ts, true)}`),
      correctionsOf(r),
      session && r.model ? msg(str`Model ${r.model}`) : '',
      sw ? msg(str`Model switch: ${sw}`) : '',
      reason,
      r.route || '',
    ]
      .filter(Boolean)
      .join('\n');
    const cost = r.cost_usd !== null && r.cost_usd !== undefined ? usd(r.cost_usd) : '';
    return html`<span class="runchip ${ok ? 'ok' : 'bad'}" title=${tip}>
      ${mark(ok)} ${facts(name, stopLabel(r.stop, r.reason), fmtDur(r.wall_s), cost)}
    </span>`;
  }

  private renderViews(d: TaskDetail, view: TaskView) {
    const io = d.io;
    const py = this.isPy(d) && !d.stream;
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

  private renderPane(d: TaskDetail, view: TaskView, live: boolean) {
    if (view === 'input') return this.inputPane(d, live);
    if (view === 'output') return this.outputPane(d);
    return html`<ca-definition .definition=${d.definition ?? null} memory="task-definition"></ca-definition>`;
  }

  private inputPane(d: TaskDetail, live: boolean) {
    const io = d.io;
    const params = Object.entries(io.params);
    const { files, earlier } = inputView(io);
    const source = (v: unknown) => io.upstream.find((u) => u.outputs.some((o) => o.file.exists && sameJson(o.file.content, v)));
    return html`<h4 class="sect-h">${msg('Parameters')}</h4>
      ${params.length
        ? html`<table class="ct-fields params">
            ${params.map(([k, v]) => {
              const from = source(v);
              return html`<tr>
                <td class="jmono">${k}</td>
                <td>${v !== null && typeof v === 'object' ? html`<ca-json-tree .value=${v} .open=${0}></ca-json-tree>` : html`<span class="jmono">${valueText(v)}</span>`}</td>
                <td>${from ? html`<span class="from">${msg(html`From ${this.link(from)}`)}</span>` : nothing}</td>
              </tr>`;
            })}
          </table>`
        : html`<div class="meta">${msg('No parameters')}</div>`}
      <h4 class="sect-h">${msg('Input files')}</h4>
      ${files.length ? files.map((f) => this.inputCard(f)) : html`<div class="meta">${msg('No input files')}</div>`}
      <h4 class="sect-h">${msg('Earlier tasks')}</h4>
      ${earlier.length ? earlier.map((e) => this.earlierTask(e)) : html`<div class="meta">${msg('No earlier tasks')}</div>`}
      ${this.isPy(d) ? nothing : this.promptSection(d, live)}`;
  }

  /** One file the task reads: its check, and the earlier task that writes it or that it is from before the run. */
  private inputCard(f: InputFile) {
    const u = f.from;
    const state = u ? this.outcomes.get(u.key)?.outcome : undefined;
    const origin = u
      ? html`<span>${msg(html`Output of ${this.link(u)}`)}</span>${state && state !== 'done' ? html`<span class="pill o-${state}">${outcomeLabel(state)}</span>` : nothing}`
      : msg('File from before the run');
    // Written by an earlier task: that task's check of it ("passed", "not written (task failed)").
    const st = f.out?.status;
    if (!st) return ioFileCard(f.spec, 'input', this.run, { origin });
    const chip = html`<span class="ct-chip ${st}" title=${statusWhy(st)}>${statusLabel(st)}</span>`;
    return ioFileCard({ ...f.spec, status: st }, 'input', this.run, { origin, chip });
  }

  /** One earlier task: its status, how many of its output files this task reads, and the others folded under it (open when one did not pass). */
  private earlierTask(e: EarlierTask) {
    const u = e.task;
    const kindName = isPython(u) ? msg('Python task') : msg('Agent task');
    const state = this.outcomes.get(u.key)?.outcome;
    const n = u.outputs.length;
    const summary = !n
      ? msg('No output files')
      : facts(n === 1 ? msg('1 output file') : msg(str`${n} output files`), e.read ? (e.read === 1 ? msg('1 read by this task') : msg(str`${e.read} read by this task`)) : '');
    const head = html`<div class="up-hd">
      <span class="k-ic ${isPython(u) ? '' : 'llm'}" title=${kindName}><span aria-hidden="true">${isPython(u) ? '⚙' : '✦'}</span><span class="sr">${kindName}</span></span>
      ${this.link(u)}
      ${state ? html`<span class="pill o-${state}">${outcomeLabel(state)}</span>` : nothing}
      <span class="meta">${summary}</span>
    </div>`;
    if (!e.rest.length) return html`<div class="upstream">${head}</div>`;
    const cards = e.rest.map((o) => ioFileCard(o, 'output', this.run, { producerOf: this.producerOf }));
    return e.rest.some(notPassed)
      ? html`<div class="upstream">${head}${cards}</div>`
      : html`<details class="upstream"><summary>${head}</summary>${cards}</details>`;
  }

  /** The prompt of the round chosen in the transcript, or why there is none. */
  private promptSection(d: TaskDetail, live: boolean) {
    const n = this.launches.length;
    const shown = this.shownRound;
    const info = this.rounds[shown];
    const tries = this.rounds[this.rounds.length - 1]?.tryNo ?? 1;
    const ran = d.rows.filter(isLaunched);
    const names = attemptNames(ran);
    const starts = runStarts(ran);
    const prompt = this.launches[shown]?.prompt ?? '';
    const state = this.stateOf(d, live);
    return html`<h4 class="sect-h">${msg('Prompt')}${n > 1 && info
        ? html` <span class="meta">${roundLabel(info, tries, names[info.tryNo - 1])}: ${roundWhy(info, starts[info.tryNo - 1] !== starts[info.tryNo - 2])}</span>`
        : nothing}</h4>
      ${prompt
        ? html`<ca-markdown .text=${prompt}></ca-markdown>`
        : html`<div class="meta">${d.stream
            ? msg('Loading…')
            : this.hadSession(d)
              ? msg('Prompt not saved (keep_transcripts = false)')
              : facts(msg('No prompt'), outcomeLabel(state))}</div>`}`;
  }

  /** Per attempt that reported any: tokens, API calls, cost and identity; per hop under a model switch. */
  private usageTable(rows: JournalRow[]) {
    const spent = rows.filter((r) => isLaunched(r) && (r.usage || (r.cost_usd !== null && r.cost_usd !== undefined)));
    if (!spent.length) return nothing;
    const dash = html`<td class="jdim">—</td>`;
    const readings: SourcedReading[] = runReadings(this.journal.length ? this.journal : rows);
    const quota = spent.some((r) => (r.quota ?? []).length);
    const dashL = html`<td class="l jdim">—</td>`;
    // The identity column is next to it: name the account only when the reading is another one's.
    const reading = (q: ReturnType<typeof tryQuota>['start'], cred: string | undefined) =>
      q ? html`<td class="l" title=${readingTip(q)}>${(q.credential ?? '') === (cred ?? '') ? readingShort(q) : accountReading(q)}</td>` : dashL;
    return html`<h4 class="sect-h">${msg('Tokens and cost')}</h4>
      <div class="usage-wrap"><table class="usage">
        <tr>
          <th class="l"></th><th>${msg('Input')}</th><th>${msg('Output')}</th><th>${msg('Cache read')}</th><th>${msg('Cache write')}</th>
          <th>${msg('API calls')}</th><th title=${msg('Reported by the coding agent')}>${msg('Cost')}</th><th class="l">${msg('Identity')}</th>
          ${quota
            ? html`<th class="l" title=${msg('Subscription usage when the agent session started (account-wide)')}>${msg('Usage at start')}</th>
                <th class="l" title=${msg('The first reading of the same account after this attempt ended')}>${msg('Usage after')}</th>`
            : nothing}
        </tr>
        ${spent.map((r) => {
          const u = r.usage;
          const hops = r.hops ?? [];
          return html`<tr>
              <td class="l">${attemptLabel(r.attempt)}</td>
              ${u
                ? html`<td>${tokens(u.input)}</td><td>${tokens(u.output)}</td><td>${tokens(u.cache_read)}</td><td>${tokens(u.cache_creation)}</td><td>${u.calls}</td>`
                : html`${dash}${dash}${dash}${dash}${dash}`}
              <td>${usd(r.cost_usd)}</td><td class="l" title=${credentialTip(r.credential) || nothing}>${credentialLabel(r.credential) || '—'}</td>
              ${quota ? html`${reading(tryQuota(r, readings).start, r.credential)}${reading(tryQuota(r, readings).next, r.credential)}` : nothing}
            </tr>
            ${hops.length > 1
              ? hops.map(
                  (h) => html`<tr class="hop">
                    <td class="l">${facts(h.model || h.route || '—', stopLabel(h.stop))}</td>
                    <td></td><td></td><td></td><td></td><td></td>
                    <td>${usd(h.cost_usd)}</td><td class="l" title=${credentialTip(h.credential) || nothing}>${credentialLabel(h.credential) || '—'}</td>
                    ${quota ? html`<td></td><td></td>` : nothing}
                  </tr>`,
                )
              : nothing}`;
        })}
      </table></div>`;
  }

  private outputPane(d: TaskDetail) {
    const io = d.io;
    const last = d.rows[d.rows.length - 1];
    // The reason, a refusal's cause and a model switch are in the verdict above, so they are not repeated here.
    return html`<h4 class="sect-h">${msg('Output files')}</h4>
      ${io.outputs.length
        ? io.outputs.map((o) =>
            ioFileCard(o, 'output', this.run, { producerOf: this.producerOf }),
          )
        : html`<div class="meta">${msg('No output files')}</div>`}
      ${last
        ? html`<h4 class="sect-h">${msg('Outcome')}</h4>
            <div class="ct-in">
              ${pill(STOP_PILL[stopTone(last.stop)] ?? 'error', stopLabel(last.stop, last.reason))}
              ${isLaunched(last) ? html`<span class="meta">${facts(attemptLabel(last.attempt), fmtDur(last.wall_s), correctionsOf(last))}</span>` : nothing}

            </div>`
        : nothing}
      ${this.usageTable(d.rows)}
      <h4 class="sect-h">${msg('Later tasks')}</h4>
      ${io.downstream.length
        ? html`<div class="down">${io.downstream.map((x) => taskChip(this, kindUnit(x), x))}</div>`
        : html`<div class="meta">${msg('No later tasks')}</div>`}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-task-view': CaTaskView;
  }
}
