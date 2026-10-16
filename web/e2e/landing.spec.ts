// The documentation site's landing page (apps/docs/dist, built by `pnpm build`): in
// the "how it works" scene, the rail behind the step numbers never paints over a
// number. At points across each number's glyph, the topmost element is the number,
// and nothing about the number lets the rail show through (its opacity, its fill):
// along the scroll through the scene, wide and narrow, light and dark, with motion
// and with reduced motion (where the rail is drawn full). In Firefox too, which has
// no scroll-driven animations (the scene's fallback), when Playwright's Firefox is
// installed.
//
// The replay's window fits one screen on a wide one: once the scroll has settled it
// (when the replay starts), all of it is under the site's header and above the foot
// of the screen, at 1280×720, 1366×768, 1440×900 and 1920×1080; and nothing in it is
// wider than its box or cut off at the bottom (./fit.ts), while it plays and at its
// last frame.
import { expect, firefox, test, type Page } from '@playwright/test';
import { clips, overflows, settle } from './fit.js';

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

/** The replay's window against the screen: its box, the header's foot and the screen's height. */
async function windowBox(page: Page): Promise<{ top: number; bottom: number; below: number; height: number }> {
  return page.evaluate(() => {
    const r = document.querySelector('.rr-window')!.getBoundingClientRect();
    const below = document.querySelector('header.header')?.getBoundingClientRect().bottom ?? 0;
    return { top: r.top, bottom: r.bottom, below, height: innerHeight };
  });
}

/** What is cut off or too wide in the replay's window. */
async function misfits(page: Page): Promise<string[]> {
  return [...(await overflows(page, '.rr-window')), ...(await clips(page, '.rr-window'))];
}

for (const [width, height] of [[1280, 720], [1366, 768], [1440, 900], [1920, 1080]] as const) {
  test(`the replay's window fits the screen at ${width}×${height} once the scroll has settled it`, async ({ browser }) => {
    test.setTimeout(60_000);
    const context = await browser.newContext({ viewport: { width, height }, colorScheme: 'dark' });
    const page = await context.newPage();
    await page.goto(`${DOCS}/`);
    await page.waitForLoadState('networkidle');
    // A reader's scroll, a step at a time, until the replay starts.
    for (let i = 0; i < 200 && !(await page.locator('.rr.rr-playing').count()); i++) {
      await page.mouse.wheel(0, 40);
      await page.waitForTimeout(20);
    }
    await expect(page.locator('.rr')).toHaveClass(/rr-playing/);
    // The scroll comes to rest (and snaps, the browser's proximity snap).
    await expect.poll(async () => {
      const y = await page.evaluate(() => scrollY);
      await page.waitForTimeout(250);
      return (await page.evaluate(() => scrollY)) === y;
    }).toBe(true);
    await settle(page);
    const box = await windowBox(page);
    expect(box.top).toBeGreaterThanOrEqual(box.below);
    expect(box.bottom).toBeLessThanOrEqual(box.height);
    // While it plays: the graph and the transcript have content.
    await page.waitForTimeout(6000);
    expect(await misfits(page)).toEqual([]);
    await context.close();
  });

  test(`the replay's last frame fits its window at ${width}×${height}`, async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width, height }, colorScheme: 'light', reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.goto(`${DOCS}/`);
    await page.waitForLoadState('networkidle');
    await page.locator('.rr-window').evaluate((e) => e.scrollIntoView({ block: 'end' }));
    await settle(page);
    const box = await windowBox(page);
    expect(box.bottom - box.top).toBeLessThanOrEqual(box.height - box.below);
    expect(await misfits(page)).toEqual([]);
    await context.close();
  });
}
