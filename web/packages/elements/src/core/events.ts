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

/** A named action of an item (a tile's link): the item's id and the action's id. */
export interface ActionDetail {
  id: string;
  action: string;
}

/** Every `cae-*` event and its detail. */
export interface CaeEventMap {
  'cae-change': ChangeDetail;
  /** The item's primary action (a click or Enter on an item that has one). */
  'cae-activate': ItemDetail;
  'cae-select': SelectDetail;
  'cae-sort': SortDetail;
  'cae-action': ActionDetail;
}

declare global {
  interface HTMLElementEventMap {
    'cae-change': CustomEvent<ChangeDetail>;
    'cae-activate': CustomEvent<ItemDetail>;
    'cae-select': CustomEvent<SelectDetail>;
    'cae-sort': CustomEvent<SortDetail>;
    'cae-action': CustomEvent<ActionDetail>;
  }
}

/** Sends a `cae-*` event from `el`: bubbling and composed. */
export function emit<K extends keyof CaeEventMap>(el: EventTarget, name: K, detail: CaeEventMap[K]): boolean {
  return el.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}
