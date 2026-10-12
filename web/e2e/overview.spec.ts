// The overview's pipeline graph over the demo's two generator flows: `docs` (a
// review loop per unit) and `analyse` (three layers of flow calls, a loop inside a
// loop).
import { expect, test, type Page } from '@playwright/test';

const graph = (page: Page) => page.locator('ca-pipeline-graph');
const crumbs = (page: Page) => graph(page).locator('.crumbs');
const crumbTexts = async (page: Page) => (await crumbs(page).locator('li').allTextContents()).map((t) => t.replace('›', '').trim());
const nodeName = (page: Page, text: string) => graph(page).locator('.node .name', { hasText: text }).first();

const open = async (page: Page, run: string) => {
  await page.goto(`/?run=${run}&tab=overview`);
  await expect(graph(page).locator('.dag').first()).toBeVisible();
};

test.describe('docs: a review loop per unit', () => {
  test.beforeEach(({ page }) => open(page, 'docs'));

  test('opens below the single top node, with the breadcrumb', async ({ page }) => {
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs']);
    await expect(nodeName(page, 'review_loop')).toBeVisible();
    await expect(nodeName(page, 'report')).toBeVisible();
  });

  test("draws the loop box with its passes, and gamma's 2 passes on its marks", async ({ page }) => {
    await nodeName(page, 'review_loop').click();
    const box = graph(page).locator('.box');
    await expect(box.locator('> .hd .count')).toHaveText('up to 2 passes');
    await expect(box.locator('> .hd .spread')).toHaveText('1 pass: 4 | 2 passes: 1');
    await expect(box.locator('.mark[data-n="2"]').first()).toHaveAttribute('title', /gamma/);
    await expect(graph(page).locator('.box .ret')).toHaveAttribute('title', 'Next pass');
  });

  test("shows the loop's passes as units by node and pass, and Escape goes back to the box", async ({ page }) => {
    await nodeName(page, 'review_loop').click();
    await graph(page).locator('.box > .hd .name').click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop', 'loop']);
    const matrix = graph(page).locator('table.matrix');
    await expect(matrix.locator('thead th.pass')).toHaveText(['Pass 1', 'Pass 2']);
    await expect(matrix.locator('tbody th')).toHaveText(['alpha', 'beta', 'gamma', 'delta', 'epsilon']);
    const gamma = matrix.locator('tbody tr', { hasText: 'gamma' });
    await expect(gamma.locator('.mark')).toHaveCount(5);
    await expect(matrix.locator('tbody tr', { hasText: 'alpha' }).locator('.mark')).toHaveCount(2);
    // Sorted by passes, gamma comes first.
    await graph(page).locator('select').selectOption('passes');
    await expect(matrix.locator('tbody th').first()).toHaveText('gamma');
    // Keyboard: the arrow keys move between marks; Escape goes up, back to the loop box.
    await matrix.locator('.mark[tabindex="0"]').focus();
    await page.keyboard.press('ArrowRight');
    await expect(matrix.locator('.mark[data-r="0"][data-c="1"]')).toBeFocused();
    await page.keyboard.press('Escape');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop']);
    await expect(graph(page).locator('.box > .hd .name')).toBeFocused();
  });

  test('Shift and an arrow key follow an edge on the same unit', async ({ page }) => {
    await nodeName(page, 'review_loop').click();
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[title*="gamma"]').focus();
    await page.keyboard.press('Shift+ArrowRight');
    const summarize = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'summarize' }) });
    await expect(summarize.locator('.mark[title*="gamma"]')).toBeFocused();
    await page.keyboard.press('Shift+ArrowLeft');
    await expect(prepare.locator('.mark[title*="gamma"]')).toBeFocused();
  });
});

test.describe('analyse: nested flow calls and loops', () => {
  test.beforeEach(({ page }) => open(page, 'analyse'));

  test('drills down three layers of flow calls with the breadcrumb, and back up', async ({ page }) => {
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse']);
    await nodeName(page, 'analyse_bundle').click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle']);
    await nodeName(page, 'analyse_file').click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle', 'analyse_file']);
    await expect(nodeName(page, 'parse_csv')).toBeVisible();
    await expect(nodeName(page, 'parse_json')).toBeVisible();
    await crumbs(page).locator('button', { hasText: 'analyse_bundle' }).click();
    await expect(crumbs(page).locator('[aria-current]')).toHaveText('analyse_bundle');
  });

  test('draws a loop inside a loop as nested boxes', async ({ page }) => {
    await nodeName(page, 'analyse_bundle').click();
    await nodeName(page, 'analyse_file').click();
    await expect(graph(page).locator('.box')).toHaveCount(2);
    await expect(graph(page).locator('.box .box')).toHaveCount(1);
    await expect(graph(page).locator('.box .box .node .name', { hasText: 'verify' })).toBeVisible();
    await expect(graph(page).locator('.box .box .node .name', { hasText: 'propose' })).toHaveCount(0);
  });

  test('shows the inner loop within each pass of the outer one, a breadcrumb level below it', async ({ page }) => {
    await nodeName(page, 'analyse_bundle').click();
    await nodeName(page, 'analyse_file').click();
    await expect(graph(page).locator('.box .box .hd .spread')).toHaveText('1 pass: 7 | 2 passes: 1');
    await graph(page).locator('.box .box > .hd .name').click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle', 'analyse_file', 'loop', 'loop']);
    const matrix = graph(page).locator('table.matrix');
    await expect(matrix.locator('thead th.nh')).toHaveText(['verify', 'refine', 'verify']);
    await expect(matrix.locator('tbody tr', { hasText: 'east-0-id' }).locator('.mark')).toHaveCount(3);
    // The outer loop's passes: its own node, then the nested loop's passes inside each pass.
    await crumbs(page).locator('button', { hasText: 'loop' }).click();
    await expect(matrix.locator('thead th.pass').first()).toHaveText('Pass 1');
    await expect(matrix.locator('thead th.loop')).toHaveCount(2);
    await expect(matrix.locator('thead th.nh').first()).toHaveText('propose');
  });
});
