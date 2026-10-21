// The documentation site's landing page (apps/docs/dist, built by `pnpm build`): in
// the "how it works" scene, the rail behind the step numbers never paints over a
// number. At points across each number's glyph, the topmost element is the number,
// and nothing about the number lets the rail show through (its opacity, its fill):
// along the scroll through the scene, wide and narrow, light and dark, with motion
// and with reduced motion (where the rail is drawn full). In Firefox too, which has
// no scroll-driven animations (the scene's fallback), when Playwright's Firefox is
// installed.
//
// The replay's window fits one screen on a wide one: it starts once all of it is on
// the screen, where all of it is under the site's header, at 1280×720, 1366×768,
// 1440×900 and 1920×1080; and nothing in it is wider than its box or cut off at the
// bottom (./fit.ts), while it plays and at its last frame. The replay's clock is the
// test's (`page.clock`): what it shows at a time does not depend on the machine.
//
// On a phone (390×844 and 360×740, light and dark, with motion and with reduced
// motion): the page stays within a height budget and nothing in it is wider than the
// screen; the replay is one stage within the screen under the header, its tabs follow
// the run until the reader picks one, and its moments open from their disclosure; the
// steps are a carousel that scrolls a card at a time, by a swipe and by its buttons,
// whose long outputs open in full; a fast flick of a finger moves it one card, long
// or short, and a finger up or down scrolls the page; and its controls are at least
// 44 px high.
import { expect, firefox, test, type Browser, type Page } from '@playwright/test';
import { clips, overflows, settle } from './fit.js';
import { DOCS } from './docs-site.js';

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
      // A phone's steps are a carousel: a number on a card at the side, or off the screen, is not checked either.
      if (r.top < below || r.bottom > innerHeight || r.left < 0 || r.right > innerWidth || r.width === 0) continue;
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
    // The scroll-driven animations catch up in a frame or two; the fallback's transitions, which those frames start, then end.
    await settle(page);
    await page.evaluate(() =>
      Promise.allSettled(document.getAnimations().filter((a) => a instanceof CSSTransition).map((a) => a.finished)),
    );
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

/**
 * Stop the test's clock (`page.clock`) a second on: from there the page's timers and
 * requestAnimationFrame move only by `runFor`, so what the replay shows follows from
 * the test's steps alone, not from how fast the machine ran them.
 */
async function pause(page: Page): Promise<void> {
  await page.clock.pauseAt((await page.evaluate(() => Date.now())) + 1000);
}

/** Two of the browser's frames, counted by a resize observer: they come while the test's clock is paused, as requestAnimationFrame's do not. */
function frames(page: Page): Promise<void> {
  return page.evaluate(
    () =>
      new Promise<void>((done) => {
        const probe = document.createElement('div');
        probe.style.cssText = 'position: fixed; top: 0; left: 0; width: 0; height: 0; pointer-events: none';
        document.body.append(probe);
        let seen = 0;
        const observer = new ResizeObserver(() => {
          if (++seen === 1) {
            probe.style.width = '1px';
            return;
          }
          observer.disconnect();
          probe.remove();
          done();
        });
        observer.observe(probe);
      }),
  );
}

/** `settle` on a paused clock: the layout and the observers (two frames), 200 ms of the page's time, and two frames again. */
async function settleOnClock(page: Page): Promise<void> {
  await frames(page);
  await page.clock.runFor(200);
  await frames(page);
}

/** Scroll the page so that the foot of the replay's window is `fromFoot` px above the foot of the screen (the clock paused). */
async function windowFootAt(page: Page, fromFoot: number): Promise<void> {
  // Twice: the window rises as it comes on screen (a transform), and stands flat once all of it is on it.
  for (let i = 0; i < 2; i++) {
    await page.locator('.rr-window').evaluate((e, up) => {
      const bottom = e.getBoundingClientRect().bottom;
      window.scrollTo({ top: Math.round(scrollY + bottom - innerHeight + up), behavior: 'instant' });
    }, fromFoot);
    await settleOnClock(page);
  }
}

