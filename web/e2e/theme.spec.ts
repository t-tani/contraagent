// The theme in the settings of the header: a choice applies at once, is kept
// across a reload (set before the first paint), and is reachable by keyboard.
import { expect, test, type Page } from '@playwright/test';

const theme = (page: Page) => page.evaluate(() => document.documentElement.getAttribute('data-ca-theme'));
const control = (page: Page) => page.locator('ca-settings');
const panel = (page: Page) => control(page).getByRole('dialog');

test('the default follows the colour scheme, on the page and on the monitor', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/?run=docs&tab=overview');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'contraagent-dark');
  expect(await theme(page)).toBe('contraagent-dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect.poll(() => theme(page)).toBe('contraagent-light');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'contraagent-light');
});

test('choosing a theme applies it and keeps it across a reload', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/?run=docs&tab=overview');
  await expect(panel(page)).toBeHidden();
  await control(page).locator('.trig').click();
  await expect(panel(page)).toBeVisible();
  const themes = panel(page).getByRole('radiogroup', { name: 'Theme' });
  await expect(themes.getByRole('radio')).toHaveText([
    'System contraagent Dark',
    'contraagent Dark',
    'contraagent Light',
    'GitHub Dark',
    'GitHub Light',
    'One Dark',
    'Nord',
    'High contrast',
  ]);
  await expect(themes.locator('[aria-checked="true"]')).toHaveText(/System/);
  await themes.locator('[data-theme="nord"]').click();
  await expect.poll(() => theme(page)).toBe('nord');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'nord');
  // The panel stays open for the next choice; a press outside it closes it.
  await expect(panel(page)).toBeVisible();
  await page.locator('ca-monitor main').click({ position: { x: 5, y: 5 } });
  await expect(panel(page)).toBeHidden();

  // Set before the module runs: the page never shows another theme first.
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      (window as unknown as { firstTheme: string | null }).firstTheme = document.documentElement.getAttribute('data-ca-theme');
    });
  });
  await page.reload();
  expect(await page.evaluate(() => (window as unknown as { firstTheme: string | null }).firstTheme)).toBe('nord');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'nord');
});

test('System follows the colour scheme after another theme', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.addInitScript(() => localStorage.setItem('contraagent:theme', 'one-dark'));
  await page.goto('/?run=docs&tab=overview');
  await expect.poll(() => theme(page)).toBe('one-dark');
  await control(page).locator('.trig').click();
  await control(page).locator('[data-theme="system"]').click();
  await expect.poll(() => theme(page)).toBe('contraagent-light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect.poll(() => theme(page)).toBe('contraagent-dark');
});

test('the settings work by keyboard', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  const trig = control(page).locator('.trig');
  await trig.focus();
  await page.keyboard.press('Enter');
  await expect(panel(page)).toBeVisible();
  // Tab goes into the panel, to the chosen theme; the arrow keys, Home and End move in the list.
  await page.keyboard.press('Tab');
  await expect(control(page).locator('.item[aria-checked="true"]')).toBeFocused();
  await page.keyboard.press('End');
  await expect(control(page).locator('[data-theme="high-contrast"]')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect.poll(() => theme(page)).toBe('high-contrast');
  await page.keyboard.press('Escape');
  await expect(panel(page)).toBeHidden();
  await expect(trig).toBeFocused();
});

test('the settings are under their button, inside the window', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  await control(page).locator('.trig').click();
  const [b, p] = [await control(page).locator('.trig').boundingBox(), await panel(page).boundingBox()];
  expect(p!.y).toBeGreaterThanOrEqual(b!.y + b!.height);
  expect(Math.abs(p!.x + p!.width - (b!.x + b!.width))).toBeLessThanOrEqual(2);
  expect(p!.x).toBeGreaterThanOrEqual(0);
});

test('the settings have their Japanese words, and the keys that work', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('contraagent:locale', 'ja'));
  await page.goto('/?run=docs&tab=overview');
  await expect(control(page).locator('.trig')).toHaveAccessibleName('設定');
  await control(page).locator('.trig').click();
  await expect(control(page).locator('[data-theme="system"]')).toContainText('システム設定に合わせる');
  await expect(control(page).locator('[data-theme="high-contrast"]')).toHaveText('ハイコントラスト');
  await expect(control(page).locator('[role="group"]')).toHaveAccessibleName('エディタのテーマ');
  await expect(control(page).locator('.keys dt')).toHaveText(['1–7', 'r', '/']);
});
