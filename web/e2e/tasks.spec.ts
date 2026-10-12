// The tasks tab over the demo's `docs` run: every task of the plan is a row (two
// passes of review · gamma are two tasks), and every count of tasks agrees.
import { expect, test } from '@playwright/test';

test('the tasks tab counts and lists as many tasks as the header', async ({ page }) => {
  await page.goto('/?run=docs&tab=tasks');
  const line = page.locator('header .runbtn .rs');
  await expect(line).toContainText(/\d+ of \d+ tasks done/);
  const total = Number(/\d+ of (\d+) tasks done/.exec((await line.textContent()) ?? '')?.[1]);
  expect(total).toBeGreaterThan(0);
  await expect(page.locator('nav .tab', { hasText: 'Tasks' }).locator('.badge')).toHaveText(String(total));
  await expect(page.locator('.bar .meta')).toHaveText(`${total} tasks`);
  await expect(page.locator('ca-task-table .trow:not(.hd)')).toHaveCount(total);
  // Both passes of review · gamma, each its own row.
  const passes = page.locator('ca-task-table .trow', { hasText: 'gamma' }).filter({ hasText: 'review' }).locator('.pass');
  await expect(passes).toHaveCount(2);
  expect((await passes.allTextContents()).sort()).toEqual(['Pass 1', 'Pass 2']);
  // The task that did not start names the earlier task that failed.
  const z = page.locator('ca-task-table .trow', { hasText: 'summarize' }).filter({ hasText: 'zeta' });
  await expect(z.locator('.pill')).toHaveText('not started');
  await expect(z.locator('.cause')).not.toBeEmpty();
  await z.click();
  await expect(page).toHaveURL(/tab=stream/);
});
