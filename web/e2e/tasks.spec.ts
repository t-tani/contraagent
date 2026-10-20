// The tasks tab over the demo's `docs` run: every task of the plan is a row (two
// passes of review · gamma are two tasks), and every count of tasks agrees.
import { expect, test, type Page } from '@playwright/test';
import { feedReady } from './monitor.js';

test('the tasks tab counts and lists as many tasks as the header', async ({ page }) => {
  await page.goto('/?run=docs&tab=tasks');
  const line = page.locator('header .runbtn .rs');
  await expect(line).toContainText(/\d+ of \d+ tasks done/);
  const total = Number(/\d+ of (\d+) tasks done/.exec((await line.textContent()) ?? '')?.[1]);
  expect(total).toBeGreaterThan(0);
  await expect(page.getByRole('tab', { name: /Tasks/ }).locator('.badge')).toHaveText(String(total));
  await expect(page.locator('.bar .meta')).toHaveText(`${total} tasks`);
  await expect(page.locator('ca-task-table tbody tr')).toHaveCount(total);
  // Both passes of review · gamma, each its own row.
  const passes = page.locator('ca-task-table tbody tr', { hasText: 'gamma' }).filter({ hasText: 'review' }).locator('.pass');
  await expect(passes).toHaveCount(2);
  expect((await passes.allTextContents()).sort()).toEqual(['Pass 1', 'Pass 2']);
  // zeta's prepare failed, and its review loop created nothing after it.
  const zeta = page.locator('ca-task-table tbody tr', { hasText: 'zeta' });
  await expect(zeta).toHaveCount(1);
  await expect(zeta.locator('.pill')).toHaveText('failed');
  await zeta.click();
  await expect(page).toHaveURL(/tab=stream/);
});

/** The tag of the element that has the focus, through shadow roots. */
const focused = (page: Page) =>
  page.evaluate(() => {
    let el = document.activeElement;
    while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
    return el?.tagName ?? null;
  });

for (const [tab, list] of [['tasks', 'ca-task-table'], ['journal', 'ca-journal-table']] as const) {
  test(`${list}: Tab reaches the first row, the arrow keys move, Enter opens the task`, async ({ page }) => {
    await page.goto(`/?run=docs&tab=${tab}`);
    // Every row is in once the feed has replayed: the first row stays the first.
    await feedReady(page);
    const rows = page.locator(`${list} tbody tr`);
    await expect(rows.first()).toBeVisible();
    await page.locator('ca-monitor .bar input').focus();
    let at = await focused(page);
    for (let i = 0; i < 30 && at !== 'TR'; i++) {
      await page.keyboard.press('Tab');
      at = await focused(page);
    }
    await expect(rows.first()).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(rows.nth(1)).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/tab=stream/);
    expect(new URL(page.url()).searchParams.get('key')).toBeTruthy();
  });
}

test('a task given earlier outputs names, by each param, the earlier task it came from', async ({ page }) => {
  await page.goto('/?run=docs&tab=stream&key=review-gamma&view=input');
  const view = page.locator('ca-task-view');
  const param = (name: string) => view.locator('table.params tr', { has: page.locator('td.jmono', { hasText: name }) });
  await expect(param('summary').locator('.from')).toHaveText('From summarize · gamma');
  // A task is given values, not files: it reads no input file of an earlier task.
  await expect(view).toContainText('No input files');
  await expect(view.locator('.upstream', { hasText: 'summarize · gamma' })).toHaveCount(1);
  await expect(view.locator('.upstream', { hasText: 'score · gamma' })).toHaveCount(1);
  await param('summary').locator('.from a').click();
  await expect(page).toHaveURL(/key=summarize-gamma/);
});


test('a partly done task: its reason in its header, its own status in the tasks list and the problems', async ({ page }) => {
  await page.goto('/?run=docs&tab=stream&key=python:score-epsilon&view=output');
  const view = page.locator('ca-task-view');
  await expect(view.locator('div.verdict')).toHaveText('Partly done: the word counter is unavailable: words left at 0');
  await expect(view.locator('div.verdict')).toHaveAttribute('data-tone', 'attention');
  await expect(view.locator('.runchip.part')).toContainText('partly done');
  await page.goto('/?run=docs&tab=overview');
  await expect(page.locator('ca-overview .fl', { hasText: 'score · epsilon' })).toContainText('partly done');
});
