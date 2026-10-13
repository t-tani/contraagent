// @vitest-environment happy-dom
// The element over a plan: its views render into one shadow root, and a click or a key sends its event.
import type { Plan } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import type { CaPipelineGraph } from './ca-pipeline-graph.js';
import './ca-pipeline-graph.js';
import { AT, LOOP, RUN, reviewRun, staticDemo } from './graph/plans.fixture.js';

async function graph(plan: Plan, props: Partial<Pick<CaPipelineGraph, 'layer' | 'sel' | 'live'>> = {}): Promise<{ el: CaPipelineGraph; root: ShadowRoot; sent: CustomEvent<unknown>[] }> {
  const el = document.createElement('ca-pipeline-graph');
  Object.assign(el, { plan, ...props });
  const sent: CustomEvent<unknown>[] = [];
  for (const name of ['ca-navigate', 'ca-open-task']) el.addEventListener(name, (e) => sent.push(e as CustomEvent<unknown>));
  document.body.append(el);
  await el.updateComplete;
  return { el, root: el.shadowRoot!, sent };
}

afterEach(() => document.body.replaceChildren());

describe('ca-pipeline-graph', () => {
  it('draws a node per kind, with a mark per unit', async () => {
    const { root } = await graph(staticDemo());
    const names = [...root.querySelectorAll('.node .name')].map((n) => n.textContent?.trim());
    expect(names.sort()).toEqual(['prepare', 'report', 'review', 'summarize', 'write_note']);
    const prepare = root.querySelector('.node[data-id="kind:prepare"]')!;
    expect(prepare.querySelectorAll('.mark')).toHaveLength(6);
    expect(prepare.querySelector('.count')?.textContent).toBe('5/6');
    expect(prepare.querySelector('.ex .err')?.textContent).toBe('1 failed');
    // One tab stop per node's marks.
    expect(prepare.querySelectorAll('.mark[tabindex="0"]')).toHaveLength(1);
  });

  it('selects a node or a mark on a click, and opens a kind node’s tasks on a double click', async () => {
    const { root, sent } = await graph(staticDemo());
    (root.querySelector('.node[data-id="kind:summarize"] .name') as HTMLElement).click();
    expect(sent.map((e) => e.detail)).toEqual([{ sel: 'kind:summarize' }]);
    (root.querySelector('.node[data-id="kind:prepare"] .mark[title*="zeta"]') as HTMLElement).click();
    expect(sent[1]?.detail).toEqual({ sel: 'kind:prepare#zeta' });
    root.querySelector('.node[data-id="kind:summarize"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
    expect(sent[2]?.detail).toEqual({ tab: 'tasks', kind: 'summarize' });
  });

  it('shows the selection in its card, and Escape clears it', async () => {
    const { el, root, sent } = await graph(staticDemo(), { sel: 'kind:prepare#zeta' });
    expect(root.querySelector('.insp h4')?.textContent?.trim()).toBe('prepare · zeta');
    expect(root.querySelector('.node[data-id="kind:prepare"] .mark.sel')).not.toBeNull();
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(sent.map((e) => e.detail)).toEqual([{ sel: '' }]);
  });

  it('opens a mark’s task on Enter: a task that did not start on its input', async () => {
    const { root, sent } = await graph(staticDemo());
    const mark = root.querySelector('.node[data-id="kind:summarize"] .mark[title*="zeta"]') as HTMLElement;
    mark.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(sent.at(-1)?.type).toBe('ca-open-task');
    expect(sent.at(-1)?.detail).toEqual({ key: 'summarize-zeta', view: 'input' });
  });

  it('shows the layer as a table, and a loop’s passes as a matrix', async () => {
    const plan = reviewRun({ a: 1, b: 2 });
    const { el, root } = await graph(plan, { layer: `${RUN}/${LOOP}` });
    expect(root.querySelector('.box')).not.toBeNull();
    root.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'table' } }));
    await el.updateComplete;
    expect([...root.querySelectorAll('table.list tbody .name')].map((n) => n.textContent)).toEqual(['summarize', 'check', 'fix', 'score', 'check']);
    el.layer = `${RUN}/${LOOP}/loop:${AT}`;
    await el.updateComplete;
    expect([...root.querySelectorAll('table.matrix tbody th')].map((n) => n.textContent)).toEqual(['a', 'b']);
    expect([...root.querySelectorAll('table.matrix thead th.pass')].map((n) => n.textContent)).toEqual(['Pass 1', 'Pass 2']);
  });

  it('sets the route right, after the update, for a layer the run does not have', async () => {
    const { root, sent } = await graph(staticDemo(), { layer: 'flows.gone' });
    await Promise.resolve();
    expect(sent.map((e) => e.detail)).toEqual([{ layer: '', unit: '', sel: '', replace: true }]);
    expect(root.querySelector('.missing')?.textContent).toContain('flows.gone');
  });
});
