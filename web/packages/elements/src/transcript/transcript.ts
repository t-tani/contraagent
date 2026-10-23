import { LitElement, html, nothing, type PropertyValues, type TemplateResult } from 'lit';
import { property, query, state } from 'lit/decorators.js';
import { keyed } from 'lit/directives/keyed.js';
import { repeat } from 'lit/directives/repeat.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { emit } from '../core/events.js';
import { withDefaults } from '../core/strings.js';
import { toneAttr } from '../core/tone.js';
import { base, prose } from '../styles/index.js';
import { FollowScroll } from './follow-scroll.js';
import { transcriptStyles } from './styles.js';
import { tagChips, tagStyles } from './tags.js';
import { toolCard, type CardHost } from './tool-card.js';
import {
  DEFAULT_TRANSCRIPT_STRINGS,
  type TranscriptDetail,
  type TranscriptItem,
  type TranscriptMemory,
  type TranscriptSection,
  type TranscriptStrings,
} from './types.js';

const reducedMotion = (): boolean => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/**
 * A conversation with an agent, in sections (one session each): chat bubbles,
 * reasoning, notices and collapsible tool cards (a web search lists the pages
 * it returned as links). Above two sections, a picker shows one at a time;
 * the latest is followed unless `shown` names another. While the reader is at
 * the bottom, new content scrolls into view; once they scroll up, it stays,
 * and a button counts what arrived below. A new section that starts while
 * they read the latest one keeps the one they read on screen.
 *
 * Give it a new element (or set `loading` until the content arrives) for
 * another transcript: what the reader opened and where they were belong to one
 * transcript, kept in `memory`.
 *
 * @tagname cae-transcript
 * @fires cae-section-change - `{index}`: the reader picked a section (null: the latest)
 * @fires cae-section-shown - `{index}`: the section on screen changed (-1: none)
 * @fires cae-load-earlier - the reader asked for the content before `earlier`
 * @csspart picker - the section picker
 * @csspart section - the section shown
 * @csspart tag - a chip at the head of the section
 * @csspart bubble - a prompt, an answer, reasoning or an event
 * @csspart notice - a line of the agent's log
 * @csspart tool - a tool card
 * @csspart tool-body - an open tool card's body
 * @csspart verdict - the box after the items (`footer`)
 */
export class CaeTranscript extends LitElement {
  static override styles = [base, prose, tagStyles, transcriptStyles];

  @property({ attribute: false }) sections: readonly TranscriptSection[] = [];
  /** The section to show, 0-based; null follows the latest. */
  @property({ attribute: false }) shown: number | null = null;
  /** The transcript is still being written: it shows the agent working; a tool call with no result is running, not interrupted. */
  @property({ type: Boolean }) live = false;
  /** Lines before the content that are not loaded: above 0, a button asks for them (`cae-load-earlier`). */
  @property({ type: Number }) earlier = 0;
  /** The content has not arrived yet: the reader's position is restored once it has. */
  @property({ type: Boolean }) loading = false;
  /** How much the transcript holds, for the count of what arrived below; by default its sections and items. */
  @property({ attribute: false }) count: number | null = null;
  /** `full`; `tabs`: only the section picker; `none`: hidden. */
  @property({ reflect: true }) mode: 'full' | 'tabs' | 'none' = 'full';
  /** Where the open tool cards and the scroll position are kept. */
  @property({ attribute: false }) memory: TranscriptMemory | null = null;
  /** Markdown to safe HTML (the text escaped), for answers and reasoning; without it they show as plain text. */
  @property({ attribute: false }) markdown: ((text: string) => string) | null = null;
  /** Draws an open prose detail (a prompt); by default as `markdown`. */
  @property({ attribute: false }) renderDetail: ((detail: TranscriptDetail) => unknown) | null = null;
  @property({ attribute: false }) strings: Partial<TranscriptStrings> = {};

