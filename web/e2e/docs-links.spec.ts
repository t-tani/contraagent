// The documentation site is served under a base path (apps/docs/site.ts), as the
// tests serve it (./docs-site.ts):
// - in the built site (apps/docs/dist, built by `pnpm build`), every link and file
//   reference of a page (an attribute that is a path from the server's root, an `href`
//   or a `src` relative to the page) and every `url()` of a stylesheet is under the
//   base and names a file of the site;
// - on the landing page, the element gallery, the monitor's page, a reference page and
//   a topic of the Python package, and in the search, the browser requests nothing
//   outside the base and nothing that is not found, and every link on the page, the
//   ones the live elements draw included, stays under the base.
import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { BASE, DOCS } from './docs-site.js';

const DIST = fileURLToPath(new URL('../apps/docs/dist/', import.meta.url));
/** An origin for resolving the site's URLs; only the path matters. */
const ORIGIN = 'http://site.invalid';

/** The built site's files of one kind, as paths relative to dist with `/`. */
function files(suffix: string): string[] {
  if (!existsSync(DIST)) return [];
  return readdirSync(DIST, { recursive: true, encoding: 'utf8' })
    .filter((f) => f.endsWith(suffix))
    .map((f) => f.split(sep).join('/'))
    .sort();
}

/** The URL path a file of dist is served at: a page's directory for its index.html. */
const served = (file: string): string => `${BASE}/${file.replace(/(^|\/)index\.html$/, '$1')}`;

/** Why the path `pathname` of the site names nothing, or undefined when it names a file (a page's directory, or a directory of files with `directory`). */
function missing(pathname: string, directory: boolean): string | undefined {
  if (pathname !== BASE && !pathname.startsWith(`${BASE}/`)) return 'outside the base';
  const file = `${DIST}${decodeURIComponent(pathname.slice(BASE.length + 1))}`;
  if (existsSync(file) && statSync(file).isFile()) return undefined;
  if (existsSync(`${file.replace(/\/?$/, '/')}index.html`)) return undefined;
  if (directory && existsSync(file) && statSync(file).isDirectory()) return undefined;
  return 'no file of the site';
}

