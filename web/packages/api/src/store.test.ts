import { describe, expect, it } from 'vitest';
import type { MonitorClient } from './client.js';
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
});