  @state() private bulk = true;
  @state() private unseen = 0;
  /** A section kept on screen while the reader reads it and a new one starts (`shown` still says "latest"). */
  @state() private pinned: number | null = null;
  /** The card `reveal` asked for: scrolled to once it is drawn. */
  @state() private revealed = '';
  private revealPending = false;

  @query('.scroller') private scroller?: HTMLElement;
  private readonly follow = new FollowScroll(() => this.scroller);
  private started = false;
  private total = 0;
  /** The next `sections` is the content again, from further back (`cae-load-earlier`). */
  private reloading = false;
  private lastShown = -1;
  private readonly opened = new Set<string>();
  private readonly folds = new Set<string>();
  private readonly openDetails = new Set<string>();
  private readonly mdCache = new Map<string, { raw: string; html: string }>();

  /** The section on screen, 0-based; -1 with none. */
  get shownIndex(): number {
    const n = this.sections.length;
    if (!n) return -1;
    const want = this.shown ?? this.pinned ?? n - 1;
    return Math.max(0, Math.min(n - 1, want));
  }

  /**
   * Opens the tool card `id` and scrolls it into view once its section is shown.
   * Returns that section's index (the host shows it), or -1 when no section has the card.
   */
  reveal(id: string): number {
    const i = this.sections.findIndex((s) => s.items.some((it) => it.id === id));
    if (i < 0) return -1;
    this.setOpen(id, true);
    this.pinned = null;
    this.revealed = id;
    this.revealPending = true;
    this.requestUpdate();
    return i;
  }

  private onLatest(): boolean {
    const n = this.sections.length;
    return n < 2 || this.shownIndex === n - 1;
  }

  private isOpen(id: string): boolean {
    return this.memory ? this.memory.isOpen(id) : this.opened.has(id);
  }

  private setOpen(id: string, open: boolean): void {
    if (this.memory) this.memory.setOpen(id, open);
    else if (open) this.opened.add(id);
    else this.opened.delete(id);
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    const total = this.count ?? this.sections.reduce((n, s) => n + 1 + s.items.length, 0);
    if (changed.has('sections')) {
      const was = changed.get('sections')?.length ?? 0;
      // A new section while the reader is scrolled up in the latest one: keep showing the one being read.
      if (was && this.sections.length > was && this.shown === null && this.pinned === null && !this.follow.stick && !this.bulk)
        this.pinned = was - 1;
      if (this.reloading) {
        this.reloading = false;
        this.lastShown = -1;
        this.total = total;
      }
    }
    if (this.loading) return;
    if (!this.started) {
      this.started = true;
      this.total = total;
      void this.afterFirst();
    } else if (total !== this.total) {
      const n = total - this.total;
      this.total = total;
      if (n > 0)
        void this.updateComplete.then(() => {
          // New content glides into view, as a log does; at once with reduced motion.
          if (this.follow.stick && this.onLatest()) this.follow.toBottom(!reducedMotion());
          else this.unseen += n;
        });
    }
  }

  /** The first content is drawn without entry animations, then the reader is put back where they were. */
  private async afterFirst(): Promise<void> {
    await this.updateComplete;
    await this.follow.restore(this.memory?.scroll(), () => !this.isConnected);
    requestAnimationFrame(() => (this.bulk = false));
  }

  private onScroll(): void {
    const at = this.follow.read();
    if (!at) return;
    if (this.follow.stick && this.onLatest()) this.unseen = 0;
    if (this.follow.restored) this.memory?.setScroll(at);
  }

  protected override updated(changed: PropertyValues<this>): void {
    const shown = this.shownIndex;
    if (shown !== this.lastShown) {
      const before = this.lastShown;
      this.lastShown = shown;
      if (before !== -1 && this.follow.restored) {
        this.follow.toBottom();
        // Another section in place of the one shown: it fades in once, the list as a whole.
        if (!reducedMotion()) this.scroller?.animate?.([{ opacity: 0.25 }, { opacity: 1 }], { duration: 240, easing: 'ease-out' });
      }
      emit(this, 'cae-section-shown', { index: shown });
    }
    const prevMode = changed.get('mode');
    // Shown again after another view: back to where the reader was.
    if (prevMode && prevMode !== 'full' && this.mode === 'full') this.follow.reshow();
    if (this.revealPending) {
      const card = this.renderRoot.querySelector<HTMLElement>(`[data-card="${CSS.escape(this.revealed)}"]`);
      if (card && this.mode === 'full') {
        this.revealPending = false;
        this.follow.stick = false;
        card.scrollIntoView({ block: 'center' });
      }
    }
  }

