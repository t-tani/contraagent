// A monitor embedded with a base-url that names no monitor API shows the URL
// and the cause, and writes it to the console; a base-url set after the
// element connected takes effect.
import { expect, test, type Page } from '@playwright/test';

const HOST = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Host page</title>
<script type="module" src="/app.js"></script>
<style>.pane { height: 420px; }</style></head>
<body><div class="pane"><ca-monitor id="m" history="memory"></ca-monitor></div></body></html>`;

/** The host page on the monitor's origin; `/spa/...` answers every path with an HTML page, `/gone/...` with 404. */
async function open(page: Page, baseUrl: string): Promise<string[]> {
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  await page.route('**/spa/**', (route) => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>app</title>' }));
  await page.route('**/gone/**', (route) => route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' }));
  await page.route('**/connection-host', (route) => route.fulfill({ contentType: 'text/html', body: HOST.replace('<ca-monitor', `<ca-monitor base-url="${baseUrl}"`) }));
  await page.goto('/connection-host');
  return errors;
}

const alert = (page: Page) => page.locator('#m [role="alert"]');

test('an HTML page in place of the API: its URL and cause, a console error, and no "No runs yet"', async ({ page, baseURL }) => {
  const errors = await open(page, `${baseURL}/spa`);
  await expect(alert(page)).toHaveText(`✕ No monitor API at ${baseURL}/spa/api/info: the response is HTML, not JSON`);
  await expect(page.locator('#m main')).not.toContainText('No runs yet');
  expect(errors.join('\n')).toContain(`No monitor API at ${baseURL}/spa/api/info: the response is HTML, not JSON`);
});

test('a 404 and a network error, each with its URL and cause', async ({ page, baseURL }) => {
  await open(page, `${baseURL}/gone`);
  await expect(alert(page)).toHaveText(`✕ No monitor API at ${baseURL}/gone/api/info: the response status is 404`);
  await page.locator('#m').evaluate((el) => ((el as HTMLElement & { baseUrl: string }).baseUrl = 'http://127.0.0.1:9'));
  await expect(alert(page)).toHaveText('✕ No monitor API at http://127.0.0.1:9/api/info: network error, no response');
});

test('a base-url set after connecting takes effect: the runs of the new server show', async ({ page, baseURL }) => {
  await open(page, `${baseURL}/spa`);
  await expect(alert(page)).toContainText('the response is HTML, not JSON');
  await page.locator('#m').evaluate((el, url) => ((el as HTMLElement & { baseUrl: string }).baseUrl = url), baseURL);
  await expect(alert(page)).toHaveText('');
  await expect(page.locator('#m header .rn')).not.toHaveText('—');
  await expect(page.locator('#m').getByRole('tab', { name: /Tasks/ })).toBeVisible();
});

test('the Japanese message', async ({ page, baseURL }) => {
  await open(page, `${baseURL}/spa`);
  await page.locator('#m').evaluate((el) => el.setAttribute('locale', 'ja'));
  await expect(alert(page)).toHaveText(`✕ ${baseURL}/spa/api/info にモニター API がありません: 応答が JSON ではなく HTML`);
});
