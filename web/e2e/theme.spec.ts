// The theme control in the header: a choice applies at once, is kept across a
// reload (set before the first paint), and is reachable by keyboard.
import { expect, test, type Page } from '@playwright/test';

const theme = (page: Page) => page.evaluate(() => document.documentElement.getAttribute('data-ca-theme'));
const control = (page: Page) => page.locator('ca-theme-switch');

test('the default is contraagent Dark, on the page and on the monitor', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'contraagent-dark');
  expect(await theme(page)).toBe('contraagent-dark');
});

test('choosing a theme applies it and keeps it across a reload', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  await control(page).locator('.trig').click();
  const menu = control(page).locator('[role="menu"]');
  await expect(menu.locator('[role="menuitemradio"]')).toHaveText([
    'contraagent Dark',
    'contraagent Light',
    /System/,
    'GitHub Dark',
    'GitHub Light',
    'One Dark',
    'Nord',
    'High contrast',
  ]);
  await expect(menu.locator('[aria-checked="true"]')).toHaveText('contraagent Dark');
  await menu.locator('[data-theme="nord"]').click();
  await expect.poll(() => theme(page)).toBe('nord');
  await expect(page.locator('ca-monitor')).toHaveAttribute('data-ca-theme', 'nord');
  await expect(menu).toHaveCount(0);

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

test('System follows the colour scheme', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/?run=docs&tab=overview');
  await control(page).locator('.trig').click();
  await control(page).locator('[data-theme="system"]').click();
  await expect.poll(() => theme(page)).toBe('contraagent-light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect.poll(() => theme(page)).toBe('contraagent-dark');
});

test('the control works by keyboard', async ({ page }) => {
  await page.goto('/?run=docs&tab=overview');
  const trig = control(page).locator('.trig');
  await trig.focus();
  await page.keyboard.press('Enter');
  const checked = control(page).locator('[aria-checked="true"]');
  await expect(checked).toBeFocused();
  await page.keyboard.press('End');
  await expect(control(page).locator('[data-theme="high-contrast"]')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect.poll(() => theme(page)).toBe('high-contrast');
  await expect(trig).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(control(page).locator('[role="menu"]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(control(page).locator('[role="menu"]')).toHaveCount(0);
  await expect(trig).toBeFocused();
});

test('the control has its Japanese label', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('contraagent:locale', 'ja'));
  await page.goto('/?run=docs&tab=overview');
  await expect(control(page).locator('.trig')).toHaveText('テーマ');
  await control(page).locator('.trig').click();
  await expect(control(page).locator('[data-theme="system"]')).toContainText('システム設定に合わせる');
  await expect(control(page).locator('[data-theme="high-contrast"]')).toHaveText('ハイコントラスト');
  await expect(control(page).locator('[role="group"]')).toHaveAccessibleName('エディタのテーマ');
});
