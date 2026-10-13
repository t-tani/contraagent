// The overview's pipeline graph over the demo's two generator flows: `docs` (a
// review loop per unit) and `analyse` (three layers of flow calls, a loop inside a
// loop).
import { expect, test, type Page } from '@playwright/test';

const graph = (page: Page) => page.locator('ca-pipeline-graph');
const crumbs = (page: Page) => graph(page).locator('.crumbs');
const crumbTexts = async (page: Page) => (await crumbs(page).locator('li').allTextContents()).map((t) => t.replace('›', '').trim());
const nodeName = (page: Page, text: string) => graph(page).locator('.node .name', { hasText: text }).first();
const inspector = (page: Page) => graph(page).locator('section.insp');
/** Into a function's layer: a double click on its node (a click selects it). */
const enter = async (page: Page, text: string) => nodeName(page, text).dblclick();
const params = (page: Page) => Object.fromEntries(new URL(page.url()).searchParams);

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
    await enter(page, 'review_loop');
    const box = graph(page).locator('.box');
    await expect(box.locator('> .hd .count')).toHaveText('up to 2 passes');
    await expect(box.locator('> .hd .spread')).toHaveText('1 pass: 4 | 2 passes: 1');
    await expect(box.locator('.mark[data-n="2"]').first()).toHaveAttribute('title', /gamma/);
    // The return to the next pass: a dotted edge inside the box, named in the legend.
    await expect(graph(page).locator('.edges path.ret')).toHaveCount(1);
    await expect(graph(page).locator('.legend')).toContainText('next pass');
  });

  test("shows the loop's passes as units by node and pass, and Escape goes back to the box", async ({ page }) => {
    await enter(page, 'review_loop');
    await graph(page).locator('.box > .hd .name').dblclick();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop', expect.stringMatching(/^Loop at tasks\.py:\d+$/)]);
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
    // The focused mark is selected: Escape clears the selection, then goes up.
    await expect.poll(() => params(page).sel).toBeTruthy();
    await page.keyboard.press('Escape');
    await expect.poll(() => params(page).sel).toBeUndefined();
    await page.keyboard.press('Escape');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop']);
    await expect(graph(page).locator('.box > .hd .name')).toBeFocused();
  });

  test('Shift and an arrow key follow an edge on the same unit', async ({ page }) => {
    await enter(page, 'review_loop');
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[title*="gamma"]').focus();
    await page.keyboard.press('Shift+ArrowRight');
    const summarize = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'summarize' }) });
    await expect(summarize.locator('.mark[title*="gamma"]')).toBeFocused();
    await page.keyboard.press('Shift+ArrowLeft');
    await expect(prepare.locator('.mark[title*="gamma"]')).toBeFocused();
  });

  test('the table is a second view in the same frame: the frame, its height and the switch stay; a row shows its status and is selected', async ({ page }) => {
    await enter(page, 'review_loop');
    const frame = graph(page).locator('.main > .frame');
    const views = graph(page).locator('.views');
    const before = { frame: (await frame.boundingBox())!, views: (await views.boundingBox())! };
    await expect(views.getByRole('radio', { name: 'Graph' })).toHaveAttribute('aria-checked', 'true');
    await views.getByRole('radio', { name: 'Table' }).click();
    await expect(views.getByRole('radio', { name: 'Table' })).toHaveAttribute('aria-checked', 'true');
    const table = frame.locator('table.list');
    await expect(table).toBeVisible();
    const after = { frame: (await frame.boundingBox())!, views: (await views.boundingBox())! };
    for (const k of ['x', 'y', 'width', 'height'] as const) {
      expect(Math.abs(after.frame[k] - before.frame[k])).toBeLessThan(1);
      expect(Math.abs(after.views[k] - before.views[k])).toBeLessThan(1);
    }
    // The zoom controls belong to the graph.
    await expect(graph(page).locator('.tools button', { hasText: 'Show all' })).toHaveCount(0);
    // A row's status: done of all, then only the states the node has.
    const row = (name: string) => table.locator('tbody tr', { has: page.locator('.name', { hasText: name }) });
    await expect(row('prepare').locator('.st .n')).toHaveText('5/6');
    await expect(row('prepare').locator('.st .err')).toHaveText('1 failed');
    await expect(row('summarize').locator('.st .warn')).toHaveText('1 not started');
    await expect(row('score').locator('.st .sep')).toHaveCount(0);
    await expect(table.locator('thead th')).toHaveText(['Kind', 'Status', 'Waits for', 'Created after', 'Later tasks']);
    // A click on a row selects it, with the node's card beside it.
    await row('summarize').locator('td').first().click();
    await expect(row('summarize')).toHaveClass(/sel/);
    await expect(inspector(page).locator('h4')).toHaveText(/summarize$/);
    await expect.poll(() => params(page).sel).toBe('kind:summarize');
    // Back to the graph: the same node is selected there.
    await views.getByRole('radio', { name: 'Graph' }).click();
    await expect(graph(page).locator('.node.sel .name')).toHaveText('summarize');
    expect(Math.abs((await views.boundingBox())!.x - before.views.x)).toBeLessThan(1);
  });

  test("a loop's passes narrower than the frame are in its middle, and Graph shows the loop's box in its layer", async ({ page }) => {
    await enter(page, 'review_loop');
    const views = graph(page).locator('.views');
    const at = (await views.boundingBox())!;
    await graph(page).locator('.box > .hd .name').dblclick();
    const frame = graph(page).locator('.main > .frame');
    const block = frame.locator('.mxblock');
    await expect(block.locator('table.matrix')).toBeVisible();
    const f = (await frame.boundingBox())!;
    const b = (await block.boundingBox())!;
    expect(b.width).toBeLessThan(f.width - 100);
    expect(Math.abs(b.x + b.width / 2 - (f.x + f.width / 2))).toBeLessThan(3);
    // The line above the passes is as wide as they are: the sort ends at their right edge.
    const sort = (await block.locator('.mxbar select').boundingBox())!;
    const mx = (await block.locator('.mx').boundingBox())!;
    expect(Math.abs(sort.x + sort.width - (mx.x + mx.width))).toBeLessThan(2);
    // The switch is where it was, Table pressed.
    expect(Math.abs((await views.boundingBox())!.x - at.x)).toBeLessThan(1);
    await expect(views.getByRole('radio', { name: 'Table' })).toHaveAttribute('aria-checked', 'true');
    await views.getByRole('radio', { name: 'Graph' }).click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop']);
    await expect(graph(page).locator('.box.sel')).toHaveCount(1);
    await expect(inspector(page).locator('h4')).toHaveText(/Loop at tasks\.py:\d+$/);
  });
});

