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
 * `--cae-segmented-padding`, `--cae-segmented-font-size` and
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
      .group { display: inline-flex; gap: 2px; padding: 2px; background: var(--track); border-radius: var(--cae-segmented-radius, var(--radius-md)); }
      button { min-width: 24px; height: var(--cae-segmented-height, 22px); line-height: var(--cae-segmented-height, 22px); padding: var(--cae-segmented-padding, 0 10px);
        margin: 0; border: 0; border-radius: calc(var(--cae-segmented-radius, var(--radius-md)) - 2px); background: none; font-size: var(--cae-segmented-font-size, var(--font-size-xs)); text-align: center;
        color: var(--text-2); cursor: pointer; transition: color 0.15s, background 0.15s; }
      button:hover { color: var(--cae-segmented-hover, var(--text)); }
      button[aria-checked='true'] { background: var(--panel); color: var(--text); font-weight: 600; cursor: default; box-shadow: 0 1px 2px color-mix(in srgb, var(--shadow) 30%, transparent); }
      button:disabled { opacity: 0.5; cursor: default; }
      button:focus-visible { outline-offset: -2px; }
      /* forced colours: no fill and no shadow, so the chosen option has a line around it */
      @media (forced-colors: active) {
        .group { border: 1px solid CanvasText; }
        button[aria-checked='true'] { outline: 2px solid Highlight; outline-offset: -2px; }
      }
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
