import { describe, expect, it } from 'vitest';
import { DEFAULT_VIEW_ROUTE, applyPatch, formatViewRoute, isNewPlace, parseViewRoute } from './view-route.js';

describe('view route', () => {
  it('round-trips through the query string, leaving defaults out', () => {
    const r = { ...DEFAULT_VIEW_ROUTE, run: 'r1', tab: 'stream' as const, key: 'k-u', view: 'input' as const, round: 2 };
    expect(formatViewRoute(r)).toBe('?run=r1&tab=stream&key=k-u&view=input&round=2');
    expect(parseViewRoute(formatViewRoute(r))).toEqual(r);
    const j = { ...DEFAULT_VIEW_ROUTE, run: 'r1', tab: 'journal' as const, kind: 'review', stop: 'bad', q: 'x y' };
    expect(formatViewRoute(j)).toBe('?run=r1&tab=journal&kind=review&stop=bad&q=x+y');
    expect(parseViewRoute(formatViewRoute(j))).toEqual(j);
    expect(formatViewRoute(DEFAULT_VIEW_ROUTE)).toBe('');
  });

  it('names the hosts page alone: it belongs to no run', () => {
    const r = { ...DEFAULT_VIEW_ROUTE, page: 'hosts' as const };
    expect(formatViewRoute(r)).toBe('?page=hosts');
    expect(formatViewRoute({ ...r, run: 'r', tab: 'tasks' })).toBe('?page=hosts');
    expect(parseViewRoute('?page=hosts&run=r')).toEqual(r);
    expect(parseViewRoute('?page=nope').page).toBe('');
    expect(isNewPlace({ ...DEFAULT_VIEW_ROUTE, run: 'r' }, r)).toBe(true);
  });

  it('drops what a tab does not use, and rejects unknown values', () => {
    expect(formatViewRoute({ ...DEFAULT_VIEW_ROUTE, run: 'r', tab: 'journal', key: 'k', def: 'd' })).toBe('?run=r&tab=journal');
    expect(parseViewRoute('?tab=nope&view=nope&round=-1')).toEqual(DEFAULT_VIEW_ROUTE);
    expect(parseViewRoute('?tab=panel:facts').tab).toBe('panel:facts');
    expect(formatViewRoute({ ...DEFAULT_VIEW_ROUTE, run: 'r', tab: 'tasks', layer: 'a/b', unit: 'u' })).toBe('?run=r&tab=tasks');
  });

  it("keeps the pipeline graph's layer and highlighted unit on the overview; another layer is a new place, a unit is not", () => {
    const r = { ...DEFAULT_VIEW_ROUTE, run: 'r', layer: 'flows.run_all/flows.review_loop/loop:7', unit: 'alpha' };
    expect(formatViewRoute(r)).toBe('?run=r&layer=flows.run_all%2Fflows.review_loop%2Floop%3A7&unit=alpha');
    expect(parseViewRoute(formatViewRoute(r))).toEqual(r);
    expect(isNewPlace(r, { ...r, layer: 'flows.run_all' })).toBe(true);
    expect(isNewPlace(r, { ...r, unit: 'beta' })).toBe(false);
    expect(applyPatch(r, { run: 's' })).toMatchObject({ layer: '', unit: '' });
  });

  it("keeps the graph's selection on the overview, as a refinement of its layer", () => {
    const r = { ...DEFAULT_VIEW_ROUTE, run: 'r', layer: 'flows.run_all', sel: 'kind:review#alpha' };
    expect(formatViewRoute(r)).toBe('?run=r&layer=flows.run_all&sel=kind%3Areview%23alpha');
    expect(parseViewRoute(formatViewRoute(r))).toEqual(r);
    expect(formatViewRoute({ ...r, tab: 'tasks' })).toBe('?run=r&tab=tasks');
    expect(isNewPlace(r, { ...r, sel: 'kind:review' })).toBe(false);
    expect(applyPatch(r, { layer: 'flows.other' })).toMatchObject({ layer: 'flows.other', sel: '' });
    expect(applyPatch(r, { layer: 'flows.other', sel: 'loop:7' })).toMatchObject({ sel: 'loop:7' });
    expect(applyPatch(r, { unit: 'beta' })).toMatchObject({ sel: 'kind:review#alpha' });
  });

  it('opening another task resets its view and round; another run resets every selection', () => {
    const at = { ...DEFAULT_VIEW_ROUTE, run: 'r', tab: 'stream' as const, key: 'a', view: 'output' as const, round: 2, def: 'x' };
    expect(applyPatch(at, { key: 'b' })).toMatchObject({ key: 'b', view: 'transcript', round: null });
    expect(applyPatch(at, { key: 'b', view: 'input' })).toMatchObject({ view: 'input' });
    expect(applyPatch(at, { run: 's' })).toMatchObject({ run: 's', key: null, def: null, round: null, tab: 'stream' });
  });

  it("keeps the Tasks and History filters while another tab is shown, and names them in the URL only on their tabs", () => {
    const tasks = { ...DEFAULT_VIEW_ROUTE, run: 'r', tab: 'tasks' as const, kind: 'classify', stop: 'bad', q: 'x' };
    expect(formatViewRoute(tasks)).toBe('?run=r&tab=tasks&kind=classify&q=x');
    const overview = applyPatch(tasks, { tab: 'overview', layer: 'a/b' });
    expect(formatViewRoute(overview)).toBe('?run=r&layer=a%2Fb');
    expect(formatViewRoute({ ...tasks, tab: 'stream', key: 'k' })).toBe('?run=r&tab=stream&key=k');
    // Back on the Tasks tab, the filter is there again.
    expect(formatViewRoute(applyPatch(overview, { tab: 'tasks' }))).toBe('?run=r&tab=tasks&kind=classify&q=x');
  });

  it('a filter refines a place; a tab, a task or a view is a new place', () => {
    const r = { ...DEFAULT_VIEW_ROUTE, run: 'r', tab: 'journal' as const };
    expect(isNewPlace(r, { ...r, q: 'x', stop: 'bad', kind: 'k' })).toBe(false);
    expect(isNewPlace(r, { ...r, tab: 'tasks' })).toBe(true);
    expect(isNewPlace({ ...r, tab: 'stream' }, { ...r, tab: 'stream', view: 'input' })).toBe(true);
  });

  it('names the trends page with its period, and no run', () => {
    const r = { ...DEFAULT_VIEW_ROUTE, page: 'trends' as const };
    expect(formatViewRoute(r)).toBe('?page=trends');
    expect(formatViewRoute({ ...r, days: 30, tz: 'Asia/Tokyo', group: 'nightly', run: 'x' })).toBe('?page=trends&days=30&tz=Asia%2FTokyo&group=nightly');
    expect(formatViewRoute({ ...r, days: 0, from: '2026-10-01', to: '2026-10-14' })).toBe('?page=trends&from=2026-10-01&to=2026-10-14');
    expect(parseViewRoute('?page=trends&run=x')).toEqual(r);
    expect(parseViewRoute('?page=trends&from=2026-10-01&to=2026-10-14')).toMatchObject({ days: 0, from: '2026-10-01', to: '2026-10-14' });
    expect(parseViewRoute('?page=trends&days=9')).toMatchObject({ days: 14 }); // a length it does not offer
    expect(parseViewRoute('?page=trends&from=10/01&to=x')).toMatchObject({ days: 14, from: '', to: '' });
    expect(formatViewRoute({ ...r, trendsTab: 'Reliability' })).toBe('?page=trends&tab=Reliability');
    expect(parseViewRoute('?page=trends&tab=tasks')).toMatchObject({ tab: 'overview', trendsTab: 'tasks' }); // a tab of the page, not of a run
    expect(parseViewRoute('?run=a&tab=tasks')).toMatchObject({ tab: 'tasks', trendsTab: '' });
  });
});
