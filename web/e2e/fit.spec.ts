// The monitor's page fits the width it is given: at 360, 600, 900 and 1280 px no box
// is wider than its own content box allows, except the boxes meant to scroll
// sideways (`data-scroll="x"`, e2e/fit.ts). Checked over the demo runs on every tab,
// the task detail's views, the trends page and a hub's hosts page. The live elements
// of the documentation site are site/fit.spec.ts's.
import { expect, test, type Page } from '@playwright/test';
import { overflows, settle } from './fit.js';
import { feedReady } from './monitor.js';

const WIDTHS = [360, 600, 900, 1280];
const HUB = `http://127.0.0.1:${Number(process.env['E2E_HUB_PORT'] ?? 18794)}`;

/** The monitor's places to check: each tab of a run, the task detail's views, the trends page. */
const PLACES = [
  ...['overview', 'tasks', 'journal', 'outputs', 'definitions', 'procs'].map((tab) => `/?run=docs&tab=${tab}`),
  '/?run=analyse&tab=overview',
  ...['transcript', 'input', 'output', 'definition'].map((view) => `/?run=docs&tab=stream&key=review-gamma&view=${view}`),
  '/?page=trends',
];

/** The monitor at `url`, drawn: its header names a run or a page, its main view has content, and a run's feed has replayed. */
async function openMonitor(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator('ca-monitor header .runbtn')).toBeVisible();
  await expect(page.locator('ca-monitor main#main > *').first()).toBeVisible();
  if (new URL(url, 'http://x').searchParams.has('run')) await feedReady(page);
  await page.waitForLoadState('networkidle');
  await settle(page);
}

for (const width of WIDTHS) {
  test(`the monitor's page fits ${width} px`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 800 });
    const found: string[] = [];
    for (const url of [...PLACES, `${HUB}/?page=hosts`]) {
      await openMonitor(page, url);
      found.push(...(await overflows(page, 'body')).map((s) => `${url}: ${s}`));
    }
    expect(found).toEqual([]);
  });
}