  private pick(i: number): void {
    this.pinned = null;
    emit(this, 'cae-section-change', { index: i === this.sections.length - 1 ? null : i });
  }

  private toLatest(): void {
    const n = this.sections.length;
    if (n > 1 && this.shownIndex !== n - 1) {
      this.pinned = null;
      if (this.shown !== null) emit(this, 'cae-section-change', { index: null });
    }
    this.follow.stick = true;
    this.unseen = 0;
    void this.updateComplete.then(() => this.follow.toBottom(true));
  }

  private loadEarlier(): void {
    this.reloading = true;
    emit(this, 'cae-load-earlier', {});
  }

  override render() {
    const s = withDefaults(DEFAULT_TRANSCRIPT_STRINGS, this.strings);
    const sections = this.sections;
    const shown = this.shownIndex;
    const section = sections[shown];
    const cards: CardHost = {
      s,
      live: this.live,
      revealed: this.revealed,
      folds: this.folds,
      isOpen: (id) => this.isOpen(id),
      toggle: (id) => {
        this.setOpen(id, !this.isOpen(id));
        this.requestUpdate();
      },
      requestUpdate: () => this.requestUpdate(),
    };
    return html`${this.renderPicker(sections, shown, s)}
      <div class="scroller ${this.bulk ? 'bulk' : ''}" @scroll=${() => this.onScroll()}>
        ${this.earlier
          ? html`<div class="meta"><button type="button" class="back" @click=${() => this.loadEarlier()}>
              ${s.loadEarlier(this.earlier)}</button></div>`
          : nothing}
        ${section ? keyed(section.id, this.renderSection(section, shown === sections.length - 1, s, cards)) : nothing}
        ${!section && this.live ? this.typing(s) : nothing}
      </div>
      ${this.unseen
        ? html`<button type="button" class="newpill" @click=${() => this.toLatest()}>
            ${this.onLatest() ? s.newBelow(this.unseen) : s.newInLatest(this.unseen)}</button>`
        : nothing}`;
  }

  private renderPicker(sections: readonly TranscriptSection[], shown: number, s: TranscriptStrings) {
    if (sections.length < 2) return nothing;
    // The buttons say what they pick: the picker's name is for screen readers, its tooltip on the group.
    return html`<div class="rounds" role="group" aria-label=${s.sections} title=${s.sectionsTip || nothing} part="picker">
      ${sections.map((sec, i) => {
        const v = sec.verdict;
        return html`<button type="button" class="stab ${i === shown ? 'sel' : ''}" title=${v?.tip || nothing} aria-pressed=${i === shown}
          @click=${() => this.pick(i)}>
          ${v ? html`<span class="mk ${v.tone === 'done' ? 'ok' : 'bad'}" aria-hidden="true">${v.tone === 'done' ? '✓' : '✕'}</span><span class="sr">${v.text}</span>` : nothing}${sec.title}
          ${sec.facts?.length ? html` <span class="stab-m">${sec.facts.join(' | ')}</span>` : nothing}
          ${sec.active ? html`<span class="dot" data-tone="running"></span>` : nothing}
        </button>`;
      })}
    </div>`;
  }

