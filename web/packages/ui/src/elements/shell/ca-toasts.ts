import { LitElement, css, html, nothing } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { base } from '@contraagent/elements/styles';

/** The notice's status (its mark and the colour of its edge); `agent` is a model switch, which is not a status. */
export type ToastKind = 'done' | 'failed' | 'attention' | 'running' | 'agent';

interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  sub: string;
  out: boolean;
}

const ICON: Record<ToastKind, string> = { done: '✓', failed: '✕', attention: '◌', running: '●', agent: '✦' };
const SHOW_MS = 5200;
const MAX = 4;

/** Short notices in a corner; each leaves on its own after a few seconds. */
@customElement('ca-toasts')
export class CaToasts extends LitElement {
  static override styles = [
    base,
    css`
      :host { position: fixed; right: 18px; bottom: 18px; display: flex; flex-direction: column; gap: 8px; z-index: 60; pointer-events: none; }
      .toast { pointer-events: auto; min-width: 240px; max-width: 380px; padding: 10px 14px; border-radius: 11px;
        background: var(--panel2); border: 1px solid var(--line2); box-shadow: 0 18px 40px color-mix(in srgb, var(--shadow) 60%, transparent);
        display: flex; gap: 10px; align-items: flex-start; animation: toast-in 0.35s var(--ease) both; }
      .toast.out { animation: toast-out 0.35s var(--ease) both; }
      .ti { font-size: 16px; line-height: 1.2; }
      b { display: block; font-size: 12.5px; }
      span.sub { font-size: 11.5px; color: var(--text-muted); }
      .ti { color: var(--text-muted); }
      .toast[data-tone] .ti { color: var(--tone); }
      .toast[data-tone='failed'], .toast[data-tone='attention'] { border-color: color-mix(in srgb, var(--tone) 50%, var(--line2)); }
      .agent .ti { color: var(--agent); }
    `,
  ];

  @state() private toasts: Toast[] = [];
  private next = 0;

  show(kind: ToastKind, title: string, sub = ''): void {
    const t: Toast = { id: this.next++, kind, title, sub, out: false };
    this.toasts = [...this.toasts, t].slice(-MAX);
    setTimeout(() => {
      this.toasts = this.toasts.map((x) => (x.id === t.id ? { ...x, out: true } : x));
      setTimeout(() => (this.toasts = this.toasts.filter((x) => x.id !== t.id)), 400);
    }, SHOW_MS);
  }

  override render() {
    return html`<div aria-live="polite" style="display:contents">
      ${repeat(
        this.toasts,
        (t) => t.id,
        (t) => html`<div class="toast ${t.kind === 'agent' ? 'agent' : ''} ${t.out ? 'out' : ''}" data-tone=${t.kind === 'agent' ? nothing : t.kind}>
          <span class="ti" aria-hidden="true">${ICON[t.kind]}</span>
          <div><b>${t.title}</b>${t.sub ? html`<span class="sub">${t.sub}</span>` : nothing}</div>
        </div>`,
      )}
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-toasts': CaToasts;
  }
}
