// The documentation site's landing page (apps/docs/dist, built by `pnpm build`): in
// the "how it works" scene, the rail behind the step numbers never paints over a
// number. At points across each number's glyph, the topmost element is the number,
// and nothing about the number lets the rail show through (its opacity, its fill):
// along the scroll through the scene, wide and narrow, light and dark, with motion
// and with reduced motion (where the rail is drawn full). In Firefox too, which has
// no scroll-driven animations (the scene's fallback), when Playwright's Firefox is
// installed.
import { expect, firefox, test, type Page } from '@playwright/test';

const DOCS = `http://127.0.0.1:${Number(process.env['E2E_DOCS_PORT'] ?? 18795)}`;

/** Fractions of the scroll from just before the scene to just after it. */
const ALONG = [0, 0.1, 0.22, 0.35, 0.5, 0.62, 0.75, 0.88, 1];

/** Each number in view whose glyph is covered by something else, and why; [] when every number is intact. */
async function coveredNumbers(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const bad: string[] = [];
    // The site's header is fixed over the page: a number under it, or out of view, is not checked.
    const below = document.querySelector('header.header')?.getBoundingClientRect().bottom ?? 0;
    for (const n of document.querySelectorAll<HTMLElement>('.how-n')) {
      const r = n.getBoundingClientRect();
      if (r.top < below || r.bottom > innerHeight || r.width === 0) continue;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      // The glyph's area: its centre and four points around it, inside the fill.
      for (const [dx, dy] of [[0, 0], [-4, 0], [4, 0], [0, -5], [0, 5]] as const) {
        const top = document.elementFromPoint(cx + dx, cy + dy);
        if (!top || !n.contains(top)) bad.push(`${n.textContent}: ${top?.className || top?.localName || 'nothing'} on top at ${dx},${dy}`);
      }
      for (let el: Element | null = n; el && el !== document.body; el = el.parentElement)
        if (Number(getComputedStyle(el).opacity) < 1) bad.push(`${n.textContent}: ${el.className} has opacity ${getComputedStyle(el).opacity}`);
      const fill = getComputedStyle(n).backgroundColor;
      if (/\/\s*0?\.\d|rgba\([^)]*,\s*0?\.\d+\)/.test(fill)) bad.push(`${n.textContent}: its fill is not opaque (${fill})`);
    }
    return bad;
  });
}

async function alongTheScene(page: Page): Promise<string[]> {
  await page.goto(`${DOCS}/`);
  await page.waitForLoadState('networkidle');
  const [from, to] = await page.evaluate(() => {
    const how = document.querySelector<HTMLElement>('.how')!;
    const top = how.getBoundingClientRect().top + scrollY;
    return [top - innerHeight / 2, top + how.offsetHeight - innerHeight / 2];
  });
  const found: string[] = [];
  for (const f of ALONG) {
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'instant' }), Math.round(from + (to - from) * f));
    // Two frames: the scroll-driven animations (or the fallback's transitions, which take up to 0.6 s) catch up.
    await page.waitForTimeout(700);
    found.push(...(await coveredNumbers(page)).map((s) => `${Math.round(f * 100)}%: ${s}`));
  }
  return found;
}

for (const width of [1280, 390])
  for (const colorScheme of ['dark', 'light'] as const)
    for (const reducedMotion of ['no-preference', 'reduce'] as const)
      test(`the scene's numbers stay on top of the rail at ${width} px, ${colorScheme}, motion ${reducedMotion}`, async ({ browser }) => {
        test.setTimeout(60_000);
        const context = await browser.newContext({ viewport: { width, height: 800 }, colorScheme, reducedMotion });
        await context.addInitScript((s) => localStorage.setItem('starlight-theme', s), colorScheme);
        const page = await context.newPage();
        expect(await alongTheScene(page)).toEqual([]);
        if (reducedMotion === 'reduce') {
          // At rest, the rail is drawn full.
          const scale = await page.locator('.how-rail-fill').evaluate((e) => getComputedStyle(e).transform);
          expect(['none', 'matrix(1, 0, 0, 1, 0, 0)']).toContain(scale);
        }
        await context.close();
      });

test("in Firefox (the scene's fallback), the numbers stay on top of the rail", async () => {
  test.setTimeout(60_000);
  let ff;
  try {
    ff = await firefox.launch();
  } catch {
    test.skip(true, "Playwright's Firefox is not installed");
    return;
  }
  for (const width of [1280, 390]) {
    const page = await ff.newPage({ viewport: { width, height: 800 } });
    expect(await alongTheScene(page)).toEqual([]);
    await page.close();
  }
  await ff.close();
});
