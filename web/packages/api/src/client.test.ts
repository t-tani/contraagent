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
    await expect(c.journal('r')).rejects.toEqual(new ApiError(404, '/api/runs/r/journal'));
    await expect(c.info()).rejects.toBeInstanceOf(ApiError);
  });

  it('types each call by the generated schema', () => {
    expectTypeOf<ReturnType<MonitorClient['runs']>>().toEqualTypeOf<Promise<RunSummary[]>>();
    expectTypeOf<ReturnType<MonitorClient['journal']>>().toEqualTypeOf<Promise<JournalPage>>();
  });
});
