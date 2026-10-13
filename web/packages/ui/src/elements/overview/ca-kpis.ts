import { outcomeCounts, spendByKind, spendOf, taskOutcomes, totalTokens, type JournalRow, type Plan, type TaskOutcome } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { emit } from '../../events.js';
import { facts, fmtDur, kindUnit, tokens, usd } from '../../lib/format.js';
import { inputProblems, stateCount } from '../../lib/labels.js';
import { base } from '../../styles/base.js';
import '../shared/ca-count.js';
import { factLine } from '../shared/fact-line.js';
import { problemTone, type Tone } from '../../lib/tone.js';
import { kpis } from './logic.js';

interface Tile {
  id: string;
  /** The status the tile's subject is in: only a problem count above 0 has one (`problemTone`); totals and measures are neutral. */
  tone: Tone;
  label: string;
  /** A count (counts up and bumps the tile when it changes), or a text. */
  value: number | string;
  /** The line under the value, or several lines. */
  sub: string | string[];
  /** Instead of `sub`: one line of facts, each with the tone of its status ("29 done | 1 failed"). */
  parts?: Fact[];
  /** The code's term for what is counted: the tooltip. */
  tip?: string;
  /** A link under the sub line. */
  action?: { label: string; run: () => void };
}

/**
 * Why the tasks that did not start did not start, as the data names it: an
 * input missing, an input that failed checks, an earlier task that failed.
 */
function notStartedCauses(outcomes: Iterable<TaskOutcome>): string {
  let missing = false;
  let checks = false;
  let earlier = false;
  for (const t of outcomes) {
    if (t.outcome !== 'not_started') continue;
    const last = t.attempts[t.attempts.length - 1];
    const ps = last?.stop === 'invalid_input' ? inputProblems(last.reason) : [];
    if (ps.some((p) => p.problem === 'missing')) missing = true;
    if (ps.some((p) => p.problem === 'checks')) checks = true;
    if (!ps.length && t.cause) earlier = true;
  }
  return facts(earlier ? msg('Earlier task failed') : '', missing ? msg('Input missing') : '', checks ? msg('Input failed checks') : '');
}

/** A fact that is a status ("1 failed"): shown in that status's colour. */
interface Fact {
  text: string;
  tone: Tone;
}

/** The mark before a problem tile's label: the shape keeps the status without colour. */
const MARK: Partial<Record<Tone, string>> = { failed: 'mk-failed', attention: 'mk-pending' };

/** One line of facts, each kept whole (as `factLine`), a status fact in its colour. */
function tonedFacts(fs: readonly Fact[]): TemplateResult {
  return html`${fs.filter((f) => f.text).map((f, i) => html`${i ? ' | ' : ''}<span class="f ${f.tone ? `t-${f.tone}` : ''}">${f.text}</span>`)}`;
}

const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/**
 * The run in numbers: tasks and how they ended (with `plan`; from the journal
 * alone otherwise), attempts, failed attempts, agent time, retries, corrections and
 * model switches.
 *
 * @fires ca-navigate - `{tab: 'journal', stop}`: the history filtered to what a tile counts (`bad`, `invalid_input`, `retried`, `fixup`)
 * @fires ca-open-task - `{key}`: the one task a tile counts
 */
