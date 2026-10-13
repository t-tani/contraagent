// Single-key shortcuts for an element: the keys pressed anywhere in the page,
// except while the reader types in a field or holds a modifier.
import type { ReactiveController, ReactiveControllerHost } from 'lit';

/** Calls `onKey` for each key the reader presses in the page while the host is connected, except in a text field or with Ctrl, Alt or Meta. */
export class ShortcutsController implements ReactiveController {
  private readonly listener = (e: KeyboardEvent): void => {
    const t = e.composedPath()[0];
    if ((t instanceof HTMLElement && t.matches('input, select, textarea')) || e.metaKey || e.ctrlKey || e.altKey) return;
    this.onKey(e);
  };

  constructor(
    host: ReactiveControllerHost,
    private readonly onKey: (e: KeyboardEvent) => void,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    document.addEventListener('keydown', this.listener);
  }

  hostDisconnected(): void {
    document.removeEventListener('keydown', this.listener);
  }
}
