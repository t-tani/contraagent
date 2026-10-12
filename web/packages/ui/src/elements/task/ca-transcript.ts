import {
  createMonitorClient,
  openStreamFeed,
  type JournalRow,
  type LaunchEvent,
  type MonitorClient,
  type StreamPage,
  type TranscriptEvent,
  type Unsubscribe,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { emit } from '../../events.js';
import { runRelative, stopLabel } from '../../lib/labels.js';
import { md } from '../../lib/markdown.js';
import { SessionSet, recall, remember } from '../../lib/memory.js';
import { base, prose } from '../../styles/base.js';
import '../shared/ca-markdown.js';
import { roundLabel, roundMark, switchText } from './rounds.js';
import {
  applyEvents,
  classifyRounds,
  emptyTranscript,
  type Item,
  type Round,
  type RoundInfo,
  type ToolItem,
  webResults,
  type WebResult,
  type Transcript,
} from './transcript-model.js';
import { whoChips, whoStyles } from './who.js';

/** Within this many pixels of the bottom, the transcript follows new events. */
const STICK_PX = 60;
/** Tool output longer than this is folded. */
const FOLD_AT = 1200;
/** A tool card shows at most this much of a command or an output. */
const SHOW_MAX = 4000;
/** How far back "load earlier" reaches, in transcript lines. */
const EARLIER_LINES = 3000;
const RESTORE_GIVE_UP_MS = 4000;

export interface RoundsChangedDetail {
  /** Each round's launch event (null for events before any launch). */
  launches: (LaunchEvent | null)[];
  /** The round shown, 0-based; -1 while there is none. */
  shown: number;
  /** Each round as a try or a fix-up, with its result when known. */
  rounds: RoundInfo[];
}

/** The host of a URL, for the line under a result; '' when it does not parse. */
function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

interface SavedScroll {
  stick: boolean;
  top: number;
}

/**
 * The transcript of one task: every round (one session of the coding agent,
 * with its command line and prompt), chat bubbles, collapsible tool cards (a
 * web search shows its query and the pages it returned as links, a web page
 * read its URL as a link),
 * tailed live. A round is a try (a new session) or a fix-up (the same session,
 * sent back because its output failed its checks); give it the task's journal
 * rows (`.rows`) and each round says how it ended.
 *
 * Give it `.events` to show a saved transcript, or `run` + `stream` (and
 * `base-url`) to tail one from the monitor. Sends `ca-navigate` with `round`
 * when the reader picks a round, and a non-bubbling `rounds-changed`
 * (`RoundsChangedDetail`) whenever its rounds or the shown round change.
 *
 * @fires ca-navigate - `{round}`: the reader picked a round (null for the latest)
 * @fires rounds-changed - `{launches, shown, rounds}`, not bubbling: the rounds' launch events and what each was, for a host that shows a round's prompt
 */
@customElement('ca-transcript')
@localized()
export class CaTranscript extends LitElement {
  static override styles = [
    base,
    prose,
    whoStyles,
    css`
      :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
      :host([mode='none']) { display: none; }
      :host([mode='tabs']) { flex: none; }
      :host([mode='tabs']) .scroller, :host([mode='tabs']) .newpill { display: none; }

      .rounds { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 0 0 10px; padding-left: 2px; }
      .rounds-lbl { color: var(--mut); font-size: 11.5px; font-weight: 600; margin-right: 4px; cursor: help; }
      .stab { padding: 3px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--card); color: var(--mut);
        cursor: pointer; font-size: 12px; display: inline-flex; align-items: center; }
      .stab:hover { border-color: var(--info); }
      .stab.sel { background: var(--live-a); border-color: var(--live); color: var(--fg); }
      .stab-m { font-family: var(--mono); font-size: 10.5px; color: var(--llm); margin-left: 4px; }
      .stab .dot { width: 6px; height: 6px; margin-left: 4px; }
      .stab .mk { margin-right: 4px; }
      .stab .mk.ok { color: var(--ok); }
      .stab .mk.bad { color: var(--err); }
      .verdict { margin: 6px 10px 4px 41px; padding: 7px 11px; border-radius: 10px; border: 1px solid; font-size: 12px; }
      .verdict.rejected { border-color: rgba(251, 191, 36, 0.4); background: var(--warn-a); color: var(--fg); }
      .verdict.failed { border-color: rgba(248, 113, 113, 0.45); background: var(--err-a); color: var(--fg); }
      .verdict b { display: block; margin-bottom: 2px; }
      .verdict ul { margin: 2px 0 0; padding-left: 18px; font-family: var(--mono); font-size: 11.5px; }

      .scroller { flex: 1 1 auto; min-height: 0; overflow: auto; border: 1px solid var(--line); border-radius: 14px;
        background: linear-gradient(180deg, rgba(15, 23, 36, 0.85), rgba(9, 14, 22, 0.9)); padding: 4px 2px 8px; font-size: 12.5px; }
      .back { margin: 6px 10px; background: var(--raise); border: 1px solid var(--line2); border-radius: 8px; padding: 3px 10px; cursor: pointer; color: var(--fg2); }
      .back:hover { border-color: var(--live); }

      .inv-body { display: flex; flex-direction: column; gap: 10px; }
      .inv-head { border: 1px solid rgba(34, 211, 238, 0.25); border-radius: 12px; background: rgba(34, 211, 238, 0.05); padding: 8px 10px; margin: 4px 8px 6px; }
      .inv-who { display: flex; flex-wrap: wrap; gap: 6px; }
      .inv-cmdbox { margin-top: 6px; }
      .inv-cmdbox summary, .inv-prompt summary { cursor: pointer; font-size: 11px; color: var(--mut); }
      .inv-prompt summary { font-size: 11.5px; }
      .inv-prompt summary:hover { color: var(--info); }
      .inv-cmd { font-family: var(--mono); font-size: 11.5px; white-space: pre-wrap; word-break: break-all; margin: 4px 0 6px; max-height: 160px; overflow: auto; color: var(--fg); }
      .inv-ptext { margin-top: 6px; max-height: 360px; overflow: auto; }

      .msg { display: flex; gap: 9px; padding: 3px 10px; }
      .av { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 7px; line-height: 22px; font-size: 11px; text-align: center; font-weight: 700; }
      .av-a { background: linear-gradient(135deg, #7c3aed, #a78bfa); box-shadow: 0 4px 12px rgba(124, 58, 237, 0.35); color: #fff; }
      .av-l { background: var(--raise); color: var(--live); }
      .av-t { background: var(--raise); color: var(--mut); }
      .bd { flex: 1; min-width: 0; background: rgba(255, 255, 255, 0.025); border: 1px solid var(--line); border-radius: 3px 10px 10px 10px; padding: 5px 10px; }
      .hd { font-size: 11px; font-weight: 600; color: var(--mut); margin-bottom: 1px; }
      .tx { color: var(--fg); line-height: 1.5; word-break: break-word; }
      .tx pre, .tx code { white-space: pre-wrap; }
      .tx pre { margin: 0 0 4px; }

      .toolcard, .typing { margin-left: 41px; margin-right: 10px; }
      .toolcard { border: 1px solid var(--line); border-left: 3px solid var(--line2); border-radius: 10px; margin-top: 3px; margin-bottom: 3px;
        overflow: hidden; background: rgba(0, 0, 0, 0.18); transition: border-color 0.3s; }
      .toolcard.run { border-left-color: var(--live); }
      .toolcard.ok { border-left-color: rgba(52, 211, 153, 0.6); }
      .toolcard.err { border-left-color: var(--err); }
      .th { display: flex; gap: 9px; align-items: baseline; padding: 4px 9px; cursor: pointer; }
      .th:hover { background: rgba(255, 255, 255, 0.03); }
      .tn { font-family: var(--mono); font-weight: 600; flex: none; display: inline-flex; align-items: center; }
      .tn::before { content: '⚒'; display: inline-grid; place-items: center; width: 20px; height: 20px; margin-right: 7px;
        border-radius: 6px; background: var(--raise); color: var(--fg2); font-size: 11px; }
      .toolcard[data-tool='bash'] .tn::before { content: '❯'; color: var(--ok); }
      .toolcard[data-tool='read'] .tn::before { content: '▤'; color: var(--info); }
      .toolcard[data-tool='grep'] .tn::before, .toolcard[data-tool='glob'] .tn::before { content: '⌕'; color: var(--warn); }
      .toolcard[data-tool='edit'] .tn::before, .toolcard[data-tool='write'] .tn::before { content: '✎'; color: var(--llm); }
      .toolcard[data-tool='task'] .tn::before, .toolcard[data-tool='agent'] .tn::before { content: '✦'; color: var(--llm); }
      .toolcard[data-tool='web-search'] .tn::before { content: '◍'; color: var(--info); }
      .toolcard[data-tool='web-fetch'] .tn::before { content: '⇣'; color: var(--info); }
      .toolcard.revealed { box-shadow: 0 0 0 1px var(--live); }
      .tp { font-family: var(--mono); font-size: 11.5px; color: var(--fg); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .ti { color: var(--mut); font-size: 11px; flex: none; max-width: 35%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .st-run, .st-ok, .st-err, .st-int { flex: none; white-space: nowrap; }
      .st-run { color: var(--live); display: inline-flex; align-items: center; gap: 6px; }
      .st-ok { color: var(--ok); }
      .st-err { color: var(--err); }
      .st-int { color: var(--warn); }
      .pdot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--live); animation: breathe 1.8s ease-in-out infinite; }
      .tb { padding: 6px 9px; border-top: 1px solid var(--line); background: rgba(0, 0, 0, 0.25); }
      .tb pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0; font-family: var(--mono); font-size: 12px; }
      .fold { max-height: 220px; overflow: hidden; position: relative; }
      .fold.open { max-height: none; }
      .foldbtn { cursor: pointer; color: var(--info); font-size: 11px; background: none; border: 0; padding: 0; font-family: inherit; }
      .wq { font-size: 12px; margin: 2px 0 6px; }
      .wq b { font-family: var(--mono); font-weight: 600; }
      .wl { color: var(--mut); font-size: 11px; margin-right: 6px; }
      .links { margin: 0 0 6px; padding-left: 30px; font-size: 12px; }
      .links li { margin: 2px 0; overflow-wrap: anywhere; }
      .links a { color: var(--info); text-decoration: none; }
      .links a:hover { text-decoration: underline; }
      .rawfold > summary { cursor: pointer; color: var(--mut); font-size: 11px; }
      .plink { color: var(--info); text-decoration: none; font-family: var(--mono); overflow-wrap: anywhere; }
      .plink:hover { text-decoration: underline; }
      .host { color: var(--mut); font-family: var(--mono); font-size: 11px; margin-left: 6px; }

      .sysline { display: flex; gap: 8px; align-items: baseline; padding: 2px 10px 2px 41px; font-size: 11px; color: var(--mut); font-family: var(--mono); }
      .sysline .tx { color: var(--mut); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .typing { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
      .typing .av { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 9px; display: grid; place-items: center; font-size: 12px; }
      .dots { display: inline-flex; gap: 4px; padding: 8px 12px; border-radius: 12px; background: var(--llm-a); }
      .dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--llm); animation: bounce 1.2s infinite ease-in-out; }
      .dots i:nth-child(2) { animation-delay: 0.15s; }
      .dots i:nth-child(3) { animation-delay: 0.3s; }
      .scroller:not(.bulk) .msg, .scroller:not(.bulk) .toolcard { animation: enter 0.35s var(--ease) both; }

      .newpill { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); z-index: 5; cursor: pointer; padding: 6px 14px;
        border-radius: 999px; border: 1px solid rgba(34, 211, 238, 0.5); background: rgba(8, 20, 32, 0.92); color: var(--live);
        font-size: 12px; font-weight: 600; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5); backdrop-filter: blur(6px); animation: toast-in 0.3s var(--ease) both; }
      .newpill:hover { background: var(--live-a); }
    `,
  ];

  /** A saved transcript to show as is (no feed). */
  @property({ attribute: false }) events: TranscriptEvent[] | null = null;
  @property() run = '';
  /** The transcript's task key (`TaskDetail.stream`). */
  @property({ attribute: false }) stream: string | null = null;
  @property({ attribute: 'base-url' }) baseUrl = '';
  /** For "load earlier"; one is made from `base-url` when absent. */
  @property({ attribute: false }) client: MonitorClient | null = null;
  /** The task is running: show it working; when not, a call still marked running was interrupted. */
  @property({ type: Boolean }) live = false;
  /** The round to show, 1-based; null follows the latest. */
  @property({ attribute: false }) round: number | null = null;
  /** The task's journal rows (finished tries): each round then says how it ended. */
  @property({ attribute: false }) rows: JournalRow[] = [];
  /** `full`; `tabs`: only the round picker (another view of the task is shown); `none`: hidden. */
  @property({ reflect: true }) mode: 'full' | 'tabs' | 'none' = 'full';

  @state() private version = 0;
  @state() private behind = 0;
  @state() private bulk = true;
  @state() private unseen = 0;
  /** A round kept on screen while the reader reads it and a new one starts (the route still says "latest"). */
  @state() private pinned: number | null = null;
  /** The card `revealWebSearch` asked for: scrolled to once it is drawn. */
  @state() private revealed = '';
  private revealPending = false;

  @query('.scroller') private scroller?: HTMLElement;

  private model: Transcript = emptyTranscript();
  private close: Unsubscribe | null = null;
  private loaded = '';
  private token = 0;
  private first = true;
  private stick = true;
  private restored = false;
  private lastTop = 0;
  private lastShown = -1;
  private lastSent = '';
  private openCards = new SessionSet('transcript::open');
  private readonly folds = new Set<string>();
  private readonly openPrompts = new Set<string>();
  private readonly mdCache = new WeakMap<Item, { raw: string; html: string }>();

  private get source(): string {
    return this.events ? 'static' : this.run && this.stream ? `${this.run}\n${this.stream}` : '';
  }

  private get memoryId(): string {
    return `transcript:${this.run}/${this.stream ?? ''}`;
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.close?.();
    this.close = null;
    this.loaded = '';
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.hasUpdated) this.requestUpdate();
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    const source = this.source;
    if (changed.has('events') || source !== this.loaded) this.load(source);
  }

  /** Start over: a new transcript (or the same one after the element was re-attached). */
  private load(source: string): void {
    this.close?.();
    this.close = null;
    this.loaded = source;
    this.token++;
    this.model = emptyTranscript();
    this.first = true;
    this.behind = 0;
    this.bulk = true;
    this.unseen = 0;
    this.pinned = null;
    this.stick = true;
    this.restored = false;
    this.lastShown = -1;
    this.folds.clear();
    this.openPrompts.clear();
    this.openCards = new SessionSet(`${this.memoryId}:open`);
    if (this.events) {
      applyEvents(this.model, this.events);
      this.version++;
      void this.afterFirstPage(this.token);
      return;
    }
    if (!source || !this.stream) return;
    const token = this.token;
    this.close = openStreamFeed(this.run, this.stream, { message: (page) => this.onPage(page, token) }, { baseUrl: this.baseUrl });
  }

  private onPage(page: StreamPage, token: number): void {
    if (token !== this.token) return;
    if (this.first && page.behind) this.behind = page.behind;
    const rounds = this.model.rounds.length;
    const n = applyEvents(this.model, page.events);
    // A new round while the reader is scrolled up in the latest one: keep showing the one being read.
    if (rounds && this.model.rounds.length > rounds && this.round === null && this.pinned === null && !this.stick && !this.bulk)
      this.pinned = rounds;
    this.version++;
    if (this.first) {
      this.first = false;
      void this.afterFirstPage(token);
      return;
    }
    void this.updateComplete.then(() => {
      if (token !== this.token) return;
      if (this.stick && this.onLiveRound()) this.toBottom();
      else this.unseen += n;
    });
  }

  /** The first page is drawn without entry animations, then the reader is put back where they were. */
  private async afterFirstPage(token: number): Promise<void> {
    await this.updateComplete;
    if (token !== this.token) return;
    const saved = this.stream ? recall<SavedScroll>(`${this.memoryId}:scroll`) : undefined;
    const sc = this.scroller;
    if (!saved || saved.stick || !sc) {
      this.stick = true;
      this.toBottom();
    } else {
      this.stick = false;
      const until = performance.now() + RESTORE_GIVE_UP_MS;
      await new Promise<void>((done) => {
        const step = () => {
          const max = sc.scrollHeight - sc.clientHeight;
          sc.scrollTop = Math.min(saved.top, max);
          if (max >= saved.top || performance.now() > until || token !== this.token) done();
          else requestAnimationFrame(step);
        };
        step();
      });
      this.lastTop = sc.scrollTop;
    }
    this.restored = true;
    requestAnimationFrame(() => {
      if (token === this.token) this.bulk = false;
    });
  }

  private shownIndex(): number {
    const n = this.model.rounds.length;
    if (!n) return -1;
    const want = this.round !== null ? this.round - 1 : (this.pinned ?? n - 1);
    return Math.max(0, Math.min(n - 1, want));
  }

  private onLiveRound(): boolean {
    const n = this.model.rounds.length;
    return n < 2 || this.shownIndex() === n - 1;
  }

  private toBottom(smooth = false): void {
    const sc = this.scroller;
    if (!sc) return;
    if (smooth) sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' });
    else sc.scrollTop = sc.scrollHeight;
  }

  private onScroll(): void {
    const sc = this.scroller;
    if (!sc || !sc.clientHeight) return; // hidden: no position to keep
    this.stick = sc.scrollHeight - sc.scrollTop - sc.clientHeight < STICK_PX;
    this.lastTop = sc.scrollTop;
    if (this.stick && this.onLiveRound()) this.unseen = 0;
    if (this.restored && this.stream) remember(`${this.memoryId}:scroll`, { stick: this.stick, top: Math.round(sc.scrollTop) } satisfies SavedScroll);
  }

  protected override updated(changed: PropertyValues<this>): void {
    const shown = this.shownIndex();
    if (shown !== this.lastShown) {
      const before = this.lastShown;
      this.lastShown = shown;
      if (before !== -1 && this.restored) this.toBottom();
    }
    const prevMode = changed.get('mode');
    if (prevMode && prevMode !== 'full' && this.mode === 'full' && this.scroller) {
      // Shown again after another view of the task: back to where the reader was.
      if (this.stick) this.toBottom();
      else this.scroller.scrollTop = this.lastTop;
    }
    const sig = `${this.version}|${shown}|${this.model.rounds.length}|${this.rows.length}`;
    if (sig !== this.lastSent) {
      this.lastSent = sig;
      const detail: RoundsChangedDetail = { launches: this.model.rounds.map((r) => r.launch), shown, rounds: this.infos() };
      this.dispatchEvent(new CustomEvent('rounds-changed', { detail }));
    }
    if (this.revealPending) {
      const card = this.renderRoot.querySelector<HTMLElement>(`[data-card="${CSS.escape(this.revealed)}"]`);
      if (card && this.mode === 'full') {
        this.revealPending = false;
        this.stick = false;
        card.scrollIntoView({ block: 'center' });
      }
    }
  }

  private infos(): RoundInfo[] {
    return classifyRounds(this.model.rounds.map((r) => r.launch), this.rows);
  }

  private pickRound(i: number): void {
    this.pinned = null;
    const last = this.model.rounds.length - 1;
    emit(this, 'ca-navigate', { round: i === last ? null : i + 1 });
  }

  private jumpToLive(): void {
    const n = this.model.rounds.length;
    if (n > 1 && this.shownIndex() !== n - 1) {
      this.pinned = null;
      if (this.round !== null) emit(this, 'ca-navigate', { round: null });
    }
    this.stick = true;
    this.unseen = 0;
    void this.updateComplete.then(() => this.toBottom(true));
  }

  private async loadEarlier(): Promise<void> {
    const { run, stream } = this;
    if (!stream) return;
    const token = this.token;
    const back = Math.max(0, this.behind - EARLIER_LINES);
    this.behind = 0;
    const client = this.client ?? createMonitorClient({ baseUrl: this.baseUrl });
    const page = await client.stream(run, stream, back);
    if (token !== this.token) return;
    this.model = emptyTranscript();
    this.lastShown = -1;
    applyEvents(this.model, page.events);
    this.version++;
  }

  override render() {
    const rounds = this.model.rounds;
    const shown = this.shownIndex();
    const round = rounds[shown];
    const onLive = this.onLiveRound();
    return html`${this.renderRounds(rounds, shown)}
      <div class="scroller ${this.bulk ? 'bulk' : ''}" @scroll=${() => this.onScroll()}>
        ${this.behind
          ? html`<div class="meta"><button type="button" class="back" @click=${() => void this.loadEarlier()}>
              ${this.behind === 1 ? msg('Show 1 earlier line') : msg(str`Show ${this.behind} earlier lines`)}</button></div>`
          : nothing}
        ${round ? this.renderRound(round, shown === rounds.length - 1, this.infos()[shown]) : nothing}
        ${!round && this.live ? this.typing() : nothing}
      </div>
      ${this.unseen
        ? html`<button type="button" class="newpill" @click=${() => this.jumpToLive()}>
            ${this.unseen === 1
              ? onLive
                ? msg('Show 1 new event')
                : msg('Show 1 new event in the running agent session')
              : onLive
                ? msg(str`Show ${this.unseen} new events`)
                : msg(str`Show ${this.unseen} new events in the running agent session`)}</button>`
        : nothing}`;
  }

  private renderRounds(rounds: Round[], shown: number) {
    if (rounds.length < 2) return nothing;
    const last = rounds.length - 1;
    const infos = this.infos();
    const tries = infos[infos.length - 1]?.tryNo ?? 1;
    return html`<div class="rounds" role="group" aria-label=${msg('Agent sessions')}>
      <span class="rounds-lbl"
        title=${msg('Attempt: a new agent session. Correction: the same agent session after failed checks. Model switch: a new agent session on the next model.')}
        >${msg('Agent sessions')}</span>
      ${rounds.map((r, i) => {
        const info = infos[i];
        const [mark, word, why] = info ? roundMark(info, this.run) : ['', '', ''];
        return html`<button type="button" class="stab ${i === shown ? 'sel' : ''}" title=${why || nothing} aria-pressed=${i === shown}
          @click=${() => this.pickRound(i)}>
          ${mark ? html`<span class="mk ${mark === '✓' ? 'ok' : 'bad'}" aria-hidden="true">${mark}</span><span class="sr">${word}</span>` : nothing}${info ? roundLabel(info, tries) : String(i + 1)}
          ${r.who?.model ? html` <span class="stab-m">${r.who.model.replace(/^claude-/, '')}</span>` : nothing}
          ${i === last && this.live && this.close ? html`<span class="dot live"></span>` : nothing}
        </button>`;
      })}
    </div>`;
  }

  private renderRound(r: Round, isLast: boolean, info: RoundInfo | undefined) {
    return html`<div class="inv-body">
      ${r.launch ? this.renderHead(r, r.launch) : nothing}
      ${repeat(r.items, (it) => it.id, (it) => this.renderItem(it))}
      ${isLast && this.live ? this.typing() : nothing}
      ${info ? this.renderVerdict(info) : nothing}
    </div>`;
  }

  /** How the round ended, after its transcript: its output was sent back, or its try failed. */
  private renderVerdict(info: RoundInfo) {
    if (info.result === 'rejected') {
      return html`<div class="verdict rejected">
        <b>${msg('Output failed checks')}</b>
        ${info.rejectedWith.length
          ? html`<ul>${info.rejectedWith.map((e) => html`<li>${runRelative(e, this.run)}</li>`)}</ul>`
          : html`<span class="meta">${msg('Errors: in the correction prompt')}</span>`}
      </div>`;
    }
    if (info.result === 'switched') {
      return html`<div class="verdict failed">
        <b>${switchText(info)}</b>
      </div>`;
    }
    if (info.result === 'failed' && info.row) {
      const why = runRelative(info.row.reason, this.run) || stopLabel(info.row.stop);
      return html`<div class="verdict failed"><b>${msg(str`Attempt ${info.tryNo} failed: ${why}`)}</b></div>`;
    }
    return nothing;
  }

  private renderHead(r: Round, launch: LaunchEvent) {
    const prompt = launch.prompt || '';
    const trunc = launch.prompt_truncated || 0;
    const open = this.openPrompts.has(r.id);
    return html`<div class="inv-head">
      <div class="inv-who">${whoChips(r.who)}</div>
      <details class="inv-cmdbox"><summary>${msg('Command line')}</summary><pre class="inv-cmd"><code>${launch.argv.join(' ')}</code></pre></details>
      <details class="inv-prompt" ?open=${open}
        @toggle=${(e: Event) => {
          const on = (e.target as HTMLDetailsElement).open;
          if (on === this.openPrompts.has(r.id)) return;
          if (on) this.openPrompts.add(r.id);
          else this.openPrompts.delete(r.id);
          this.requestUpdate();
        }}>
        <summary>${trunc
          ? msg(str`Prompt (${prompt.length} characters; ${trunc} characters not saved)`)
          : msg(str`Prompt (${prompt.length} characters)`)}</summary>
        ${open
          ? html`<div class="inv-ptext"><ca-markdown .text=${prompt + (trunc ? `\n\n${msg(str`(${trunc} characters not saved)`)}` : '')}></ca-markdown></div>`
          : nothing}
      </details>
    </div>`;
  }

  private mdOf(item: Item, raw: string): string {
    const hit = this.mdCache.get(item);
    if (hit?.raw === raw) return hit.html;
    const out = md(raw);
    this.mdCache.set(item, { raw, html: out });
    return out;
  }

  private bubble(av: string, avCls: string, head: string, body: TemplateResult | string, title?: string) {
    return html`<div class="msg" title=${title ?? nothing}>
      <div class="av ${avCls}">${av}</div>
      <div class="bd"><div class="hd">${head}</div>${body}</div>
    </div>`;
  }

  private renderItem(it: Item) {
    switch (it.kind) {
      case 'prompt':
        return this.bubble('▸', 'av-l', msg('Prompt'),
          html`<div class="tx meta">${msg(str`${it.text.length} characters`)}</div>`, it.text.slice(0, 600));
      case 'assistant':
        return this.bubble('A', 'av-a', msg('Assistant'), html`<div class="tx">${unsafeHTML(this.mdOf(it, it.raw))}</div>`);
      case 'summary':
        return this.bubble('✦', 'av-t', msg('Reasoning'), html`<div class="tx">${unsafeHTML(this.mdOf(it, it.text))}</div>`);
      case 'retry':
        return html`<div class="msg"><div class="av av-t" aria-hidden="true">↻</div><div class="bd"><div class="hd">${it.attempt
          ? msg(str`API request sent again (${it.attempt})`)
          : msg('API request sent again')}</div></div></div>`;
      case 'notice':
        return html`<div class="sysline"><span aria-hidden="true">⚙</span><span class="tx">${it.text}</span></div>`;
      case 'tool':
        return this.toolCard(it);
    }
  }

  private toolCard(c: ToolItem) {
    const open = this.openCards.has(c.id);
    const results = c.webQuery ? webResults(c.out) : [];
    const status =
      c.status === 'ok'
        ? html`<span class="st-ok"><span aria-hidden="true">✓</span> ${msg('done')}</span>`
        : c.status === 'err'
          ? html`<span class="st-err"><span aria-hidden="true">✕</span> ${msg('failed')}</span>`
          : this.live
            ? html`<span class="st-run"><i class="pdot"></i>${msg('running')}</span>`
            : html`<span class="st-int" title=${msg('The run ended before the tool call returned')}><span aria-hidden="true">◌</span> ${msg('interrupted')}</span>`;
    const tool = c.webQuery ? 'web-search' : c.webFetch ? 'web-fetch' : c.icon;
    return html`<div class="toolcard ${c.status} ${this.revealed === c.id ? 'revealed' : ''}" data-tool=${tool} data-card=${c.id}>
      <div class="th" @click=${() => {
        this.openCards.set(c.id, !open);
        this.requestUpdate();
      }}>
        <span class="tn">${c.name || msg('tool')}</span><span class="tp">${c.preview}</span><span class="ti"
          >${results.length === 1 ? msg('1 result') : results.length ? msg(str`${results.length} results`) : c.intent}</span
        >${status}
      </div>
      ${open
        ? html`<div class="tb">${c.webQuery ? this.webSearchBody(c, results) : c.webFetch ? this.webFetchBody(c) : this.toolBody(c)}</div>`
        : nothing}
    </div>`;
  }

  private toolBody(c: ToolItem) {
    return c.out === null
      ? this.codeBlock(c.cmd, `${c.id}:cmd`)
      : html`${c.cmd ? this.codeBlock(c.cmd, `${c.id}:cmd`) : nothing}${this.codeBlock(c.out, `${c.id}:out`)}`;
  }

  /** A web search: its query, the pages it returned as links, and its full text (folded when it listed pages). */
  private webSearchBody(c: ToolItem, results: WebResult[]) {
    return html`<div class="wq"><span class="wl">${msg('query')}</span><b>${c.webQuery}</b></div>
      ${results.length
        ? html`<ol class="links">
            ${results.map(
              (r) =>
                html`<li><a href=${r.url} target="_blank" rel="noopener noreferrer">${r.title}</a><span class="host">${hostOf(r.url)}</span></li>`,
            )}
          </ol>`
        : nothing}
      ${c.out === null
        ? nothing
        : results.length
          ? html`<details class="rawfold"><summary>${msg('Full text')}</summary>${this.codeBlock(c.out, `${c.id}:out`)}</details>`
          : this.codeBlock(c.out, `${c.id}:out`)}`;
  }

  /** A web page read: its URL as a link, then what the agent got from it. */
  private webFetchBody(c: ToolItem) {
    const url = /^https?:\/\//.test(c.webFetch) ? c.webFetch : '';
    return html`<div class="wq">
        <span class="wl">${msg('page')}</span>${url
          ? html`<a class="plink" href=${url} target="_blank" rel="noopener noreferrer">${url}</a>`
          : html`<b>${c.webFetch}</b>`}
      </div>
      ${c.out !== null ? this.codeBlock(c.out, `${c.id}:out`) : nothing}`;
  }

  /**
   * Show the `nth` (0-based) web search for `query`: its card opens, and is scrolled into
   * view once its round is shown. Returns that round as the `round` of a `ca-navigate`
   * (1-based; null for the latest), or undefined when the transcript holds no such search.
   */
  revealWebSearch(query: string, nth = 0): { round: number | null } | undefined {
    let seen = 0;
    const last = this.model.rounds.length - 1;
    for (const [i, r] of this.model.rounds.entries()) {
      for (const it of r.items) {
        if (it.kind !== 'tool' || it.webQuery !== query || seen++ !== nth) continue;
        this.openCards.set(it.id, true);
        this.pinned = null;
        this.revealed = it.id;
        this.revealPending = true;
        this.requestUpdate();
        return { round: i === last ? null : i + 1 };
      }
    }
    return undefined;
  }

  private codeBlock(text: string, id: string) {
    const pre = html`<pre><code>${text.slice(0, SHOW_MAX)}</code></pre>`;
    if (text.length <= FOLD_AT) return pre;
    const open = this.folds.has(id);
    return html`<div>
      <div class="fold ${open ? 'open' : ''}">${pre}</div>
      <button type="button" class="foldbtn" @click=${() => {
        if (open) this.folds.delete(id);
        else this.folds.add(id);
        this.requestUpdate();
      }}>${open ? msg('Show less') : msg(str`Show all (${text.length} characters)`)}</button>
    </div>`;
  }

  private typing() {
    return html`<div class="typing"><span class="av av-a">A</span><span class="dots"><i></i><i></i><i></i></span><span class="meta">${msg('running')}</span></div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-transcript': CaTranscript;
  }
  interface HTMLElementEventMap {
    'rounds-changed': CustomEvent<RoundsChangedDetail>;
  }
}