@customElement('ca-kpis')
@localized()
export class CaKpis extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
      @media (max-width: 1150px) { .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
      @media (max-width: 700px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      /* Neutral by default: the number is emphasised by size and weight. A tile whose subject is a problem
         (above 0) takes its status: the number, the mark before the label and a thin edge. */
      .kpi { position: relative; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line);
        border-radius: 11px; padding: 12px 14px; overflow: hidden; }
      .kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--edge, transparent); }
      .k { font-size: 12px; font-weight: 600; color: var(--text-muted); }
      .v { font-size: 28px; font-weight: 700; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; color: var(--text); }
      .s { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
      .a { font-size: 11.5px; margin-top: 4px; }
      .kpi.failed { --edge: var(--status-failed); }
      .kpi.failed .v, .kpi.failed .k::before { color: var(--status-failed); }
      .kpi.attention { --edge: var(--status-attention); }
      .kpi.attention .v, .kpi.attention .k::before { color: var(--status-attention); }
    `,
  ];

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The scheduled tasks; without it, tasks are counted from the journal. */
  @property({ attribute: false }) plan: Plan = { nodes: [], groups: [] };

  /** The last value each counted tile showed; a tile whose value changes bumps. */
  private readonly prev = new Map<string, number>();
  private changed: string[] = [];

  private history(stop: string): () => void {
    return () => emit(this, 'ca-navigate', { tab: 'journal', stop });
  }

  /** The tasks behind a count: the task itself when it is one (named), else the history filtered to them (`label`). */
  private show(keys: readonly string[], stop: string, label: string): Tile['action'] {
    const only = keys.length === 1 ? keys[0] : undefined;
    const row = only ? this.journal.find((r) => r.key === only) : undefined;
    return only
      ? { label: row ? kindUnit(row) : only, run: () => emit(this, 'ca-open-task', { key: only }) }
      : { label, run: this.history(stop) };
  }

  private tiles(): Tile[] {
    const k = kpis(this.journal);
    const outcomes = taskOutcomes(this.journal, this.plan);
    const c = outcomeCounts(outcomes);
    const done = c.done + c.recovered;
    // The total is neutral; the parts that are problems carry their own status.
    const parts: Fact[] = [
      { text: stateCount('done', done), tone: '' },
      { text: c.failed ? stateCount('failed', c.failed) : '', tone: problemTone(c.failed, 'failed') },
      { text: c.not_started ? stateCount('not_started', c.not_started) : '', tone: problemTone(c.not_started, 'attention') },
    ];
    return [
      { id: 'tasks', tone: '', label: msg('Tasks'), value: c.total, sub: '', parts },
      {
        id: 'attempts',
        tone: '',
        label: msg('Attempts'),
        value: k.attempts,
        sub: facts(k.launches === 1 ? msg('1 agent session') : msg(str`${k.launches} agent sessions`), k.python === 1 ? msg('1 Python task attempt') : msg(str`${k.python} Python task attempts`)),
        tip: msg('Attempts that ran, retries included (journal.jsonl)'),
      },
      ...this.spendTiles(),
      {
        id: 'bad',
        tone: problemTone(k.bad, 'failed'),
        label: msg('Failed attempts'),
        value: k.bad,
        sub: k.bad ? '' : msg('All attempts passed'),
        ...(k.bad ? { action: { label: msg('Failed attempts in history'), run: this.history('bad') } } : {}),
      },
      {
        id: 'notstarted',
        tone: problemTone(c.not_started, 'attention'),
        label: msg('Not started'),
        value: c.not_started,
        sub: c.not_started ? notStartedCauses(outcomes.values()) : msg('All tasks started'),
        ...(c.not_started ? { action: { label: msg('Not-started tasks in history'), run: this.history('invalid_input') } } : {}),
      },
      {
        id: 'wall',
        tone: '',
        label: msg('Agent session time'),
        value: fmtDur(k.launchWall),
        sub: msg(str`Python tasks: ${fmtDur(k.pythonWall)}`),
        tip: msg('Sum over all agent sessions, including ones running at once'),
      },
      {
        id: 'retry',
        tone: '',
        label: msg('Retries'),
        value: k.retries,
        sub: !k.retries ? msg('No retries') : k.retriedTasks === 1 ? msg('1 task retried') : msg(str`${k.retriedTasks} tasks retried`),
        tip: msg('Attempts after a failed attempt, each in a new agent session (RetryingRunner)'),
        ...(k.retries ? { action: this.show(k.retriedKeys, 'retried', msg('Retried tasks in history')) } : {}),
      },
      {
        id: 'ct',
        tone: '',
        label: msg('Corrections'),
        value: k.fixups,
        sub: !k.fixups ? msg('No corrections') : k.fixupTasks === 1 ? msg('1 task with corrections') : msg(str`${k.fixupTasks} tasks with corrections`),
        tip: msg('More rounds in the same agent session after the output failed checks (rounds)'),
        ...(k.fixups ? { action: this.show(k.fixupKeys, 'fixup', msg('Attempts with corrections in history')) } : {}),
      },
      {
        id: 'fo',
        tone: '',
        label: msg('Model switches'),
        value: k.switches,
        sub: !k.switches ? msg('No model switches') : k.switchTasks === 1 ? msg('1 task with model switches') : msg(str`${k.switchTasks} tasks with model switches`),
        tip: msg('To the next model after a failure such as a rate limit, an error or a timeout (Router hops)'),
      },
    ];
  }

  /** Cost and tokens, when any attempt reported them. */
  private spendTiles(): Tile[] {
    const s = spendOf(this.journal);
    if (!s) return [];
    const top = spendByKind(this.journal)[0];
    return [
      {
        id: 'cost',
        tone: '',
        label: msg('Cost'),
        value: usd(s.cost),
        sub: top && top.share !== null ? [msg(str`Highest cost: ${top.kind}`), facts(usd(top.spend.cost), msg(str`${Math.round(top.share * 100)}% of the total`))] : '',
        tip: msg('Reported by the coding agent'),
      },
      {
        id: 'tokens',
        tone: '',
        label: msg('Tokens'),
        value: tokens(totalTokens(s)),
        sub: facts(msg(str`${tokens(s.input)} input`), msg(str`${tokens(s.output)} output`), msg(str`${tokens(s.cache_read + s.cache_creation)} cache`)),
        tip: facts(
          msg(str`${tokens(s.cache_read)} cache read`),
          msg(str`${tokens(s.cache_creation)} cache write`),
          s.calls === 1 ? msg('1 API call') : msg(str`${s.calls} API calls`),
        ),
      },
    ];
  }

  override render() {
    const tiles = this.tiles();
    this.changed = [];
    for (const t of tiles) {
      if (typeof t.value !== 'number') continue;
      if ((this.prev.get(t.id) ?? 0) !== t.value) this.changed.push(t.id);
      this.prev.set(t.id, t.value);
    }
    return html`<div class="kpis">${tiles.map((t) => this.tile(t))}</div>`;
  }

  private tile(t: Tile): TemplateResult {
    return html`<div class="kpi ${t.tone}" data-id=${t.id} title=${t.tip ?? nothing}>
      <div class="k words ${MARK[t.tone] ?? ''}">${t.label}</div>
      <div class="v">${typeof t.value === 'number' ? html`<ca-count .value=${t.value}></ca-count>` : t.value}</div>
      ${t.parts
        ? html`<div class="s words">${tonedFacts(t.parts)}</div>`
        : (typeof t.sub === 'string' ? [t.sub] : t.sub).map((line) => html`<div class="s words">${factLine(line)}</div>`)}
      ${t.action
        ? html`<div class="a words"><a class="lnk" href="#" @click=${(e: Event) => {
            e.preventDefault();
            t.action?.run();
          }}>${t.action.label}</a></div>`
        : nothing}
    </div>`;
  }

  protected override updated(): void {
    if (reducedMotion()) return;
    for (const id of this.changed) {
      this.renderRoot.querySelector(`.kpi[data-id="${id}"]`)?.animate(
        [{ transform: 'scale(1)' }, { transform: 'scale(1.04)', boxShadow: '0 0 0 1px var(--line2)', offset: 0.35 }, { transform: 'scale(1)' }],
        { duration: 700, easing: 'cubic-bezier(.2,.8,.2,1)' },
      );
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-kpis': CaKpis;
  }
}