/** Each attribute of each tag in `html`, outside scripts and styles. */
function* attributes(html: string): Generator<{ tag: string; name: string; value: string }> {
  const markup = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, (m) => m.slice(0, m.indexOf('>') + 1));
  // An attribute's value may hold `<` and `>` (a code block's copy button holds its code).
  for (const t of markup.matchAll(/<([a-zA-Z][\w-]*)((?:\s+[^\s"'=<>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*\/?>/g)) {
    for (const a of t[2]!.matchAll(/([^\s"'=<>/]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/g)) {
      const value = (a[2] ?? a[3] ?? a[4] ?? '').replace(/&amp;/g, '&').replace(/&#x2F;/gi, '/');
      yield { tag: t[1]!.toLowerCase(), name: a[1]!.toLowerCase(), value };
    }
  }
}

/** The attributes that are a link or a file, relative to the page or not. */
const LINKS = new Set(['href', 'src', 'srcset', 'poster']);

/** The URLs in an attribute's value that name a place of this site, resolved against `page`. */
function references(name: string, value: string, page: string): { path: string; directory: boolean }[] {
  const link = LINKS.has(name);
  const values = name === 'srcset' ? value.split(',').map((v) => v.trim().split(/\s+/)[0]!) : [value];
  const out: { path: string; directory: boolean }[] = [];
  for (const v of values) {
    if (!v || v.startsWith('#') || v.startsWith('//') || /^[a-z][a-z0-9+.-]*:/i.test(v)) continue;
    // In any other attribute, a value that is a path from the server's root (an element's
    // `export`, an island's `component-url`), not text such as a copy button's code.
    if (!link && !/^\/[\w.~%-][^\s]*$/.test(v)) continue;
    out.push({ path: new URL(v, `${ORIGIN}${page}`).pathname, directory: !link });
  }
  return out;
}

test('every link and file reference in the built site is under the base and names a file of the site', () => {
  const pages = files('.html');
  expect(pages.length, 'pnpm build writes apps/docs/dist').toBeGreaterThan(10);
  const bad: string[] = [];
  let checked = 0;
  for (const file of pages) {
    const page = served(file);
    for (const { tag, name, value } of attributes(readFileSync(`${DIST}${file}`, 'utf8'))) {
      for (const ref of references(name, value, page)) {
        checked++;
        const why = missing(ref.path, ref.directory);
        if (why) bad.push(`${file}: <${tag} ${name}="${value}">, ${why}`);
      }
    }
  }
  for (const file of files('.css')) {
    for (const m of readFileSync(`${DIST}${file}`, 'utf8').matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
      const v = m[1]!.trim();
      if (v.startsWith('#') || /^[a-z][a-z0-9+.-]*:/i.test(v)) continue;
      checked++;
      const why = missing(new URL(v, `${ORIGIN}${served(file)}`).pathname, false);
      if (why) bad.push(`${file}: url(${v}), ${why}`);
    }
  }
  expect(checked).toBeGreaterThan(1000);
  expect(bad).toEqual([]);
});

/** The pages the browser opens: one of each kind. */
const OPENED = ['/', '/elements/', '/demo/monitor/', '/reference/ui/', '/python/tutorial/'];

/** Every link on the page, in its document and in its elements' shadow roots, as absolute URLs. */
const links = (page: Page): Promise<string[]> =>
  page.evaluate(() => {
    const found: string[] = [];
    const walk = (root: Document | ShadowRoot) => {
      for (const a of root.querySelectorAll<HTMLAnchorElement | HTMLLinkElement>('a[href], link[href]')) found.push(a.href);
      for (const el of root.querySelectorAll('*')) if (el.shadowRoot) walk(el.shadowRoot);
    };
    walk(document);
    return found;
  });

/** Watches what `page` requests from the site: each request outside the base or not found, as `status url`. */
function watch(page: Page): string[] {
  const bad: string[] = [];
  const origin = new URL(DOCS).origin;
  page.on('response', (r) => {
    const u = new URL(r.url());
    if (u.origin !== origin) return;
    if (!u.pathname.startsWith(`${BASE}/`) || r.status() >= 400) bad.push(`${r.status()} ${u.pathname}${u.search}`);
  });
  page.on('requestfailed', (r) => bad.push(`failed ${r.url()}`));
  return bad;
}

for (const path of OPENED) {
  test(`${path} loads nothing outside the base, and its links stay under it`, async ({ page }) => {
    const bad = watch(page);
    await page.goto(`${DOCS}${path}`);
    await page.waitForLoadState('networkidle');
    if (path === '/elements/' || path === '/demo/monitor/') {
      // The monitor has read the demo export.
      await expect(page.locator('ca-monitor').first().locator('header .runbtn')).toBeVisible();
      await page.waitForLoadState('networkidle');
    }
    const origin = new URL(DOCS).origin;
    const outside = (await links(page)).filter((h) => h.startsWith(origin) && !new URL(h).pathname.startsWith(`${BASE}/`));
    expect(outside).toEqual([]);
    expect(bad).toEqual([]);
  });
}

test('the search loads its index from under the base, and its results link under it', async ({ page }) => {
  const bad = watch(page);
  await page.goto(`${DOCS}/python/tutorial/`);
  await page.getByRole('button', { name: 'Search' }).click();
  await page.locator('#starlight__search input').fill('monitor');
  const result = page.locator('#starlight__search a[href]').first();
  await expect(result).toBeVisible();
  expect(new URL((await result.getAttribute('href'))!, page.url()).pathname).toMatch(new RegExp(`^${BASE}/`));
  await page.waitForLoadState('networkidle');
  expect(bad).toEqual([]);
});
