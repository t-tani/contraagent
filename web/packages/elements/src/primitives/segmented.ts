import { LitElement, css, html, nothing } from 'lit';
import { property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../core/events.js';
import { base } from '../styles/index.js';
import { RovingFocusController } from './roving-focus.js';

export interface SegmentedOption {
  value: string;
  label: string;
  title?: string;
  disabled?: boolean;
  /** The option's language (`lang`), when its label is in another language than the page. */
  lang?: string;
}

/**
 * One choice among a few, as a row of buttons (a radio group): a click, or the
 * arrow keys, Home and End, choose. The group is one tab stop.
 *
 * Its look: `--cae-segmented-radius`, `--cae-segmented-height`,
 * `--cae-segmented-padding`, `--cae-segmented-font-size`,
 * `--cae-segmented-divider` (the line between options) and
 * `--cae-segmented-hover` (an option's text under the pointer), or the parts.
 *
 * @tagname cae-segmented
 * @fires cae-change - `{value}`: the option the reader chose
 * @csspart group - the row of options
 * @csspart option - each option
 * @csspart option-selected - the chosen option
 */
export class CaeSegmented extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: inline-flex; vertical-align: middle; }
      .group { display: inline-flex; border: 1px solid var(--line); border-radius: var(--cae-segmented-radius, 6px); overflow: hidden; }
      button { min-width: 22px; height: var(--cae-segmented-height, 20px); line-height: var(--cae-segmented-height, 20px); padding: var(--cae-segmented-padding, 0 10px);
        margin: 0; border: 0; border-radius: 0; background: none; font-size: var(--cae-segmented-font-size, 11.5px); text-align: center;
        color: var(--text-muted); cursor: pointer; }
      button + button { border-left: var(--cae-segmented-divider, 1px solid var(--line)); }
      button:hover { color: var(--cae-segmented-hover, var(--text)); }
      button[aria-checked='true'] { background: var(--raise); color: var(--text); cursor: default; }
      button:disabled { opacity: 0.5; cursor: default; }
      button:focus-visible { outline-offset: -2px; }
    `,
  ];

  @property({ attribute: false }) options: readonly SegmentedOption[] = [];
  @property() value = '';
  /** The group's accessible name. */
  @property() label = '';

  private readonly roving = new RovingFocusController(this, {
    items: () => [...(this.renderRoot.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])],
    layout: 'horizontal',
    wrap: true,
    onMove: (el) => this.choose(el.dataset['value'] ?? ''),
  });

  override willUpdate(): void {
    const i = this.options.filter((o) => !o.disabled).findIndex((o) => o.value === this.value);
    if (i >= 0) this.roving.current = i;
  }

  private choose(value: string): void {
    if (value === this.value) return;
    this.value = value;
    emit(this, 'cae-change', { value });
  }

  override render() {
    return html`<div class="group" part="group" role="radiogroup" aria-label=${this.label || nothing}>
      ${repeat(
        this.options,
        (o) => o.value,
        (o) => {
          const on = o.value === this.value;
          return html`<button type="button" role="radio" part=${on ? 'option option-selected' : 'option'} aria-checked=${on ? 'true' : 'false'}
            data-value=${o.value} lang=${o.lang || nothing} title=${o.title || nothing} ?disabled=${!!o.disabled}
            @click=${() => this.choose(o.value)}>${o.label}</button>`;
        },
      )}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-segmented': CaeSegmented;
  }
}
