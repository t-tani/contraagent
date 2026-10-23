// @vitest-environment happy-dom
// The element over a plan: the generic graph draws the layer, the card's content and
// the breadcrumb are the element's own, and a click or a key sends its event.
import type { Plan } from '@contraagent/api';
import type { CaeLayeredGraph, CaeMarkMatrix } from '@contraagent/elements';
import { afterEach, describe, expect, it } from 'vitest';
import { AT, LOOP, RUN, reviewRun, staticDemo } from '../../adapters/graph/plans.fixture.js';
import type { CaPipelineGraph } from './ca-pipeline-graph.js';
import './ca-pipeline-graph.js';

interface Drawn {
  el: CaPipelineGraph;
  /** The element's own shadow root (the breadcrumb, the card's content), and the generic graph's. */
  root: ShadowRoot;
  g: ShadowRoot;
  sent: CustomEvent<unknown>[];
}

async function settle(el: CaPipelineGraph): Promise<ShadowRoot> {
  await el.updateComplete;
  const inner = el.shadowRoot!.querySelector<CaeLayeredGraph>('cae-layered-graph')!;
  await inner.updateComplete;
  return inner.shadowRoot!;
}

async function graph(plan: Plan, props: Partial<Pick<CaPipelineGraph, 'layer' | 'sel' | 'live' | 'controls'>> = {}): Promise<Drawn> {
  const el = document.createElement('ca-pipeline-graph');
  Object.assign(el, { plan, ...props });
  const sent: CustomEvent<unknown>[] = [];
  for (const name of ['ca-navigate', 'ca-open-task']) el.addEventListener(name, (e) => sent.push(e as CustomEvent<unknown>));
  document.body.append(el);
  const g = await settle(el);
  return { el, root: el.shadowRoot!, g, sent };
}

afterEach(() => document.body.replaceChildren());