test.describe('analyse: nested flow calls and loops', () => {
  test.beforeEach(({ page }) => open(page, 'analyse'));

  test('drills down three layers of flow calls with the breadcrumb, and back up', async ({ page }) => {
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse']);
    await enter(page, 'analyse_bundle');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle']);
    await enter(page, 'analyse_file');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle', 'analyse_file']);
    await expect(nodeName(page, 'parse_csv')).toBeVisible();
    await expect(nodeName(page, 'parse_json')).toBeVisible();
    await crumbs(page).locator('button', { hasText: 'analyse_bundle' }).click();
    await expect(crumbs(page).locator('[aria-current]')).toHaveText('analyse_bundle');
  });

  test('draws a loop inside a loop as nested boxes', async ({ page }) => {
    await enter(page, 'analyse_bundle');
    await enter(page, 'analyse_file');
    await expect(graph(page).locator('.box')).toHaveCount(2);
    await expect(graph(page).locator('.box .box')).toHaveCount(1);
    await expect(graph(page).locator('.box .box .node .name', { hasText: 'verify' })).toBeVisible();
    await expect(graph(page).locator('.box .box .node .name', { hasText: 'propose' })).toHaveCount(0);
  });

  test('shows the inner loop within each pass of the outer one, a breadcrumb level below it', async ({ page }) => {
    await enter(page, 'analyse_bundle');
    await enter(page, 'analyse_file');
    await expect(graph(page).locator('.box .box .hd .spread')).toHaveText('1 pass: 7 | 2 passes: 1');
    await graph(page).locator('.box .box > .hd .name').dblclick();
    // Each loop is named by where it is: the outer one and the one inside it are told apart.
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle', 'analyse_file', 'Loop at flow.py:122', 'Loop at flow.py:125']);
    const matrix = graph(page).locator('table.matrix');
    // Each column names its node, after the mark of who runs it.
    await expect(matrix.locator('thead th.nh')).toHaveText([/verify$/, /refine$/, /verify$/]);
    await expect(matrix.locator('thead th.nh').first()).toHaveAttribute('aria-label', 'verify | Python task');
    await expect(matrix.locator('tbody tr', { hasText: 'east-0-id' }).locator('.mark')).toHaveCount(3);
    // The outer loop's passes: its own node, then the nested loop's passes inside each pass.
    await crumbs(page).locator('button', { hasText: 'Loop at flow.py:122' }).click();
    await expect(matrix.locator('thead th.pass').first()).toHaveText('Pass 1');
    await expect(matrix.locator('thead th.loop')).toHaveCount(2);
    await expect(matrix.locator('thead th.nh').first()).toHaveText(/propose$/);
  });
});

