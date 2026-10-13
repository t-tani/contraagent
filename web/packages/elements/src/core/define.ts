// Registration. The element classes are plain classes: a `define/` module (or
// the host, under a tag name of its own) registers them.

/** Registers `cls` as `tag`, unless the tag is already registered. */
export function defineElement(tag: string, cls: CustomElementConstructor): void {
  if (!customElements.get(tag)) customElements.define(tag, cls);
}
