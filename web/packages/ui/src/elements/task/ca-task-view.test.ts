// @vitest-environment happy-dom
// One task's detail: fetched for the task shown, then its header and the pane
// of the view chosen.
import type { ContractSpec, JournalRow, MonitorClient, Plan, TaskDetail } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { emptyDetail } from '../../controllers/task-detail.js';
import './ca-task-view.js';
import type { CaTaskView } from './ca-task-view.js';

const row = (key: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop: 'completed', ok: true, wall_s: 1.5, ...extra,
});
const spec = (path: string, extra: Partial<ContractSpec> = {}): ContractSpec =>
  ({
    path, schema_name: 'Review', schema_ref: '', fields: [], required: true, fresh: true, status: 'valid',
    file: { exists: true, content: { ok: true }, size: 10, mtime: null, truncated: false }, ...extra,
  }) as unknown as ContractSpec;

/** review · a: failed once, then done; reads one file and writes one. */
const review: TaskDetail = {
  ...emptyDetail('review-a'),
  rows: [row('review-a', { stop: 'error', ok: false, attempt: 0, reason: 'tool crashed' }), row('review-a', { attempt: 1 })],
  io: {
    params: { depth: 2 },
    inputs: [spec('/r/in/a.md', { schema_name: 'text' })],
    outputs: [spec('/r/out/review/a.json')],
    executor: 'agent',
    upstream: [],
    downstream: [{ key: 'write-a', kind: 'write', unit: 'a', executor: 'agent' }],
  } as unknown as TaskDetail['io'],
};
const python: TaskDetail = {
  ...emptyDetail('python:score-a'),
  rows: [row('python:score-a', { kind: 'score', unit: 'a', executor: 'python' })],
  io: { ...emptyDetail('x').io, executor: 'python' },
};

/** A client whose `task` answers from `details` after `delay` ms; the keys asked for, in order. */
function fakeClient(details: Record<string, TaskDetail>, delay: Record<string, number> = {}) {
  const asked: string[] = [];
  const client = {
    baseUrl: '',
    task: (_run: string, key: string) => {
      asked.push(key);
      const d = details[key];
      return new Promise<TaskDetail>((ok, fail) => setTimeout(() => (d ? ok(d) : fail(new Error('404'))), delay[key] ?? 0));
    },
  } as unknown as MonitorClient;
  return { client, asked };
}

const settle = (ms = 10) => new Promise((r) => setTimeout(r, ms));
const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();

async function view(props: Partial<CaTaskView>): Promise<CaTaskView> {
  const el = document.createElement('ca-task-view');
  Object.assign(el, { run: 'r', ...props });
  document.body.append(el);
  await el.updateComplete;
  await settle();
  await el.updateComplete;
  return el;
}

const root = (el: CaTaskView) => el.shadowRoot!;