test.describe('docs: selecting, and where a selection leads', () => {
  test.beforeEach(({ page }) => open(page, 'docs'));

  test('a click selects a mark; the inspector shows it and links to its task detail', async ({ page }) => {
    await enter(page, 'review_loop');
    // No selection, no card: the graph has the panel's whole width.
    await expect(inspector(page)).toHaveCount(0);
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[title*="zeta"]').click();
    await expect(prepare.locator('.mark.sel')).toHaveCount(1);
    await expect(inspector(page).locator('h4')).toHaveText('prepare · zeta');
    await expect(inspector(page).locator('dd').first()).toHaveText('failed');
    expect(params(page).sel).toBe('kind:prepare#zeta');
    // A reload keeps the selection.
    await page.reload();
    await expect(inspector(page).locator('h4')).toHaveText('prepare · zeta');
    await inspector(page).locator('.go', { hasText: 'Task detail' }).click();
    await expect.poll(() => params(page)).toMatchObject({ tab: 'stream', key: 'python:prepare-zeta', view: 'output' });
  });

  test('a function node: a click selects it, its link opens its layer; a kind node links to its tasks', async ({ page }) => {
    await nodeName(page, 'review_loop').click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs']);
    await expect(inspector(page)).toContainText('Function');
    await inspector(page).locator('.go', { hasText: 'Inside review_loop' }).click();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop']);
    // Who runs a kind's tasks: prepare is Python, summarize an agent.
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    const summarize = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'summarize' }) });
    await expect(prepare).not.toHaveClass(/agent/);
    await expect(summarize).toHaveClass(/agent/);
    await expect(summarize).toHaveAttribute('aria-label', /Agent task/);
    await summarize.locator('.name').click();
    await expect(inspector(page)).toContainText('Agent task');
    await inspector(page).locator('.go', { hasText: 'Tasks of summarize' }).click();
    await expect.poll(() => params(page)).toMatchObject({ tab: 'tasks', kind: 'summarize' });
  });

  test('a double click follows the first link: a mark to its task, a loop box to its passes', async ({ page }) => {
    await enter(page, 'review_loop');
    await graph(page).locator('.box > .hd').dblclick();
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop', expect.stringMatching(/^Loop at tasks\.py:\d+$/)]);
    await page.goBack();
    // The loop box is selected again; its card may cover a mark: close it.
    await inspector(page).locator('.switch', { hasText: 'Clear selection' }).click();
    await expect(inspector(page)).toHaveCount(0);
    const summarize = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'summarize' }) });
    await summarize.locator('.mark[title*="alpha"]').dblclick();
    await expect.poll(() => params(page)).toMatchObject({ tab: 'stream', key: 'summarize-alpha' });
  });

  test('keyboard: the focus selects, Enter follows, Escape clears the selection, then goes up', async ({ page }) => {
    await nodeName(page, 'review_loop').focus();
    await expect.poll(() => params(page).sel).toBe('flow:contraagent.docs.examples.demo.tasks.review_loop');
    await page.keyboard.press('Enter');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs', 'review_loop']);
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[tabindex="0"]').focus();
    await page.keyboard.press('ArrowRight');
    await expect(inspector(page).locator('h4')).toHaveText('prepare · beta');
    await page.keyboard.press('Escape');
    await expect.poll(() => params(page).sel).toBeUndefined();
    await expect(inspector(page)).toHaveCount(0);
    await page.keyboard.press('Escape');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs']);
  });
});

