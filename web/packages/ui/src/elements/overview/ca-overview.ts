import {
  deriveRun,
  isPython,
  isRunLive,
  liveActivities,
  progress,
  result,
  runAccounts,
  runRelative,
  spendOf,
  type ContractRecord,
  type ContractSpec,
  type Info,
  type OutputTally,
  type RunState,
  type HostSummary,
  type RunSummary,
  type TaskOutcome,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../core/events.js';
import { facts, kindUnit, localTime, sentence } from '../../words/format.js';
import { notStartedCause, outcomeLabel, stateCount, stopLabel } from '../../words/index.js';
import { base } from '@contraagent/elements/styles';
import { pill, statusWord } from '@contraagent/elements/primitives';
import { contractTone, outcomeTone } from '../../lib/tone.js';
import { contractChip, formatOf } from '../shared/contract-parts.js';
import { contractStatusLabel, contractStatusWhy } from '../../words/contract.js';
import { taskChip } from '../shared/task-chip.js';
import '../lists/ca-proc-tree.js';
import './ca-kpis.js';
import './ca-spend-breakdown.js';
import './ca-model-usage.js';
import './ca-quota.js';
import './ca-pipeline-graph.js';
import './ca-run-driver.js';
import './ca-timeline.js';
import './ca-workers.js';

/** Failed outputs listed on the overview; the rest are behind a link to the outputs tab. */
const OUTPUTS_SHOWN = 5;

const CT_ORDER = ['invalid', 'refused', 'failed', 'running', 'pending', 'valid'] as const satisfies readonly (keyof OutputTally)[];

/** A one-line peek at a panel's body. */
function peek(v: unknown): string {
  if (v === undefined) return msg('Loading…');
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  const keys = Object.keys(v);
  if (!keys.length) return msg('Empty');
  const names = `${keys.slice(0, 4).join(', ')}${keys.length > 4 ? ', …' : ''}`;
  return Array.isArray(v) ? msg(str`${keys.length} items: ${names}`) : msg(str`${keys.length} keys: ${names}`);
}

/**
 * The run on one page, in the order a reader checks it: whether it runs, what runs
 * now, the tasks with a problem (causes first) and the outputs; the pipeline graph
 * (every task, by layer of the flow) and the figures; where the tokens, the cost and
 * the subscription went, the process tree (while running), the resume cursor and the
 * pipeline's own panels; then a timeline. A card takes the width its content needs.
 * Sends `ca-open-task` and `ca-navigate`.
 *
 * @fires ca-navigate - `{tab, stop?}`: a link to another tab or a panel; `{layer, unit, sel}`: a layer of the pipeline graph, or what is selected in it
 * @fires ca-open-task - `{key, view?}`: a task with a problem was clicked
 */
@customElement('ca-overview')
@localized()
export class CaOverview extends LitElement {
  static override styles = [
    base,
    css`
      /* The overview is a column of bands. A band's cards take the width their content
         needs: the state of the run (with the running tasks while none runs), the
         problems and the outputs share a row; the breakdowns share two columns; only
         what is wide by nature (the running tasks' cards, the pipeline graph, the
         totals' tiles, the timeline) runs the whole width. */
      :host { display: block; container-type: inline-size; }
      .ov { display: flex; flex-direction: column; gap: 14px; }
      .band.status { display: grid; gap: 14px; align-items: start; }
      .stack { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
      /* the breakdowns flow in columns, so cards of different heights fill them */
      .band.parts { columns: 2 440px; column-gap: 14px; }
      .band.parts > .panel { break-inside: avoid; margin-bottom: 14px; display: block; }
      .band.parts > .panel:last-child { margin-bottom: 0; }
      .stack { grid-area: stack; }
      .problems { grid-area: problems; }
      .outputs { grid-area: outputs; }
      .row { grid-area: running; }
      .band.status { grid-template-areas: 'stack' 'problems' 'outputs' 'running'; }
      @container (min-width: 760px) {
        .band.status { grid-template-columns: minmax(240px, 1fr) minmax(0, 1.7fr); grid-template-areas: 'stack problems' 'outputs outputs' 'running running'; }
      }
      @container (min-width: 1100px) {
        .band.status { grid-template-columns: minmax(240px, 1fr) minmax(0, 1.7fr) minmax(0, 1.5fr); grid-template-areas: 'stack problems outputs' 'running running running'; }
      }
      .ok { display: flex; align-items: baseline; gap: 6px; color: var(--text-2); }
      .ok span[aria-hidden] { color: var(--status-done); }
      /* a failed output: its status and its task on one line, what it is and where under them */
      .ofl { grid-template-columns: max-content minmax(0, 1fr); }
      .ofl > .jstop { white-space: nowrap; }
      .ofl > b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .ofl > .meta { grid-column: 1 / -1; overflow: hidden; text-overflow: ellipsis; }
      .ct-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      .pcards { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 12px; }
      .pcard { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; align-items: start; padding: 12px 14px; border-radius: 10px;
        background: var(--raise); border: 1px solid var(--line); cursor: pointer; transition: border-color 0.15s, transform 0.15s;
        text-align: left; color: inherit; font: inherit; width: 100%; min-width: 0; }
      .pcard > div { min-width: 0; }
      .pcard .meta { overflow-wrap: anywhere; }
      .pcard:hover { border-color: var(--accent); transform: translateY(-1px); }
      .pc-ic { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; background: var(--well); color: var(--text-2); font-size: 16px; }
      .pc-peek { font-family: var(--mono); font-size: 11.5px; color: var(--text-2); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pc-go { grid-column: 2; color: var(--accent); font-size: 12px; opacity: 0.8; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pcard:hover .pc-go { opacity: 1; }
      .cur-units { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 14px; }
      .cu { display: grid; grid-template-columns: 90px 1fr 70px auto; gap: 8px; align-items: center; }
      .cu-bar { height: 5px; border-radius: 3px; background: var(--track); overflow: hidden; }
      .cu-bar i { display: block; height: 100%; background: var(--meter); }
      .fl > div.meta { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
      .stopped { grid-column: 1 / 4; color: var(--text-muted); font-size: 11px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
      .fl.muted { opacity: 0.7; }
      .next { margin: 10px 2px 2px; font-size: 12px; color: var(--text-2); }
      .next code { font-family: var(--mono); }
      .more { font-size: 12px; margin: 6px 10px 0; }
    `,
  ];

  @property({ attribute: false }) state!: RunState;
  @property({ attribute: false }) summary: RunSummary | undefined;
  /** The run's host (a hub). */
  @property({ attribute: false }) host: HostSummary | undefined;
  @property({ attribute: false }) info!: Info;
  @property() run = '';
  /** The pipeline graph's layer (`Route.layer`). */
  @property() layer = '';
  /** The unit highlighted in the pipeline graph (`Route.unit`). */
  @property() unit = '';
  /** What is selected in the pipeline graph (`Route.sel`). */
  @property() sel = '';

  private go(tab: 'outputs' | 'procs' | `panel:${string}`): void {
    emit(this, 'ca-navigate', { tab });
  }

  /** Open a task: a Python task has no transcript, so its output. */
  private open(t: { key: string; executor?: string }): void {
    emit(this, 'ca-open-task', { key: t.key, ...(isPython(t) ? { view: 'output' as const } : {}) });
  }

  override render() {
    const s = this.state;
    const live = isRunLive(s, this.summary);
    const busy = live ? liveActivities(s.procs).length : 0;
    /** The run's limit (`run.json` `max_workers`); null when the run did not record one. */
    const max = s.procs?.max_workers || null;
    const panels = this.info.panels;
    // Running tasks need the width of their cards; while none runs, one line under the run's state.
    // A run that is over runs nothing: its state says so.
    const running = live && busy > 0;
    return html`<div class="ov">
      <div class="band status">
        <div class="stack">
          <section class="panel enter">
            <h3>${msg('Run')}</h3>
            <ca-run-driver .procs=${s.procs} .summary=${this.summary} .plan=${s.plan} .host=${this.host}></ca-run-driver>
          </section>
          ${live && !running ? this.runningCard(live, busy, max) : nothing}
        </div>
        <section class="panel enter problems">
          <h3>${msg('Problems')}
            <span class="r"><a class="lnk" href="#" @click=${(e: Event) => this.nav(e, () => emit(this, 'ca-navigate', { tab: 'journal', stop: 'bad' }))}>${msg('Failed attempts in history')}</a></span></h3>
          ${this.problems(live)}
        </section>
        <section class="panel enter outputs">
          <h3 title=${msg('Checked files (OutputContract, InputContract)')}>${msg('Outputs')}
            <span class="r"><a class="lnk" href="#" @click=${(e: Event) => this.nav(e, () => this.go('outputs'))}>${msg('All outputs')}</a></span></h3>
          ${this.outputs()}
        </section>
        ${running ? html`<div class="row">${this.runningCard(live, busy, max)}</div>` : nothing}
      </div>
      <section class="panel enter">
        <h3 title=${msg('Every task the run scheduled, by kind (plan.jsonl)')}>${msg('Pipeline')}
          <span class="r">${this.progressLine(live)}</span></h3>
        <ca-pipeline-graph .plan=${s.plan} .journal=${s.journal} .run=${this.run} .layer=${this.layer} .unit=${this.unit} .sel=${this.sel} ?live=${live}></ca-pipeline-graph>
      </section>
      <section class="panel enter">
        <h3 title=${msg('Counted from every finished attempt (journal.jsonl)')}>${msg('Totals')}</h3>
        <ca-kpis .journal=${s.journal} .plan=${s.plan}></ca-kpis>
      </section>
      <div class="band parts">
        ${live
          ? html`<section class="panel enter">
              <h3>${msg('Process tree')}
                <span class="r"><a class="lnk" href="#" @click=${(e: Event) => this.nav(e, () => this.go('procs'))}>${msg('All processes')}</a></span></h3>
              <ca-proc-tree .procs=${s.procs}></ca-proc-tree>
            </section>`
          : nothing}
        ${spendOf(s.journal)
          ? html`<section class="panel enter">
              <h3 title=${msg('Reported by the coding agents')}>${msg('Tokens and cost by kind')}</h3>
              <ca-spend-breakdown .journal=${s.journal}></ca-spend-breakdown>
            </section>`
          : nothing}
        ${s.plan.models?.length
          ? html`<section class="panel enter">
              <h3 title=${msg('The agent sessions by the model they ran on. Each model of a model switch counts its own part. Python tasks run on no model.')}>${msg('Models')}
                <span class="r">${s.plan.models.length === 1 ? msg('1 model') : msg(str`${s.plan.models.length} models`)}</span></h3>
              <ca-model-usage .models=${s.plan.models}></ca-model-usage>
            </section>`
          : nothing}
        ${runAccounts(s.journal).length || s.plan.rests?.length
          ? html`<section class="panel enter">
              <h3 title=${msg('Reported at each agent session start. Account-wide: every task that runs at once shares it.')}>
                ${msg('Subscription usage')}<span class="r">${msg('Per account, first → last reading')}</span></h3>
              <ca-quota .journal=${s.journal} .caps=${s.plan.quota_caps ?? []} .rests=${s.plan.rests ?? []} .rule=${s.plan.quota_rule ?? ''} ?live=${live}></ca-quota>
            </section>`
          : nothing}
        ${s.cursor
          ? html`<section class="panel enter">
              <h3 title=${msg('Stage and step per unit (CursorStore)')}>${msg('Resume cursor')}</h3>
              ${this.cursor()}
            </section>`
          : nothing}
        ${panels.length
          ? html`<section class="panel enter">
              <h3 title=${msg('monitor.Panel')}>${msg('Custom views')}</h3>
              ${this.panelCards()}
            </section>`
          : nothing}
      </div>
      <section class="panel enter">
        <h3>${msg('Timeline')}
          <span class="r">${this.triesLine()}</span></h3>
        <ca-timeline .journal=${s.journal} .plan=${s.plan} .procs=${s.procs} .live=${live} .run=${this.run}></ca-timeline>
      </section>
    </div>`;
  }

  private runningCard(live: boolean, busy: number, max: number | null) {
    return html`<section class="panel enter">
      <h3 title=${msg('Limit: max_concurrent')}>${msg('Running tasks')}
        ${live ? html`<span class="r">${max ? msg(str`${busy} of ${max} running at once`) : msg(str`${busy} running at once`)}</span>` : nothing}</h3>
      ${busy ? html`<ca-workers .procs=${this.state.procs} .live=${live}></ca-workers>` : html`<div class="meta">${msg('No tasks running')}</div>`}
    </section>`;
  }

  // ---- contracts: the files tasks must leave behind (OutputContract) and read (InputContract) ----
  private outputs() {
    const { contracts, tally } = this.state.outputs;
    if (!contracts.length) {
      return html`<div class="meta">${msg('No output files')}</div>`;
    }
    const chips = CT_ORDER.filter((k) => tally[k]);
    // Only what went wrong with a file; tasks that never started are the problems section's.
    const bad = contracts
      .flatMap((c) => (c.outputs ?? []).map((o): [ContractRecord, ContractSpec] => [c, o]))
      .filter(([, o]) => o.status === 'invalid' || o.status === 'failed');
    const shown = bad.slice(0, OUTPUTS_SHOWN);
    const refused = tally.refused;
    return html`<div class="ct-row">
        ${chips.length
          ? chips.map((k) => contractChip(k, tally[k]))
          : html`<span class="meta">${msg('No checked files')}</span>`}
      </div>
      ${shown.map(
        ([c, o]) => html`<button type="button" class="fl ofl" @click=${() => this.go('outputs')}>
          ${statusWord({ text: o.status ? contractStatusLabel(o.status) : '—', tone: contractTone(o.status), title: o.status ? contractStatusWhy(o.status) : null })}
          <b class="jmono" title=${c.key}>${kindUnit({ kind: c.kind, unit: c.unit === c.key ? '' : c.unit })}</b>
          <span class="meta">${formatOf(o)}</span>
          <span class="meta">${runRelative(o.errors?.[0] || o.path, this.run).slice(0, 160)}</span>
        </button>`,
      )}
      ${bad.length > shown.length
        ? html`<div class="more"><a class="lnk" href="#" @click=${(e: Event) => this.nav(e, () => this.go('outputs'))}>${bad.length - shown.length === 1
            ? msg('1 more output')
            : msg(str`${bad.length - shown.length} more outputs`)}</a></div>`
        : nothing}
      ${refused
        ? html`<div class="meta more">${refused === 1
            ? msg('1 output not written (task not started)')
            : msg(str`${refused} outputs not written (tasks not started)`)}</div>`
        : nothing}`;
  }

  /** While running, how far the run is; once over, how its tasks ended. */
  private progressLine(live: boolean): string {
    const plan = this.state.plan;
    const r = result(plan);
    if (live || r.left) {
      const p = progress(plan);
      return facts(msg(str`${p.pct}%`), msg(str`${p.done} of ${p.total} tasks done`), p.skipped ? stateCount('skipped', p.skipped) : '');
    }
    return facts(
      stateCount('done', r.done),
      r.skipped ? stateCount('skipped', r.skipped) : '',
      r.failed ? stateCount('failed', r.failed) : '',
      r.notStarted ? stateCount('not_started', r.notStarted) : '',
    );
  }

  /** "23 attempts | 4 not started": a task that never started has no attempt. */
  private triesLine(): string {
    const { tries, notStarted } = deriveRun(this.state.journal, this.state.plan).tries;
    return facts(tries === 1 ? msg('1 attempt') : msg(str`${tries} attempts`), notStarted ? stateCount('not_started', notStarted) : '');
  }

  /** A link's click: no navigation of the page's own, then `go`. */
  private nav(e: Event, go: () => void): void {
    e.preventDefault();
    go();
  }

  // The run's own position, from its CursorStore: the stage it is in, the stages behind it,
  // and how far each unit has got. Shown only for a run that keeps a cursor (Run.cursor()).
  private cursor() {
    const c = this.state.cursor;
    const units = Object.entries(c?.units ?? {});
    if (!c || (!c.stage && !units.length)) return html`<div class="meta">${msg('No resume cursor')}</div>`;
    const done = c.completed_stages ?? [];
    return html`<div class="chips" style="margin-bottom:10px">
        ${done.length || c.stage
          ? html`${done.map((n) => html`<span class="chip" data-tone="done"><span aria-hidden="true">✓</span><span class="sr">${msg('done', { id: 'stage-done', desc: 'A stage of the resume cursor that is complete' })}</span> ${n}</span>`)}${c.stage
              ? html`<span class="chip" data-tone="running"><span class="sr">${msg('current')}</span>${c.stage}</span>`
              : nothing}`
          : html`<span class="meta">${msg('No stage')}</span>`}
      </div>
      ${units.length
        ? html`<div class="cur-units">
            ${units.map(
              ([u, x]) => html`<div class="cu">
                <span class="jmono">${u}</span>
                <span class="meta">${facts(x.step || '—', x.loop_pass ? msg(str`loop pass ${x.loop_pass}`) : '')}</span>
                <span class="cu-bar" title=${x.completed.length === 1 ? msg('1 step completed') : msg(str`${x.completed.length} steps completed`)}><i style="width:${Math.min(100, 12 * (x.completed.length + 1))}%"></i></span>
                ${x.inflight.length ? pill({ text: msg('running'), tone: 'running', title: x.inflight.join('\n') }) : nothing}
              </div>`,
            )}
          </div>`
        : nothing}`;
  }

  // One card per view the pipeline added: what it is, a one-line peek, and where to open it.
  private panelCards() {
    return html`<div class="pcards">
      ${repeat(
        this.info.panels,
        (p) => p.name,
        (p) => html`<button type="button" class="pcard" @click=${() => this.go(`panel:${p.name}`)}>
          <span class="pc-ic" aria-hidden="true">${p.icon || '▤'}</span>
          <div>
            <b>${p.title || p.name}</b>
            ${p.description ? html`<div class="meta">${p.description}</div>` : nothing}
            <div class="pc-peek">${peek(this.state.panels[p.name])}</div>
          </div>
          <span class="pc-go">${msg(str`Show ${p.title || p.name}`)}</span>
        </button>`,
      )}
    </div>`;
  }

  /** A task's name as the button that opens it: the keyboard's way into a problem row. */
  private nameButton(t: TaskOutcome) {
    return html`<button type="button" class="fl-name jmono" title=${t.key} @click=${() => this.open(t)}>${this.name(t)}</button>`;
  }

  /** A click on a problem row opens its task, except on a button in it (its name, a later task's chip), which acts on its own. */
  private openRow(e: MouseEvent, t: TaskOutcome): void {
    if (!(e.target as Element).closest('button')) this.open(t);
  }

  /** One task by name: kind · unit, or kind alone for a task of the whole run. */
  private name(t: TaskOutcome): string {
    return kindUnit(t);
  }

  private problems(live: boolean) {
    const { outcomes, problems } = deriveRun(this.state.journal, this.state.plan);
    const { failed, notStarted, recovered } = problems;
    if (!failed.length && !notStarted.length && !recovered.length) {
      return html`<div class="ok"><span aria-hidden="true">✓</span>${msg('No problems')}</div>`;
    }
    const reason = (t: TaskOutcome) => runRelative(t.attempts[t.attempts.length - 1]?.reason || '—', this.run).slice(0, 200);
    const stoppedLine = (stopped: TaskOutcome[]) =>
      stopped.length
        ? html`<div class="stopped">
            <span>${stopped.length === 1 ? msg('1 later task not started') : msg(str`${stopped.length} later tasks not started`)}</span>
            ${stopped.map((x) => taskChip(this, this.name(x), x))}
          </div>`
        : nothing;
    return html`${repeat(
        failed,
        (p) => p.task.key,
        (p) => {
          const last = p.task.attempts[p.task.attempts.length - 1];
          return html`<div class="fl" @click=${(e: MouseEvent) => this.openRow(e, p.task)}>
            ${statusWord({ text: outcomeLabel('failed'), tone: 'failed' })}
            ${this.nameButton(p.task)}<span class="meta">${localTime(last?.ts, true)}</span>
            <div class="meta">${stopLabel(last?.stop)}: ${reason(p.task)}</div>
            ${stoppedLine(p.stopped)}
          </div>`;
        },
      )}
      ${repeat(
        notStarted,
        (t) => t.key,
        (t) => html`<div class="fl" @click=${(e: MouseEvent) => this.openRow(e, t)}>
          ${statusWord({ text: outcomeLabel('not_started'), tone: 'attention' })}
          ${this.nameButton(t)}<span></span>
          <div class="meta">${notStartedCause(t, outcomes, this.run) ? sentence(notStartedCause(t, outcomes, this.run)) : reason(t)}</div>
        </div>`,
      )}
      ${repeat(
        recovered,
        (t) => t.key,
        (t) => {
          const fails = t.tries.filter((a) => !a.ok).length;
          const n = t.tries.length;
          return html`<div class="fl muted" @click=${(e: MouseEvent) => this.openRow(e, t)}>
            ${statusWord({ text: outcomeLabel('recovered'), tone: outcomeTone('recovered') })}
            ${this.nameButton(t)}<span></span>
            <div class="meta">${fails === 1
              ? msg(str`Done on attempt ${n} after 1 failed attempt`)
              : msg(str`Done on attempt ${n} after ${fails} failed attempts`)}</div>
          </div>`;
        },
      )}
      ${this.nextStep(live, failed.length + notStarted.length)}`;
  }

  /** For a finished run with problems: how many tasks are not done (the tasks resume=True runs again). */
  private nextStep(live: boolean, problemCount: number) {
    if (live || !problemCount) return nothing;
    const c = deriveRun(this.state.journal, this.state.plan).counts;
    const again = c.total - c.finished;
    if (!again) return nothing;
    return html`<div class="next" title="resume=True">${msg(str`${again} of ${c.total} tasks not done`)}</div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-overview': CaOverview;
  }
}
