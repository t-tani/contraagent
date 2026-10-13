import { LitElement, css, html, nothing } from 'lit';
import { property, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { withDefaults } from '../core/strings.js';
import { base, prose } from '../styles/index.js';
import { mdFile } from './markdown.js';

export interface MarkdownStrings {
  /** The button that shows the text rendered. */
  showRendered: string;
  /** The button that shows the text as it is. */
  showSource: string;
}

export const DEFAULT_MARKDOWN_STRINGS: Readonly<MarkdownStrings> = { showRendered: 'Show rendered', showSource: 'Show source' };

/**
 * A markdown text with a rendered/source switch. `split` may take a leading line
 * off the text, shown apart above the rendered body; the source is the text as
 * it is.
 *
 * @tagname cae-markdown
 * @csspart toggle - the rendered/source button
 */
export class CaeMarkdown extends LitElement {
  static override styles = [
    base,
    prose,
    css`
      :host { display: block; }
      .bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
    `,
  ];

  @property() text = '';
  /** Takes a leading line off the text (`head`), shown apart above the rendered `body`. */
  @property({ attribute: false }) split?: (text: string) => { head: string; body: string };
  /** Marks up the rendered (escaped) HTML further, as `mdFile`'s `mark`. */
  @property({ attribute: false }) transform?: (html: string) => string;
  /** The visible words; English by default. */
  @property({ attribute: false }) strings: Partial<MarkdownStrings> = {};
  @state() private source = false;

  override render() {
    const s = withDefaults(DEFAULT_MARKDOWN_STRINGS, this.strings);
    const { head, body } = this.split?.(this.text) ?? { head: '', body: this.text };
    const rendered = mdFile(body, this.transform);
    return html`<div class="bar">
        <button type="button" class="df-tog" part="toggle" @click=${() => (this.source = !this.source)}>
          ${this.source ? s.showRendered : s.showSource}</button>
      </div>
      ${this.source
        ? html`<pre class="df-text">${this.text}</pre>`
        : html`${head ? html`<div class="md-tele jmono">${head}</div>` : nothing}${unsafeHTML(rendered)}`}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-markdown': CaeMarkdown;
  }
}
