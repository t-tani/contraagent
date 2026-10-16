// A monitor behind a reverse proxy, under a path of a site that serves other paths
// too: `contraagent monitor --base-path /monitor` (playwright.config.ts), reached
// through a proxy that takes `/monitor` off and rewrites `Host` to the monitor's
// address, as `proxy_pass http://127.0.0.1:<port>/;` does. The page, its scripts and
// icons, the API and both live feeds go through `/monitor/`, and nothing else of the
// site is asked for.
import { createServer, request, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { expect, test } from '@playwright/test';

const MONITOR_PORT = Number(process.env['E2E_BASE_PATH_PORT'] ?? 18796);
const BASE = '/monitor';

let proxy: Server;
let site = '';
/** The paths the proxy got outside `/monitor/`: each a request the page should not make. */
const outside: string[] = [];

test.beforeAll(async () => {
  proxy = createServer((req, res) => {
    const path = req.url ?? '/';
    if (!path.startsWith(`${BASE}/`)) {
      outside.push(path);
      res.writeHead(404, { 'content-type': 'text/plain' }).end('not the monitor');
      return;
    }
    // Node sets `Host` to the target's address; the rest of the headers pass as they are.
    const headers = { ...req.headers };
    delete headers.host;
    const upstream = request(
      { host: '127.0.0.1', port: MONITOR_PORT, method: req.method, path: path.slice(BASE.length), headers },
      (answer) => {
        res.writeHead(answer.statusCode ?? 502, answer.headers);
        answer.pipe(res); // unbuffered: each server-sent event goes on as it arrives
      },
    );
    upstream.on('error', () => res.writeHead(502).end());
    req.pipe(upstream);
  });
  await new Promise<void>((done) => proxy.listen(0, '127.0.0.1', done));
  site = `http://127.0.0.1:${(proxy.address() as AddressInfo).port}`;
});

test.afterAll(async () => {
  proxy.closeAllConnections();
  await new Promise((done) => proxy.close(done));
});

test('the page, the API and the live feeds all go through the base path', async ({ page }) => {
  const asked: string[] = [];
  page.on('request', (r) => asked.push(r.url()));
  const feeds: string[] = [];
  page.on('response', (r) => {
    if ((r.headers()['content-type'] ?? '').startsWith('text/event-stream') && r.status() === 200) feeds.push(new URL(r.url()).pathname);
  });

  await page.goto(`${site}${BASE}/?run=docs&tab=tasks`);
  await expect(page.locator('ca-monitor')).toHaveAttribute('base-url', BASE);
  // the run feed (/events) brings the journal and the plan the table is made of
  await expect(page.locator('header .runbtn .rs')).toContainText(/\d+ of \d+ tasks done/);
  await expect(page.locator('ca-task-table tbody tr').first()).toBeVisible();
  // a transcript, tailed from /events/stream
  await page.goto(`${site}${BASE}/?run=docs&tab=stream&key=summarize-beta`);
  await expect(page.locator('ca-transcript .msg').first()).toBeVisible();

  await expect.poll(() => feeds).toEqual(expect.arrayContaining([`${BASE}/events`, `${BASE}/events/stream`]));
  const ours = asked.filter((u) => u.startsWith(site));
  expect(ours.some((u) => u.startsWith(`${site}${BASE}/api/`))).toBe(true);
  expect(ours.some((u) => u === `${site}${BASE}/app.js`)).toBe(true);
  expect(ours.filter((u) => !u.startsWith(`${site}${BASE}/`))).toEqual([]);
  expect(asked.filter((u) => !u.startsWith(site) && !u.startsWith('data:'))).toEqual([]);
  expect(outside).toEqual([]);
});
