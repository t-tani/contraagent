// @vitest-environment happy-dom
// The overview's layout: the state of the run, its problems and its outputs share a row;
// an empty state is one line; the running tasks show while the run is live.
import { emptyRunState, type Info, type JournalRow, type Procs, type RunState } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import './ca-overview.js';

const INFO = { title: 'contraagent', panels: [], api_version: '0' } as unknown as Info;

const row = (key: string, ok: boolean): JournalRow => ({ ts: '2026-10-14T00:00:05+00:00', key, kind: 'k', unit: key, stop: ok ? 'completed' : 'error', ok, reason: ok ? '' : 'boom' });

function procs(running: number, maxWorkers: number | null = 4): Procs {
  return {
    run: 'r',
    alive: true,
    pid: 1,
    argv: [],
    started_at: '2026-10-14T00:00:00+00:00',
    max_workers: maxWorkers,
    run_group: 'r',
    tree: [],
    python_tasks: [],
    launches: Array.from({ length: running }, (_, i) => ({ key: `k-${i}`, kind: 'k', unit: `u${i}`, pid: 10 + i, age_s: 3, plugin: '', model: 'm', role: '', cmd: '' })),
  } as unknown as Procs;
}

async function overview(state: Partial<RunState>): Promise<ShadowRoot> {
  const el = document.createElement('ca-overview');
  Object.assign(el, { state: { ...emptyRunState(), ...state }, info: INFO, run: 'r' });
  document.body.append(el);
  await el.updateComplete;
  return el.shadowRoot!;
}

/** A card's name: its heading's own text, without the facts on its right. */
const name = (h: Element): string =>
  [...h.childNodes]
    .filter((n) => n.nodeType === Node.TEXT_NODE)
    .map((n) => n.textContent)
    .join('')
    .trim();
const headings = (root: ShadowRoot): string[] => [...root.querySelectorAll('section > h3')].map(name);
const statusCards = (root: ShadowRoot): string[] => [...root.querySelectorAll('.band.status section > h3')].map(name);

afterEach(() => document.body.replaceChildren());

describe('ca-overview', () => {
  it('puts the run, its problems and its outputs in one band, before the pipeline', async () => {
    const root = await overview({ journal: [row('a', true)] });
    expect(statusCards(root)).toEqual(['Run', 'Problems', 'Outputs']);
    expect(headings(root).indexOf('Problems')).toBeLessThan(headings(root).indexOf('Pipeline'));
    expect(headings(root).at(-1)).toBe('Timeline');
  });

  it('says there is no problem in one line, its mark beside the word and hidden from screen readers', async () => {
    const root = await overview({ journal: [row('a', true)] });
    const problems = root.querySelector('.problems')!;
    expect(problems.querySelector('.blank')).toBeNull();
    const ok = problems.querySelector('.ok')!;
    expect(ok.textContent?.trim()).toBe('✓No problems'); // the mark and the word, apart by the line's gap
    expect(ok.querySelector('[aria-hidden="true"]')?.textContent).toBe('✓');
  });

  it('lists a failed task under its problems', async () => {
    const root = await overview({ journal: [row('a', false)] });
    expect(root.querySelector('.problems .ok')).toBeNull();
    expect(root.querySelector('.problems .fl-name')?.textContent).toContain('k · a');
  });

  it('shows no running tasks for a run that is over: its state says so', async () => {
    const root = await overview({ journal: [row('a', true)] });
    expect(headings(root)).not.toContain('Running tasks');
  });

  it('while live: one line under the run when none runs, a row of their own when some do', async () => {
    const idle = await overview({ procs: procs(0) });
    expect(idle.querySelector('.stack')?.textContent).toContain('No tasks running');
    expect(idle.querySelector('.row')).toBeNull();
    document.body.replaceChildren();
    const busy = await overview({ procs: procs(2) });
    expect(busy.querySelector('.stack')?.textContent).not.toContain('Running tasks');
    expect(busy.querySelector('.row h3')?.textContent).toContain('Running tasks');
    expect(busy.querySelector('.row ca-workers')).not.toBeNull();
  });

  it('states the limit of tasks running at once only when the run recorded one', async () => {
    const known = await overview({ procs: procs(2) });
    expect(known.querySelector('.row h3 .r')?.textContent?.trim()).toBe('2 of 4 running at once');
    document.body.replaceChildren();
    const unknown = await overview({ procs: procs(2, null) });
    expect(unknown.querySelector('.row h3 .r')?.textContent?.trim()).toBe('2 running at once');
  });
});
