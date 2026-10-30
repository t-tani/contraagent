// The monitor on a phone: its header is one line; a task opens on its views, the
// transcript taking most of the screen, and the rest about the task opens from its
// line of facts; a definition opens under its kind; the history keeps to the width
// of the screen. On a desktop, the rest about a task stands beside its views.
import { expect, test, type Page } from '@playwright/test';

const PHONE = { width: 390, height: 664 };

/** The monitor's view (`main`), the transcript (its round picker and its scroller) and how far the view scrolls. */
async function boxes(page: Page) {
  const main = page.locator('ca-monitor main');
  await expect(page.locator('cae-transcript .scroller')).toBeVisible();
  return {
    main: (await main.boundingBox())!,
    transcript: (await page.locator('ca-transcript').boundingBox())!,
    scroll: await main.evaluate((m) => m.scrollHeight - m.clientHeight),
  };
}

test('a phone: the header is one line', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/?run=docs');
  const header = page.locator('ca-monitor header');
  await expect(header.locator('.runbtn')).toBeVisible();
  expect((await header.boundingBox())!.height).toBeLessThan(60);
  // The language: one button, which switches to the other one.
  await expect(header.locator('.langs')).toBeHidden();
  await header.locator('.lang-next').click();
  await expect(page.locator('html')).toHaveAttribute('lang', /ja/);
});

test('a phone upright: a task opens on its transcript, which takes most of the screen, and the view does not scroll', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/?run=docs&tab=stream&key=summarize-beta');
  const { main, transcript, scroll } = await boxes(page);
  expect(scroll).toBeLessThanOrEqual(1);
  expect(transcript.height).toBeGreaterThan(main.height * 0.6);
  // The rest about the task opens from the line of facts, and closes again.
  const facts = page.locator('ca-task-view .tm-toggle');
  const more = page.locator('ca-task-view .tm-more');
  await expect(more).toBeHidden();
  await facts.click();
  await expect(facts).toHaveAttribute('aria-expanded', 'true');
  await expect(more).toBeVisible();
  await expect(more.locator('.runchip')).not.toHaveCount(0);
  await facts.click();
  await expect(more).toBeHidden();
});

test('a phone on its side: the transcript fills the view once the header is scrolled past', async ({ page }) => {
  await page.setViewportSize({ width: 844, height: 340 });
  await page.goto('/?run=docs&tab=stream&key=summarize-beta');
  await expect(page.locator('cae-transcript .scroller')).toBeVisible();
  await page.locator('ca-monitor main').evaluate((m) => (m.scrollTop = m.scrollHeight));
  const { main, transcript } = await boxes(page);
  // Above it are only the view tabs (44px) and the view's padding (28px).
  expect(transcript.height).toBeGreaterThanOrEqual(main.height - 80);
  expect(transcript.y + transcript.height).toBeLessThanOrEqual(main.y + main.height);
});

test('a desktop: the rest about a task stands beside its views, and the view does not scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/?run=docs&tab=stream&key=summarize-beta');
  const { transcript, scroll } = await boxes(page);
  expect(scroll).toBeLessThanOrEqual(1);
  const more = page.locator('ca-task-view .tm-more');
  await expect(more).toBeVisible();
  await expect(page.locator('ca-task-view .tm-toggle')).toBeHidden();
  expect((await more.boundingBox())!.x).toBeGreaterThan(transcript.x + transcript.width);
});

test('a phone: a definition opens under its kind, and a second tap closes it', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/?run=docs&tab=definitions');
  const items = page.locator('ca-definitions .defitem');
  const panel = page.locator('ca-definitions section.panel');
  await expect(items.first()).toBeVisible();
  await expect(panel).toBeHidden();
  const item = items.last();
  await item.click();
  await expect(panel).toBeVisible();
  const at = (await item.boundingBox())!;
  const p = (await panel.boundingBox())!;
  expect(p.y).toBeGreaterThan(at.y);
  expect(p.y - (at.y + at.height)).toBeLessThan(20);
  await item.click();
  await expect(panel).toBeHidden();
});

test('a phone: picking a definition keeps the list where it was', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 300 });
  await page.goto('/?run=docs&tab=definitions');
  const main = page.locator('ca-monitor main');
  const item = page.locator('ca-definitions .defitem').last();
  await item.scrollIntoViewIfNeeded();
  const top = await main.evaluate((m) => m.scrollTop);
  expect(top).toBeGreaterThan(0);
  await item.click();
  await expect(page).toHaveURL(/def=/);
  await expect(item).toBeInViewport();
  expect(await main.evaluate((m) => m.scrollTop)).toBeGreaterThanOrEqual(top);
});

test('a phone: the history is as wide as the screen', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto('/?run=docs&tab=journal');
  const row = page.locator('ca-journal-table tbody tr').first();
  await expect(row).toBeVisible();
  expect((await row.boundingBox())!.width).toBeLessThanOrEqual(PHONE.width);
});
