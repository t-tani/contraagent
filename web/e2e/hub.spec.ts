// A hub over the demo's runs shipped from two hosts (e2e/hub.py): h1 is up and
// drives docs@h1; h2 stopped reporting while it drove docs@h2. The runs are
// grouped by host, a host filter shows one host's, a run whose host stopped
// reporting says so wherever its state shows, and the hosts page lists the hosts
// and every account's utilization. A monitor of one host shows none of it.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const HUB = `http://127.0.0.1:${Number(process.env['E2E_HUB_PORT'] ?? 18794)}`;

const picker = (page: Page) => page.getByRole('dialog', { name: 'Runs' });
const params = (page: Page) => Object.fromEntries(new URL(page.url()).searchParams);

/** The element that has the focus, through shadow roots. */
const focused = (page: Page) =>
  page.evaluate(() => {
    let el = document.activeElement;
    while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
    return el ? { tag: el.tagName, role: el.getAttribute('role') } : null;
  });

async function openPicker(page: Page) {
  await page.locator('ca-monitor .runbtn').click();
  await expect(picker(page)).toBeVisible();
  await expect.poll(async () => (await focused(page))?.role).toBe('combobox');
}

async function noSeriousViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' > ')).join(', ')}`);
  expect(serious).toEqual([]);
}

test.describe('a hub', () => {
  test('the run picker groups the runs by host, each headed by its state', async ({ page }) => {
    await page.goto(`${HUB}/?run=docs@h1`);
    await openPicker(page);
    const groups = picker(page).getByRole('group');
    await expect(groups).toHaveCount(2);
    await expect(groups.nth(0)).toHaveAccessibleName(/^h1 \| up \| 2 runs$/);
    await expect(groups.nth(1)).toHaveAccessibleName(/^h2 \| no report since .+ \| 2 runs$/);
    // the host is in its header, not in each run's name
    await expect(groups.nth(0).getByRole('option').first().locator('.nm')).toHaveText('docs');
    await expect(groups.nth(0).getByRole('option').first()).toContainText('running');
    const quiet = groups.nth(1).getByRole('option', { name: /docs/ });
    await expect(quiet.locator('.when')).toHaveText('no report from host');
    await expect(quiet.locator('.when')).toHaveAttribute('data-tone', 'attention');
    await noSeriousViolations(page);
  });

  test('the host filter shows one host, and Tab moves between it and the search field', async ({ page }) => {
    await page.goto(`${HUB}/?run=docs@h1`);
    await openPicker(page);
    await page.keyboard.press('Tab');
    expect((await focused(page))?.tag).toBe('SELECT');
    await picker(page).getByRole('combobox', { name: 'Host' }).selectOption('h2');
    await expect(picker(page).getByRole('group')).toHaveCount(1);
    await expect(picker(page).getByRole('group')).toHaveAccessibleName(/^h2 /);
    await page.keyboard.press('Tab');
    expect((await focused(page))?.role).toBe('combobox');
    // the first options are the trends and the hosts pages; then h2's runs, the running and quiet one first
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(picker(page)).toBeHidden();
    await expect.poll(() => params(page).run).toBe('docs@h2');
  });

  test('a run whose host stopped reporting says so in the header and the run panel', async ({ page }) => {
    await page.goto(`${HUB}/?run=docs@h2`);
    const button = page.locator('ca-monitor .runbtn');
    await expect(button.locator('.rn')).toHaveText('docs');
    await expect(button.locator('.hostchip')).toHaveText(/h2/);
    await expect(button.locator('.pill')).toHaveText('no report from host');
    await expect(button).toHaveAccessibleName(/Host h2/);
    const driver = page.locator('ca-run-driver');
    await expect(driver.locator('.drv-t')).toHaveText('No report from host');
    await expect(driver.locator('.meta')).toContainText(/Last report .+ \| Last activity .+ \| Run group docs \| Host h2/);
    await page.goto(`${HUB}/?run=docs@h2&tab=procs`);
    await expect(page.locator('ca-procs-view .blank b')).toHaveText('No processes | no report from host');
  });

  test('the hosts page lists the hosts and each account over every run, and has its own URL', async ({ page }) => {
    await page.goto(`${HUB}/?run=docs@h1`);
    await openPicker(page);
    await page.keyboard.press('ArrowDown');
    await expect(picker(page).getByRole('listbox').getByRole('option', { selected: true })).toContainText('Trends');
    await page.keyboard.press('ArrowDown');
    await expect(picker(page).getByRole('listbox').getByRole('option', { selected: true })).toContainText('Hosts');
    await page.keyboard.press('Enter');
    await expect.poll(() => page.url()).toBe(`${HUB}/?page=hosts`);
    await expect(page.getByRole('tablist')).toHaveCount(0);
    await expect(page.locator('ca-monitor .runbtn .rn')).toHaveText('Hosts');
    const rows = page.locator('ca-hosts tbody tr');
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText('h1');
    await expect(rows.nth(0).locator('td').first()).toHaveText('up');
    await expect(rows.nth(0).locator('td').last()).toHaveText('2 runs | 1 running');
    await expect(rows.nth(1).locator('td').first()).toHaveText('no report');
    await expect(rows.nth(1).locator('td').last()).toHaveText('2 runs | 1 with no report from host');
    await expect(page.locator('ca-hosts ca-quota .acct')).toHaveCount(2);
    await noSeriousViolations(page);

    // Back returns to the run; a reload of the page's URL shows the hosts again.
    await page.goBack();
    await expect.poll(() => params(page).run).toBe('docs@h1');
    await page.goto(`${HUB}/?page=hosts`);
    await expect(rows).toHaveCount(2);
    // picking a run leaves the hosts page
    await openPicker(page);
    await picker(page).getByRole('option', { name: /analyse/ }).first().click();
    await expect.poll(() => params(page).run).toBe('analyse@h1');
    await expect(page.getByRole('tablist')).toBeVisible();
  });

  test('axe finds no serious or critical violation on the overview of a run whose host stopped reporting', async ({ page }) => {
    await page.goto(`${HUB}/?run=docs@h2`);
    await expect(page.locator('ca-monitor main > *').first()).toBeVisible();
    await page.waitForLoadState('networkidle');
    await noSeriousViolations(page);
  });
});

test('one host: no host filter, no hosts page, no host in the header', async ({ page }) => {
  await page.goto('/?run=docs');
  await expect(page.locator('ca-monitor .runbtn .hostchip')).toHaveCount(0);
  await openPicker(page);
  await expect(picker(page).locator('select')).toHaveCount(0);
  await expect(picker(page).getByRole('option', { name: /Hosts/ })).toHaveCount(0);
  await page.goto('/?page=hosts');
  await expect.poll(() => params(page).run).toBeTruthy();
  expect(params(page).page).toBeUndefined();
  await expect(page.locator('ca-hosts')).toHaveCount(0);
});

// Narrow screens: the open run picker stays inside the viewport, 16px from each side, and the page does not scroll sideways.
for (const width of [390, 600]) {
  test(`at ${width}px wide, the run picker fits the viewport, on one host and on a hub`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    for (const url of ['/?run=docs', `${HUB}/?run=docs@h1`]) {
      await page.goto(url);
      await openPicker(page);
      const box = await page.locator('ca-monitor ca-run-picker').boundingBox();
      expect(box, url).not.toBeNull();
      expect(box!.x, url).toBeGreaterThanOrEqual(16 - 0.5);
      expect(box!.x + box!.width, url).toBeLessThanOrEqual(width - 16 + 0.5);
      if (url.startsWith(HUB)) {
        const select = await picker(page).getByRole('combobox', { name: 'Host' }).boundingBox();
        expect(select!.x + select!.width, url).toBeLessThanOrEqual(box!.x + box!.width);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth), url).toBeLessThanOrEqual(width);
    }
  });
}
