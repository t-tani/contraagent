// Two monitors embedded with history="memory" in a host page that has its own
// title, text field and single-key shortcuts (embed.html): the host keeps its
// keys, title, URL, history and <html> attributes, and each monitor keeps its
// own route, keys and run picker.
import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

const HOST = readFileSync(new URL('./embed.html', import.meta.url), 'utf8');

/** The host page, served on the monitor's origin, with both monitors showing their run. */
async function open(page: Page) {
  await page.route('**/embed-host', (route) => route.fulfill({ contentType: 'text/html', body: HOST }));
  await page.goto('/embed-host');
  for (const id of ['#a', '#b']) await expect(page.locator(`${id} header .rn`)).toHaveText('docs');
}

/** The name of the selected tab of the monitor `id`. */
const selected = (page: Page, id: string) => page.locator(id).getByRole('tab', { selected: true });
const picker = (page: Page, id: string) => page.locator(`${id} ca-run-picker`);
const hostKeys = (page: Page) => page.evaluate(() => (window as unknown as { hostKeys: string[] }).hostKeys);

test('the host keeps its title, URL, history and <html> attributes', async ({ page }) => {
  await open(page);
  const before = await page.evaluate(() => ({ length: history.length, attrs: [...document.documentElement.attributes].map((a) => `${a.name}=${a.value}`) }));
  await page.locator('#a').getByRole('tab', { name: /Tasks/ }).click();
  await page.locator('#b').getByRole('tab', { name: /History/ }).click();
  await expect(selected(page, '#a')).toContainText('Tasks');
  await expect(page).toHaveTitle('Host page');
  expect(new URL(page.url()).pathname + new URL(page.url()).search).toBe('/embed-host');
  const after = await page.evaluate(() => ({
    length: history.length,
    attrs: [...document.documentElement.attributes].map((a) => `${a.name}=${a.value}`),
    state: history.state as unknown,
  }));
  expect(after).toEqual({ ...before, state: null });
  expect(before.attrs).toEqual(['lang=de']);
});

test("keys typed in the host's field, or pressed outside the monitors, stay the host's", async ({ page }) => {
  await open(page);
  const input = page.locator('#host-input');
  await input.click();
  await page.keyboard.type('/2r');
  await expect(input).toHaveValue('/2r');
  await expect(input).toBeFocused();
  await page.locator('#host-button').focus();
  await page.keyboard.press('3');
  await page.keyboard.press('r');
  await page.keyboard.press('/');
  expect(await hostKeys(page)).toEqual(['3', 'r', '/']);
  for (const id of ['#a', '#b']) {
    await expect(selected(page, id)).toContainText('Overview');
    await expect(picker(page, id)).not.toHaveAttribute('open');
  }
});

test('a key pressed inside one monitor works there only', async ({ page }) => {
  await open(page);
  await selected(page, '#a').focus();
  await page.keyboard.press('2');
  await expect(selected(page, '#a')).toContainText('Tasks');
  await expect(selected(page, '#b')).toContainText('Overview');
  await page.keyboard.press('/');
  await expect(page.locator('#a .bar input')).toBeFocused();
  await page.keyboard.type('summ');
  await expect(page.locator('#a .bar input')).toHaveValue('summ');
  await expect(selected(page, '#a')).toContainText('Tasks');
});

test("each monitor's run picker opens on its own and closes on a click in the host", async ({ page }) => {
  await open(page);
  await selected(page, '#b').focus();
  await page.keyboard.press('r');
  await expect(picker(page, '#b')).toHaveAttribute('open');
  await expect(picker(page, '#a')).not.toHaveAttribute('open');
  await page.mouse.click(600, 4);
  await expect(picker(page, '#b')).not.toHaveAttribute('open');
});

test("a task's transcript keeps its open tool calls and position in its monitor, not in the page", async ({ page }) => {
  await open(page);
  await page.locator('#a').getByRole('tab', { name: /Tasks/ }).click();
  await page.locator('#a ca-task-table tbody tr', { hasText: 'beta' }).filter({ hasText: 'summarize' }).first().click();
  const transcript = page.locator('#a ca-transcript');
  await expect(transcript.locator('.msg').first()).toBeVisible();
  const card = transcript.locator('.toolcard').first();
  await card.locator('.th').click();
  await expect(card.locator('.tb')).toBeVisible();
  await transcript.locator('.scroller').evaluate((sc) => {
    sc.scrollTop = 0;
    sc.dispatchEvent(new Event('scroll'));
  });
  // The page's memory writes what it holds 200 ms after a change, or at once when the page hides: hide it now.
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
  const kept = await page.evaluate(() => ({
    state: history.state as unknown,
    session: Object.keys(sessionStorage).filter((k) => k.startsWith('contraagent')),
  }));
  expect(kept).toEqual({ state: null, session: [] });
});
