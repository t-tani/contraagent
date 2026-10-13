// The events the generic elements send. Each bubbles and crosses shadow roots
// (`composed`), so a host listens on any ancestor. An element states what the
// reader did; its host decides what happens.

/** A control's value changed (a segmented control). */
export interface ChangeDetail {
  value: string;
}

/** Every `cae-*` event and its detail. */
export interface CaeEventMap {
  'cae-change': ChangeDetail;
}

declare global {
  interface HTMLElementEventMap {
    'cae-change': CustomEvent<ChangeDetail>;
  }
}

/** Sends a `cae-*` event from `el`: bubbling and composed. */
export function emit<K extends keyof CaeEventMap>(el: EventTarget, name: K, detail: CaeEventMap[K]): boolean {
  return el.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}
