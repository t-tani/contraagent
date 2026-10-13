// @vitest-environment happy-dom
// The tasks list: one row per task of the plan, a task that never ran included.
import type { JournalRow, Plan, PlanNode, Stop } from '@contraagent/api';
import { deriveRun } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import './ca-task-table.js';
import type { CaTaskTable } from './ca-task-table.js';

const node = (key: string, state: PlanNode['state'], after: string[] = [], extra: Partial<PlanNode> = {}): PlanNode => ({
  key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', after, state, level: 0, group: key.split('-')[0]!, ...extra,
});
const row = (key: string, stop: Stop, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', wall_s: 1.5, ...extra,
});

const at = (pass: number) => [{ function: 'f', file: 'f.py', line: 1, loops: [{ line: 3, pass }] }];
// prepare-z failed, so summarize-z never ran; review-g ran twice (two passes); write-a waits.
const plan: Plan = {
  nodes: [
    node('prepare-z', 'failed'),
    node('summarize-z', 'blocked', ['prepare-z']),
    node('review-g', 'done', [], { flow: at(1) }),
    { ...node('review-g~2', 'done', ['review-g'], { flow: at(2) }), unit: 'g' },
    node('write-a', 'pending', ['review-g~2']),
  ],
  groups: [],
};
const journal = [row('prepare-z', 'error'), row('review-g', 'completed'), { ...row('review-g~2', 'completed'), unit: 'g' }];

async function table(props: Partial<CaTaskTable>): Promise<{ el: CaTaskTable; rows: HTMLElement[] }> {
  const el = document.createElement('ca-task-table');
  Object.assign(el, { run: 'r', journal, plan, ...props });
  document.body.append(el);
  await el.updateComplete;
  const inner = el.shadowRoot!.querySelector('cae-data-table')!;
  await inner.updateComplete;
  const rows = [...inner.shadowRoot!.querySelectorAll<HTMLElement>('tbody tr')];
  return { el, rows };
}

/** A row by its task's key. */
const byKey = (rows: HTMLElement[], key: string) => rows.find((r) => r.dataset['key'] === key)!;

const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('ca-task-table', () => {
  it('lists every task of the plan, as many as the run counts', async () => {
    const { rows, el } = await table({});
    expect(rows).toHaveLength(deriveRun(journal, plan).counts.total);
    expect(rows).toHaveLength(5);
    el.remove();
  });

  it('a task that never ran: no attempts, "none" for its values, its status and cause in words', async () => {
    const { rows, el } = await table({ live: false });
    const z = byKey(rows, 'summarize-z');
    const cells = [...z.children].map(text);
    expect(cells.slice(1, 6)).toEqual(['0', 'none', 'none', 'none', 'none']);
    expect([text(z.querySelector('.pill')), text(z.querySelector('.cause'))]).toEqual(['not started', 'earlier task prepare · z failed']);
    const w = byKey(rows, 'write-a');
    // Waiting when the run ended: it did not run.
    expect(text(w.querySelector('.pill'))).toBe('not run');
    el.remove();
  });

  it('a waiting task of a live run names the earlier task it waits for', async () => {
    const live: Plan = { ...plan, nodes: plan.nodes.map((n) => (n.key === 'review-g~2' ? { ...n, state: 'running' } : n)) };
    const { rows, el } = await table({ live: true, plan: live });
    const w = byKey(rows, 'write-a');
    expect([text(w.querySelector('.pill')), text(w.querySelector('.cause'))]).toEqual(['waiting', 'waits for output of review · g']);
    el.remove();
  });

  it('two passes of one kind and unit are two rows, each with its pass', async () => {
    const { rows, el } = await table({ kind: 'review' });
    expect(rows.map((r) => [r.dataset['key'], text(r.querySelector('.pass'))])).toEqual([
      ['review-g', 'Pass 1'],
      ['review-g~2', 'Pass 2'],
    ]);
    el.remove();
  });

  it('a row opens its task by key, with a click or with Enter', async () => {
    const { rows, el } = await table({});
    const got: unknown[] = [];
    el.addEventListener('ca-open-task', (e) => got.push((e as CustomEvent).detail));
    byKey(rows, 'summarize-z').click();
    byKey(rows, 'write-a').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, composed: true }));
    expect(got).toEqual([{ key: 'summarize-z' }, { key: 'write-a' }]);
    el.remove();
  });

  it('a row is a table row with its task as the row header, one tab stop for all rows', async () => {
    const { rows, el } = await table({});
    expect(rows.map((r) => r.querySelector('th[scope=row]')?.getAttribute('data-col'))).toEqual(rows.map(() => 'task'));
    expect(rows.filter((r) => r.tabIndex === 0)).toHaveLength(1);
    expect(byKey(rows, 'prepare-z').dataset['executor']).toBe('agent');
    el.remove();
  });
});
