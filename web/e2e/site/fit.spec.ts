// Every live element of the documentation site fits the width it is given: on every
// page that shows live elements (apps/docs/dist, built by `pnpm build`), each
// element's frame set to 360, 600, 900 and 1280 px, no box is wider than its own
// content box allows, except the boxes meant to scroll sideways (`data-scroll="x"`,
// ../fit.ts), and nothing is cut off at the bottom: no frame is shorter than what it
// shows, and no box in it clips what is taller than it; in the graph view and in the
// table view of each element that has the switch. And axe finds no serious or
// critical violation in those live elements, in a light and a dark theme. The
// monitor's own page is ../fit.spec.ts's.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clips, overflows, settle } from '../fit.js';
import { DOCS } from './docs-site.js';

const WIDTHS = [360, 600, 900, 1280];

/** The documentation pages that show live elements: the built site's pages (apps/docs/dist) with a live element's frame. */
function docsPages(): string[] {
  const dist = fileURLToPath(new URL('../../apps/docs/dist/', import.meta.url));
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

/** Choose the graph or the table in every "Graph | Table" switch in the frames (a graph's, inside a view too); how many there are. */
function showView(page: Page, view: 'graph' | 'table'): Promise<number> {
  return page.locator('.ca-demo-frame').evaluateAll((frames, view) => {
    let n = 0;
    const visit = (root: Element | ShadowRoot): void => {
      for (const el of root.querySelectorAll('*')) {
        if (el.localName === 'cae-segmented' && el.classList.contains('views')) {
          el.shadowRoot?.querySelectorAll('button')[view === 'graph' ? 0 : 1]?.click();
          n++;
        }
        if (el.shadowRoot) visit(el.shadowRoot);
      }
    };
    for (const f of frames) visit(f);
    return n;
  }, view);
}

/** What does not fit in the frames, sideways and downwards. */
async function misfits(page: Page, selector = '.ca-demo-frame'): Promise<string[]> {
  return [...(await overflows(page, selector)), ...(await clips(page, selector))];
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
        const found = await misfits(page);
        // The table view of each element with a "Graph | Table" switch, then the graph again.
        if (await showView(page, 'table')) {
          await settle(page);
          found.push(...(await misfits(page)).map((s) => `[table] ${s}`));
          await showView(page, 'graph');
          await settle(page);
        }
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
            found.push(...(await misfits(page, '.ca-demo-frame:has(ca-monitor)')).map((s) => `[${name}] ${s}`));
          }
        }
        expect([...new Set(found)]).toEqual([]);
      });
    }

    // Each live element in a light and a dark theme.
    for (const theme of ['contraagent-light', 'contraagent-dark']) {
      test(`its live elements pass axe in ${theme}`, async ({ page }) => {
        test.setTimeout(60_000);
        // axe reads colours: none of them mid-way through the theme's transition or a fade.
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await openDocs(page, path);
        // One analysis of every frame (one per frame costs several times more); its time grows with the frames:
        // about 0.8 s each alone (24 frames, 18 s), so the budget is a guard against a hang, not a race with the machine.
        test.setTimeout(30_000 + (await page.locator('.ca-demo-frame').count()) * 5_000);
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
