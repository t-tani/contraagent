// @vitest-environment happy-dom
// The whole monitor over a fake server: the tabs count what `deriveRun` counts,
// the header's run line says it in words, and the number keys switch tabs.
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
    const body = answer(url);
    return Promise.resolve(new Response(JSON.stringify(body), { status: body ? 200 : 404, headers: { 'Content-Type': 'application/json' } }));
  });
});
afterEach(() => vi.unstubAllGlobals());

const settle = (ms = 80) => new Promise((r) => setTimeout(r, ms));
const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();

/** A monitor in memory mode, its run's feed replayed. */
async function monitor(): Promise<CaMonitor> {
  const el = document.createElement('ca-monitor');
  el.setAttribute('history', 'memory');
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
    expect(text(root(el).querySelector('header .rs'))).toBe(`${d.counts.doneTotal} of ${d.counts.total} tasks done | took 1m 05s`);
    // The custom view comes after the built-in tabs, behind a separator.
    expect(root(el).querySelector('nav .tab-sep + .tab.panel-tab')?.textContent).toContain('Notes');
    expect(document.title).toBe('Pipeline monitor');
    el.remove();
  });

  it('switches tabs with the number keys, and the bar counts what the tab lists', async () => {
    const el = await monitor();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '2' }));
    await el.updateComplete;
    expect(text(root(el).querySelector('nav .tab.sel'))).toMatch(/^≡ ?Tasks/);
    expect(text(root(el).querySelector('.bar .meta'))).toBe('3 tasks');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '3' }));
    await el.updateComplete;
    expect(text(root(el).querySelector('.bar .meta'))).toBe('3 attempts | 1 not started');
    el.remove();
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
    el.remove();
  });
});