test.describe('the selection’s card', () => {
  test.beforeEach(({ page }) => open(page, 'docs'));

  const box = async (l: ReturnType<Page['locator']>) => (await l.boundingBox())!;
  const gap = (a: { x: number; y: number; width: number; height: number }, b: typeof a) =>
    Math.max(0, b.x - (a.x + a.width), a.x - (b.x + b.width), b.y - (a.y + a.height), a.y - (b.y + b.height));
  const inside = (a: { x: number; y: number; width: number; height: number }, f: typeof a) =>
    a.x >= f.x - 1 && a.y >= f.y - 1 && a.x + a.width <= f.x + f.width + 1 && a.y + a.height <= f.y + f.height + 1;

  test('sits next to the selected mark, inside the frame, and keeps clear of its node', async ({ page }) => {
    await enter(page, 'review_loop');
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[title*="zeta"]').click();
    const card = inspector(page);
    await expect(card).toBeVisible();
    await expect(card).toHaveAttribute('data-side', 'right');
    const c = await box(card);
    expect(gap(await box(prepare), c)).toBeLessThan(40);
    expect(gap(await box(prepare), c)).toBeGreaterThan(0);
    expect(inside(c, await box(graph(page).locator('.frame')))).toBe(true);
    // The selected mark is described by the card.
    await expect(prepare.locator('.mark.sel')).toHaveAttribute('aria-describedby', 'insp');
  });

  test('flips to the left of a node at the frame’s right edge, and stays in the frame', async ({ page }) => {
    await enter(page, 'review_loop');
    const last = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'write_note' }) });
    await last.locator('.name').click();
    const card = inspector(page);
    await expect(card).toHaveAttribute('data-side', 'left');
    const c = await box(card);
    expect(gap(await box(last), c)).toBeLessThan(40);
    expect(inside(c, await box(graph(page).locator('.frame')))).toBe(true);
  });

  test('follows a pan, and hides while the item is out of the frame', async ({ page }) => {
    await nodeName(page, 'report').click();
    const card = inspector(page);
    await expect(card).toBeVisible();
    const report = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'report' }) });
    // Measured once it has faded in (it scales from 96%).
    await card.evaluate((e) => Promise.all(e.getAnimations().map((a) => a.finished)));
    const offset = async () => Math.round((await box(card)).x - (await box(report)).x);
    const before = await offset();
    const nodeX = (await box(report)).x;
    const frame = graph(page).locator('.frame');
    const f = await box(frame);
    // Drag the graph 60px left: the card moves with it.
    await page.mouse.move(f.x + 40, f.y + f.height - 20);
    await page.mouse.down();
    await page.mouse.move(f.x - 20, f.y + f.height - 20, { steps: 5 });
    await page.mouse.up();
    await expect.poll(async () => Math.round((await box(report)).x - nodeX)).toBe(-60);
    await expect.poll(async () => Math.abs((await offset()) - before)).toBeLessThanOrEqual(1);
    // Far out of the frame: hidden; Show all brings it back.
    await page.mouse.move(f.x + 40, f.y + f.height - 20);
    await page.mouse.down();
    await page.mouse.move(f.x + f.width + 400, f.y + f.height - 20, { steps: 5 });
    await page.mouse.up();
    await expect(card).toBeHidden();
    await graph(page).locator('.tools button', { hasText: 'Show all' }).click();
    await expect(card).toBeVisible();
  });

  test('Tab from the selected item reaches the card; Escape closes it and keeps the focus on the item', async ({ page }) => {
    await nodeName(page, 'review_loop').focus();
    await expect(inspector(page)).toBeVisible();
    await expect(nodeName(page, 'review_loop')).toBeFocused();
    await expect(graph(page).locator('[role="status"]')).toContainText('review_loop');
    await page.keyboard.press('Tab');
    await expect(inspector(page).locator('.go', { hasText: 'Inside review_loop' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(nodeName(page, 'review_loop')).toBeFocused();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Escape');
    await expect(inspector(page)).toHaveCount(0);
    await expect(nodeName(page, 'review_loop')).toBeFocused();
  });

  test('on a narrow screen, docks under the frame as a sheet that names the item', async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 800 });
    await open(page, 'docs');
    await enter(page, 'review_loop');
    const prepare = graph(page).locator('.node', { has: page.locator('.name', { hasText: 'prepare' }) });
    await prepare.locator('.mark[title*="zeta"]').click();
    const card = inspector(page);
    await expect(card).toHaveClass(/sheet/);
    await expect(card.locator('h4')).toHaveText('prepare · zeta');
    await expect(card).toBeInViewport();
    await expect(prepare.locator('.mark.sel')).toBeInViewport();
  });
});

