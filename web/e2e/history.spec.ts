// Back, Forward and reload return the reader to where they were.
import { expect, test, type Page } from '@playwright/test';
import { feedReady } from './monitor.js';

const params = (page: Page) => Object.fromEntries(new URL(page.url()).searchParams);
const main = (page: Page) => page.locator('ca-monitor main');
const tab = (page: Page, name: string) => page.getByRole('tab', { name: new RegExp(name, 'i') });
/** What the monitor remembers under `id` in the current history entry (`core/memory.ts`), once written. */
const remembered = (page: Page, id: string) =>
  page.evaluate((id) => (history.state as { contraagent?: Record<string, unknown> } | null)?.contraagent?.[id], id);

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  // No run named: the most recent one is opened, replacing (not adding) the entry.
  await expect.poll(() => params(page).run).toBeTruthy();
});

test('tabs and tasks are places: Back and Forward step between them', async ({ page }) => {
  const run = params(page).run;
  await tab(page, 'history').click();
  await expect.poll(() => params(page)).toEqual({ run, tab: 'journal' });

  await page.locator('ca-journal-table tbody tr[data-executor="agent"]').first().click();
  await expect.poll(() => params(page).tab).toBe('stream');
  const key = params(page).key;
  expect(key).toBeTruthy();

  await page.goBack();
  await expect.poll(() => params(page)).toEqual({ run, tab: 'journal' });
  await expect(page.locator('ca-journal-table')).toBeVisible();

  await page.goBack();
  await expect.poll(() => params(page)).toEqual({ run });
  await expect(page.locator('ca-overview')).toBeVisible();

  await page.goForward();
  await page.goForward();
  await expect.poll(() => params(page)).toMatchObject({ tab: 'stream', key });
});

test('a filter refines the place: it is in the URL but adds no history entry', async ({ page }) => {
  await tab(page, 'history').click();
  await expect.poll(() => params(page).tab).toBe('journal');
  const depth = await page.evaluate(() => history.length);

  await page.locator('ca-journal-table .jchip', { hasText: /^done/ }).click();
  await expect.poll(() => params(page).stop).toBe('completed'); // the URL keeps the stop value; the chip says it in words
  await page.locator('ca-monitor .bar input').fill('beta');
  await expect.poll(() => params(page).q).toBe('beta');
  expect(await page.evaluate(() => history.length)).toBe(depth);

  await page.reload();
  await expect(page.locator('ca-monitor .bar input')).toHaveValue('beta');
  await expect(page.locator('ca-journal-table .jchip.on')).toHaveText(/done/);
});

test('reload and Back restore how far the list was scrolled', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 420 });
  await tab(page, 'history').click();
  // The rows arrive over the feed: measure once it has replayed, when all of them are in.
  await feedReady(page);
  await expect(page.locator('ca-journal-table tbody tr[data-executor="agent"]').first()).toBeVisible();
  const max = await main(page).evaluate((m) => m.scrollHeight - m.clientHeight);
  test.skip(max < 120, 'the demo journal is too short to scroll');
  const y = Math.round(max / 2);
  await main(page).evaluate((m, top) => m.scrollTo({ top }), y);
  // The scroll's event comes at the next frame, and the position is written to the history entry after it.
  await expect.poll(() => remembered(page, 'main')).toBe(y);

  await page.reload();
  await feedReady(page);
  await expect.poll(() => main(page).evaluate((m) => m.scrollTop)).toBe(y);

  await tab(page, 'tasks').click();
  await expect.poll(() => main(page).evaluate((m) => m.scrollTop)).toBe(0); // a new place starts at the top
  await page.goBack();
  await expect.poll(() => main(page).evaluate((m) => m.scrollTop)).toBe(y);
});

test('open contracts stay open across a reload', async ({ page }) => {
  await tab(page, 'outputs').click();
  const first = page.locator('ca-contracts details.ct').first();
  await first.locator('summary.ct-sum').click();
  await expect(first).toHaveJSProperty('open', true);
  // Written to the history entry once its toggle event has come.
  await expect.poll(async () => ((await remembered(page, 'contracts:open')) as unknown[] | undefined)?.length).toBe(1);
  await page.reload();
  await expect(page.locator('ca-contracts details.ct').first()).toHaveJSProperty('open', true);
});

test('a task: its transcript, its views as places, open tool cards kept', async ({ page }) => {
  const run = params(page).run;
  await page.goto(`/?run=${run}&tab=stream&key=summarize-beta`);
  const transcript = page.locator('ca-transcript');
  await expect(transcript.locator('.msg').first()).toBeVisible();
  const card = transcript.locator('.toolcard').first();
  await card.locator('.th').click();
  await expect(card.locator('.tb')).toBeVisible();

  await page.locator('ca-task-view .tview', { hasText: 'input' }).click();
  await expect.poll(() => params(page).view).toBe('input');
  await expect(page.locator('ca-task-view cae-markdown').first()).toBeVisible(); // the round's prompt
  await page.reload();
  await expect(page.locator('ca-task-view .tview.sel')).toHaveText(/Input/);

  await page.goBack();
  await expect.poll(() => params(page).view).toBeUndefined();
  await expect(page.locator('ca-transcript .toolcard').first().locator('.tb')).toBeVisible();
});

test('the page makes no request the monitor does not answer', async ({ page }) => {
  const failed: string[] = [];
  page.on('response', (r) => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
  page.on('pageerror', (e) => failed.push(String(e)));
  for (const t of ['overview', 'tasks', 'journal', 'outputs', 'definitions', 'procs', 'stream']) {
    await page.goto(`/?run=${params(page).run || 'docs'}&tab=${t}`);
    // What the tab asks for: the feed, then what the view fetches beside it.
    await feedReady(page);
    await page.waitForLoadState('networkidle');
  }
  expect(failed).toEqual([]);
});

test('the language switch: Japanese in place, kept across a reload, back to English', async ({ page }) => {
  // The graph legend's "done", a word xliff/ja.xlf translates.
  const legend = page.locator('ca-pipeline-graph .legend');
  await expect(legend).toContainText('done');
  await page.locator('ca-monitor .langs button[lang=ja]').click();
  await expect(legend).toContainText('完了');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ja');
  await page.reload();
  await expect(legend).toContainText('完了');
  await page.locator('ca-monitor .langs button[lang=en]').click();
  await expect(legend).toContainText('done');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
});
