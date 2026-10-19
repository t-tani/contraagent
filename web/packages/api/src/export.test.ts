import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './client.js';
import { createExportClient, openExportFeed, taskFileName } from './export.js';
import { MonitorStore } from './store.js';
import type { RunFeedMessage } from './types.js';

const BASE = 'https://site.test/stats/data/';

/** An export as files: path under data/ -> body. */
const FILES: Record<string, unknown> = {
  'info.json': {
    title: 'reports',
    panels: [{ name: 'p', title: 'P', description: '', icon: '▤' }],
    api_version: '3.3.0',
    hosts: false,
    export: { exported_at: '2026-10-14T21:30:00+09:00', runs: ['r1'], left_out: ['transcripts', 'processes'], redacted: ['host', 'paths'] },
  },
  'runs.json': [{ run: 'r1' }],
  'runs/r1/journal.json': {
    entries: [
      { ts: 't1', key: 'review-a', kind: 'review', stop: 'completed', ok: true },
      { ts: 't2', key: 'review-b', kind: 'review', stop: 'completed', ok: true },
    ],
    total: 2,
  },
  'runs/r1/plan.json': { nodes: [{ key: 'review-a', kind: 'review' }, { key: 'python:report', kind: 'report' }] },
  'runs/r1/outputs.json': { contracts: [] },
  'runs/r1/cursor.json': {},
  'runs/r1/definitions.json': [{ kind: 'review', role: 'reviewer' }, { kind: 'report' }],
  'runs/r1/tasks/review-a.json': { key: 'review-a', rows: [], launches: [], definition: null, io: {}, stream: null },
  'runs/r1/tasks/python_report.json': { key: 'python:report', rows: [], launches: [], definition: null, io: {}, stream: null },
  'runs/r1/panels/p.json': { n: 3 },
};

/** A client over FILES; `requests` records each URL read. */
function exportClient() {
  const requests: string[] = [];
  const client = createExportClient(BASE, {
    fetch: (input) => {
      const url = (input as Request).url;
      requests.push(url);
      const path = url.slice(BASE.length);
      return Promise.resolve(
        path in FILES
          ? new Response(JSON.stringify(FILES[path]), { headers: { 'Content-Type': 'application/json' } })
          : new Response('not found', { status: 404, headers: { 'Content-Type': 'text/plain' } }),
      );
    },
  });
  return { client, requests };
}

describe('createExportClient', () => {
  it('reads each endpoint from its file, once', async () => {
    const { client, requests } = exportClient();
    expect((await client.info()).export?.runs).toEqual(['r1']);
    expect(await client.runs()).toEqual([{ run: 'r1' }]);
    expect((await client.journal('r1')).total).toBe(2);
    expect((await client.journal('r1', 1)).entries.map((e) => e.key)).toEqual(['review-b']);
    expect(await client.panel('r1', 'p')).toEqual({ n: 3 });
    expect(requests.filter((u) => u.endsWith('journal.json'))).toHaveLength(1);
  });

  it("puts a task's rows and definition back from the run's journal and definitions", async () => {
    const { client } = exportClient();
    const a = await client.task('r1', 'review-a');
    expect(a.rows.map((r) => r.ts)).toEqual(['t1']);
    expect(a.definition?.role).toBe('reviewer');
    // A task with no row yet takes its kind from the plan; its file takes the key's file name.
    const report = await client.task('r1', 'python:report');
    expect(report.rows).toEqual([]);
    expect(report.definition?.kind).toBe('report');
  });

  it('answers 404 for a view the export does not hold', async () => {
    const { client } = exportClient();
    await expect(client.stream('r1', 'review-a')).rejects.toMatchObject({ failure: 'status', status: 404 });
    await expect(client.hosts()).rejects.toBeInstanceOf(ApiError);
    await expect(client.journal('gone')).rejects.toMatchObject({ status: 404 });
  });
});

describe('taskFileName', () => {
  it("names a task's files as Python's file_name does", () => {
    // The pairs tests/test_run_files.py checks against file_name.
    const names: [string, string][] = [
      ['summarize-alpha', 'summarize-alpha'],
      ['python:prepare-alpha', 'python_prepare-alpha'],
      ['review-a~2', 'review-a_2'],
      ['x/../y', 'x____y'],
      ['.hidden', '_hidden'],
      ['a@h.1', 'a_h.1'],
      ['é/ü', 'é_ü'],
    ];
    for (const [key, name] of names) expect(taskFileName(key)).toBe(name);
  });
});

describe('openExportFeed', () => {
  it("replays the run's files once, then ready, and nothing after", async () => {
    const { client } = exportClient();
    const got: RunFeedMessage[] = [];
    let opened = 0;
    await new Promise<void>((done) => {
      openExportFeed(client)('r1', ['p'], {
        open: () => opened++,
        message: (m) => {
          got.push(m);
          if (m.event === 'ready') done();
        },
      });
    });
    expect(opened).toBe(1);
    expect(got.map((m) => m.event)).toEqual(['journal', 'journal', 'plan', 'outputs', 'cursor', 'panel:p', 'ready']);
    expect(got.find((m) => m.event === 'cursor')?.data).toBeNull();
    expect(got.at(-1)?.data).toEqual({ journal: 2 });
  });

  it('sends error for a run the export does not hold, and nothing once closed', async () => {
    const { client } = exportClient();
    const error = await new Promise<boolean>((done) => {
      openExportFeed(client)('gone', [], { message: () => done(false), error: () => done(true) });
    });
    expect(error).toBe(true);
    const got: string[] = [];
    const close = openExportFeed(client)('r1', [], { message: (m) => got.push(m.event) });
    close();
    // A feed left open would have replayed by the time a second one, opened now, is ready.
    await new Promise<void>((done) => {
      openExportFeed(client)('r1', [], { message: (m) => m.event === 'ready' && done() });
    });
    expect(got).toEqual([]);
  });
});

describe('MonitorStore over an export', () => {
  it('opens the run from the files and asks for the run list once', async () => {
    const { client, requests } = exportClient();
    const store = new MonitorStore({ client, openRunFeed: openExportFeed(client), runsEveryMs: 0, batchMs: 0 });
    await store.start();
    store.selectRun('r1');
    await vi.waitFor(() => expect(store.snapshot.state.ready).toBe(true));
    const s = store.snapshot;
    expect(s.info.export?.exported_at).toBe('2026-10-14T21:30:00+09:00');
    expect(s.state.ready).toBe(true);
    expect(s.state.journal).toHaveLength(2);
    expect(requests.filter((u) => u.endsWith('runs.json'))).toHaveLength(1);
    store.stop();
  });
});
