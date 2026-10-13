// @vitest-environment happy-dom
// The generic graph over hand-written data: it arranges and draws the nodes,
// selects and sends events, and shows the host's card in its slot.
import { afterEach, describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeMarkMatrix } from '../matrix/mark-matrix.js';
import { CaeSegmented } from '../primitives/segmented.js';
import type { StateStyles } from '../primitives/states.js';
import { arrange } from './arrange.js';
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

/** After the host's content changed: the element has seen it and drawn again. */
async function settled(el: CaeLayeredGraph) {
  await new Promise((r) => setTimeout(r));
  await el.updateComplete;
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

  it('shows the host’s card for the selection, and Escape clears it', async () => {
    const { el, root, sent } = await drawn({ selected: 'b' });
    expect(root.querySelector('[part~="inspector"]')).toBeNull();
    const card = document.createElement('h4');
    card.slot = 'inspector';
    card.textContent = 'node b';
    el.append(card);
    await settled(el);
    expect(root.querySelector('[part~="inspector"] slot[name="inspector"]')).not.toBeNull();
    el.showInspector = false;
    await el.updateComplete;
    expect(root.querySelector('[part~="inspector"]')).toBeNull();
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(sent.at(-1)?.detail).toEqual({ id: null });
  });

  it('keeps the room of the key hints, or draws none', async () => {
    const { el, root } = await drawn();
    expect(root.querySelector('[part~="keys"]')).not.toBeNull();
    el.showKeys = false;
    await el.updateComplete;
    expect(root.querySelector('[part~="keys"]')).toBeNull();
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
    expect(root.querySelector('.node[data-id="q"] .count')).toBeNull();
  });

  it('switches to the node table', async () => {
    const { el, root, sent } = await drawn();
    root.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'table' } }));
    await el.updateComplete;
    expect(sent.at(-1)?.detail).toEqual({ view: 'table' });
    expect([...root.querySelectorAll('table.list tbody tr')].map((r) => r.getAttribute('data-id'))).toEqual(['a', 'b', 'd']);
  });
});