for (const [width, height] of [[1280, 720], [1366, 768], [1440, 900], [1920, 1080]] as const) {
  test(`the replay's window plays once all of it is on the screen at ${width}×${height}, under the header`, async ({ browser }) => {
    test.setTimeout(60_000);
    const context = await browser.newContext({ viewport: { width, height }, colorScheme: 'dark' });
    const page = await context.newPage();
    await page.clock.install();
    await page.goto(`${DOCS}/`);
    await page.waitForLoadState('networkidle');
    await pause(page);
    const replay = page.locator('.rr');
    // A third of the window below the screen: it has not started.
    const tall = await page.locator('.rr-window').evaluate((e) => (e as HTMLElement).offsetHeight);
    await windowFootAt(page, -Math.round(tall / 3));
    await expect(replay).not.toHaveClass(/rr-playing/);
    // All of it on the screen: it plays, and all of it is under the header.
    await windowFootAt(page, 0);
    await expect(replay).toHaveClass(/rr-playing/);
    const box = await windowBox(page);
    expect(box.top).toBeGreaterThanOrEqual(box.below);
    expect(box.bottom).toBeLessThanOrEqual(box.height);
    // Six seconds into the replay: the graph and the transcript have content, and nothing is cut off.
    await page.clock.runFor(6000);
    await frames(page);
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

/** The whole landing page on a phone, at most this tall (px): about seven screens of 844 px. */
const PHONE_BUDGET = 6000;
const PHONES = [[390, 844], [360, 740]] as const;

/**
 * A phone's page, its theme and motion, loaded, with the test's clock (`page.clock`)
 * unless `clock` is false: that clock also sets the times of the page's events, which
 * a finger's speed is measured by.
 */
async function phone(browser: Browser, [width, height]: readonly [number, number], colorScheme: 'light' | 'dark', reducedMotion: 'reduce' | 'no-preference', clock = true) {
  const context = await browser.newContext({ viewport: { width, height }, colorScheme, reducedMotion, hasTouch: true });
  await context.addInitScript((s) => localStorage.setItem('starlight-theme', s), colorScheme);
  const page = await context.newPage();
  if (clock) await page.clock.install();
  await page.goto(`${DOCS}/`);
  await page.waitForLoadState('networkidle');
  return { context, page };
}

/** The controls of the replay and of the steps shown on screen that are less than 44 px high, as `selector height`. */
async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const small: string[] = [];
    for (const sel of ['.rr-tabs [role="tab"]', '.rr-toggle', '.rr-more > summary', '.how-go', '.how-more', '.ca-primary', '.ca-secondary'])
      for (const e of document.querySelectorAll<HTMLElement>(sel)) {
        const r = e.getBoundingClientRect();
        if (r.width > 0 && r.height < 44) small.push(`${sel} ${Math.round(r.height)}`);
      }
    return small;
  });
}

for (const size of PHONES)
  for (const colorScheme of ['dark', 'light'] as const)
    for (const reducedMotion of ['no-preference', 'reduce'] as const)
      test(`the landing page fits a phone at ${size.join('×')}, ${colorScheme}, motion ${reducedMotion}`, async ({ browser }) => {
        const { context, page } = await phone(browser, size, colorScheme, reducedMotion);
        await pause(page);
        await settleOnClock(page);
        expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(PHONE_BUDGET);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size[0]);
        // The page's parts (not their lights and veils, which reach past them on purpose, nor the arrows between the loop's words).
        expect(await overflows(page, '.ca-hero-inner, .rr-window, .rr-more, .rr-lede, .how-lede, .how-steps, .how-nav, .ca-runner, .ca-start .sl-link-card')).toEqual([]);
        // The replay: one stage within the screen under the header, nothing in it cut off or too wide.
        await page.locator('.rr-window').evaluate((e) => e.scrollIntoView({ block: 'center' }));
        await settleOnClock(page);
        const box = await windowBox(page);
        expect(box.bottom - box.top).toBeLessThanOrEqual(box.height - box.below);
        expect(await misfits(page)).toEqual([]);
        expect(await smallTargets(page)).toEqual([]);
        await context.close();
      });

