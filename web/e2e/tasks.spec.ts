// The tasks tab over the demo's `docs` run: every task of the plan is a row (two
// passes of review · gamma are two tasks), and every count of tasks agrees.
import { expect, test, type Page } from '@playwright/test';

test('the tasks tab counts and lists as many tasks as the header', async ({ page }) => {
  await page.goto('/?run=docs&tab=tasks');
  const line = page.locator('header .runbtn .rs');
  await expect(line).toContainText(/\d+ of \d+ tasks done/);
  const total = Number(/\d+ of (\d+) tasks done/.exec((await line.textContent()) ?? '')?.[1]);
  expect(total).toBeGreaterThan(0);
  await expect(page.locator('nav .tab', { hasText: 'Tasks' }).locator('.badge')).toHaveText(String(total));
  await expect(page.locator('.bar .meta')).toHaveText(`${total} tasks`);
  await expect(page.locator('ca-task-table tbody tr')).toHaveCount(total);
  // Both passes of review · gamma, each its own row.
  const passes = page.locator('ca-task-table tbody tr', { hasText: 'gamma' }).filter({ hasText: 'review' }).locator('.pass');
  await expect(passes).toHaveCount(2);
  expect((await passes.allTextContents()).sort()).toEqual(['Pass 1', 'Pass 2']);
  // The task that did not start names the earlier task that failed.
  const z = page.locator('ca-task-table tbody tr', { hasText: 'summarize' }).filter({ hasText: 'zeta' });
  await expect(z.locator('.pill')).toHaveText('not started');
  await expect(z.locator('.cause')).not.toBeEmpty();
  await z.click();
  await expect(page).toHaveURL(/tab=stream/);
});

/** The element that has the focus, through shadow roots. */
const focused = (page: Page) =>
  page.evaluate(() => {
    let el = document.activeElement;
    while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
    return el ? { tag: el.tagName, key: (el as HTMLElement).dataset['key'] ?? null } : null;
  });

for (const [tab, list] of [['tasks', 'ca-task-table'], ['journal', 'ca-journal-table']] as const) {
  test(`${list}: Tab reaches the first row, the arrow keys move, Enter opens the task`, async ({ page }) => {
    await page.goto(`/?run=docs&tab=${tab}`);
    await expect(page.locator(`${list} tbody tr`).first()).toBeVisible();
    await page.locator('ca-monitor .bar input').focus();
    let at = await focused(page);
    for (let i = 0; i < 30 && at?.tag !== 'TR'; i++) {
      await page.keyboard.press('Tab');
      at = await focused(page);
    }
    expect(at?.tag).toBe('TR');
    const rows = page.locator(`${list} tbody tr`);
    expect(at?.key).toBe(await rows.first().getAttribute('data-key'));
    await page.keyboard.press('ArrowDown');
    at = await focused(page);
    expect(at?.key).toBe(await rows.nth(1).getAttribute('data-key'));
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/tab=stream/);
    expect(new URL(page.url()).searchParams.get('key')).toBeTruthy();
  });
}

test('a task that did not start reads its input file by file, from the earlier task that failed', async ({ page }) => {
  await page.goto('/?run=docs&tab=stream&key=summarize-zeta&view=input');
  const view = page.locator('ca-task-view');
  const card = view.locator('.io-card').first();
  await expect(card.locator('.ct-path')).toHaveText('out/prepare/zeta.json');
  await expect(card.locator('.io-from')).toContainText('Output of prepare · zeta');
  await expect(card.locator('.io-from .pill')).toHaveText('failed');
  await expect(card.locator('.io-hd .ct-chip')).toHaveText('not written (task failed)');
  const earlier = view.locator('.upstream');
  await expect(earlier).toHaveCount(1);
  await expect(earlier.locator('.meta').first()).toHaveText('1 output file | 1 read by this task');
  // The file it reads is not shown again under the earlier task.
  await expect(earlier.locator('.io-card')).toHaveCount(0);
  await expect(view).not.toContainText('Also an input');
  await card.locator('.io-from a').click();
  await expect(page).toHaveURL(/key=python%3Aprepare-zeta|key=python:prepare-zeta/);
});

test('an agent task that reads two earlier outputs, and a Python task', async ({ page }) => {
  await page.goto('/?run=docs&tab=stream&key=review-gamma&view=input');
  const view = page.locator('ca-task-view');
  await expect(view.locator('.io-card .io-from')).toHaveText([/Output of summarize · gamma/, /Output of score · gamma/]);
  await expect(view.locator('.upstream .meta')).toHaveText(['1 output file | 1 read by this task', '1 output file | 1 read by this task']);
  await page.goto('/?run=docs&tab=stream&key=python:score-gamma&view=input');
  await expect(view.locator('.io-card .io-from')).toHaveText([/Output of summarize · gamma/]);
});