  private renderSection(sec: TranscriptSection, isLast: boolean, s: TranscriptStrings, cards: CardHost) {
    const f = sec.footer;
    return html`<div class="inv-body" part="section">
      ${sec.tags?.length || sec.details?.length ? this.renderHead(sec) : nothing}
      ${repeat(sec.items, (it) => it.id, (it) => this.renderItem(it, s, cards))}
      ${isLast && this.live ? this.typing(s) : nothing}
      ${f
        ? html`<div class="verdict" part="verdict" data-tone=${toneAttr(f.tone)}>
            <b>${f.title}</b>
            ${f.list?.length
              ? html`<ul>${f.list.map((e) => html`<li>${e}</li>`)}</ul>`
              : f.note
                ? html`<span class="meta">${f.note}</span>`
                : nothing}
          </div>`
        : nothing}
    </div>`;
  }

  private renderHead(sec: TranscriptSection) {
    return html`<div class="inv-head">
      <div class="inv-who">${tagChips(sec.tags ?? [])}</div>
      ${(sec.details ?? []).map((d) => (d.code ? html`<details class="inv-cmdbox"><summary>${d.summary}</summary><pre class="inv-cmd"><code>${d.text}</code></pre></details>` : this.renderProse(sec, d)))}
    </div>`;
  }

  /** A prose detail is drawn only while it is open. */
  private renderProse(sec: TranscriptSection, d: TranscriptDetail) {
    const key = `${sec.id}:${d.id}`;
    const open = this.openDetails.has(key);
    return html`<details class="inv-prompt" ?open=${open}
      @toggle=${(e: Event) => {
        const on = (e.target as HTMLDetailsElement).open;
        if (on === this.openDetails.has(key)) return;
        if (on) this.openDetails.add(key);
        else this.openDetails.delete(key);
        this.requestUpdate();
      }}>
      <summary>${d.summary}</summary>
      ${open ? html`<div class="inv-ptext">${this.renderDetail ? this.renderDetail(d) : html`<div class="tx">${this.md(key, d.text)}</div>`}</div>` : nothing}
    </details>`;
  }

  private md(id: string, raw: string) {
    if (!this.markdown) return raw;
    const hit = this.mdCache.get(id);
    if (hit?.raw === raw) return unsafeHTML(hit.html);
    const out = this.markdown(raw);
    this.mdCache.set(id, { raw, html: out });
    return unsafeHTML(out);
  }

  /** A bubble under its head; `named`: no head, the avatar carries the name (the agent's own messages). */
  private bubble(av: string, avCls: string, head: string, body: TemplateResult | string, title?: string, named = false) {
    return html`<div class="msg" part="bubble" title=${title ?? nothing}>
      ${named
        ? html`<div class="av ${avCls}" role="img" aria-label=${head} title=${head}>${av}</div>`
        : html`<div class="av ${avCls}" aria-hidden="true">${av}</div>`}
      <div class="bd">${named ? nothing : html`<div class="hd">${head}</div>`}${body}</div>
    </div>`;
  }

  private renderItem(it: TranscriptItem, s: TranscriptStrings, cards: CardHost) {
    switch (it.type) {
      case 'prompt':
        return this.bubble('▸', 'av-l', s.prompt, html`<div class="tx meta">${s.characters(it.text.length)}</div>`, it.text.slice(0, 600));
      case 'message':
        return this.bubble('A', 'av-a', s.assistant, html`<div class="tx">${this.md(it.id, it.text)}</div>`, undefined, true);
      case 'reasoning':
        return this.bubble('✦', 'av-t', s.reasoning, html`<div class="tx">${this.md(it.id, it.text)}</div>`);
      case 'event':
        return html`<div class="msg" part="bubble"><div class="av av-t" aria-hidden="true">${it.icon}</div><div class="bd"><div class="hd">${it.title}</div>${it.text
          ? html`<div class="tx meta">${it.text}</div>`
          : nothing}</div></div>`;
      case 'notice':
        return html`<div class="sysline" part="notice"><span aria-hidden="true">⚙</span><span class="tx">${it.text}</span></div>`;
      case 'tool':
        return toolCard(cards, it);
    }
  }

  private typing(s: TranscriptStrings) {
    return html`<div class="typing"><span class="av av-a" aria-hidden="true">A</span><span class="dots"><i></i><i></i><i></i></span><span class="meta">${s.running}</span></div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-transcript': CaeTranscript;
  }
}