for (const size of PHONES)
  test(`on a phone at ${size.join('×')}, the replay's tabs follow the run until the reader picks one`, async ({ browser }) => {
    test.setTimeout(60_000);
    const { context, page } = await phone(browser, size, 'dark', 'no-preference');
    const tab = (name: string) => page.getByRole('tab', { name });
    await expect(page.getByRole('tablist', { name: 'Panels of the replay' })).toBeVisible();
    await expect(tab('Code')).toHaveAttribute('aria-selected', 'true');
    await page.locator('.rr-window').evaluate((e) => e.scrollIntoView({ block: 'center' }));
    // The run plays: the graph's tab, then the transcript's for a correction, without the reader.
    await expect(tab('Graph')).toHaveAttribute('aria-selected', 'true', { timeout: 15_000 });
    await expect(page.getByRole('tabpanel')).toHaveAttribute('id', 'rr-panel-graph');
    await expect(page.locator('.rr-graph ca-pipeline-graph')).toBeVisible();
    await expect(tab('Transcript')).toHaveAttribute('aria-selected', 'true', { timeout: 15_000 });
    // The reader picks the code, by the keyboard: it stays while the run plays on.
    await tab('Transcript').focus();
    await page.keyboard.press('Home');
    await expect(tab('Code')).toBeFocused();
    await expect(tab('Code')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#rr-panel-code')).toBeVisible();
    await expect(page.locator('#rr-panel-graph')).toBeHidden();
    await page.clock.runFor(5000);
    await expect(tab('Code')).toHaveAttribute('aria-selected', 'true');
    // The numbers: one row that scrolls sideways, a region the keyboard reaches.
    const strip = page.getByRole('region', { name: 'The run in numbers' });
    await expect(strip).toHaveAttribute('tabindex', '0');
    // Where the layout puts each tile (`offsetTop`): a tile whose value just changed grows a little for a moment (a transform).
    const tops = await page.locator('.rr-kpis ca-kpis').evaluate((e) => {
      const tiles: Element[] = [];
      const walk = (root: ParentNode): void => {
        for (const n of root.querySelectorAll('*')) {
          if (n.getAttribute('part')?.split(' ').includes('tile')) tiles.push(n);
          if (n.shadowRoot) walk(n.shadowRoot);
        }
      };
      walk(e.shadowRoot!);
      return tiles.map((t) => (t as HTMLElement).offsetTop);
    });
    expect(tops.length).toBeGreaterThan(3);
    expect(new Set(tops).size).toBe(1);
    // The moments: folded, and opened from their summary.
    const more = page.locator('.rr-more');
    await expect(more).not.toHaveAttribute('open');
    await expect(page.getByRole('list', { name: 'What happened in the run' })).toBeHidden();
    await more.locator('summary').click();
    await expect(page.getByRole('list', { name: 'What happened in the run' })).toBeVisible();
    await context.close();
  });

/**
 * Records where the steps' list is each time a scroll of it ends (`scrollend`), from now
 * on, for `restingStep`; the list stands where it was loaded. It also keeps the list's
 * last scrolls and changes of size, which a failed check shows (`Steps`).
 */
async function watchSteps(page: Page): Promise<void> {
  await page.locator('.how-steps').evaluate((list) => {
    const w = window as unknown as { stepsEnded: number; stepsLog: string[] };
    w.stepsEnded = list.scrollLeft;
    w.stepsLog = [];
    const log = (s: string): void => {
      w.stepsLog.push(`${Math.round(performance.now())} ${s}`);
      w.stepsLog.splice(0, w.stepsLog.length - 40);
    };
    list.addEventListener('scrollend', () => {
      w.stepsEnded = list.scrollLeft;
      log(`scrollend ${list.scrollLeft}`);
    });
    list.addEventListener('scroll', () => log(`scroll ${list.scrollLeft}`), { passive: true });
    new ResizeObserver(() => log(`size ${list.clientWidth}×${list.clientHeight} page ${document.documentElement.clientWidth}×${document.documentElement.scrollHeight}`)).observe(list);
  });
}

/**
 * The step the carousel shows, as its card's index (-1 when none is), and the facts it
 * was found from, which a failed check prints: where the list is and where it last
 * ended a scroll, its width and the page's, where each card snaps, the height of the
 * box around it (`--how-h`) and its last scrolls and changes of size (`watchSteps`).
 */
interface Steps {
  step: number;
  facts: Record<string, unknown>;
}

/**
 * The card whose snap position the list is at, within 2 px: its middle at the list's
 * middle or, for a card at an end, the list at that end. `resting`: only while the list
 * is where a scroll of it last ended (`watchSteps`).
 */
async function stepsAt(page: Page, resting: boolean): Promise<Steps> {
  return page.locator('.how-steps').evaluate((list, resting) => {
    const w = window as unknown as { stepsEnded?: number; stepsLog?: string[] };
    const mid = list.getBoundingClientRect().left + list.clientWidth / 2;
    const end = list.scrollWidth - list.clientWidth;
    const snaps = [...list.querySelectorAll('.how-step')].map((s) => {
      const r = s.getBoundingClientRect();
      return Math.max(0, Math.min(end, list.scrollLeft + r.left + r.width / 2 - mid));
    });
    const still = !resting || list.scrollLeft === w.stepsEnded;
    const facts = {
      scrollLeft: list.scrollLeft,
      stepsEnded: w.stepsEnded,
      listWidth: list.clientWidth,
      pageWidth: document.documentElement.clientWidth,
      innerWidth,
      snaps,
      howH: list.closest<HTMLElement>('.how-steps-box')?.style.getPropertyValue('--how-h'),
      log: w.stepsLog,
    };
    return { step: still ? snaps.findIndex((x) => Math.abs(x - list.scrollLeft) <= 2) : -1, facts };
  }, resting);
}

/** The card at its snap position, whether or not the list is still moving. */
const centredStep = (page: Page): Promise<Steps> => stepsAt(page, false);
/** The card the steps' list rests on: at that card's snap position, where a scroll of it last ended. */
const restingStep = (page: Page): Promise<Steps> => stepsAt(page, true);

/**
 * Waits until `read` finds card `step`; a failure carries the facts read after it, since a
 * comparison of the step alone prints only the step.
 */
async function expectStep(page: Page, read: (page: Page) => Promise<Steps>, step: number): Promise<void> {
  try {
    await expect.poll(async () => (await read(page)).step).toBe(step);
  } catch (error) {
    throw new Error(`${(error as Error).message}\nfacts: ${JSON.stringify((await read(page)).facts, null, 2)}`);
  }
}

for (const size of PHONES)
  for (const reducedMotion of ['no-preference', 'reduce'] as const)
    test(`on a phone at ${size.join('×')}, motion ${reducedMotion}, the steps scroll a card at a time`, async ({ browser }) => {
      test.setTimeout(60_000);
      const { context, page } = await phone(browser, size, 'light', reducedMotion);
      await watchSteps(page);
      const list = page.locator('.how-steps');
      const count = page.locator('.how-at');
      const prev = page.getByRole('button', { name: 'Previous step' });
      const next = page.getByRole('button', { name: 'Next step' });
      await list.scrollIntoViewIfNeeded();
      await expect(page.getByRole('group', { name: 'Steps' })).toBeVisible();
      await expect(count).toHaveText(/^Step 1 of 7: Install contraagent$/);
      await expect(prev).toHaveAttribute('aria-disabled', 'true');
      // The buttons: a card at a time, the loop lighting up to the card's step.
      await next.click();
      await expect(count).toContainText('Step 2 of 7');
      await expectStep(page, centredStep, 1);
      for (let k = 2; k < 7; k++) await next.click();
      await expect(count).toContainText('Step 7 of 7');
      await expect(next).toHaveAttribute('aria-disabled', 'true');
      await expect(page.locator('.how-loop-step.is-on')).toHaveCount(5);
      // The keyboard: the button before, by Enter; the scroll below comes once the list rests there.
      await prev.focus();
      await page.keyboard.press('Enter');
      await expect(count).toContainText('Step 6 of 7');
      await expect(page.locator('.how-loop-step.is-on')).toHaveCount(4);
      await expectStep(page, restingStep, 5);
      // A scroll the steps did not start, part of a card back (a trackpad's, or a script's): the
      // list snaps to the card before, not between two, and that card is the step.
      const width = await page.locator('.how-step').first().evaluate((e) => (e as HTMLElement).offsetWidth);
      await list.evaluate((e, dx) => e.scrollBy({ left: dx, behavior: 'instant' }), Math.round(-width * 0.6));
      await expectStep(page, restingStep, 4);
      await expect(count).toContainText('Step 5 of 7');
      // A long output: cut, and open in full from its button.
      const card = page.locator('.how-step').nth(4);
      const stage = card.locator('.how-stage');
      const full = card.getByRole('button', { name: 'Show full output' });
      await expect(full).toBeVisible();
      await expect(full).toHaveAttribute('aria-expanded', 'false');
      expect(await stage.evaluate((e) => e.scrollHeight > e.clientHeight + 1)).toBe(true);
      await full.click();
      await expect(card.locator('.how-more')).toHaveAttribute('aria-expanded', 'true');
      await expect(card.locator('.how-more')).toHaveText('Hide full output');
      expect(await stage.evaluate((e) => e.scrollHeight <= e.clientHeight + 1)).toBe(true);
      // The box around the list is as tall as the card on screen: the buttons right under it.
      const [cardBottom, navTop] = await page.evaluate(() => [
        document.querySelectorAll('.how-step')[4]!.getBoundingClientRect().bottom,
        document.querySelector('.how-nav')!.getBoundingClientRect().top,
      ]);
      expect(navTop - cardBottom).toBeLessThan(40);
      // A short output has no button.
      await expect(page.locator('.how-step').first().locator('.how-more')).toBeHidden();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size[0]);
      await context.close();
    });

