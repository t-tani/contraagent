// Every element fits the width it is given: at 360, 600, 900 and 1280 px no box
// is wider than its own content box allows, except the boxes meant to scroll
// sideways (`data-scroll="x"`, e2e/fit.ts). Checked on the monitor's page over
// the demo runs (every tab, the trends page, a hub's hosts page), and on every
// page of the documentation site that shows live elements (apps/docs/dist,
// built by `pnpm build`), each element's frame set to the width. And axe finds
// no serious or critical violation in those live elements, in a light and a
// dark theme.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { overflows, settle } from './fit.js';

const WIDTHS = [360, 600, 900, 1280];
const HUB = `http://127.0.0.1:${Number(process.env['E2E_HUB_PORT'] ?? 18794)}`;
const DOCS = `http://127.0.0.1:${Number(process.env['E2E_DOCS_PORT'] ?? 18795)}`;

/** The monitor's places to check: each tab of a run, the task detail's views, the trends page. */
const PLACES = [
  ...['overview', 'tasks', 'journal', 'outputs', 'definitions', 'procs'].map((tab) => `/?run=docs&tab=${tab}`),
  '/?run=analyse&tab=overview',
  ...['transcript', 'input', 'output', 'definition'].map((view) => `/?run=docs&tab=stream&key=review-gamma&view=${view}`),
  '/?page=trends',
];

/** The monitor at `url`, drawn: its header names a run or a page, and its main view has content. */
async function openMonitor(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator('ca-monitor header .runbtn')).toBeVisible();
  await expect(page.locator('ca-monitor main#main > *').first()).toBeVisible();
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

/** The documentation pages that show live elements: the built site's pages (apps/docs/dist) with a live element's frame. */
function docsPages(): string[] {
  const dist = fileURLToPath(new URL('../apps/docs/dist/', import.meta.url));
  if (!existsSync(dist)) return [];
  return readdirSync(dist, { recursive: true, encoding: 'utf8' })
    .filter((f) => f.endsWith('index.html') && readFileSync(`${dist}${f}`, 'utf8').includes('class="ca-demo-frame"'))
    .map((f) => `/${f.slice(0, -'index.html'.length).split(sep).join('/')}`)
    .sort();
}

/** Each frame on the page at `width` px for its element, and wider than the page if it must be. */
async function frameAt(page: Page, width: number) {
  await page.locator('.ca-demo-frame').evaluateAll((frames, width) => {
    for (const f of frames as HTMLElement[]) {
      const cs = getComputedStyle(f);
      const sides = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth);
      Object.assign(f.style, { width: `${width + sides}px`, maxWidth: 'none', overflowX: 'visible' });
    }
  }, width);
  await settle(page);
}

/** The page at `path`, every live element on it drawn: a view's shadow root has content, an example has mounted. */
async function openDocs(page: Page, path: string) {
  await page.goto(`${DOCS}${path}`);
  await page.waitForLoadState('networkidle');
  await expect
    .poll(() =>
      page.locator('.ca-demo-frame').evaluateAll((frames) =>
        frames.every((f) => {
          const el = f.firstElementChild;
          return !!el && (!el.localName.startsWith('ca-') || (el.shadowRoot?.childElementCount ?? 0) > 0);
        }),
      ),
    )
    .toBe(true);
  const monitors = page.locator('.ca-demo-frame ca-monitor');
  for (let i = 0; i < (await monitors.count()); i++) await expect(monitors.nth(i).locator('header .runbtn')).toBeVisible();
  await settle(page);
}

const PAGES = docsPages();
test('the documentation site is built, with live elements', () => {
  expect(PAGES.length, 'run `pnpm build` first').toBeGreaterThan(0);
});

for (const path of PAGES) {
  test.describe(`documentation ${path}`, () => {
    for (const width of WIDTHS) {
      test(`its live elements fit ${width} px`, async ({ page }) => {
        test.setTimeout(90_000);
        await openDocs(page, path);
        await frameAt(page, width);
        const found = (await overflows(page, '.ca-demo-frame')).map((s) => `${s}`);
        // The whole monitor: each of its tabs (a frame wider than the page may lie under the page's sidebars).
        const monitor = page.locator('.ca-demo-frame ca-monitor').first();
        if (await monitor.count()) {
          const tabs = monitor.getByRole('tab');
          for (let i = 0; i < (await tabs.count()); i++) {
            await tabs.nth(i).dispatchEvent('click');
            await expect(tabs.nth(i)).toHaveAttribute('aria-selected', 'true');
            await page.waitForLoadState('networkidle');
            await settle(page);
            const name = (await tabs.nth(i).textContent())?.trim() ?? String(i);
            found.push(...(await overflows(page, '.ca-demo-frame:has(ca-monitor)')).map((s) => `[${name}] ${s}`));
          }
        }
        expect([...new Set(found)]).toEqual([]);
      });
    }

    // Each live element in a light and a dark theme.
    for (const theme of ['contraagent-light', 'contraagent-dark']) {
      test(`its live elements pass axe in ${theme}`, async ({ page }) => {
        test.setTimeout(60_000);
        await openDocs(page, path);
        await page.locator('.ca-demo').evaluateAll((figures, theme) => {
          for (const f of figures) {
            f.setAttribute('data-ca-theme', theme);
            f.classList.remove('solarized-light');
            f.querySelector('ca-monitor')?.setAttribute('theme', theme);
          }
        }, theme);
        await settle(page);
        const { violations } = await new AxeBuilder({ page }).include('.ca-demo-frame').analyze();
        const serious = violations
          .filter((v) => v.impact === 'serious' || v.impact === 'critical')
          .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => `${n.target.join(' > ')} ${n.failureSummary ?? ''}`).join(', ')}`);
        expect(serious).toEqual([]);
      });
    }
  });
}
