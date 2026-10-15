import { describe, expect, it, vi } from 'vitest';
import { ApiError, createMonitorClient, type MonitorClient } from './client.js';
import { MonitorStore } from './store.js';
import type { Info } from './types.js';

/** Records which SSE event names each opened feed listens for. */
function fakeEventSource(opened: string[][]) {
  return class {
    onopen: (() => void) | null = null;
    onerror: (() => void) | null = null;
    private readonly names: string[] = [];
    constructor() {
      opened.push(this.names);
    }
    addEventListener(name: string) {
      this.names.push(name);
    }
    close() {}
  } as unknown as typeof EventSource;
}

describe('MonitorStore', () => {
  it('listens for the panels even when the run was opened before the panel list arrived', async () => {
    const opened: string[][] = [];
    const info: Info = { title: 't', panels: [{ name: 'notes', title: 'notes', description: '', icon: '' }], api_version: '1' };
    const client = { baseUrl: '', info: () => Promise.resolve(info), runs: () => Promise.resolve([]) } as unknown as MonitorClient;
    const store = new MonitorStore({ client, feed: { EventSource: fakeEventSource(opened) } });
    store.selectRun('docs'); // what the page does on load, from the URL
    await store.start();
    store.stop();
    expect(opened.at(-1)).toContain('panel:notes');
    expect(store.snapshot.run).toBe('docs');
  });

  it('sets error when the API answers with an HTML page, and clears it on an answer', async () => {
    let answer = (): Response => new Response('<!doctype html>', { headers: { 'Content-Type': 'text/html' } });
    const fetch = () => Promise.resolve(answer());
    const store = new MonitorStore({ client: createMonitorClient({ baseUrl: 'http://app.test', fetch }), runsEveryMs: 60_000 });
    expect(store.snapshot).toMatchObject({ runsLoaded: false, error: null });
    await store.start();
    expect(store.snapshot.runsLoaded).toBe(false);
    expect(store.snapshot.error).toMatchObject({ url: 'http://app.test/api/info', failure: 'not-json', type: 'text/html' });
    await store.refreshRuns();
    answer = () => new Response('[]', { headers: { 'Content-Type': 'application/json' } });
    await store.refreshRuns();
    // /api/info is asked for again on the next refresh: until then its error stays.
    expect(store.snapshot).toMatchObject({ runsLoaded: true, runs: [] });
    expect(store.snapshot.error?.url).toBe('http://app.test/api/info');
    store.stop();
  });

  it('sets error for a 404 of the run list', async () => {
    const info: Info = { title: 't', panels: [], api_version: '1' };
    const client = {
      baseUrl: '',
      info: () => Promise.resolve(info),
      runs: () => Promise.reject(new ApiError('http://x.test/api/runs', 'status', 404, 'application/json')),
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client, runsEveryMs: 60_000 });
    await store.start();
    store.stop();
    expect(store.snapshot.error).toMatchObject({ failure: 'status', status: 404 });
  });

  it('on a hub, sets error when the host list gets no answer', async () => {
    const client = {
      baseUrl: 'http://hub.test',
      info: () => Promise.resolve({ title: 't', panels: [], api_version: '3', hosts: true }),
      runs: () => Promise.resolve([]),
      hosts: () => Promise.reject(new ApiError('http://hub.test/api/hosts', 'not-json', 200, 'text/html')),
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client, runsEveryMs: 60_000 });
    await store.start();
    store.stop();
    expect(store.snapshot).toMatchObject({ runsLoaded: true, error: { url: 'http://hub.test/api/hosts', failure: 'not-json' } });
  });

  it('on a hub, fetches the host list with the run list', async () => {
    const info: Info = { title: 't', panels: [], api_version: '3', hosts: true };
    const hosts = { hosts: [{ host_id: 'h1', up: true, last_seen: '', interval_s: 3, runs: 1, running: 0, unresponsive: 0 }], quota: [] };
    let asked = 0;
    const client = {
      baseUrl: '',
      info: () => Promise.resolve(info),
      runs: () => Promise.resolve([]),
      hosts: () => (asked++, Promise.resolve(hosts)),
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client });
    await store.start();
    store.stop();
    expect(asked).toBe(1);
    expect(store.snapshot.hosts).toEqual(hosts);
  });

  it('on one host, asks for no host list', async () => {
    const client = {
      baseUrl: '',
      info: () => Promise.resolve({ title: 't', panels: [], api_version: '3' }),
      runs: () => Promise.resolve([]),
      hosts: () => Promise.reject(new Error('not asked')),
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client });
    await store.start();
    store.stop();
    expect(store.snapshot.hosts).toBeNull();
  });

  it('loads the trends of a period and the trend panels, and drops an answer to an older request', async () => {
    const info: Info = { title: 't', panels: [{ name: 'q', title: 'q', description: '', icon: '', scope: 'trends' }, { name: 'r', title: 'r', description: '', icon: '' }], api_version: '1' };
    const asked: unknown[] = [];
    let slow: (v: unknown) => void = () => {};
    const client = {
      baseUrl: '',
      info: () => Promise.resolve(info),
      runs: () => Promise.resolve([]),
      trends: (q: unknown) => {
        asked.push(q);
        return asked.length === 1 ? new Promise((r) => (slow = r)) : Promise.resolve({ period: { from: '2026-10-01' } });
      },
      trendsPanel: (name: string) => Promise.resolve({ panel: name }),
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client, runsEveryMs: 0 });
    await store.start();
    const first = store.loadTrends({ from: '2026-09-01', to: '2026-09-30', tz: 'UTC' });
    expect(store.snapshot.trends).toMatchObject({ loading: true, data: null });
    await store.loadTrends({ from: '2026-10-01', to: '2026-10-14', tz: 'UTC' });
    slow({ period: { from: '2026-09-01' } }); // the older answer arrives last
    await first;
    expect(store.snapshot.trends).toMatchObject({ loading: false, error: null, data: { period: { from: '2026-10-01' } }, panels: { q: { panel: 'q' } } });
    expect(Object.keys(store.snapshot.trends!.panels)).toEqual(['q']); // a run panel is no trend panel
    store.stop();
  });
});

