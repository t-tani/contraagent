import { describe, expect, expectTypeOf, it } from 'vitest';
import { ApiError, createMonitorClient, type MonitorClient } from './client.js';
import type { JournalPage, RunSummary } from './types.js';

/** A client whose fetch records each request and answers with `answer`. */
function client(answer: (url: string) => Response, baseUrl = 'http://monitor.test/') {
  const requests: Request[] = [];
  const c = createMonitorClient({
    baseUrl,
    fetch: (input) => {
      const req = input as Request;
      requests.push(req);
      const res = answer(req.url);
      Object.defineProperty(res, 'url', { value: req.url });
      return Promise.resolve(res);
    },
  });
  return { c, requests };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('createMonitorClient', () => {
  it('builds each route from the base URL, its path parameters (encoded) and its query', async () => {
    const { c, requests } = client(() => json({}));
    await c.info();
    await c.runs();
    await c.journal('r 1');
    await c.definitions('r');
    await c.task('r', 'review/a b');
    await c.stream('r', 'k', 12);
    await c.panel('r', 'p');
    expect(requests.map((r) => [r.method, r.url])).toEqual([
      ['GET', 'http://monitor.test/api/info'],
      ['GET', 'http://monitor.test/api/runs'],
      ['GET', 'http://monitor.test/api/runs/r%201/journal?since=0'],
      ['GET', 'http://monitor.test/api/runs/r/definitions'],
      ['GET', 'http://monitor.test/api/runs/r/task/review%2Fa%20b'],
      ['GET', 'http://monitor.test/api/runs/r/stream/k?since=12'],
      ['GET', 'http://monitor.test/api/runs/r/panels/p'],
    ]);
    expect(c.baseUrl).toBe('http://monitor.test');
  });

  it('answers the JSON body', async () => {
    const { c } = client(() => json([{ run: 'r' }]));
    expect(await c.runs()).toEqual([{ run: 'r' }]);
  });

  it('throws ApiError on an error status or an empty answer', async () => {
    const { c } = client((url) => (url.endsWith('/journal?since=0') ? json({ detail: 'no' }, 404) : new Response(null, { status: 204 })));
    const e = await c.journal('r').catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ url: 'http://monitor.test/api/runs/r/journal?since=0', failure: 'status', status: 404 });
    expect((e as ApiError).message).toBe('No monitor API at http://monitor.test/api/runs/r/journal?since=0: the response status is 404');
    await expect(c.info()).rejects.toMatchObject({ failure: 'empty', status: 204 });
    const { c: broken } = client(() => json({ detail: 'boom' }, 500));
    await expect(broken.runs()).rejects.toThrow('Monitor API error at http://monitor.test/api/runs: the response status is 500');
  });

  it('throws ApiError for an HTML page, as a server without the API answers every path', async () => {
    const { c } = client(() => new Response('<!doctype html><title>app</title>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
    await expect(c.runs()).rejects.toMatchObject({ failure: 'not-json', status: 200, type: 'text/html' });
    await expect(c.runs()).rejects.toThrow('No monitor API at http://monitor.test/api/runs: the response is HTML, not JSON');
  });

  it('throws ApiError for a body that is not valid JSON', async () => {
    const { c } = client(() => new Response('{"run":', { headers: { 'Content-Type': 'application/json' } }));
    await expect(c.runs()).rejects.toThrow('the response is not valid JSON');
  });

  it('throws ApiError when no response comes', async () => {
    const c = createMonitorClient({ baseUrl: 'http://down.test', fetch: () => Promise.reject(new TypeError('Failed to fetch')) });
    await expect(c.info()).rejects.toMatchObject({ failure: 'network', status: 0, url: 'http://down.test/api/info' });
  });

  it('types each call by the generated schema', () => {
    expectTypeOf<ReturnType<MonitorClient['runs']>>().toEqualTypeOf<Promise<RunSummary[]>>();
    expectTypeOf<ReturnType<MonitorClient['journal']>>().toEqualTypeOf<Promise<JournalPage>>();
  });
});
