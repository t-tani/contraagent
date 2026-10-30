// The monitor on a phone: a task's header scrolls away above the transcript,
// which then fills the view, upright or on its side; the history keeps to the
// width of the screen.
import { expect, test, type Page } from '@playwright/test';

/** The transcript (its round picker and its scroller) and the view (`main`) around it, once the view is scrolled to its end. */
async function atEnd(page: Page) {
  const main = page.locator('ca-monitor main');
  await expect(page.locator('cae-transcript .scroller')).toBeVisible();
  await main.evaluate((m) => (m.scrollTop = m.scrollHeight));
  return { main: (await main.boundingBox())!, transcript: (await page.locator('ca-transcript').boundingBox())! };
}

for (const [name, size] of [
  ['upright', { width: 390, height: 664 }],
  ['on its side', { width: 844, height: 340 }],
] as const) {
  test(`a phone ${name}: the transcript fills the view once the header is scrolled past`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto('/?run=docs&tab=stream&key=summarize-beta');
    const { main, transcript } = await atEnd(page);
    // Above it are only the view tabs (44px) and the view's padding (28px).
    expect(transcript.height).toBeGreaterThanOrEqual(main.height - 80);
    expect(transcript.y + transcript.height).toBeLessThanOrEqual(main.y + main.height);
  });
}

test('a desktop: the header and the transcript share the view, which does not scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/?run=docs&tab=stream&key=summarize-beta');
  await expect(page.locator('cae-transcript .scroller')).toBeVisible();
  const main = page.locator('ca-monitor main');
  expect(await main.evaluate((m) => m.scrollHeight - m.clientHeight)).toBeLessThanOrEqual(1);
});

test('a phone: the history is as wide as the screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto('/?run=docs&tab=journal');
  const row = page.locator('ca-journal-table tbody tr').first();
  await expect(row).toBeVisible();
  // The table draws its rows again as the run's records arrive: measure a row that is there.
  await expect.poll(async () => (await row.boundingBox())?.width ?? Infinity).toBeLessThanOrEqual(390);
});
