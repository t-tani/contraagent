import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import { base } from '../../styles/index.js';
import { EDITOR_THEMES, THEMES, THEME_CHOICES, type ThemeChoice, type ThemeName } from '../../themes/index.js';

/** A choice's name in the control: a theme's own name stays as it is; `system` and High contrast are words. */
export function themeLabel(choice: ThemeChoice): string {
  if (choice === 'system') return msg('System');
  if (choice === 'high-contrast') return msg('High contrast');
  return THEMES[choice].label;
}

/** A small picture of a theme: its panel, its accent and two of its code colours. */
const swatch = (n: ThemeName) => {
  const t = THEMES[n].tokens;
  return html`<span class="sw" style="background:${t.card};border-color:${t.line2}"
    ><i style="background:${t.accent}"></i><i style="background:${t['code-string']}"></i><i style="background:${t['code-keyword']}"></i
  ></span>`;
};

/**
 * The theme control in the monitor's header: a button that opens a menu of
 * the themes. Arrow keys, Home and End move in the menu; Enter or Space
 * chooses; Escape closes it.
 *
 * @fires ca-choose-theme - `{theme}`: a theme (or `system`) was chosen
 */
@customElement('ca-theme-switch')
@localized()
export class CaThemeSwitch extends LitElement {
  static override styles = [
    base,
    css`
      :host { position: relative; display: inline-flex; }
      .trig { display: inline-flex; align-items: center; gap: 6px; background: none; border: 1px solid var(--line); border-radius: 999px;
        padding: 2px 10px 2px 7px; font-size: 11px; color: var(--text-muted); cursor: pointer; }
      .trig:hover, .trig[aria-expanded='true'] { color: var(--text); border-color: var(--line2); }
      .trig svg { width: 13px; height: 13px; }
      .menu { position: absolute; right: 0; top: calc(100% + 8px); min-width: 236px; padding: 6px; z-index: 50;
        background: var(--panel); border: 1px solid var(--line2); border-radius: 12px;
        box-shadow: 0 18px 48px color-mix(in srgb, var(--shadow) 65%, transparent); animation: enter 0.16s var(--ease) both; }
      .grp { font-size: 11px; color: var(--text-muted); padding: 8px 9px 4px; }
      [role='separator'] { height: 1px; background: var(--line); margin: 6px 4px; }
      .item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 10px; width: 100%;
        background: none; border: 0; border-radius: 8px; padding: 6px 9px; text-align: left; cursor: pointer; color: var(--text-2); font-size: 12px; }
      .item:hover { background: var(--raise); color: var(--text); }
      .item:focus-visible { outline-offset: -2px; }
      .item[aria-checked='true'] { background: var(--accent-bg); color: var(--text); font-weight: 600; }
      .item .meta { font-weight: 400; }
      .item .sub { display: block; }
      /* a radio mark: a ring, filled for the current choice */
      .rd { width: 12px; height: 12px; border-radius: 50%; border: 1.5px solid var(--line2); display: grid; place-items: center; }
      [aria-checked='true'] .rd { border-color: var(--accent); }
      [aria-checked='true'] .rd::after { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }
      .sw { display: inline-flex; gap: 2px; align-items: flex-end; width: 30px; height: 18px; border-radius: 5px; border: 1px solid; padding: 3px 4px; }
      .sw i { flex: 1; height: 4px; border-radius: 2px; }
      .sw i:first-child { height: 8px; }
      .sw.split { padding: 0; overflow: hidden; gap: 0; }
      .sw.split > span { flex: 1; height: 100%; display: flex; gap: 2px; align-items: flex-end; padding: 3px 2px; }
    `,
  ];

  /** The current choice. */
  @property() value: ThemeChoice = 'contraagent-dark';
  /** The theme `system` shows now, by the system's colour scheme. */
  @property() system: ThemeName = 'contraagent-dark';
  @state() private open = false;
  @query('.trig') private trig!: HTMLButtonElement;

  private readonly onDocDown = (e: PointerEvent) => {
    if (this.open && !e.composedPath().includes(this)) this.open = false;
  };

  override connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener('pointerdown', this.onDocDown);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    document.removeEventListener('pointerdown', this.onDocDown);
  }

  private items(): HTMLButtonElement[] {
    return [...this.renderRoot.querySelectorAll<HTMLButtonElement>('.item')];
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('open' as keyof CaThemeSwitch) && this.open) {
      (this.items().find((b) => b.getAttribute('aria-checked') === 'true') ?? this.items()[0])?.focus();
    }
  }

  private close(focusTrigger: boolean): void {
    this.open = false;
    if (focusTrigger) this.trig?.focus();
  }

  private choose(choice: ThemeChoice): void {
    this.value = choice;
    emit(this, 'ca-choose-theme', { theme: choice });
    this.close(true);
  }

  private onTrigKey(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      this.open = true;
    }
  }

  private onMenuKey(e: KeyboardEvent): void {
    const items = this.items();
    const i = items.indexOf(e.composedPath()[0] as HTMLButtonElement);
    const go = (n: number) => items[(n + items.length) % items.length]?.focus();
    if (e.key === 'ArrowDown') go(i + 1);
    else if (e.key === 'ArrowUp') go(i - 1);
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(items.length - 1);
    else if (e.key === 'Escape') this.close(true);
    else if (e.key === 'Tab') {
      this.open = false;
      return;
    } else return;
    e.preventDefault();
    e.stopPropagation();
  }

  private item(choice: ThemeChoice) {
    const on = choice === this.value;
    const pic =
      choice === 'system'
        ? html`<span class="sw split" style="border-color:${THEMES['contraagent-dark'].tokens.line2}"
            ><span style="background:${THEMES['contraagent-dark'].tokens.card}"><i style="background:${THEMES['contraagent-dark'].tokens.accent}"></i></span
            ><span style="background:${THEMES['contraagent-light'].tokens.card}"><i style="background:${THEMES['contraagent-light'].tokens.accent}"></i></span
          ></span>`
        : swatch(choice);
    return html`<button type="button" class="item" role="menuitemradio" aria-checked=${on ? 'true' : 'false'} tabindex="-1"
      data-theme=${choice} @click=${() => this.choose(choice)}>
      ${pic}<span>${themeLabel(choice)}${choice === 'system' ? html`<span class="meta sub">${THEMES[this.system].label}</span>` : nothing}</span><span class="rd" aria-hidden="true"></span>
    </button>`;
  }

  override render() {
    const own = THEME_CHOICES.filter((c) => c === 'system' || !(EDITOR_THEMES as readonly string[]).includes(c));
    return html`<button type="button" class="trig" aria-haspopup="menu" aria-expanded=${this.open ? 'true' : 'false'} aria-controls="menu"
        title=${msg(str`Theme: ${themeLabel(this.value)}`)} @click=${() => (this.open = !this.open)} @keydown=${(e: KeyboardEvent) => this.onTrigKey(e)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5" /><path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor" /></svg>
        ${msg('Theme')}
      </button>
      ${this.open
        ? html`<div id="menu" class="menu" role="menu" aria-label=${msg('Theme')} @keydown=${(e: KeyboardEvent) => this.onMenuKey(e)}>
            ${own.map((c) => this.item(c))}
            <div role="separator"></div>
            <div role="group" aria-labelledby="grp-editor">
              <div class="grp" id="grp-editor">${msg('Editor themes')}</div>
              ${EDITOR_THEMES.map((c) => this.item(c))}
            </div>
          </div>`
        : nothing}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-theme-switch': CaThemeSwitch;
  }
}