describe('MonitorStore refreshes', () => {
  const info: Info = { title: 't', panels: [{ name: 'q', title: 'q', description: '', icon: '', scope: 'trends' }], api_version: '1' };
  const run = (last_ts: string) => ({ run: 'r1', last_ts, attempts: 1 });

  it('starts the next refresh only after the last one ended, however slow the answer', async () => {
    vi.useFakeTimers();
    let open = 0;
    let most = 0;
    let release: () => void = () => {};
    const client = {
      baseUrl: '',
      info: () => Promise.resolve(info),
      runs: () => {
        open += 1;
        most = Math.max(most, open);
        return new Promise((r) => {
          release = () => {
            open -= 1;
            r([]);
          };
        });
      },
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client, runsEveryMs: 1000 });
    const started = store.start();
    await vi.advanceTimersByTimeAsync(0);
    release(); // the first answer
    await started;
    await vi.advanceTimersByTimeAsync(10_000); // the second refresh is asked, and stays unanswered for 10 s
    expect(most).toBe(1);
    release();
    await vi.advanceTimersByTimeAsync(1000);
    expect(most).toBe(1);
    store.stop();
    vi.useRealTimers();
  });

  it('asks for the trends and their panels again only when the runs changed, and shows each answer as it arrives', async () => {
    vi.useFakeTimers();
    let runs = [run('2026-10-15T01:00:00Z')];
    const trends: unknown[] = [];
    const panels: unknown[] = [];
    let slowPanel: (v: unknown) => void = () => {};
    const client = {
      baseUrl: '',
      info: () => Promise.resolve(info),
      runs: () => Promise.resolve(runs),
      trends: (q: unknown) => {
        trends.push(q);
        return Promise.resolve({ period: q });
      },
      trendsPanel: (name: string) => {
        panels.push(name);
        return new Promise((r) => (slowPanel = r));
      },
    } as unknown as MonitorClient;
    const store = new MonitorStore({ client, runsEveryMs: 1000 });
    await store.start();
    void store.loadTrends({ from: '2026-10-01', to: '2026-10-14', tz: 'UTC' });
    await vi.advanceTimersByTimeAsync(0);
    // The trends are shown while the panel is still on its way.
    expect(store.snapshot.trends).toMatchObject({ loading: false, data: { period: { from: '2026-10-01' } }, panels: {} });
    await vi.advanceTimersByTimeAsync(5000); // five refreshes: the runs did not change
    expect([trends.length, panels.length]).toEqual([1, 1]);
    slowPanel({ panel: 'q' });
    await vi.advanceTimersByTimeAsync(0);
    expect(store.snapshot.trends!.panels).toEqual({ q: { panel: 'q' } });
    runs = [run('2026-10-15T01:05:00Z')]; // a new record
    await vi.advanceTimersByTimeAsync(1000);
    expect([trends.length, panels.length]).toEqual([2, 2]);
    store.stop();
    vi.useRealTimers();
  });
});
