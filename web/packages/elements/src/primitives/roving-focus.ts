// One tab stop for a group of items: the arrow keys move the focus between them
// (a roving tabindex), Tab leaves the group.
import type { ReactiveController, ReactiveControllerHost } from 'lit';

export interface RovingFocusOptions {
  /** The items, in order (row by row in a grid). */
  items: () => readonly HTMLElement[];
  /** Which arrow keys move: Left and Right, Up and Down, or both (a grid). */
  layout: 'horizontal' | 'vertical' | 'grid';
  /** The number of columns of a grid. */
  columns?: () => number;
  /** From the last item to the first and back (not in a grid). */
  wrap?: boolean;
  /** Called after the focus moved to `el`. */
  onMove?: (el: HTMLElement, index: number) => void;
}

/**
 * Where a key moves the focus among `n` items from `i`, or null when it does not
 * move. A grid has `cols` columns: Left and Right move in the row, Up and Down in
 * the column, Home and End to the row's ends, with Ctrl to the first and last
 * item.
 */
export function rovingStep(
  n: number,
  i: number,
  key: string,
  o: { layout: RovingFocusOptions['layout']; cols?: number; wrap?: boolean; ctrl?: boolean },
): number | null {
  if (n <= 0) return null;
  const to = (j: number): number | null => (j === i || j < 0 || j >= n ? null : j);
  if (o.layout === 'grid') {
    const cols = Math.max(1, o.cols ?? 1);
    const row = Math.floor(i / cols) * cols;
    switch (key) {
      case 'ArrowRight':
        return (i + 1) % cols && i + 1 < n ? to(i + 1) : null;
      case 'ArrowLeft':
        return i % cols ? to(i - 1) : null;
      case 'ArrowDown':
        return to(i + cols);
      case 'ArrowUp':
        return to(i - cols);
      case 'Home':
        return to(o.ctrl ? 0 : row);
      case 'End':
        return to(o.ctrl ? n - 1 : Math.min(row + cols, n) - 1);
      default:
        return null;
    }
  }
  const [prev, next] = o.layout === 'horizontal' ? ['ArrowLeft', 'ArrowRight'] : ['ArrowUp', 'ArrowDown'];
  const step = (s: number): number | null => (o.wrap ? to((i + s + n) % n) : to(i + s));
  switch (key) {
    case next:
      return step(1);
    case prev:
      return step(-1);
    case 'Home':
      return to(0);
    case 'End':
      return to(n - 1);
    default:
      return null;
  }
}

/**
 * A roving tabindex over the host's items: the current item has `tabindex=0`, the
 * others -1, and the keys of `rovingStep` move the focus. `current` follows a
 * click or a focus too.
 */
export class RovingFocusController implements ReactiveController {
  /** The index of the item that holds the tab stop. */
  current = 0;

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly o: RovingFocusOptions,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    this.host.addEventListener('keydown', this.onKey);
    this.host.addEventListener('focusin', this.onFocus);
  }

  hostDisconnected(): void {
    this.host.removeEventListener('keydown', this.onKey);
    this.host.removeEventListener('focusin', this.onFocus);
  }

  hostUpdated(): void {
    this.sync();
  }

  /** Gives the tab stop to item `i`, without moving the focus. */
  set(i: number): void {
    this.current = i;
    this.sync();
  }

  private sync(): void {
    const items = this.o.items();
    if (!items.length) return;
    this.current = Math.min(Math.max(0, this.current), items.length - 1);
    items.forEach((el, j) => (el.tabIndex = j === this.current ? 0 : -1));
  }

  private indexOf(e: Event): number {
    const items = this.o.items();
    return items.findIndex((el) => e.composedPath().includes(el));
  }

  private readonly onFocus = (e: FocusEvent): void => {
    const i = this.indexOf(e);
    if (i >= 0 && i !== this.current) this.set(i);
  };

  private readonly onKey = (e: KeyboardEvent): void => {
    const items = this.o.items();
    const i = this.indexOf(e);
    if (i < 0) return;
    const j = rovingStep(items.length, i, e.key, {
      layout: this.o.layout,
      cols: this.o.columns?.(),
      wrap: this.o.wrap,
      ctrl: e.ctrlKey || e.metaKey,
    });
    const el = j === null ? undefined : items[j];
    if (j === null || !el) return;
    e.preventDefault();
    this.set(j);
    el.focus();
    this.o.onMove?.(el, j);
  };
}
