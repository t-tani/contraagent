// The selection's card in the graph's frame: placed beside the selected item
// (`place-card`), joined to it for the keyboard, and the focus put back on the item.
import type { ReactiveController, ReactiveControllerHost } from 'lit';
import { PAD, placeCard, type Box } from './place-card.js';

export interface CardOptions {
  /** The card is a sheet under the frame (a narrow screen): it is not placed. */
  docked: () => boolean;
  /** The frame's height. */
  frameH: () => number;
  /** The card needs another least height of the frame (`room`): make the frame that tall. */
  grow: () => void;
  /** A pointer is down on the frame. */
  pressed: () => boolean;
}

/** The selected item as drawn, what the card keeps clear of, and the box it is shown in. */
export interface Anchor {
  item: HTMLElement;
  clear: HTMLElement;
  frame: HTMLElement;
}

/**
 * The card (`.insp`) of the selected item in the host's frame (`.main > .frame`):
 * a table row (`tr.sel > th`), a mark (`.mark.sel`, `.taskchip.sel`), a node
 * (`.node.sel`) or a loop box (`.box.sel`). It runs after every draw, pan, zoom
 * and scroll (`place`), and keeps Tab and Shift+Tab between the item and its card.
 */
export class CardController implements ReactiveController {
  /** The frame height the card needs (0 without one). */
  room = 0;
  /** Focus is being put back, not moved by the reader: it does not select. */
  quiet = false;

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly o: CardOptions,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    this.host.addEventListener('keydown', this.onTabToCard);
  }

  hostDisconnected(): void {
    this.host.removeEventListener('keydown', this.onTabToCard);
  }

  private get root(): ParentNode {
    return this.host.shadowRoot ?? this.host;
  }

  private get focused(): Element | null {
    return this.host.shadowRoot?.activeElement ?? null;
  }

  /** The card, when there is a selection. */
  card(): HTMLElement | null {
    return this.root.querySelector<HTMLElement>('.insp');
  }

  /**
   * The selected item as drawn (a mark, a node, a loop box's header), what the card keeps clear of
   * (a mark's whole node), and the box it is shown in (the frame, or a loop's passes).
   */
  anchor(): Anchor | null {
    const frame = this.root.querySelector<HTMLElement>('.main > .frame');
    const row = frame?.querySelector<HTMLElement>('tr.sel > th');
    if (frame && row) return { item: row, clear: row, frame };
    const sel = frame?.querySelector<HTMLElement>('.mark.sel, .taskchip.sel, .node.sel, .box.sel');
    if (!frame || !sel) return null;
    // A loop box: the card points at its header, where its name is, and keeps clear of the whole box when there is room.
    const item = sel.classList.contains('box') ? (sel.querySelector<HTMLElement>(':scope > .hd') ?? sel) : sel;
    return { item, clear: item.closest<HTMLElement>('.node') ?? sel, frame };
  }

  /** Put the card beside the selected item, inside the frame; hide it while the item is out of view. */
  place(): void {
    const card = this.card();
    const docked = this.o.docked();
    const room = card && !docked ? card.querySelector<HTMLElement>('.scroll')!.scrollHeight + 24 + 2 * PAD : 0;
    if (room !== this.room && (room > this.o.frameH() || this.room > 0)) {
      this.room = room;
      this.o.grow();
    }
    if (!card || docked) return;
    const a = this.anchor();
    const main = this.root.querySelector<HTMLElement>('.main');
    if (!a || !main) {
      card.classList.remove('placed');
      return;
    }
    const m = main.getBoundingClientRect();
    const rel = (r: DOMRect): Box => ({ left: r.left - m.left, top: r.top - m.top, width: r.width, height: r.height });
    const item = rel(a.item.getBoundingClientRect());
    const clear = rel(a.clear.getBoundingClientRect());
    const f = rel(a.frame.getBoundingClientRect());
    // A loop's passes and the table scroll: the item hides when scrolled out of them.
    const port = a.frame.querySelector<HTMLElement>('.mx');
    const inView = placeCard(item, port ? rel(port.getBoundingClientRect()) : f, { width: 0, height: 0 }).shown;
    const scroll = card.querySelector<HTMLElement>('.scroll');
    if (scroll) scroll.style.maxHeight = `${Math.max(120, f.height - 2 * PAD - 24)}px`;
    const size = { width: card.offsetWidth, height: card.offsetHeight };
    let p = placeCard(clear, f, size, item);
    if (!p.fits && a.clear !== a.item && !a.clear.classList.contains('node')) p = placeCard(item, f, size);
    card.classList.toggle('placed', p.shown && inView);
    card.dataset['side'] = p.side;
    card.style.left = `${p.x}px`;
    card.style.top = `${p.y}px`;
    card.style.setProperty('--arrow', `${p.arrow}px`);
  }

  /** The focusable that stands for the selected item: the mark itself, or a node's or a box's name. */
  itemFocus(): HTMLElement | null {
    const a = this.anchor();
    if (!a) return null;
    return a.item.matches('button') ? a.item : a.item.querySelector<HTMLElement>('.name');
  }

  /**
   * The selected item's focusable described by the card (`aria-describedby`), and what
   * a live region says of the item: its name and its status (the card's `h4` and
   * `[data-status]`), '' without a selection.
   */
  describe(): [name: string, status: string] {
    for (const el of this.root.querySelectorAll('[aria-describedby="insp"]')) el.removeAttribute('aria-describedby');
    this.itemFocus()?.setAttribute('aria-describedby', 'insp');
    const card = this.card();
    return [card?.querySelector('h4')?.textContent?.trim() ?? '', card?.querySelector('[data-status]')?.textContent?.trim() ?? ''];
  }

  /** Focus `el` without selecting what it is on. */
  focusQuietly(el: HTMLElement | null | undefined): void {
    this.quiet = true;
    el?.focus();
    this.quiet = false;
  }

  /** Run `f` now, or, while a pointer is down on the frame, once it is released (a scroll under a pressed pointer would move the click elsewhere). */
  whenReleased(f: () => void): void {
    if (!this.o.pressed()) return f();
    globalThis.addEventListener('pointerup', () => setTimeout(f), { once: true });
  }

  /** On a narrow screen: scroll the selected item into view when it is out of it or under the sheet. */
  revealOverSheet(): void {
    const item = this.anchor()?.item;
    if (!item) return;
    const r = item.getBoundingClientRect();
    const sheet = this.card()?.getBoundingClientRect();
    const bottom = Math.min(globalThis.innerHeight, sheet?.top ?? Infinity);
    if (r.top < 0 || r.bottom > bottom) item.scrollIntoView({ block: 'center' });
  }

  /** Shift+Tab on the card's first link comes back to the item; Escape puts the focus back on the item first. */
  readonly onCardKey = (e: KeyboardEvent): void => {
    const card = e.currentTarget as HTMLElement;
    const items = [...card.querySelectorAll<HTMLElement>('button')];
    if (e.key === 'Tab' && e.shiftKey && this.focused === items[0]) {
      const own = this.itemFocus();
      if (!own) return;
      e.preventDefault();
      this.focusQuietly(own);
    } else if (e.key === 'Escape') {
      // The card goes with the selection: the focus goes back to the item first.
      this.focusQuietly(this.itemFocus());
    }
  };

  /** Tab on the selected item goes on to its card. */
  private readonly onTabToCard = (e: KeyboardEvent): void => {
    if (e.key !== 'Tab' || e.shiftKey || e.defaultPrevented) return;
    const own = this.itemFocus();
    if (!own || this.focused !== own) return;
    const first = this.root.querySelector<HTMLElement>('.insp button');
    if (!first) return;
    e.preventDefault();
    first.focus();
  };
}
