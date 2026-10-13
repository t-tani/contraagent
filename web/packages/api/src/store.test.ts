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

  it('sets error when the API answers with an HTML page, writes it to the console once, and clears it on an answer', async () => {
    let answer = (): Response => new Response('<!doctype html>', { headers: { 'Content-Type': 'text/html' } });
    const fetch = () => Promise.resolve(answer());
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const store = new MonitorStore({ client: createMonitorClient({ baseUrl: 'http://app.test', fetch }), runsEveryMs: 60_000 });
    expect(store.snapshot).toMatchObject({ runsLoaded: false, error: null });
    await store.start();
    expect(store.snapshot.runsLoaded).toBe(false);
    expect(store.snapshot.error).toMatchObject({ url: 'http://app.test/api/info', failure: 'not-json', type: 'text/html' });
    await store.refreshRuns();
    expect(errors).toHaveBeenCalledTimes(1);
    expect(String(errors.mock.calls[0]![0])).toContain('No monitor API at http://app.test/api/info: the response is HTML, not JSON');
    answer = () => new Response('[]', { headers: { 'Content-Type': 'application/json' } });
    await store.refreshRuns();
    // /api/info is asked for again on the next refresh: until then its error stays.
    expect(store.snapshot).toMatchObject({ runsLoaded: true, runs: [] });
    expect(store.snapshot.error?.url).toBe('http://app.test/api/info');
    store.stop();
    errors.mockRestore();
  });

  it('sets error for a 404 of the run list', async () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
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
    expect(errors).toHaveBeenCalledTimes(1);
    errors.mockRestore();
  });
});
