// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeStatTiles } from './stat-tiles.js';
import type { StatTile } from './types.js';

defineElement('cae-stat-tiles', CaeStatTiles);

const TILES: StatTile[] = [
  { id: 'jobs', label: 'Jobs', value: 12, sub: [[{ text: '11 done' }, { text: '1 failed', tone: 'failed' }]] },
  { id: 'failed', label: 'Failed', value: 1, tone: 'failed', tip: 'Jobs that failed', action: { id: 'show', label: 'Failed jobs' } },
  { id: 'time', label: 'Time', value: '4m 05s', sub: [['average 20s'], []] },
];

async function mount(tiles: StatTile[] = TILES) {
  const el = document.createElement('cae-stat-tiles');
  el.tiles = tiles;
  const events: string[] = [];
  el.addEventListener('cae-action', (e) => events.push(JSON.stringify(e.detail)));
  document.body.append(el);
  await el.updateComplete;
  const tile = (id: string) => el.shadowRoot!.querySelector<HTMLElement>(`[part~="tile"][data-id="${id}"]`)!;
  return { el, events, tile };
}

describe('cae-stat-tiles', () => {
  it('draws a tile per figure: label, value, lines of facts; a number counts in cae-count', async () => {
    const { tile, el } = await mount();
    expect(el.shadowRoot!.querySelectorAll('[part~="tile"]')).toHaveLength(3);
    expect(tile('jobs').querySelector('[part="label"]')?.textContent).toBe('Jobs');
    expect(tile('jobs').querySelector('[part="value"] cae-count')).not.toBeNull();
    expect(tile('time').querySelector('[part="value"]')?.textContent).toBe('4m 05s');
    // an empty line keeps its place
    expect(tile('time').querySelectorAll('[part="sub"]')).toHaveLength(2);
    expect(tile('jobs').querySelector('[part="sub"] [data-tone="failed"]')?.textContent).toBe('1 failed');
  });

  it('gives a tile with a tone its data-tone and mark; a plain one neither', async () => {
    const { tile } = await mount();
    expect(tile('failed').dataset['tone']).toBe('failed');
    expect(tile('failed').querySelector<HTMLElement>('[part="label"]')?.dataset['mark']).toBe('failed');
    expect(tile('failed').title).toBe('Jobs that failed');
    expect(tile('jobs').hasAttribute('data-tone')).toBe(false);
    expect(tile('jobs').querySelector('[part="label"]')?.hasAttribute('data-mark')).toBe(false);
  });

  it('makes a tile with an action a link named by its label, which sends cae-action', async () => {
    const { tile, events } = await mount();
    const link = tile('failed').querySelector<HTMLElement>('a[part="action"]')!;
    expect(link.textContent?.trim()).toBe('Failed jobs');
    expect(link.querySelector('.sr')).not.toBeNull();
    link.click();
    expect(events).toEqual(['{"id":"failed","action":"show"}']);
    expect(tile('jobs').querySelector('[part="action"]')).toBeNull();
  });

  it('sets the columns of a wide screen', async () => {
    const { el } = await mount();
    el.columns = 3;
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector<HTMLElement>('[part="tiles"]')!.getAttribute('style')).toContain('--cae-stat-tiles-columns:3');
  });
});
