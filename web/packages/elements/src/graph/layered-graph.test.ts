// @vitest-environment happy-dom
// The generic graph over hand-written data: it arranges and draws the nodes,
// selects and sends events, and shows the host's card in its slot.
import { afterEach, describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeMarkMatrix } from '../matrix/mark-matrix.js';
import { CaeSegmented } from '../primitives/segmented.js';
import type { StateStyles } from '../primitives/states.js';
import { arrange, extentOf } from './arrange.js';
import { CaeLayeredGraph } from './layered-graph.js';
import type { GraphInput, GraphNodeInput } from './types.js';

const states: StateStyles = {
  ok: { label: 'ok', tone: 'done', shape: 'round', rank: 0 },
  bad: { label: 'bad', tone: 'failed', shape: 'square', rank: 1 },
};

const node = (id: string, cluster: string | null, looks: string[], drill = false): GraphNodeInput => ({
  id,
  label: id,
  cluster,
  drill,
  marks: looks.map((state, i) => ({ id: `${id}#${['x', 'y'][i]}`, state, label: `${id} ${i}` })),
  loose: [],
  counts: { ok: looks.filter((l) => l === 'ok').length, bad: looks.filter((l) => l === 'bad').length },
  progress: { done: looks.filter((l) => l === 'ok').length, total: looks.length, label: '' },
});

const graph: GraphInput = {
  series: ['x', 'y'],
  nodes: [node('a', null, ['ok', 'ok']), node('b', 'c1', ['ok', 'bad']), node('d', 'c1', ['ok', 'ok'], true)],
  clusters: [{ id: 'c1', parent: null, label: 'loop', cycle: true, drill: true }],
  edges: [
    { from: 'a', to: 'b', style: 'solid', weight: 1, ranks: true },
    { from: 'b', to: 'd', style: 'dashed', weight: 1, ranks: true },
    { from: 'd', to: 'b', style: 'solid', weight: 1, ranks: false },
  ],
  stubs: [{ id: 's', label: 'outside', to: 'a', style: 'solid', weight: 1 }],
};

async function drawn(props: Partial<CaeLayeredGraph> = {}) {
  const el = document.createElement('cae-layered-graph');
  Object.assign(el, { graph, states, key: 'g', ...props });
  const sent: CustomEvent<unknown>[] = [];
  for (const n of ['cae-select', 'cae-activate', 'cae-drill', 'cae-view-change']) el.addEventListener(n, (e) => sent.push(e as CustomEvent<unknown>));
  document.body.append(el);
  await el.updateComplete;
  return { el, root: el.shadowRoot!, sent };
}

defineElement('cae-layered-graph', CaeLayeredGraph);
defineElement('cae-mark-matrix', CaeMarkMatrix);
defineElement('cae-segmented', CaeSegmented);

afterEach(() => document.body.replaceChildren());

describe('arrange', () => {
  it('layers by the longest path, a cluster as one item, the closing edge left out', () => {
    const a = arrange(graph);
    expect(a.layers).toEqual([['a'], ['c1']]);
    expect(a.clusters).toEqual([{ id: 'c1', parent: null, cycle: true, layers: [['b'], ['d']] }]);
    expect(a.back).toEqual([false, false, true]);
    expect(a.drawn).toEqual(['a', 'b', 'd']);
    expect(arrange(graph)).toBe(a);
  });
});

