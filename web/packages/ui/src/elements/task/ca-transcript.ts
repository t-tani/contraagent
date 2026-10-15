import { createMonitorClient, type JournalRow, type MonitorClient, type TranscriptEvent } from '@contraagent/api';
import { md } from '@contraagent/elements/markdown';
import type { CaeTranscript, TranscriptMemory, TranscriptSection, TranscriptStrings } from '@contraagent/elements/transcript';
import '@contraagent/elements/transcript/define';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { keyed } from 'lit/directives/keyed.js';
import { classifyRounds } from '../../adapters/transcript/rounds.js';
import { transcriptSections } from '../../adapters/transcript/sections.js';
import { StreamController } from '../../controllers/stream.js';
import { emit, type RoundInfo, type RoundsChangedDetail } from '../../core/events.js';
import { getLocale } from '../../core/i18n.js';
import { RememberedSet, SessionSet, memoryOf, pageMemory } from '../../core/memory.js';
import { promptText } from '../shared/prompt-text.js';
import { retryTip } from '../../words/attempts.js';
import { correctionTip } from '../../words/contract.js';
import { modelSwitchTip } from '../../words/hops.js';

/** The transcript's words, in the reader's language (call at render time). */
const strings = (): TranscriptStrings => ({
  sections: msg('Agent sessions'),
  sectionsTip: [
    `${msg('Retry')}: ${retryTip()}`,
    `${msg('Correction')}: ${correctionTip()}`,
    `${msg('Model switch')}: ${modelSwitchTip()}`,
  ].join('\n'),
  loadEarlier: (n) => (n === 1 ? msg('Show 1 earlier line') : msg(str`Show ${n} earlier lines`)),
  newBelow: (n) => (n === 1 ? msg('Show 1 new event') : msg(str`Show ${n} new events`)),
  newInLatest: (n) =>
    n === 1 ? msg('Show 1 new event in the running agent session') : msg(str`Show ${n} new events in the running agent session`),
  prompt: msg('Prompt'),
  assistant: msg('Assistant'),
  reasoning: msg('Reasoning'),
  characters: (n) => msg(str`${n} characters`),
  tool: msg('tool'),
  results: (n) => (n === 1 ? msg('1 result') : msg(str`${n} results`)),
  done: msg('done', { id: 'tool-done', desc: 'A tool call that finished' }),
  failed: msg('failed'),
  running: msg('running'),
  interrupted: msg('interrupted'),
  interruptedTip: msg('The run ended before the tool call returned'),
  query: msg('query'),
  page: msg('page'),
  fullText: msg('Full text'),
  showAll: (n) => msg(str`Show all (${n} characters)`),
  showLess: msg('Show less'),
});

/**
 * The transcript of one task: every round (one session of the coding agent,
 * with its command line and prompt), chat bubbles, collapsible tool cards (a
 * web search shows its query and the pages it returned as links, a web page
 * read its URL as a link),
 * tailed live. A round is a try (a new session) or a fix-up (the same session,
 * sent back because its output failed its checks); give it the task's journal
 * rows (`.rows`) and each round says how it ended. It draws them with
 * `<cae-transcript>`.
 *
 * Give it `.events` to show a saved transcript, or `run` + `stream` (and
 * `base-url`) to tail one from the monitor. Sends `ca-navigate` with `round`
 * when the reader picks a round, and a non-bubbling `ca-rounds`
 * (`RoundsChangedDetail`) whenever its rounds or the shown round change.
 *
 * @fires ca-navigate - `{round}`: the reader picked a round (null for the latest)
 * @fires ca-rounds - `{launches, shown, rounds}`, not bubbling: the rounds' launch events and what each was, for a host that shows a round's prompt
 */
@customElement('ca-transcript')
@localized()
export class CaTranscript extends LitElement {
  static override styles = css`
    :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
    :host([mode='none']) { display: none; }
    :host([mode='tabs']) { flex: none; }
  `;

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

  /** The round on screen, 0-based; -1 while there is none. */
  @state() private shown = -1;
  @query('cae-transcript') private view?: CaeTranscript;

  private readonly feed = new StreamController(this);
  private memory: TranscriptMemory | null = null;
  private drawn: { key: unknown[]; rounds: RoundInfo[]; sections: TranscriptSection[] } | null = null;
  private lastSent = '';

