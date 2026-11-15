import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import '@contraagent/elements/segmented/define';
import { RovingFocusController } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';
import { EDITOR_THEMES, THEMES, THEME_CHOICES, type ThemeChoice, type ThemeName } from '@contraagent/elements/themes';

/** A choice's name in the settings: a theme's own name stays as it is; `system` and High contrast are words. */
export function themeLabel(choice: ThemeChoice): string {
  if (choice === 'system') return msg('System');
  if (choice === 'high-contrast') return msg('High contrast');
  return THEMES[choice].label;
}

/** A language to choose: its code and its name in that language. */
export interface LocaleOption {
  value: string;
  label: string;
}

/** A key of the monitor and what it does: `1`–`7` Tabs. */
export interface KeyHint {
  keys: readonly string[];
  does: string;
}

/** A small picture of a theme: its panel, its accent and two of its code colours. */
const swatch = (n: ThemeName) => {
  const t = THEMES[n].tokens;
  return html`<span class="sw" style="background:${t.card};border-color:${t.line2}"
    ><i style="background:${t.accent}"></i><i style="background:${t['code-string']}"></i><i style="background:${t['code-keyword']}"></i
  ></span>`;
};

/** The picture of `system`: half contraagent Dark, half contraagent Light. */
const systemSwatch = () => {
  const [d, l] = [THEMES['contraagent-dark'].tokens, THEMES['contraagent-light'].tokens];
  return html`<span class="sw split" style="border-color:${d.line2}"
    ><span style="background:${d.card}"><i style="background:${d.accent}"></i></span
    ><span style="background:${l.card}"><i style="background:${l.accent}"></i></span
  ></span>`;
};

/**
 * The monitor's settings, behind one button of its header: the theme, the
 * language and the keys that work. The button opens a panel over the page (a
 * popover: a press outside it or Escape closes it). A choice applies at once
 * and the panel stays open. In the list of themes the arrow keys, Home and End
 * move; Enter or Space chooses.
 *
 * @fires ca-choose-theme - `{theme}`: a theme (or `system`) was chosen
 * @fires ca-choose-locale - `{locale}`: a language was chosen
 */