describe('cae-layered-graph', () => {
  it('draws the nodes, the cluster and the stub, each mark in its state’s look', async () => {
    const { root } = await drawn();
    expect([...root.querySelectorAll('.node')].map((n) => n.getAttribute('data-id'))).toEqual(['a', 'b', 'd']);
    expect(root.querySelector('.cluster[data-cluster="c1"] .node[data-id="b"]')).not.toBeNull();
    expect(root.querySelector('.stub')?.textContent).toBe('outside');
    const bad = root.querySelector('.node[data-id="b"] .mark[aria-label="b 1"]')!;
    expect(bad.getAttribute('data-tone')).toBe('failed');
    expect(bad.getAttribute('data-shape')).toBe('square');
  });

  it('selects on a click, acts on a double click, enters an inner view', async () => {
    const { root, sent } = await drawn();
    (root.querySelector('.node[data-id="a"] .mark') as HTMLElement).click();
    root.querySelector('.node[data-id="a"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    root.querySelector('.node[data-id="d"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    root.querySelector('.cluster')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    expect(sent.map((e) => [e.type, e.detail])).toEqual([
      ['cae-select', { id: 'a#x' }],
      ['cae-activate', { id: 'a' }],
      ['cae-drill', { id: 'd' }],
      ['cae-drill', { id: 'c1' }],
    ]);
  });

  it('shows the host’s card for the selection, none with an empty slot, and Escape clears it', async () => {
    const { el, root, sent } = await drawn({ selected: 'b' });
    expect(root.querySelector('[part~="inspector"]')).toBeNull();
    const card = document.createElement('h4');
    card.slot = 'inspector';
    card.textContent = 'node b';
    el.append(card);
    el.selected = 'a';
    await el.updateComplete;
    expect(root.querySelector('[part~="inspector"] slot[name="inspector"]')).not.toBeNull();
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(sent.at(-1)?.detail).toEqual({ id: null });
  });

  it('draws the key hints as the part keys', async () => {
    const { root } = await drawn();
    expect(root.querySelector('[part~="keys"]')?.textContent).toContain('Tab: next node');
  });

  it('counts a node’s marks by state when it has no counts or progress', async () => {
    const bare: GraphInput = {
      series: [],
      nodes: [
        { id: 'p', label: 'p', cluster: null, loose: [{ id: 'p1', state: 'ok', label: 'p1' }, { id: 'p2', state: 'bad', label: 'p2' }] },
        { id: 'q', label: 'q', cluster: null },
      ],
      clusters: [],
      edges: [{ from: 'p', to: 'q', style: 'solid', weight: 1, ranks: true }],
      stubs: [],
    };
    const { root } = await drawn({ graph: bare });
    const count = root.querySelector('.node[data-id="p"] .count')!;
    expect(count.textContent).toBe('1/2');
    expect(count.getAttribute('title')).toBe('1 of 2 done');
    expect(root.querySelector('.node[data-id="q"] .count')?.textContent).toBe('0/0');
  });

  it('switches to the node table', async () => {
    const { el, root, sent } = await drawn();
    root.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'table' } }));
    await el.updateComplete;
    expect(sent.at(-1)?.detail).toEqual({ view: 'table' });
    expect([...root.querySelectorAll('table.list tbody tr')].map((r) => r.getAttribute('data-id'))).toEqual(['a', 'b', 'd']);
    // A table wider than the host scrolls across inside its frame.
    expect(root.querySelector('.tframe')?.getAttribute('data-scroll')).toBe('x');
  });

  it("draws an item's open and close control, which sends cae-toggle, and a cluster named by a path whose later parts drill", async () => {
    const open: GraphInput = {
      ...graph,
      nodes: [{ ...node('a', null, ['ok', 'ok']), toggle: 'closed' }, node('b', 'f', ['ok', 'bad']), node('d', 'f', ['ok', 'ok'])],
      clusters: [{ id: 'f', parent: null, label: 'outer › inner', cycle: false, drill: true, toggle: 'open', path: [{ id: 'f', label: 'outer' }, { id: 'f2', label: 'inner', tip: 'mod.inner' }] }],
    };
    const { el, root, sent } = await drawn({ graph: open });
    const toggles: CustomEvent<unknown>[] = [];
    el.addEventListener('cae-toggle', (e) => toggles.push(e as CustomEvent<unknown>));
    const show = root.querySelector<HTMLButtonElement>('.node[data-id="a"] .tog')!;
    expect(show.getAttribute('aria-expanded')).toBe('false');
    expect(show.getAttribute('aria-label')).toBe('Show inside: a');
    show.click();
    expect(toggles.map((e) => e.detail)).toEqual([{ id: 'a', open: true }]);
    const hide = root.querySelector<HTMLButtonElement>('.cluster[data-cluster="f"] > .cue .tog')!;
    expect(hide.getAttribute('aria-label')).toBe('Hide inside: outer › inner');
    hide.click();
    expect(toggles.at(-1)?.detail).toEqual({ id: 'f', open: false });
    // The cluster's name: its first part selects it; a later part goes into its own view.
    expect(root.querySelector('.cluster[data-cluster="f"] > .hd .name')?.textContent?.trim()).toBe('outer');
    root.querySelector<HTMLButtonElement>('.cluster[data-cluster="f"] > .hd .part')!.click();
    expect(sent.at(-1)?.type).toBe('cae-drill');
    expect(sent.at(-1)?.detail).toEqual({ id: 'f2' });
    // A toggle is no selection.
    expect(sent.filter((e) => e.type === 'cae-select')).toEqual([]);
  });
});

describe('extentOf', () => {
  it('counts a cluster as what it holds: layers along the flow, items across it', () => {
    const shape = {
      nodes: [{ id: 'a', cluster: null }, { id: 'b', cluster: 'c' }, { id: 'd', cluster: 'c' }, { id: 'e', cluster: null }, { id: 'x', cluster: null }],
      clusters: [{ id: 'c', parent: null, cycle: false }],
      edges: [
        { from: 'a', to: 'b', style: 'solid' as const, ranks: true },
        { from: 'b', to: 'd', style: 'solid' as const, ranks: true },
        { from: 'd', to: 'e', style: 'solid' as const, ranks: true },
        { from: 'a', to: 'x', style: 'solid' as const, ranks: true },
      ],
      stubs: [],
    };
    // a, then the cluster (b, d: two layers) beside x, then e.
    expect(extentOf(arrange(shape))).toEqual({ span: 4, stack: 2 });
  });
});
