import { describe, expect, it } from 'vitest';
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
});