  private get source(): string {
    return this.events ? 'static' : this.run && this.stream ? `${this.run}\n${this.stream}` : '';
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.hasUpdated) this.requestUpdate();
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    const source = this.source;
    if (!changed.has('events') && source === this.feed.loaded) return;
    const { run, stream } = this;
    const id = `transcript:${run}/${stream ?? ''}`;
    // The page's monitor keeps the open cards for the browser tab and the position in the history entry;
    // an embedded one (`history="memory"`) keeps both in its own memory.
    const memory = memoryOf(this);
    const open = memory === pageMemory ? new SessionSet(`${id}:open`) : new RememberedSet(`${id}:open`, this);
    const tailed = !this.events && !!stream;
    this.memory = {
      isOpen: (card) => open.has(card),
      setOpen: (card, on) => open.set(card, on),
      scroll: () => (tailed ? memory.recall(`${id}:scroll`) : undefined),
      setScroll: (at) => tailed && memory.remember(`${id}:scroll`, at),
    };
    this.shown = -1;
    this.feed.load(source, this.events ? { events: this.events } : source && stream ? { run, stream, baseUrl: this.baseUrl } : null);
  }

  /** The rounds and their sections, drawn again only when the transcript, the rows or the language changed. */
  private sections(): { rounds: RoundInfo[]; sections: TranscriptSection[] } {
    const active = this.live && this.feed.tailing;
    const key = [this.feed.version, this.rows, this.run, active, getLocale()];
    if (this.drawn?.key.every((k, i) => k === key[i])) return this.drawn;
    const t = this.feed.model;
    const rounds = classifyRounds(
      t.rounds.map((r) => r.launch),
      this.rows,
    );
    this.drawn = { key, rounds, sections: transcriptSections(t, rounds, { run: this.run, rows: this.rows, active }) };
    return this.drawn;
  }

  override render() {
    const feed = this.feed;
    const { sections } = this.sections();
    return keyed(
      feed.generation,
      html`<cae-transcript .sections=${sections} .shown=${this.round === null ? null : this.round - 1} ?live=${this.live}
        .earlier=${feed.behind} ?loading=${!feed.ready} .count=${feed.count} mode=${this.mode} .memory=${this.memory}
        .markdown=${md} .renderDetail=${(d: { text: string }) => promptText(d.text)} .strings=${strings()}
        @cae-section-change=${(e: CustomEvent<{ index: number | null }>) => {
          e.stopPropagation();
          emit(this, 'ca-navigate', { round: e.detail.index === null ? null : e.detail.index + 1 });
        }}
        @cae-section-shown=${(e: CustomEvent<{ index: number }>) => {
          e.stopPropagation();
          this.shown = e.detail.index;
        }}
        @cae-load-earlier=${(e: Event) => {
          e.stopPropagation();
          if (this.stream) void feed.loadEarlier(this.client ?? createMonitorClient({ baseUrl: this.baseUrl }), this.run, this.stream);
        }}></cae-transcript>`,
    );
  }

  protected override updated(): void {
    const { rounds } = this.sections();
    const sig = `${this.feed.version}|${this.shown}|${rounds.length}|${this.rows.length}`;
    if (sig === this.lastSent) return;
    this.lastSent = sig;
    const detail: RoundsChangedDetail = { launches: this.feed.model.rounds.map((r) => r.launch), shown: this.shown, rounds };
    emit(this, 'ca-rounds', detail, { bubbles: false });
  }

  /**
   * Show the `nth` (0-based) web search for `query`: its card opens, and is scrolled into
   * view once its round is shown. Returns that round as the `round` of a `ca-navigate`
   * (1-based; null for the latest), or undefined when the transcript holds no such search.
   */
  revealWebSearch(query: string, nth = 0): { round: number | null } | undefined {
    const card = this.feed.model.rounds.flatMap((r) => r.items).filter((it) => it.type === 'tool' && it.query === query)[nth];
    const i = card && this.view ? this.view.reveal(card.id) : -1;
    if (i < 0) return undefined;
    return { round: i === this.feed.model.rounds.length - 1 ? null : i + 1 };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-transcript': CaTranscript;
  }
}