describe('ca-pipeline-graph', () => {
  it('draws a node per kind, with a mark per unit', async () => {
    const { g } = await graph(staticDemo());
    const names = [...g.querySelectorAll('.node .name')].map((n) => n.textContent?.trim());
    expect(names.sort()).toEqual(['prepare', 'report', 'review', 'summarize', 'write_note']);
    const prepare = g.querySelector('.node[data-id="kind:prepare"]')!;
    expect(prepare.querySelectorAll('.mark')).toHaveLength(6);
    expect(prepare.querySelector('.count')?.textContent).toBe('5/6');
    expect(prepare.querySelector('.ex .err')?.textContent).toBe('1 failed');
    // One tab stop per node's marks; a failed mark is drawn in the failed tone, a square.
    expect(prepare.querySelectorAll('.mark[tabindex="0"]')).toHaveLength(1);
    expect(prepare.querySelector('.mark[title*="zeta"]')?.getAttribute('data-tone')).toBe('failed');
    expect(prepare.querySelector('.mark[title*="zeta"]')?.getAttribute('data-shape')).toBe('square');
  });

  it('shows the forecast on its kind nodes and above the graph, and the tasks no flow awaited', async () => {
    const plan = staticDemo();
    const report = plan.nodes.find((n) => n.kind === 'report')!;
    plan.flow_calls = [
      { id: '0', parent: null, function: 'flows.docs', flow: [], state: 'returned', error: null, unawaited: [report.key] },
    ] as Plan['flow_calls'];
    const entry = (group: string, remaining: number, flow: string[] = []) => ({
      kind: group, group, flow, passes: [], expected: remaining + 1, created: 1, remaining, wall_s: 10 * remaining, cost_usd: null,
    });
    const forecast = {
      flow: 'flows.docs', earlier_run: 'docs-1', earlier_finished_at: '2026-10-11T00:00:00+00:00',
      entries: [entry('review', 2), entry('publish', 1)], remaining: 3, wall_s: 30, cost_usd: null,
    };
    const el = document.createElement('ca-pipeline-graph');
    Object.assign(el, { plan, forecast });
    document.body.append(el);
    const g = await settle(el);
    const review = g.querySelector('.node[data-id="kind:review"]')!;
    expect(review.querySelector('.expected')?.textContent).toBe('+2');
    expect(review.querySelector('.expected')?.getAttribute('title')).toBe('2 more tasks expected (forecast)');
    expect(review.getAttribute('aria-label')).toContain('2 more tasks expected (forecast)');
    expect(g.querySelector('.node[data-id="kind:prepare"] .expected')).toBeNull();
    const root = el.shadowRoot!;
    expect(root.querySelector('.forecast')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'Forecast: 3 more tasks | 30s of task time | Not in the plan yet: publish +1',
    );
    expect(root.querySelector('.unawaited')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('1 task not awaited report');
  });

  it('selects a node or a mark on a click, and opens a kind node’s tasks on a double click', async () => {
    const { g, sent } = await graph(staticDemo());
    (g.querySelector('.node[data-id="kind:summarize"] .name') as HTMLElement).click();
    expect(sent.map((e) => e.detail)).toEqual([{ sel: 'kind:summarize' }]);
    (g.querySelector('.node[data-id="kind:prepare"] .mark[title*="zeta"]') as HTMLElement).click();
    expect(sent[1]?.detail).toEqual({ sel: 'kind:prepare#zeta' });
    g.querySelector('.node[data-id="kind:summarize"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    expect(sent[2]?.detail).toEqual({ tab: 'tasks', kind: 'summarize' });
  });

  it('shows the selection in its card, and Escape clears it', async () => {
    const { el, root, g, sent } = await graph(staticDemo(), { sel: 'kind:prepare#zeta' });
    expect(g.querySelector('[part~="inspector"] slot[name="inspector"]')).not.toBeNull();
    expect(root.querySelector('[slot="inspector"] h4')?.textContent?.trim()).toBe('prepare · zeta');
    expect(g.querySelector('.node[data-id="kind:prepare"] .mark.sel')).not.toBeNull();
    g.querySelector('.node')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true }));
    expect(sent.map((e) => e.detail)).toEqual([{ sel: '' }]);
    void el;
  });

  it('opens a mark’s task on Enter: a task that did not start on its input', async () => {
    const { g, sent } = await graph(staticDemo());
    const mark = g.querySelector('.node[data-id="kind:summarize"] .mark[title*="zeta"]') as HTMLElement;
    mark.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, composed: true }));
    expect(sent.at(-1)?.type).toBe('ca-open-task');
    expect(sent.at(-1)?.detail).toEqual({ key: 'summarize-zeta', view: 'input' });
  });

  it('enters a loop’s passes on a double click on its box', async () => {
    const { g, sent } = await graph(reviewRun({ a: 1, b: 2 }), { layer: `${RUN}/${LOOP}` });
    g.querySelector('.cluster')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    expect(sent.at(-1)?.detail).toEqual({ layer: `${RUN}/${LOOP}/loop:${AT}`, unit: '' });
  });

  it('shows the layer as a table, and a loop’s passes as a matrix', async () => {
    const plan = reviewRun({ a: 1, b: 2 });
    const { el, g } = await graph(plan, { layer: `${RUN}/${LOOP}` });
    expect(g.querySelector('.cluster')).not.toBeNull();
    g.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'table' } }));
    await settle(el);
    expect([...g.querySelectorAll('table.list tbody .name')].map((n) => n.textContent)).toEqual(['summarize', 'check', 'fix', 'score', 'check']);
    el.layer = `${RUN}/${LOOP}/loop:${AT}`;
    await settle(el);
    const mx = g.querySelector<CaeMarkMatrix>('cae-mark-matrix')!;
    await mx.updateComplete;
    const m = mx.shadowRoot!;
    expect([...m.querySelectorAll('table.matrix tbody th')].map((n) => n.textContent)).toEqual(['a', 'b']);
    expect([...m.querySelectorAll('table.matrix thead th.group')].map((n) => n.textContent)).toEqual(['Pass 1', 'Pass 2']);
  });

  it('keeps the generic graph, and the focus in it, when the outline appears or moves', async () => {
    const { el, root } = await graph(staticDemo());
    // A narrow frame (`wide`, from the element's size reports).
    const sized = el as unknown as { wide: boolean };
    sized.wide = false;
    await settle(el);
    const inner = root.querySelector('cae-layered-graph');
    expect(root.querySelector('nav.outline')).toBeNull();
    // A plan that gains a function: the outline appears above the graph.
    el.plan = reviewRun({ a: 1, b: 2 });
    let g = await settle(el);
    expect(root.querySelector('details.odet nav.outline')).not.toBeNull();
    expect(root.querySelector('cae-layered-graph')).toBe(inner);
    const name = g.querySelector<HTMLElement>('.cluster > .hd .name, .node .name')!;
    name.focus();
    // The frame becomes wide and narrow again: the outline moves beside the graph and back.
    for (const wide of [true, false]) {
      sized.wide = wide;
      g = await settle(el);
      expect(root.querySelector(wide ? '.whole.side > nav.outline' : 'details.odet nav.outline')).not.toBeNull();
      expect(root.querySelector('cae-layered-graph')).toBe(inner);
      expect(g.activeElement).toBe(name);
    }
  });

  it('draws no outline, open controls, zoom buttons or view switch without controls', async () => {
    const { el, root, g } = await graph(reviewRun({ a: 1, b: 2 }), { controls: false });
    for (const wide of [false, true]) {
      (el as unknown as { wide: boolean }).wide = wide;
      await settle(el);
      expect(root.querySelector('nav.outline')).toBeNull();
    }
    expect(root.querySelector('.opens')).toBeNull();
    expect(g.querySelector('.foot .tools')).toBeNull();
  });

  it('sets the view route right, after the update, for a layer the run does not have', async () => {
    const { root, sent } = await graph(staticDemo(), { layer: 'flows.gone' });
    await Promise.resolve();
    expect(sent.map((e) => e.detail)).toEqual([{ layer: '', unit: '', sel: '', replace: true }]);
    expect(root.querySelector('.missing')?.textContent).toContain('flows.gone');
  });
});
