// What does not fit under a root, through the shadow roots.
//
// Sideways (`overflows`): every box whose content is wider than the box (beyond
// 1px). A box that is meant to scroll sideways says so (`data-scroll="x"`); what
// is inside it is its own.
//
// Downwards (`clips`): a root (a demo's frame) whose content is taller than it,
// unless it is meant to scroll (`data-scroll="y"`), and every box under it that
// clips what is taller than it (`overflow-y` hidden or clip): a box that
// scrolls shows the rest when scrolled, one that clips never does.
//
// Either way, a box that clips its text with an ellipsis, and a screen-reader
// text (1px wide), clip on purpose; and only the innermost box of a chain is
// named: an ancestor that overflows because of it is not.
import type { Page } from '@playwright/test';

/** The boxes that overflow sideways under each element `selector` matches, as `overflow-x clientWidth<scrollWidth path`. */
export function overflows(page: Page, selector: string): Promise<string[]> {
  return find(page, selector, 'x');
}

/** The roots `selector` matches that are shorter than their content, and the boxes under them that clip it, as `overflow-y clientHeight<scrollHeight path`. */
export function clips(page: Page, selector: string): Promise<string[]> {
  return find(page, selector, 'y');
}

function find(page: Page, selector: string, axis: 'x' | 'y'): Promise<string[]> {
  return page.evaluate(
    ([selector, axis]) => {
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
      const x = axis === 'x';
      const size = (e: Element): [number, number] => (x ? [e.clientWidth, e.scrollWidth] : [e.clientHeight, e.scrollHeight]);
      const found: [Element, string][] = [];
      const visit = (e: Element, root: boolean): void => {
        const cs = getComputedStyle(e);
        if (cs.display === 'none') return;
        const overflow = x ? cs.overflowX : cs.overflowY;
        const scrolls = e.getAttribute('data-scroll') === axis;
        const clipped = cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.overflowY === 'hidden' || cs.overflowY === 'clip';
        // Text for a screen reader only: a 1px box that clips all it holds.
        const screenReader = clipped && e.clientWidth <= 1 && e.clientHeight <= 1;
        const [client, content] = size(e);
        // Sideways, any box; downwards, a root, and a box that clips.
        const counts = x || root || overflow === 'hidden' || overflow === 'clip';
        if (counts && !scrolls && !screenReader && cs.display !== 'inline' && client > 0 && content > client + 1) {
          if (!(clipped && cs.textOverflow === 'ellipsis')) found.push([e, `${overflow} ${client}<${content} ${path(e)}`]);
        }
        // What is inside a box that scrolls sideways is its own; a box that scrolls downwards may still hold one that clips.
        if ((scrolls && x) || screenReader) return;
        if (e.shadowRoot) for (const c of e.shadowRoot.children) visit(c, false);
        for (const c of e.children) visit(c, false);
      };
      for (const root of document.querySelectorAll(selector)) visit(root, true);
      const above = new Set<Element>();
      for (const [e] of found) for (let n = parent(e); n; n = parent(n)) above.add(n);
      return found.filter(([e]) => !above.has(e)).map(([, s]) => s);
    },
    [selector, axis] as const,
  );
}

/** Two frames, so the layout, the resize observers and what they set have settled. */
export const settle = (page: Page): Promise<void> =>
  page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(done, 150)))));