describe('ca-task-view', () => {
  it('shows the names the task claims as its locks', async () => {
    const node = {
      key: 'review-a', kind: 'review', unit: 'a', claims: ['topic:a', 'topic:b'], after: [],
      executor: 'agent', flow: [], created_from: [], flow_call: '0', ts: '', state: 'done', group: 0, row: 0,
    };
    const plan = { nodes: [node], groups: [] } as unknown as Plan;
    const { client } = fakeClient({ 'review-a': review });
    const el = await view({ client, taskKey: 'review-a', plan });
    const metas = [...root(el).querySelectorAll('.taskmeta .meta')];
    const locks = metas.find((m) => text(m).startsWith('Locks'));
    expect(text(locks)).toBe('Locks topic:atopic:b');
    expect([...locks!.children].map(text)).toEqual(['topic:a', 'topic:b']);
    expect(locks!.getAttribute('title')).toBe('Names this task holds while it runs (claims)');
    el.remove();
  });

  it('loads the task and shows its header: name, verdict, a chip per attempt', async () => {
    const { client, asked } = fakeClient({ 'review-a': review });
    const el = await view({ client, taskKey: 'review-a' });
    expect(asked).toEqual(['review-a']);
    expect(text(root(el).querySelector('.tm-name'))).toBe('review · a');
    expect(text(root(el).querySelector('.verdict'))).toBe('Done on attempt 2 | 1 failed attempt | first failure: tool crashed');
    expect([...root(el).querySelectorAll('.runchip')].map((c) => c.className.replace(/\s+/g, ' ').trim())).toEqual(['runchip bad', 'runchip ok']);
    el.remove();
  });

  it("says an agent task's partial result in the words of the stop its launch ended on", async () => {
    const stopped: TaskDetail = {
      ...emptyDetail('scan-a'),
      rows: [row('scan-a', { stop: 'partial', ok: true, reason: 'timeout' })],
      io: {
        ...review.io,
        outputs: [
          spec('/r/out/scan/a.jsonl', {
            format: 'jsonl', schema_name: 'Rows[Finding]',
            fields: [{ name: 'line', type: 'integer', required: true }],
            file: { exists: true, content: [{ line: 1 }, { line: 2 }], size: 24, truncated: false },
          }),
        ],
      },
    };
    const { client } = fakeClient({ 'scan-a': stopped });
    const el = await view({ client, taskKey: 'scan-a' });
    expect(text(root(el).querySelector('.verdict'))).toBe('Partly done: timed out');
    el.view = 'output';
    await el.updateComplete;
    await settle();
    const pane = text(root(el).querySelector('.pane'));
    expect(pane).toContain('JSON Lines, one object of schema Finding per line');
    expect(pane).toContain('2 rows');
    el.remove();
  });

  it('lists the files each attempt changed, and a failed attempt\'s removed ones', async () => {
    const changed: TaskDetail = {
      ...emptyDetail('write-a'),
      rows: [
        row('write-a', { stop: 'timeout', ok: false, attempt: 0, changes: { created: ['t/a/x.md'], modified: [], deleted: [], removed: ['t/a/x.md'] } }),
        row('write-a', { attempt: 1, changes: { created: ['t/a/y.md'], modified: ['t/a/old.md'], deleted: ['t/a/gone.md'], removed: [] } }),
      ],
    };
    const { client } = fakeClient({ 'write-a': changed });
    const el = await view({ client, taskKey: 'write-a' });
    const fold = [...root(el).querySelectorAll('details.io-fold')].find((d) => text(d.querySelector('summary')) === '4 changed files');
    expect(fold).toBeDefined();
    expect(fold!.querySelector('summary')!.getAttribute('title')).toBe(
      "Files under the task's declared patterns that its attempts created, modified or deleted (changes)",
    );
    expect([...fold!.querySelectorAll('li')].map(text)).toEqual([
      'Attempt 1 | t/a/x.md | created, removed after the failed attempt',
      'Attempt 2 | t/a/y.md | created',
      'Attempt 2 | t/a/old.md | modified',
      'Attempt 2 | t/a/gone.md | deleted',
    ]);
    el.remove();
  });

  it("shows the pipeline's own columns: the latest attempt's, and each attempt's in its chip", async () => {
    const custom: TaskDetail = {
      ...emptyDetail('write-a'),
      rows: [
        row('write-a', { stop: 'timeout', ok: false, attempt: 0 }),
        row('write-a', { attempt: 1, effect: 'new', counts: { a: 1 } }),
      ],
      row_extras: ['effect', 'counts'],
    };
    const { client } = fakeClient({ 'write-a': custom });
    const el = await view({ client, taskKey: 'write-a' });
    const chips = [...root(el).querySelectorAll('.runchip')];
    expect(chips[1]!.getAttribute('title')).toContain('effect: new\ncounts: {"a":1}');
    expect(chips[0]!.getAttribute('title')).not.toContain('effect');
    expect(text(root(el).querySelector('.taskmeta'))).toContain('effect');
    expect(text(root(el).querySelector('.taskmeta'))).toContain('{"a":1}');
    expect([...root(el).querySelectorAll('details.io-fold summary')].map(text)).not.toContain('row_extras');
    el.remove();
  });

  it('switches its pane with the view: transcript, input, output, definition', async () => {
    const { client } = fakeClient({ 'review-a': review });
    const el = await view({ client, taskKey: 'review-a' });
    // The label, then the count badge.
    const tabs = () => [...root(el).querySelectorAll('.tview')].map((t) => [text(t), t.getAttribute('aria-selected')]);
    expect(tabs()).toEqual([['Transcript', 'true'], ['Input2', 'false'], ['Output1', 'false'], ['Definition', 'false']]);
    // No stream: the reason there is no transcript, in place of it.
    expect(text(root(el).querySelector('.notrans b'))).toBe('No transcript | not saved (keep_transcripts = false)');
    expect(root(el).querySelector('.pane')).toBeNull();

    el.view = 'input';
    await el.updateComplete;
    const headings = () => [...root(el).querySelectorAll('.pane h4.sect-h')].map(text);
    expect(headings()).toEqual(['Parameters', 'Input files', 'Earlier tasks', 'Prompt']);
    expect(root(el).querySelectorAll('.pane .io-card')).toHaveLength(1);

    el.view = 'output';
    await el.updateComplete;
    expect(headings()).toEqual(['Output files', 'Outcome', 'Later tasks']);
    expect(text(root(el).querySelector('.pane .down'))).toBe('write · a');

    el.view = 'definition';
    await el.updateComplete;
    expect(root(el).querySelector('.pane ca-definition')).not.toBeNull();
    el.remove();
  });

  it('sends ca-navigate for a view tab and ca-open-task for a later task', async () => {
    const { client } = fakeClient({ 'review-a': review });
    const el = await view({ client, taskKey: 'review-a', view: 'output' });
    const sent: [string, unknown][] = [];
    for (const name of ['ca-navigate', 'ca-open-task']) el.addEventListener(name, (e) => sent.push([name, (e as CustomEvent).detail]));
    root(el).querySelectorAll<HTMLButtonElement>('.tview')[1]!.click();
    root(el).querySelector<HTMLButtonElement>('.down .taskchip')!.click();
    expect(sent).toEqual([
      ['ca-navigate', { view: 'input' }],
      ['ca-open-task', { key: 'write-a' }],
    ]);
    el.remove();
  });

  it('opens a Python task on its output, with no transcript tab', async () => {
    const { client } = fakeClient({ 'python:score-a': python });
    const el = await view({ client, taskKey: 'python:score-a' });
    expect([...root(el).querySelectorAll('.tview')].map(text)).toEqual(['Input', 'Output', 'Definition']);
    expect(root(el).querySelector('.tview.sel')?.textContent?.trim()).toBe('Output');
    expect(text(root(el).querySelector('.tm-name'))).toBe('score · a');
    el.remove();
  });

  it('shows only the task asked for last, and an empty detail when the request fails', async () => {
    const { client, asked } = fakeClient({ 'review-a': review, 'python:score-a': python }, { 'review-a': 30 });
    const el = await view({ client, taskKey: 'review-a' });
    el.taskKey = 'python:score-a';
    await el.updateComplete;
    await settle(50);
    await el.updateComplete;
    expect(asked).toEqual(['review-a', 'python:score-a']);
    expect(text(root(el).querySelector('.tm-name'))).toBe('score · a');

    el.taskKey = 'gone-x';
    await el.updateComplete;
    expect(text(root(el).querySelector('.taskmeta'))).toBe('gone-x Loading…');
    await settle();
    await el.updateComplete;
    expect(text(root(el).querySelector('.tm-name'))).toBe('gone-x');
    expect(text(root(el).querySelector('.verdict'))).toBe('Waiting');
    el.remove();
  });

  it('shows a blank page with no task', async () => {
    const el = await view({ taskKey: null });
    expect(text(root(el).querySelector('.blank b'))).toBe('No task selected');
    el.remove();
  });
});
