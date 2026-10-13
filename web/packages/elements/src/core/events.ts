// The events the generic elements send. Each bubbles and crosses shadow roots
// (`composed`), so a host listens on any ancestor. An element states what the
// reader did; its host decides what happens.

/** A control's value changed (a segmented control). */
export interface ChangeDetail {
  value: string;
}

/** An item, by its id (a row's key). */
export interface ItemDetail {
  id: string;
}

/** The item chosen as the selection; null when the selection was cleared. */
export interface SelectDetail {
  id: string | null;
}

/** A column to order the items by, and the direction. */
export interface SortDetail {
  id: string;
  direction: 'asc' | 'desc';
}

/** A section of a list of sections (a transcript's), by its 0-based index; null: the latest. */
export interface SectionDetail {
  index: number | null;
}

/** Every `cae-*` event and its detail. */
export interface CaeEventMap {
  'cae-change': ChangeDetail;
  /** The item's primary action (a click or Enter on an item that has one). */
  'cae-activate': ItemDetail;
  'cae-select': SelectDetail;
  'cae-sort': SortDetail;
  /** The reader picked a section (null: follow the latest). */
  'cae-section-change': SectionDetail;
  /** The section on screen changed (-1: none). */
  'cae-section-shown': { index: number };
  /** The reader asked for the content before what is loaded. */
  'cae-load-earlier': Record<string, never>;
}

declare global {
  interface HTMLElementEventMap {
    'cae-change': CustomEvent<ChangeDetail>;
    'cae-activate': CustomEvent<ItemDetail>;
    'cae-select': CustomEvent<SelectDetail>;
    'cae-sort': CustomEvent<SortDetail>;
    'cae-section-change': CustomEvent<SectionDetail>;
    'cae-section-shown': CustomEvent<{ index: number }>;
    'cae-load-earlier': CustomEvent<Record<string, never>>;
  }
}

/** Sends a `cae-*` event from `el`: bubbling and composed. */
export function emit<K extends keyof CaeEventMap>(el: EventTarget, name: K, detail: CaeEventMap[K]): boolean {
  return el.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}