/**
 * A finger on the steps (touch, through the Chrome DevTools Protocol): down, `dx` px
 * sideways and `dy` px down in four moves `ms` apart, and up. The events carry the
 * finger's times, so the page measures the same speed on any machine (on a page
 * without the test's clock).
 */
async function drag(page: Page, dx: number, dy: number, ms: number): Promise<void> {
  const cdp = await page.context().newCDPSession(page);
  const box = (await page.locator('.how-steps').boundingBox())!;
  const [x, y] = [box.x + box.width / 2 - dx / 2, box.y + Math.min(120, box.height / 2) - dy / 2];
  let at = Date.now() / 1000;
  const touch = (type: 'touchStart' | 'touchMove' | 'touchEnd', touchPoints: { x: number; y: number }[]) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints, timestamp: at });
  await touch('touchStart', [{ x, y }]);
  for (let i = 1; i <= 4; i++) {
    at += ms / 1000;
    await touch('touchMove', [{ x: x + (dx * i) / 4, y: y + (dy * i) / 4 }]);
  }
  at += ms / 1000;
  await touch('touchEnd', []);
  await cdp.detach();
}

for (const size of PHONES)
  for (const reducedMotion of ['no-preference', 'reduce'] as const)
    test(`on a phone at ${size.join('×')}, motion ${reducedMotion}, a flick moves the steps one card`, async ({ browser }) => {
      test.setTimeout(60_000);
      const { context, page } = await phone(browser, size, 'light', reducedMotion, false);
      await watchSteps(page);
      const list = page.locator('.how-steps');
      const count = page.locator('.how-at');
      await list.evaluate((e) => e.scrollIntoView({ block: 'center' }));
      await expect(count).toContainText('Step 1 of 7');
      // A flick of 300 px in 40 ms, which the browser's own momentum carries two cards on: one card, either way.
      for (const [dx, step] of [[-300, 2], [-300, 3], [-300, 4], [300, 3], [300, 2], [300, 1]] as const) {
        await drag(page, dx, 0, 8);
        await expectStep(page, restingStep, step - 1);
        await expect(count).toContainText(`Step ${step} of 7`);
        await expect(list).not.toHaveClass(/is-swiped/);
      }
      // The first card is at the list's start, not its middle.
      expect(await list.evaluate((e) => e.scrollLeft)).toBe(0);
      // A short flick, fast: on to the next card; as short, slow: back to the card it began on.
      await drag(page, -60, 0, 8);
      await expectStep(page, restingStep, 1);
      await drag(page, -60, 0, 80);
      await expectStep(page, restingStep, 1);
      await expect(count).toContainText('Step 2 of 7');
      await expect(list).not.toHaveClass(/is-swiped/);
      // A finger up the steps scrolls the page, not the steps.
      const top = await page.evaluate(() => window.scrollY);
      await drag(page, 0, -200, 16);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(top + 100);
      const after = await restingStep(page);
      expect(after.step, `facts: ${JSON.stringify(after.facts, null, 2)}`).toBe(1);
      await context.close();
    });
