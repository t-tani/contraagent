import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { property, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { withDefaults } from '../core/strings.js';
import { base, prose } from '../styles/index.js';
import { languageOf, tokenLines, tokenize, tokensHtml } from './highlight.js';

/** A line marked in a text: its number, or the first and the last of a range, both included. */
export type LineMark = number | readonly [number, number];

export interface CodeStrings {
  /** The button that copies the whole text. */
  copy: string;
  /** What the copy button says for a moment after the text was copied. */
  copied: string;
  /** The switch between long lines wrapped and scrolled sideways. */
  wrap: string;
  /** What a text with no characters shows. */
  empty: string;
  /** The note under a text cut short: the lines shown of all its lines. */
  cut: (shown: number, total: number) => string;
}

export const DEFAULT_CODE_STRINGS: Readonly<CodeStrings> = {
  copy: 'Copy',
  copied: 'Copied',
  wrap: 'Wrap lines',
  empty: 'No text',
  cut: (shown, total) => `First ${shown.toLocaleString('en')} of ${total.toLocaleString('en')} lines`,
};

/** What of a text is shown. */
export interface ShownText {
  /** The text shown: its first lines. */
  shown: string;
  /** The number of lines shown. */
  lines: number;
  /** The number of lines of the whole text (a last line break ends the last line). */
  total: number;
  /** Less than the whole text is shown. */
  cut: boolean;
}

/**
 * The first lines of `text`: at most `maxLines` lines and `maxCharacters` characters, cut
 * at the end of a line (a first line longer than that is cut inside it).
 */
export function shownText(text: string, maxLines: number, maxCharacters: number): ShownText {
  const all = text.endsWith('\n') ? text.slice(0, -1) : text;
  let total = all || text ? 1 : 0;
  for (let i = all.indexOf('\n'); i >= 0; i = all.indexOf('\n', i + 1)) total++;
  let end = 0;
  let lines = 0;
  while (lines < Math.max(1, maxLines)) {
    const next = all.indexOf('\n', end);
    const stop = next < 0 ? all.length : next;
    if (lines > 0 && stop > maxCharacters) break;
    lines++;
    if (next < 0) {
      end = all.length;
      break;
    }
    end = next + 1;
  }
  let shown = lines >= total ? all : all.slice(0, end - 1);
  if (shown.length > maxCharacters) shown = shown.slice(0, maxCharacters);
  return { shown, lines: total ? lines : 0, total, cut: shown.length < all.length };
}

/** Whether line `n` is in one of `marks`. */
export function isMarked(marks: readonly LineMark[], n: number): boolean {
  return marks.some((m) => (typeof m === 'number' ? m === n : n >= m[0] && n <= m[1]));
}

/**
 * A text shown as code: highlighted by its `language` (`LANGUAGES`, another name of one
 * or a file name; anything else is plain), each line numbered from `start`, the lines of
 * `highlight` marked (a bar beside the number and a tint). Long lines scroll sideways,
 * or wrap with `wrap` or the reader's switch. A text of more than `maxLines` lines or
 * `maxCharacters` characters shows its first lines and says how many it has; the copy
 * button copies the whole text. The line numbers are not part of a selection.
 *
 * @tagname cae-code
 * @csspart header - the path, the language and the buttons
 * @csspart code - the lines, which scroll
 * @csspart cut - the note under a text cut short
 */
export class CaeCode extends LitElement {
  static override styles = [
    base,
    prose,
    css`
      :host { display: block; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--well); overflow: hidden; }
      .head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; padding: 4px 6px 4px 10px; border-bottom: 1px solid var(--line); font-size: var(--font-size-sm); color: var(--text-2); }
      .path { font-family: var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
      .lang { color: var(--text-muted); }
      .tools { margin-left: auto; display: flex; gap: 4px; flex: none; }
      .tools button { font-size: var(--font-size-sm); color: var(--text-2); border: 1px solid var(--line2); border-radius: var(--radius-pill); padding: 0 9px; cursor: pointer; background: none; }
      .tools button[aria-pressed='true'] { background: var(--raise); color: var(--text); }
      .scroll { overflow: auto; max-height: var(--cae-code-max-height, 70vh); font-family: var(--mono); font-size: var(--font-size-md); line-height: 1.5; }
      .lines { display: block; min-width: max-content; padding: 4px 0; }
      .wrap .lines { min-width: 0; }
      .ln { display: flex; }
      /* the number is the line's own: drawn by CSS, so a selection of lines copies no numbers */
      .ln::before { content: attr(data-n); position: sticky; left: 0; flex: none; box-sizing: border-box; width: calc(var(--digits) * 1ch + 22px);
        padding: 0 10px 0 8px; text-align: right; color: var(--text-muted); background: var(--well); border-left: 3px solid transparent; }
      .t { flex: 1; white-space: pre; padding-right: 12px; }
      .t:empty::after { content: ' '; }
      .wrap .t { white-space: pre-wrap; overflow-wrap: anywhere; }
      .ln[data-mark] { background: color-mix(in srgb, var(--accent) 6%, transparent); }
      .hl-doc { opacity: 1; }
      .ln[data-mark]::before { border-left-color: var(--accent); color: var(--text); background: color-mix(in srgb, var(--accent) 14%, var(--well)); }
      .cut, .empty { padding: 4px 10px; font-size: var(--font-size-sm); color: var(--text-muted); border-top: 1px solid var(--line); }
      .empty { border-top: 0; }
    `,
  ];

  /** The text. */
  @property() code = '';
  /** Its language: a name of `LANGUAGES`, another name of one, or a file name; anything else is plain text. */
  @property() language = '';
  /** The number of the first line. */
  @property({ type: Number }) start = 1;
  /** The lines marked, in the numbers shown. */
  @property({ attribute: false }) highlight: readonly LineMark[] = [];
  /** The file the text is, named over it. */
  @property() path = '';
  /** What the lines are named to a screen reader (default: the path). */
  @property() label = '';
  /** Long lines wrap at first; the reader's switch changes it. */
  @property({ type: Boolean }) wrap = false;
  /** The most lines shown. */
  @property({ type: Number }) maxLines = 5000;
  /** The most characters shown, at the end of a line. */
  @property({ type: Number }) maxCharacters = 500_000;
  /** The visible words; English by default. */
  @property({ attribute: false }) strings: Partial<CodeStrings> = {};

  @state() private wrapped = false;
  @state() private copied = false;
  private copiedTimer: ReturnType<typeof setTimeout> | undefined;

  override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('wrap')) this.wrapped = this.wrap;
    if (changed.has('code')) this.copied = false;
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    clearTimeout(this.copiedTimer);
  }

  private async copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.code);
    } catch {
      return;
    }
    this.copied = true;
    clearTimeout(this.copiedTimer);
    this.copiedTimer = setTimeout(() => (this.copied = false), 1500);
  }

  override render() {
    const s = withDefaults(DEFAULT_CODE_STRINGS, this.strings);
    const lang = languageOf(this.language);
    const { shown, lines, total, cut } = shownText(this.code, this.maxLines, this.maxCharacters);
    const last = this.start + Math.max(lines, 1) - 1;
    const rows = tokenLines(tokenize(shown, lang))
      .map((line, i) => {
        const n = this.start + i;
        return `<div class="ln" data-n="${n}"${isMarked(this.highlight, n) ? ' data-mark=""' : ''}><span class="t">${tokensHtml(line)}</span></div>`;
      })
      .join('');
    return html`<div class="head" part="header">
        ${this.path ? html`<span class="path" title=${this.path}>${this.path}</span>` : nothing}
        ${lang ? html`<span class="lang">${lang}</span>` : nothing}
        <span class="tools">
          <button type="button" aria-pressed=${this.wrapped ? 'true' : 'false'} @click=${() => (this.wrapped = !this.wrapped)}>${s.wrap}</button>
          <button type="button" ?disabled=${!this.code} @click=${() => void this.copy()}>${this.copied ? s.copied : s.copy}</button>
        </span>
        <span class="sr" role="status">${this.copied ? s.copied : ''}</span>
      </div>
      ${this.code
        ? html`<div class="scroll ${this.wrapped ? 'wrap' : ''}" part="code" data-scroll=${this.wrapped ? 'y' : 'x'} tabindex="0" role=${this.label || this.path ? 'region' : nothing}
              aria-label=${this.label || this.path || nothing}
              style="--digits: ${String(last).length}">
              <code class="lines hl">${unsafeHTML(rows)}</code>
            </div>
            ${cut ? html`<div class="cut" part="cut">${s.cut(lines, total)}</div>` : nothing}`
        : html`<div class="empty">${s.empty}</div>`}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-code': CaeCode;
  }
}
