// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { ancestorsOf, CaeTree, visibleRows, type TreeItem } from './tree.js';

defineElement('cae-tree', CaeTree);

const ITEMS: TreeItem[] = [
  {
    id: 'src',
    name: 'src',
    children: [
      { id: 'src/a.py', name: 'a.py' },
      { id: 'src/lib', name: 'lib', open: false, children: [{ id: 'src/lib/b.py', name: 'b.py', badge: 'failed', tone: 'failed' }] },
    ],
  },
  { id: 'readme', name: 'README.md' },
];

async function mount(selected: string | null = null) {
  const el = document.createElement('cae-tree');
  Object.assign(el, { items: ITEMS, selected, label: 'Files' });
  const events: string[] = [];
  el.addEventListener('cae-select', (e) => events.push(`select ${e.detail.id}`));
  el.addEventListener('cae-toggle', (e) => events.push(`toggle ${e.detail.id} ${e.detail.open}`));
  document.body.append(el);
  await el.updateComplete;
  const rows = () => [...el.shadowRoot!.querySelectorAll<HTMLElement>('[role=treeitem]')];
  const ids = () => rows().map((r) => r.dataset['id']);
  const focused = () => (el.shadowRoot!.activeElement as HTMLElement | null)?.dataset['id'];
  const key = async (k: string) => {
    (el.shadowRoot!.activeElement ?? rows().find((r) => r.tabIndex === 0))!.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, composed: true }));
    await el.updateComplete;
    await el.updateComplete;
  };
  return { el, events, rows, ids, focused, key };
}

describe('the rows of a tree', () => {
  it('are the items whose ancestors are open, each with its depth and place', () => {
    const rows = visibleRows(ITEMS, (t) => t.open ?? true);
    expect(rows.map((r) => [r.item.id, r.level, r.index + 1, r.siblings])).toEqual([
      ['src', 1, 1, 2],
      ['src/a.py', 2, 1, 2],
      ['src/lib', 2, 2, 2],
      ['readme', 1, 2, 2],
    ]);
    expect(ancestorsOf(ITEMS, 'src/lib/b.py')).toEqual(['src', 'src/lib']);
    expect(ancestorsOf(ITEMS, 'nope')).toBeNull();
  });
});

describe('cae-tree', () => {
  it('is a tree of one tab stop, its items named with their level, place and state', async () => {
    const { el, rows } = await mount('src/a.py');
    expect(el.shadowRoot!.querySelector('[role=tree]')?.getAttribute('aria-label')).toBe('Files');
    const [src, a, lib] = rows();
    expect([src!.getAttribute('aria-expanded'), lib!.getAttribute('aria-expanded'), a!.getAttribute('aria-expanded')]).toEqual(['true', 'false', null]);
    expect([a!.getAttribute('aria-level'), a!.getAttribute('aria-selected'), src!.getAttribute('aria-selected')]).toEqual(['2', 'true', null]);
    expect(rows().filter((r) => r.tabIndex === 0).map((r) => r.dataset['id'])).toEqual(['src/a.py']); // the selected item holds the tab stop
    el.remove();
  });

  it('moves with the arrow keys, opens and closes with Right and Left, and selects with Enter', async () => {
    const { el, events, ids, focused, key, rows } = await mount();
    rows()[0]!.focus();
    await key('ArrowDown');
    expect(focused()).toBe('src/a.py');
    await key('ArrowDown');
    await key('ArrowRight'); // opens lib
    expect(ids()).toContain('src/lib/b.py');
    await key('ArrowRight'); // to its first child
    expect(focused()).toBe('src/lib/b.py');
    await key('Enter');
    await key('ArrowLeft'); // a file: to its parent
    expect(focused()).toBe('src/lib');
    await key('ArrowLeft'); // closes lib
    expect(ids()).not.toContain('src/lib/b.py');
    await key('End');
    expect(focused()).toBe('readme');
    await key('Home');
    expect(focused()).toBe('src');
    await key('r'); // the next item of that initial
    expect(focused()).toBe('readme');
    await key('Home');
    await key(' '); // an item with children that is not selectable: opens and closes
    expect(ids()).toEqual(['src', 'readme']);
    expect(events).toEqual(['toggle src/lib true', 'select src/lib/b.py', 'toggle src/lib false', 'toggle src false']);
    el.remove();
  });

  it('opens the ancestors of the selected item, and a click on a toggle only opens or closes', async () => {
    const { el, events, ids, rows } = await mount('src/lib/b.py');
    expect(ids()).toContain('src/lib/b.py');
    rows()[0]!.querySelector<HTMLElement>('.twist')!.click();
    await el.updateComplete;
    expect(ids()).toEqual(['src', 'readme']);
    rows()[1]!.click();
    expect(events).toEqual(['toggle src false', 'select readme']);
    el.remove();
  });

  it('says so with no items', async () => {
    const el = document.createElement('cae-tree');
    el.strings = { empty: 'Nothing' };
    document.body.append(el);
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('[part=empty]')?.textContent).toBe('Nothing');
    el.remove();
  });
});