test.describe('a layer the run does not have', () => {
  test('opens the first layer, names the layer, and sets the URL right', async ({ page }) => {
    await page.goto('/?run=docs&tab=overview&layer=flows.gone');
    await expect(graph(page).locator('.missing')).toHaveText('No layer flows.gone in this run');
    expect(await crumbTexts(page)).toEqual(['Pipeline', 'docs']);
    await expect.poll(() => params(page).layer).toBeUndefined();
    // Going elsewhere forgets it.
    await enter(page, 'review_loop');
    await expect(graph(page).locator('.missing')).toHaveCount(0);
  });

  test("opens a function named by its qualified name alone, when the run reaches it one way", async ({ page }) => {
    await page.goto('/?run=analyse&tab=overview&layer=contraagent.docs.examples.analysis.flow.analyse_file');
    await expect.poll(() => crumbTexts(page)).toEqual(['Pipeline', 'analyse', 'analyse_bundle', 'analyse_file']);
    await expect(graph(page).locator('.missing')).toHaveCount(0);
    await expect.poll(() => params(page).layer).toContain('analyse_bundle');
  });
});

test.describe('colour means status', () => {
  test('the Tasks total stays neutral though a task failed; the failed count is red', async ({ page }) => {
    await open(page, 'docs');
    const kpis = page.locator('ca-kpis');
    const colour = (id: string) => kpis.locator(`.kpi[data-id="${id}"] .v`).evaluate((e) => getComputedStyle(e).color);
    const text = await kpis.evaluate((e) => getComputedStyle(e).color);
    await expect(kpis.locator('.kpi[data-id="tasks"]')).not.toHaveAttribute('data-tone');
    await expect(kpis.locator('.kpi[data-id="tasks"] [data-tone="failed"]')).toHaveText('1 failed');
    expect(await colour('tasks')).toBe(text);
    expect(await colour('cost')).toBe(text);
    await expect(kpis.locator('.kpi[data-id="bad"]')).toHaveAttribute('data-tone', 'failed');
    expect(await colour('bad')).not.toBe(text);
    // A tab's count is a total too.
    const badge = page.locator('ca-monitor').locator('.tab', { hasText: 'History' }).locator('.badge');
    await expect(badge).not.toHaveAttribute('data-tone');
  });
});
