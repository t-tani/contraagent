// @vitest-environment happy-dom
// The whole monitor over a fake server: the tabs count what `deriveRun` counts,
// the header's run line says it in words, and the number keys switch tabs.
// Embedded (`history="memory"`), it leaves the page alone: no listeners on the
// document or the window, no title, no shortcuts outside it.
import { deriveRun, type Info, type JournalRow, type Plan, type PlanNode, type RunSummary, type Stop } from '@contraagent/api';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import './ca-monitor.js';
import type { CaMonitor } from './ca-monitor.js';

const node = (key: string, state: PlanNode['state'], after: string[] = []): PlanNode => ({
  key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', after, state, level: 0, group: key.split('-')[0]!,
});
const row = (key: string, stop: Stop, attempt = 0): JournalRow => ({
  ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', wall_s: 1, attempt,
});

// a done after a retry, c failed, d not started.
const plan: Plan = { nodes: [node('a-1', 'done'), node('c-1', 'failed'), node('d-1', 'blocked', ['c-1'])], groups: [] };
const journal = [row('a-1', 'error', 0), row('a-1', 'completed', 1), row('c-1', 'error'), row('d-1', 'invalid_input')];
const info: Info = { title: 'Pipeline', panels: [{ name: 'notes', title: 'Notes', description: '', icon: '' }], api_version: '1' };
const summary = {
  run: 'r', started_at: '2026-10-11T00:00:00', last_ts: '2026-10-11T00:01:05', running: false, quota: [],
  tasks: { total: 3, done: 1, failed: 1, not_run: 1 },
} as unknown as RunSummary;

/** The run feeds opened, each with its listeners by event name. */
const feeds: { url: string; on: Map<string, (e: { data: string }) => void>; es: { onopen: (() => void) | null } }[] = [];

class FakeEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly on = new Map<string, (e: { data: string }) => void>();
  constructor(url: string) {
    feeds.push({ url, on: this.on, es: this });
  }
  addEventListener(name: string, fn: (e: { data: string }) => void) {
    this.on.set(name, fn);
  }
  close() {}
}

const answer = (url: string): unknown => (url.endsWith('/api/info') ? info : url.endsWith('/api/runs') ? [summary] : null);

beforeEach(() => {
  feeds.length = 0;
  vi.stubGlobal('EventSource', FakeEventSource);
  vi.stubGlobal('fetch', (input: Request | string) => {
    const url = typeof input === 'string' ? input : input.url;
    // Any other server answers every path with its page, as a development server does.
    if (!url.startsWith('http://monitor.test/')) return Promise.resolve(new Response('<!doctype html><title>app</title>', { headers: { 'Content-Type': 'text/html' } }));
    const body = answer(url);
    return Promise.resolve(new Response(JSON.stringify(body), { status: body ? 200 : 404, headers: { 'Content-Type': 'application/json' } }));
  });
});
afterEach(() => vi.unstubAllGlobals());

const settle = (ms = 80) => new Promise((r) => setTimeout(r, ms));
const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();

/** A monitor (in memory mode unless `attrs` says otherwise), its run's feed replayed. */
async function monitor(attrs: Record<string, string> = {}): Promise<CaMonitor> {
  const el = document.createElement('ca-monitor');
  el.setAttribute('history', 'memory');
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  el.setAttribute('base-url', 'http://monitor.test');
  document.body.append(el);
  await settle();
  const feed = feeds.at(-1)!;
  expect(feed.url).toBe('http://monitor.test/events?run=r');
  feed.es.onopen?.();
  feed.on.get('plan')!({ data: JSON.stringify(plan) });
  for (const r of journal) feed.on.get('journal')!({ data: JSON.stringify(r) });
  feed.on.get('ready')!({ data: 'null' });
  await settle();
  await el.updateComplete;
  return el;
}

const root = (el: CaMonitor) => el.shadowRoot!;
/** The count on the tab named `name`. */
const badge = (el: CaMonitor, name: string) =>
  text([...root(el).querySelectorAll('nav .tab')].find((t) => text(t).includes(name))?.querySelector('.badge'));

