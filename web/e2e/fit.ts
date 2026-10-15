// What overflows sideways under a root: every box, through the shadow roots,
// whose content is wider than the box (beyond 1px). A box that is meant to
// scroll sideways says so (`data-scroll="x"`); what is inside it is its own.
// A box that clips its text with an ellipsis, and a screen-reader text (1px
// wide), clip on purpose. Only the innermost box of a chain is named: an
// ancestor that overflows because of it is not.
import type { Page } from '@playwright/test';

/** The boxes that overflow under each element `selector` matches, as `overflow-x clientWidth<scrollWidth path`. */
export function overflows(page: Page, selector: string): Promise<string[]> {
  return page.evaluate((selector) => {
    const parent = (e: Element): Element | null => e.parentElement ?? ((e.getRootNode() as ShadowRoot).host || null);
    const name = (e: Element) => {
      const cls = typeof e.className === 'string' && e.className.trim() ? `.${e.className.trim().split(/\s+/).slice(0, 2).join('.')}` : '';
      return `${e.localName}${e.id ? `#${e.id}` : ''}${cls}`;
    };
    const path = (e: Element) => {
      const parts: string[] = [];
      for (let n: Element | null = e; n && parts.length < 7; n = parent(n)) parts.unshift(name(n));
      return parts.join(' > ');
    };
    const found: [Element, string][] = [];
    const visit = (e: Element): void => {
      const cs = getComputedStyle(e);
      if (cs.display === 'none') return;
      const scrolls = e.getAttribute('data-scroll') === 'x';
      const clipped = cs.overflowX === 'hidden' || cs.overflowX === 'clip';
      // Text for a screen reader only: a 1px box that clips all it holds.
      const screenReader = clipped && e.clientWidth <= 1 && e.clientHeight <= 1;
      if (!scrolls && !screenReader && cs.display !== 'inline' && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1) {
        if (!(clipped && cs.textOverflow === 'ellipsis')) found.push([e, `${cs.overflowX} ${e.clientWidth}<${e.scrollWidth} ${path(e)}`]);
      }
      if (scrolls || screenReader) return;
      if (e.shadowRoot) for (const c of e.shadowRoot.children) visit(c);
      for (const c of e.children) visit(c);
    };
    for (const root of document.querySelectorAll(selector)) visit(root);
    const above = new Set<Element>();
    for (const [e] of found) for (let n = parent(e); n; n = parent(n)) above.add(n);
    return found.filter(([e]) => !above.has(e)).map(([, s]) => s);
  }, selector);
}

/** Two frames, so the layout, the resize observers and what they set have settled. */
export const settle = (page: Page): Promise<void> =>
  page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(done, 150)))));
