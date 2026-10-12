import { describe, expect, it } from 'vitest';
import { DEFAULT_ROUTE, applyPatch, formatRoute, isNewPlace, parseRoute } from './route.js';

describe('route', () => {
  it('round-trips through the query string, leaving defaults out', () => {
    const r = { ...DEFAULT_ROUTE, run: 'r1', tab: 'stream' as const, key: 'k-u', view: 'input' as const, round: 2, q: 'x y' };
    expect(formatRoute(r)).toBe('?run=r1&tab=stream&key=k-u&view=input&round=2&q=x+y');
    expect(parseRoute(formatRoute(r))).toEqual(r);
    expect(formatRoute(DEFAULT_ROUTE)).toBe('');
  });

  it('drops what a tab does not use, and rejects unknown values', () => {
    expect(formatRoute({ ...DEFAULT_ROUTE, run: 'r', tab: 'journal', key: 'k', def: 'd' })).toBe('?run=r&tab=journal');
    expect(parseRoute('?tab=nope&view=nope&round=-1')).toEqual(DEFAULT_ROUTE);
    expect(parseRoute('?tab=panel:facts').tab).toBe('panel:facts');
    expect(formatRoute({ ...DEFAULT_ROUTE, run: 'r', tab: 'tasks', layer: 'a/b', unit: 'u' })).toBe('?run=r&tab=tasks');
  });

  it("keeps the pipeline graph's layer and highlighted unit on the overview; another layer is a new place, a unit is not", () => {
    const r = { ...DEFAULT_ROUTE, run: 'r', layer: 'flows.run_all/flows.review_loop/loop:7', unit: 'alpha' };
    expect(formatRoute(r)).toBe('?run=r&layer=flows.run_all%2Fflows.review_loop%2Floop%3A7&unit=alpha');
    expect(parseRoute(formatRoute(r))).toEqual(r);
    expect(isNewPlace(r, { ...r, layer: 'flows.run_all' })).toBe(true);
    expect(isNewPlace(r, { ...r, unit: 'beta' })).toBe(false);
    expect(applyPatch(r, { run: 's' })).toMatchObject({ layer: '', unit: '' });
  });

  it('opening another task resets its view and round; another run resets every selection', () => {
    const at = { ...DEFAULT_ROUTE, run: 'r', tab: 'stream' as const, key: 'a', view: 'output' as const, round: 2, def: 'x' };
    expect(applyPatch(at, { key: 'b' })).toMatchObject({ key: 'b', view: 'transcript', round: null });
    expect(applyPatch(at, { key: 'b', view: 'input' })).toMatchObject({ view: 'input' });
    expect(applyPatch(at, { run: 's' })).toMatchObject({ run: 's', key: null, def: null, round: null, tab: 'stream' });
  });

  it('a filter refines a place; a tab, a task or a view is a new place', () => {
    const r = { ...DEFAULT_ROUTE, run: 'r', tab: 'journal' as const };
    expect(isNewPlace(r, { ...r, q: 'x', stop: 'bad', kind: 'k' })).toBe(false);
    expect(isNewPlace(r, { ...r, tab: 'tasks' })).toBe(true);
    expect(isNewPlace({ ...r, tab: 'stream' }, { ...r, tab: 'stream', view: 'input' })).toBe(true);
  });
});
