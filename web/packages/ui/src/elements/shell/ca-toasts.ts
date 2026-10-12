import { LitElement, css, html, nothing } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { base } from '../../styles/base.js';

export type ToastKind = 'ok' | 'err' | 'warn' | 'live' | 'llm';

interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  sub: string;
  out: boolean;
}

const ICON: Record<ToastKind, string> = { ok: '✓', err: '✕', warn: '', live: '●', llm: '✦' };
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
        background: var(--panel2); border: 1px solid var(--line2); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.55);
        display: flex; gap: 10px; align-items: flex-start; animation: toast-in 0.35s var(--ease) both; }
      .toast.out { animation: toast-out 0.35s var(--ease) both; }
      .ti { font-size: 16px; line-height: 1.2; }
      b { display: block; font-size: 12.5px; }
      span.sub { font-size: 11.5px; color: var(--mut); }
      .ok { border-color: rgba(52, 211, 153, 0.45); }
      .err { border-color: rgba(248, 113, 113, 0.45); }
      .warn { border-color: rgba(251, 191, 36, 0.45); }
      .live { border-color: rgba(34, 211, 238, 0.45); }
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
        (t) => html`<div class="toast ${t.kind} ${t.out ? 'out' : ''}">
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