describe('ca-monitor', () => {
  it('counts tasks and attempts in its tabs as deriveRun does, and says it in the run line', async () => {
    const el = await monitor();
    const d = deriveRun(journal, plan);
    expect(badge(el, 'Tasks')).toBe(String(d.counts.total));
    expect(badge(el, 'History')).toBe(String(d.tries.tries));
    expect(text(root(el).querySelector('header .rs'))).toBe(`${d.counts.doneTotal} of ${d.counts.total} tasks done | 1 not run | took 1m 05s`);
    // The custom view comes after the built-in tabs, behind a separator.
    expect(root(el).querySelector('nav .tab-sep + .tab.panel-tab')?.textContent).toContain('Notes');
    el.remove();
  });

  it('switches tabs with the number keys, and the bar counts what the tab lists', async () => {
    const el = await monitor();
    const key = (key: string) => root(el).querySelector('nav .tab')!.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, composed: true }));
    key('2');
    await el.updateComplete;
    expect(text(root(el).querySelector('nav .tab.sel'))).toMatch(/^≡ ?Tasks/);
    expect(text(root(el).querySelector('.bar .meta'))).toBe('3 tasks');
    key('3');
    await el.updateComplete;
    expect(text(root(el).querySelector('.bar .meta'))).toBe('3 attempts | 1 not started');
    el.remove();
  });

  describe('embedded (history="memory")', () => {
    it('adds no listener to the document or the window, and leaves the title alone', async () => {
      document.title = 'Host page';
      const onDoc = vi.spyOn(document, 'addEventListener');
      const onWin = vi.spyOn(window, 'addEventListener');
      try {
        const el = await monitor();
        expect(text(root(el).querySelector('header .rn'))).toBe('r');
        expect(onDoc).not.toHaveBeenCalled();
        // Only @lit/localize's own: each localized element hears the language change on the window.
        expect(onWin.mock.calls.map(([type]) => type).filter((t) => t !== 'lit-localize-status')).toEqual([]);
        expect(document.title).toBe('Host page');
        el.remove();
      } finally {
        onDoc.mockRestore();
        onWin.mockRestore();
      }
    });

    it('takes keys pressed inside it only, and none typed in a field', async () => {
      const el = await monitor();
      const tab = () => text(root(el).querySelector('nav .tab.sel'));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: '2' }));
      await el.updateComplete;
      expect(tab()).toMatch(/Overview/);
      const input = document.createElement('input');
      el.append(input);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: '2', bubbles: true, composed: true }));
      await el.updateComplete;
      expect(tab()).toMatch(/Overview/);
      el.remove();
    });

    it('takes no keys with shortcuts="off", and its tab bar shows no key hint', async () => {
      const el = await monitor({ shortcuts: 'off' });
      root(el).querySelector('nav .tab')!.dispatchEvent(new KeyboardEvent('keydown', { key: '2', bubbles: true, composed: true }));
      await el.updateComplete;
      expect(text(root(el).querySelector('nav .tab.sel'))).toMatch(/Overview/);
      expect(root(el).querySelector('.tabhint')).toBeNull();
      el.remove();
    });

    it('opens the run picker on a click, and closes it on a click elsewhere in the page', async () => {
      const el = await monitor();
      root(el).querySelector<HTMLButtonElement>('.runbtn')!.click();
      await el.updateComplete;
      expect(root(el).querySelector('ca-run-picker')!.hasAttribute('open')).toBe(true);
      document.body.click();
      await el.updateComplete;
      expect(root(el).querySelector('ca-run-picker')!.hasAttribute('open')).toBe(false);
      el.remove();
    });
  });

  describe('as the page (history="url")', () => {
    it('sets the title and takes the number keys pressed anywhere in the page', async () => {
      const el = await monitor({ history: 'url' });
      expect(document.title).toBe('Pipeline monitor');
      document.dispatchEvent(new KeyboardEvent('keydown', { key: '2' }));
      await el.updateComplete;
      expect(text(root(el).querySelector('nav .tab.sel'))).toMatch(/Tasks/);
      el.remove();
      history.replaceState(null, '', '/');
    });
  });

  it('marks its tabs as a tab list: one selected, one tab stop, the arrow keys move between them', async () => {
    const el = await monitor();
    const list = root(el).querySelector('[role="tablist"]')!;
    expect(list.getAttribute('aria-label')).toBe('Views');
    const tabs = [...list.querySelectorAll<HTMLElement>('[role="tab"]')];
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(tabs.map((_, i) => String(i === 0)));
    expect(tabs.map((t) => t.tabIndex)).toEqual(tabs.map((_, i) => (i === 0 ? 0 : -1)));
    const main = root(el).querySelector('main')!;
    expect(main.getAttribute('role')).toBe('tabpanel');
    expect(main.getAttribute('aria-labelledby')).toBe(tabs[0]!.id);
    expect(tabs[0]!.getAttribute('aria-controls')).toBe(main.id);
    // ArrowLeft from the first tab wraps to the last (the custom view).
    tabs[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true, composed: true }));
    expect(tabs.at(-1)!.tabIndex).toBe(0);
    tabs.at(-1)!.click();
    await el.updateComplete;
    expect(tabs.at(-1)!.getAttribute('aria-selected')).toBe('true');
    expect(main.getAttribute('aria-labelledby')).toBe(tabs.at(-1)!.id);
    el.remove();
  });

  it('shows its theme and its language on itself', async () => {
    const el = await monitor();
    expect(el.getAttribute('data-ca-theme')).toBe(el.shownTheme);
    expect(el.lang).toBe('en');
    el.theme = 'nord';
    await el.updateComplete;
    expect(el.getAttribute('data-ca-theme')).toBe('nord');
    el.remove();
  });

  describe('connection', () => {
    const alert = (el: CaMonitor) => text(root(el).querySelector('.api-error'));

    it('shows the URL and the cause when the API answers with an HTML page, not "No runs yet"', async () => {
      const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
      const el = document.createElement('ca-monitor');
      el.setAttribute('history', 'memory');
      document.body.append(el);
      await settle();
      await el.updateComplete;
      expect(alert(el)).toBe(`✕ No monitor API at ${location.origin}/api/info: the response is HTML, not JSON`);
      expect(text(root(el).querySelector('main'))).toBe('');
      expect(errors.mock.calls).toEqual([[`No monitor API at ${location.origin}/api/info: the response is HTML, not JSON`]]);
      el.remove();
      errors.mockRestore();
    });

    it('takes a base-url set after connecting: the old feeds close, the new server is read', async () => {
      const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
      const el = document.createElement('ca-monitor');
      el.setAttribute('history', 'memory');
      document.body.append(el);
      await settle();
      expect(feeds).toEqual([]);
      el.baseUrl = 'http://monitor.test/';
      await settle();
      await el.updateComplete;
      expect(feeds.map((f) => f.url)).toEqual(['http://monitor.test/events?run=r']);
      expect(alert(el)).toBe('');
      expect(text(root(el).querySelector('header .rn'))).toBe('r');
      el.remove();
      errors.mockRestore();
    });

    it('closes the feed of the old server when base-url changes, and opens the run named by run', async () => {
      const closed = vi.spyOn(FakeEventSource.prototype, 'close');
      const el = await monitor();
      el.setAttribute('base-url', 'http://monitor.test/other');
      el.run = 'r';
      await settle();
      await el.updateComplete;
      expect(closed).toHaveBeenCalled();
      expect(feeds.at(-1)!.url).toBe('http://monitor.test/other/events?run=r');
      el.remove();
      closed.mockRestore();
    });

    it('opens the run set after connecting', async () => {
      const el = await monitor();
      el.run = 'other';
      await settle();
      await el.updateComplete;
      expect(text(root(el).querySelector('header .rn'))).toBe('other');
      expect(feeds.at(-1)!.url).toBe('http://monitor.test/events?run=other');
      el.remove();
    });

    it('takes a history set after connecting', async () => {
      document.title = 'Host page';
      const el = await monitor();
      el.history = 'url';
      el.locale = 'ja';
      // The Japanese module loads when first chosen.
      await vi.waitFor(() => expect(document.title).toBe('Pipeline モニター'), { timeout: 3000 });
      expect(el.lang).toBe('ja');
      el.remove();
      history.replaceState(null, '', '/');
    });
  });
});