@customElement('ca-settings')
@localized()
export class CaSettings extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: inline-flex; }
      .trig { anchor-name: --ca-settings; display: grid; place-items: center; width: 32px; height: 32px; padding: 0; background: none; border: 0;
        border-radius: var(--radius-md); color: var(--text-muted); cursor: pointer; transition: color 0.15s, background 0.15s; }
      .trig:hover, .trig.on { color: var(--text); background: var(--raise); }
      .trig svg { width: 16px; height: 16px; }
      .panel { position-anchor: --ca-settings; width: max-content; min-width: 240px; max-width: calc(100vw - 16px); max-height: calc(100dvh - 16px); overflow: auto;
        padding: 6px; background: var(--panel); color: var(--text); border: 1px solid var(--line2); border-radius: var(--radius-lg);
        box-shadow: 0 16px 40px color-mix(in srgb, var(--shadow) 55%, transparent); font-size: var(--font-size-sm); overscroll-behavior: contain; }
      /* closed unless the browser opened it (a popover), or, where there are no popovers, the button did */
      .panel:not(:is(:popover-open, .open)) { display: none; }
      /* under the button, its end at the button's end; over it where there is no room under it */
      @supports (position-area: block-end) {
        .panel { inset: auto; margin: 6px 0; position-area: block-end span-inline-start; position-try-fallbacks: flip-block; }
      }
      /* no anchors: placed from the button's box when it opens (place()) */
      @supports not (position-area: block-end) {
        .panel { inset: auto; margin: 0; }
        .panel.open { position: absolute; z-index: 50; }
      }
      .panel:popover-open { opacity: 1; transform: none; transition: opacity 0.14s var(--ease), transform 0.14s var(--ease); }
      @starting-style {
        .panel:popover-open { opacity: 0; transform: translateY(-4px); }
      }
      .part + .part, .part.more { border-top: 1px solid var(--line); margin-top: 6px; padding-top: 6px; }
      .item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; width: 100%; min-height: 32px;
        background: none; border: 0; border-radius: var(--radius-md); padding: 4px 8px; text-align: start; cursor: pointer; color: var(--text-2); }
      .item:hover { background: var(--raise); color: var(--text); }
      .item:focus-visible { outline-offset: -2px; }
      .item[aria-checked='true'] { color: var(--text); font-weight: 600; }
      .item .meta { font-weight: 400; margin-inline-start: 2px; }
      /* the mark of the chosen theme: a check, drawn so that it stays in forced colours */
      .ck { width: 14px; height: 14px; color: var(--accent); visibility: hidden; }
      [aria-checked='true'] .ck { visibility: visible; }
      .sw { display: inline-flex; gap: 2px; align-items: flex-end; width: 28px; height: 18px; border-radius: var(--radius-sm); border: 1px solid; padding: 3px 4px; forced-color-adjust: none; }
      .sw i { flex: 1; height: 4px; border-radius: 2px; }
      .sw i:first-child { height: 8px; }
      .sw.split { padding: 0; overflow: hidden; gap: 0; }
      .sw.split > span { flex: 1; height: 100%; display: flex; gap: 2px; align-items: flex-end; padding: 3px 2px; }
      .langs { display: flex; margin: 2px; --cae-segmented-height: 28px; --cae-segmented-font-size: var(--font-size-sm); --cae-segmented-padding: 0 12px; }
      .langs::part(group) { flex: 1; }
      .langs::part(option) { flex: 1; }
      .keys { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; margin: 0; padding: 6px 8px 4px; color: var(--text-2); align-items: center; }
      .keys dt { display: flex; gap: 3px; align-items: center; }
      .keys dd { margin: 0; }
    `,
  ];

  /** The reader's choice of a theme. */
  @property() theme: ThemeChoice = 'system';
  /** The theme `system` shows now, by the system's colour scheme. */
  @property() system: ThemeName = 'contraagent-dark';
  /** The languages to choose from; fewer than two and the panel has no language choice. */
  @property({ attribute: false }) locales: readonly LocaleOption[] = [];
  /** The language shown now. */
  @property() locale = '';
  /** The keys that work now, each with what it does; none and the panel lists none. */
  @property({ attribute: false }) keys: readonly KeyHint[] = [];

  @query('.trig') private trig!: HTMLButtonElement;
  @query('.panel') private panel!: HTMLElement;

  /** One tab stop for the list of themes, on the chosen one. */
  private readonly themeFocus = new RovingFocusController(this, {
    items: () => [...this.renderRoot.querySelectorAll<HTMLElement>('.item')],
    layout: 'vertical',
    wrap: true,
  });

  override willUpdate(): void {
    this.themeFocus.current = Math.max(0, THEME_CHOICES.indexOf(this.theme));
  }

  private choose(theme: ThemeChoice): void {
    this.theme = theme;
    emit(this, 'ca-choose-theme', { theme });
  }

  /** Open or close the panel: the browser's popover, else (no popovers) a class and a place under the button. */
  private toggle(): void {
    const p = this.panel;
    if (typeof p.togglePopover === 'function') {
      p.togglePopover();
      return;
    }
    const open = p.classList.toggle('open');
    this.trig.classList.toggle('on', open);
    if (open) this.place();
  }

  /** Where no browser anchors the panel to the button: under the button, its end at the button's end. */
  private place(): void {
    if (CSS.supports('position-area', 'block-end')) return;
    const b = this.trig.getBoundingClientRect();
    const p = this.panel;
    const fixed = p.matches(':popover-open');
    const host = fixed ? { top: 0, right: document.documentElement.clientWidth } : this.getBoundingClientRect();
    p.style.top = `${b.bottom + 6 - host.top}px`;
    p.style.right = `${host.right - b.right}px`;
  }

  /** The focus is in the panel as it closes (Escape, a press outside it): it goes back to the button. */
  private refocus = false;

  private onBeforeToggle(e: ToggleEvent): void {
    // Before the panel is hidden, while the focus is still where it was. A browser returns the focus itself
    // only when it sees it inside the panel, which it does not across a shadow root.
    if (e.newState === 'closed') this.refocus = this.panel.matches(':focus-within');
  }

  private onToggle(e: ToggleEvent): void {
    const open = e.newState === 'open';
    this.trig.classList.toggle('on', open);
    this.trig.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) this.place();
    else if (this.refocus) this.trig.focus();
    this.refocus = false;
  }

  private item(choice: ThemeChoice) {
    const on = choice === this.theme;
    return html`<button type="button" class="item" role="radio" aria-checked=${on ? 'true' : 'false'} data-theme=${choice} @click=${() => this.choose(choice)}>
      ${choice === 'system' ? systemSwatch() : swatch(choice)}
      <span>${themeLabel(choice)}${choice === 'system' ? html` <span class="meta">${THEMES[this.system].label}</span>` : nothing}</span>
      <svg class="ck" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>`;
  }

  override render() {
    const editor = EDITOR_THEMES as readonly string[];
    const own = THEME_CHOICES.filter((c) => !editor.includes(c));
    const name = msg('Settings');
    return html`<button type="button" class="trig" aria-label=${name} title=${name} aria-haspopup="dialog" aria-expanded="false" @click=${() => this.toggle()}>
        <svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M2 4.5h6M12 4.5h2M2 11.5h2M8 11.5h6" /><circle cx="10" cy="4.5" r="2" /><circle cx="6" cy="11.5" r="2" />
        </svg>
      </button>
      <div class="panel" popover role="dialog" aria-label=${name} @beforetoggle=${(e: ToggleEvent) => this.onBeforeToggle(e)} @toggle=${(e: ToggleEvent) => this.onToggle(e)}>
        <div class="part" role="radiogroup" aria-label=${msg('Theme')}>
          ${own.map((c) => this.item(c))}
          <div class="part more" role="group" aria-label=${msg('Editor themes')}>${EDITOR_THEMES.map((c) => this.item(c))}</div>
        </div>
        ${this.locales.length > 1
          ? html`<div class="part"><cae-segmented class="langs" label=${msg('Language')} .value=${this.locale}
              .options=${this.locales.map((l) => ({ value: l.value, label: l.label, lang: l.value }))}
              @cae-change=${(e: CustomEvent<{ value: string }>) => emit(this, 'ca-choose-locale', { locale: e.detail.value })}></cae-segmented></div>`
          : nothing}
        ${this.keys.length
          ? html`<dl class="part keys" aria-label=${msg('Keyboard shortcuts')}>
              ${this.keys.map((k) => html`<dt>${k.keys.map((x, i) => html`${i ? '–' : nothing}<span class="kbd">${x}</span>`)}</dt><dd>${k.does}</dd>`)}
            </dl>`
          : nothing}
      </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-settings': CaSettings;
  }
}
