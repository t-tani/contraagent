// Accessibility over the demo's `docs` run: the tabs are a tab list the keyboard
// moves through, the run picker is a dialog that takes the focus and gives it
// back, rows open from the keyboard, and axe finds no serious or critical
// violation on any tab.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const params = (page: Page) => Object.fromEntries(new URL(page.url()).searchParams);

/** The element that has the focus, through shadow roots. */
const focused = (page: Page) =>
  page.evaluate(() => {
    let el = document.activeElement;
    while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
    return el
      ? { tag: el.tagName, role: el.getAttribute('role'), cls: el.className, text: (el.textContent ?? '').trim(), active: el.getAttribute('aria-activedescendant') }
      : null;
  });

/** Press Tab until `done` holds for the focused element (at most `n` times). */
async function tabUntil(page: Page, done: (f: Awaited<ReturnType<typeof focused>>) => boolean, n = 40) {
  let at = await focused(page);
  for (let i = 0; i < n && !done(at); i++) {
    await page.keyboard.press('Tab');
    at = await focused(page);
  }
  return at;
}

test('the tabs are a tab list: one selected, the arrow keys move, Enter selects', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  const list = page.getByRole('tablist', { name: 'Views' });
  await expect(list).toBeVisible();
  await expect(list.getByRole('tab', { selected: true })).toHaveAccessibleName(/Overview/);
  await expect(page.getByRole('tabpanel', { name: /Overview/ })).toBeVisible();

  // One tab stop: Tab comes into the list on the selected tab.
  await page.locator('ca-monitor .runbtn').focus();
  const first = await tabUntil(page, (f) => f?.role === 'tab');
  expect(first?.text).toMatch(/Overview/);

  await page.keyboard.press('ArrowRight');
  expect((await focused(page))?.text).toMatch(/Tasks/);
  // The focus moves; the selection does not until Enter.
  await expect(list.getByRole('tab', { selected: true })).toHaveAccessibleName(/Overview/);
  await page.keyboard.press('Enter');
  await expect.poll(() => params(page).tab).toBe('tasks');
  await expect(list.getByRole('tab', { selected: true })).toHaveAccessibleName(/Tasks/);
  await expect(page.getByRole('tabpanel', { name: /Tasks/ })).toBeVisible();

  await page.keyboard.press('End');
  const last = await list.getByRole('tab').last().textContent();
  expect((await focused(page))?.text).toBe(last?.trim());
  await page.keyboard.press('ArrowRight');
  expect((await focused(page))?.text).toMatch(/Overview/);
  await page.keyboard.press('ArrowLeft');
  expect((await focused(page))?.text).toBe(last?.trim());
  await page.keyboard.press('Home');
  expect((await focused(page))?.text).toMatch(/Overview/);
});

test('the run picker is a dialog: it takes the focus, keeps it, and gives it back', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  const button = page.locator('ca-monitor .runbtn');
  await expect(button).toHaveAttribute('aria-expanded', 'false');
  const dialog = page.getByRole('dialog', { name: 'Runs' });
  await expect(dialog).toBeHidden();

  await button.click();
  await expect(dialog).toBeVisible();
  await expect(button).toHaveAttribute('aria-expanded', 'true');
  await expect.poll(async () => (await focused(page))?.role).toBe('combobox');
  // Tab stays in the dialog.
  await page.keyboard.press('Tab');
  expect((await focused(page))?.role).toBe('combobox');
  await page.keyboard.press('Shift+Tab');
  expect((await focused(page))?.role).toBe('combobox');
  // The arrow keys name the active option.
  await page.keyboard.press('ArrowDown');
  const active = (await focused(page))?.active;
  expect(active).toBeTruthy();
  await expect(dialog.getByRole('option', { selected: true })).toHaveCount(1);
  await expect(dialog.locator(`#${active}`)).toHaveAttribute('aria-selected', 'true');

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  expect((await focused(page))?.cls).toContain('runbtn');

  // The shortcut opens it too, and a pick gives the focus back.
  await page.keyboard.press('r');
  await expect(dialog).toBeVisible();
  await expect.poll(async () => (await focused(page))?.role).toBe('combobox');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(dialog).toBeHidden();
  expect((await focused(page))?.cls).toContain('runbtn');
});

test('a problem row opens its task from the keyboard', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  const name = page.locator('ca-overview .fl .fl-name').first();
  await expect(name).toBeVisible();
  const text = (await name.textContent())?.trim();
  await page.locator('ca-monitor .runbtn').focus();
  const at = await tabUntil(page, (f) => (f?.cls ?? '').includes('fl-name'), 80);
  expect(at?.text).toBe(text);
  await page.keyboard.press('Enter');
  await expect.poll(() => params(page).tab).toBe('stream');
});

test('a definition is a button the keyboard picks', async ({ page }) => {
  await page.goto('/?run=docs&tab=definitions');
  const items = page.locator('ca-definitions .defitem');
  await expect(items.nth(1)).toBeVisible();
  await items.nth(1).focus();
  await page.keyboard.press('Enter');
  await expect(items.nth(1)).toHaveAttribute('aria-current', 'true');
  expect(params(page).def).toBe((await items.nth(1).locator('b').textContent())?.trim());
});

test('the notices are live regions', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  await expect(page.locator('ca-toasts [role="status"]')).toHaveAttribute('aria-live', 'polite');
  await expect(page.locator('ca-toasts [role="alert"]')).toHaveAttribute('aria-live', 'assertive');
});

for (const tab of ['overview', 'tasks', 'journal', 'outputs', 'definitions', 'procs', 'stream']) {
  test(`axe finds no serious or critical violation: ${tab}`, async ({ page }) => {
    await page.goto(`/?run=docs&tab=${tab}`);
    await expect(page.locator('ca-monitor main > *').first()).toBeVisible();
    await page.waitForLoadState('networkidle');
    const { violations } = await new AxeBuilder({ page }).analyze();
    const serious = violations
      .filter((v) => v.impact === 'serious' || v.impact === 'critical')
      .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' > ')).join(', ')}`);
    expect(serious).toEqual([]);
  });
}
