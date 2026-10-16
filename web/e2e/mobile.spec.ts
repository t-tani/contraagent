// Every page of the documentation site but the landing page (apps/docs/dist, built by
// `pnpm build`) on a phone, at 360 px in the light theme and at 390 px in the dark one:
// - the page is no wider than the screen, and nothing on it, the live elements as they are drawn
//   there included, is wider than its box (./fit.ts), but for the boxes meant to scroll sideways:
//   a code block (Expressive Code's `pre`) and a table of two columns (`data-scroll="x"`);
// - no text is smaller than 14 px, a card's column names included (`td[data-label]::before`),
//   except inside a live element's frame, whose elements size their own text;
// - whatever is tapped is at least 44 px tall and wide, but for a link inside a line of text
//   (WCAG 2.5.8's inline exception) and a heading's link to itself (Starlight widens where it is
//   tapped with its ::after); in the header, the "On this page" list and the menu too;
// - a live element that scrolls inside itself (a long list, the monitor) is shorter than the screen
//   under the header, so the page can still be scrolled beside it.
import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync } from 'node:fs';
import { sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { overflows, settle } from './fit.js';

const DOCS = `http://127.0.0.1:${Number(process.env['E2E_DOCS_PORT'] ?? 18795)}`;
const PHONES = [
  { width: 360, height: 740, colorScheme: 'light' },
  { width: 390, height: 844, colorScheme: 'dark' },
] as const;

/** Every page of the built site but the landing page. */
function pages(): string[] {
  const dist = fileURLToPath(new URL('../apps/docs/dist/', import.meta.url));
  if (!existsSync(dist)) return [];
  return readdirSync(dist, { recursive: true, encoding: 'utf8' })
    .filter((f) => f.endsWith(`${sep}index.html`))
    .map((f) => `/${f.slice(0, -'index.html'.length).split(sep).join('/')}`)
    .sort();
}

/** The page at `path`, its live elements drawn. */
async function open(page: Page, path: string) {
  await page.goto(`${DOCS}${path}`);
  await page.waitForLoadState('networkidle');
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.querySelectorAll('.ca-demo-frame')].every((f) => {
          const el = f.firstElementChild;
          return !!el && (!el.localName.startsWith('ca-') || (el.shadowRoot?.childElementCount ?? 0) > 0);
        }),
      ),
    )
    .toBe(true);
  // A code block scrolls sideways inside itself: Expressive Code's own box.
  await page.evaluate(() => document.querySelectorAll('.expressive-code pre').forEach((p) => p.setAttribute('data-scroll', 'x')));
  await settle(page);
}

/** Text smaller than 14 px outside the live elements' frames, as `size "text"`. */
function smallText(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const found: string[] = [];
    const main = document.querySelector('main')!;
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!n.textContent?.trim() || !el || el.closest('.ca-demo-frame, .sr-only')) continue;
      if (!el.getClientRects().length) continue;
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (size < 14) found.push(`${size}px "${n.textContent.trim().slice(0, 40)}"`);
    }
    for (const td of main.querySelectorAll('td[data-label]')) {
      const label = getComputedStyle(td, '::before');
      if (td.getClientRects().length && label.content !== 'none' && parseFloat(label.fontSize) < 14)
        found.push(`${label.fontSize} "${td.getAttribute('data-label')}" (a card's column name)`);
    }
    return [...new Set(found)];
  });
}

/** What is tapped under `selector` and is smaller than 44 px, as `width×height "name"`. */
function smallTargets(page: Page, selector: string): Promise<string[]> {
  return page.evaluate((selector) => {
    const found: string[] = [];
    for (const root of document.querySelectorAll(selector))
      for (const e of root.querySelectorAll<HTMLElement>('a[href], button, summary, input, select')) {
        if (e.closest('.ca-demo-frame, .sl-skip-link') || e.classList.contains('sl-anchor-link')) continue;
        const r = e.getBoundingClientRect();
        if (!r.width || !r.height || getComputedStyle(e).visibility === 'hidden') continue;
        // A link inside a line of text.
        if (getComputedStyle(e).display === 'inline' && e.closest('p, li, td, dd, figcaption')) continue;
        if (r.width < 44 || r.height < 44)
          found.push(`${Math.round(r.width)}×${Math.round(r.height)} "${(e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 40)}"`);
      }
    return [...new Set(found)];
  }, selector);
}

const PAGES = pages().filter((p) => p !== '/');
test('the documentation site is built', () => {
  expect(PAGES.length, 'run `pnpm build` first').toBeGreaterThan(0);
});

test.describe.configure({ mode: 'parallel' });

for (const { width, height, colorScheme } of PHONES) {
  test.describe(`on a phone ${width} px wide, ${colorScheme}`, () => {
    test.use({ viewport: { width, height }, colorScheme, hasTouch: true });
    test.beforeEach(async ({ context }) => {
      await context.addInitScript((s) => localStorage.setItem('starlight-theme', s), colorScheme);
    });

    for (const path of PAGES) {
      test(`${path} fits, reads and taps`, async ({ page }) => {
        test.setTimeout(60_000);
        await open(page, path);
        const wide = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        expect(wide, 'the page is wider than the screen').toBeLessThanOrEqual(0);
        // The monitor on a page of its own (/demo/monitor/): the monitor's own fit is fit.spec.ts's.
        if (!(await page.locator('div.page main').count())) return;
        const misfits = (await overflows(page, 'main')).filter((s) => !s.includes('sl-anchor-link'));
        expect(misfits, 'boxes wider than they are').toEqual([]);
        expect(await smallText(page), 'text smaller than 14 px').toEqual([]);
        expect(await smallTargets(page, 'header, main'), 'targets smaller than 44 px').toEqual([]);

        // What scrolls inside itself leaves room beside it to scroll the page.
        const tall = await page.evaluate(() => {
          const below = document.querySelector('mobile-starlight-toc nav')?.getBoundingClientRect().bottom ?? document.querySelector('header')!.getBoundingClientRect().bottom;
          return [...document.querySelectorAll<HTMLElement>(".ca-demo-frame[data-scroll='y'], .ca-demo-frame[style*='--ca-demo-height']")]
            .filter((f) => f.getBoundingClientRect().height > innerHeight - below)
            .map((f) => `${f.firstElementChild?.localName} ${Math.round(f.getBoundingClientRect().height)}px`);
        });
        expect(tall, 'frames that scroll and are as tall as the screen').toEqual([]);

        // The "On this page" list, open.
        const toc = page.locator('mobile-starlight-toc summary');
        if (await toc.isVisible()) {
          await toc.click();
          expect(await smallTargets(page, 'mobile-starlight-toc'), 'targets smaller than 44 px in "On this page"').toEqual([]);
        }
      });
    }

    test('the menu fits and taps', async ({ page }) => {
      for (const path of ['/python/', '/node/ui/', '/reference/ui/']) {
        await open(page, path);
        await page.locator('.sl-menu-button').click();
        await expect(page.locator('#starlight__sidebar')).toBeVisible();
        expect(await smallTargets(page, '#starlight__sidebar'), `${path}: targets smaller than 44 px in the menu`).toEqual([]);
        // Starlight's theme select reaches past its label on purpose (negative margins), into the menu's room.
        const misfits = (await overflows(page, '#starlight__sidebar')).filter((s) => !s.includes('starlight-theme-select'));
        expect(misfits, `${path}: boxes wider than they are in the menu`).toEqual([]);
      }
    });
  });
}
