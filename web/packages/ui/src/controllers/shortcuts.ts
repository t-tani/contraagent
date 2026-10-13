// Single-key shortcuts for an element: the keys pressed in the page or inside
// the element, except while the reader types in a field or holds a modifier.
import type { ReactiveController, ReactiveControllerHost } from 'lit';

/**
 * Where an element's single-key shortcuts work: `page`, anywhere in the page
 * (an element that is the page); `element`, only while the focus is inside the
 * element (an element embedded in another page); `off`, nowhere.
 */
export type ShortcutScope = 'page' | 'element' | 'off';

export const isShortcutScope = (s: unknown): s is ShortcutScope => s === 'page' || s === 'element' || s === 'off';

/** Whether the key went to something the reader types into. */
function typing(e: KeyboardEvent): boolean {
  const t = e.composedPath()[0];
  return t instanceof HTMLElement && (t.isContentEditable || t.matches('input, select, textarea, [contenteditable]:not([contenteditable="false"])'));
}

/**
 * Calls `onKey` for each key the reader presses in the scope `scope()` names,
 * while the host is connected; never in a text field, with Ctrl, Alt or Meta,
 * or for a key another listener already handled (`defaultPrevented`).
 */
export class ShortcutsController implements ReactiveController {
  /** The target listened on now, and its scope. */
  private bound: EventTarget | null = null;
  private boundScope: ShortcutScope = 'off';

  private readonly listener = (e: Event): void => {
    const k = e as KeyboardEvent;
    if (k.defaultPrevented || typing(k) || k.metaKey || k.ctrlKey || k.altKey) return;
    this.onKey(k);
  };

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly onKey: (e: KeyboardEvent) => void,
    private readonly scope: () => ShortcutScope,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    this.bind();
  }

  hostUpdated(): void {
    if (this.scope() !== this.boundScope) this.bind();
  }

  hostDisconnected(): void {
    this.unbind();
  }

  private bind(): void {
    this.unbind();
    const scope = this.scope();
    this.boundScope = scope;
    this.bound = scope === 'page' ? document : scope === 'element' ? this.host : null;
    this.bound?.addEventListener('keydown', this.listener);
  }

  private unbind(): void {
    this.bound?.removeEventListener('keydown', this.listener);
    this.bound = null;
    this.boundScope = 'off';
  }
}
