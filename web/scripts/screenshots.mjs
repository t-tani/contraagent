// The documentation's screenshots, taken from the real elements:
//
// - `readme`: the root README's (docs/assets/readme/*.png), from the monitor;
// - `ui`: one per view of @contraagent/ui (web/packages/ui/docs/images/*.webp), from the monitor;
// - `elements`: one per topic of @contraagent/elements (web/packages/elements/docs/images/*.webp),
//   each example of docs/examples/ mounted alone on a page (scripts/examples-page/, served by Vite).
//
// The monitor shows the showcase runs (showcase.py: the demo pipelines on the demo agent, every
// task done, no coding agent, nothing spent), written into a temporary directory and served by
// `contraagent monitor` on a free port. Each screenshot is the region that matters, at device
// scale 2, in full colour: the PNGs are optimized losslessly (oxipng), the WebP files are
// lossless (Pillow); both through `uv run --with`.
//
//   pnpm --dir web screenshots                       # all of them
//   pnpm --dir web screenshots --only ui,elements    # some sets
//   pnpm --dir web screenshots --runs DIR            # over showcase runs already written (DIR/demo-runs)
//
// Needs uv, and Playwright's Chromium (`pnpm --dir web exec playwright install chromium`).
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { chromium } from '@playwright/test';

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
const WEB = join(ROOT, 'web');
const { values: args } = parseArgs({
  options: {
    only: { type: 'string', default: 'readme,ui,elements' },
    runs: { type: 'string' },
  },
});
const sets = new Set(args.only.split(','));

/** Where each set goes, and the format its files are in. */
const SETS = {
  readme: { dir: join(ROOT, 'docs', 'assets', 'readme'), format: 'png' },
  ui: { dir: join(WEB, 'packages', 'ui', 'docs', 'images'), format: 'webp' },
  elements: { dir: join(WEB, 'packages', 'elements', 'docs', 'images'), format: 'webp' },
};

const LIGHT = 'contraagent-light';
/**
 * The fonts, named (`--ca-sans`, `--ca-mono`, the themes' own properties) in place of
 * `system-ui` and `ui-monospace`, which name another font on each machine.
 */
const FONTS = `:root { --ca-sans: 'Segoe UI', Arial, sans-serif; --ca-mono: Consolas, 'Liberation Mono', monospace; }
body { font-family: var(--ca-sans); }`;
const DOCS_LOOP = 'contraagent.docs.examples.demo.tasks.review_loop';

/**
 * Each screenshot: its set and file, the monitor's page (`url`) or an example of
 * @contraagent/elements (`example`), the theme, the viewport, and the region it keeps
 * (`clip(page)`, in CSS pixels). The README's are 1200 px wide; the packages' are at most
 * 900, so GitHub (about 880 px) shows them near their size.
 */
const SHOTS = [
  // The root README.
  {
    set: 'readme',
    name: 'overview', // the hero: a finished run, every task done, the review loop's layer, and the totals
    url: `/?run=docs&tab=overview&layer=${DOCS_LOOP}`,
    width: 1200,
    height: 1100,
    ready: 'ca-pipeline-graph .dag',
    clip: async (page) => rows(page, 0, bottom(await boxOf(page, 'ca-kpis')) + 12),
  },
  {
    set: 'readme',
    name: 'pipeline-graph', // a nested flow's inner layer: two loops, one inside the other
    url: '/?run=analyse&tab=overview&layer=contraagent.docs.examples.analysis.flow.analyse_file',
    width: 1200,
    height: 1000,
    ready: 'ca-pipeline-graph .dag',
    clip: async (page) => {
      const g = await boxOf(page, 'ca-pipeline-graph');
      return rows(page, g.y - 64, bottom(g) + 12);
    },
  },
  {
    set: 'readme',
    name: 'task-detail', // an output checked, sent back with its failed checks, corrected in the same session
    url: '/?run=docs&tab=stream&key=write_note-alpha&round=1',
    width: 1200,
    height: 1100,
    ready: 'ca-task-view',
    clip: async (page) => rows(page, 104, bottom(await boxOf(page, 'ca-task-view', 'Output failed checks')) + 28),
  },
  {
    set: 'readme',
    name: 'history', // the summaries' history: a correction, and the model switch after a rate limit
    url: '/?run=docs&tab=journal&kind=summarize',
    width: 1200,
    height: 900,
    ready: 'ca-journal-table',
    clip: async (page) => rows(page, 0, bottom(await boxOf(page, 'ca-journal-table')) + 8),
  },
  {
    set: 'readme',
    name: 'model-switch-dark', // the model switch in the task's detail, in the dark theme (the monitor's default)
    url: '/?run=docs&tab=stream&key=summarize-beta',
    theme: 'contraagent-dark',
    width: 1200,
    height: 1100,
    ready: 'ca-task-view',
    clip: async (page) => rows(page, 104, bottom(await boxOf(page, 'ca-task-view', 'Done.', -1)) + 28),
  },
  {
    set: 'readme',
    name: 'trends', // the runs of a period added up: totals, cost by day and kind, the kinds
    url: '/?page=trends&days=7',
    width: 1200,
    height: 1300,
    ready: 'ca-trends',
    clip: async (page) => rows(page, 0, 990),
  },

  // @contraagent/ui: one per view.
  { set: 'ui', name: 'monitor', url: `/?run=docs&tab=overview&layer=${DOCS_LOOP}`, height: 900, ready: 'ca-pipeline-graph .dag', clip: async (page) => rows(page, 0, 712) },
  { set: 'ui', name: 'pipeline-graph', url: `/?run=docs&tab=overview&layer=${DOCS_LOOP}`, ready: 'ca-pipeline-graph .dag', clip: (page) => element(page, 'ca-pipeline-graph') },
  { set: 'ui', name: 'task-view', url: '/?run=docs&tab=stream&key=write_note-alpha&round=1', height: 1200, ready: 'ca-task-view', clip: async (page) => {
      const v = await boxOf(page, 'ca-task-view');
      return box(v.x, v.y, v.width, bottom(await boxOf(page, 'ca-task-view', 'Output failed checks')) + 16 - v.y);
    } },
  { set: 'ui', name: 'journal-table', url: '/?run=docs&tab=journal&kind=summarize', ready: 'ca-journal-table', clip: (page) => element(page, 'ca-journal-table') },
  { set: 'ui', name: 'task-table', url: '/?run=docs&tab=tasks&kind=summarize', ready: 'ca-task-table', clip: (page) => element(page, 'ca-task-table') },
  { set: 'ui', name: 'contracts', url: '/?run=docs&tab=outputs', height: 1200, ready: 'ca-contracts', clip: (page) => element(page, 'ca-contracts', 760) },
  { set: 'ui', name: 'definitions', url: '/?run=docs&tab=definitions', height: 1200, ready: 'ca-definitions', clip: (page) => element(page, 'ca-definitions', 760) },
  { set: 'ui', name: 'kpis', url: '/?run=docs&tab=overview', height: 1400, ready: 'ca-kpis', clip: (page) => element(page, 'ca-kpis') },
  { set: 'ui', name: 'timeline', url: '/?run=docs&tab=overview', height: 2400, ready: 'ca-timeline', clip: (page) => element(page, 'ca-timeline') },

  // @contraagent/elements: one per topic, from its example.
  ...['charts', 'check-table', 'data-table', 'graph', 'lanes', 'matrix', 'tiles', 'transcript'].map((example) => ({ set: 'elements', name: example, example })),
  // The page's own theme switch starts on Dark: Light is chosen for the light one.
  { set: 'elements', name: 'page', example: 'ci-pipeline', height: 1400, prepare: (page) => page.getByText('Light', { exact: true }).click() },
  { set: 'elements', name: 'primitives', example: 'status' },
  { set: 'elements', name: 'theming-dark', example: 'ci-pipeline', theme: 'contraagent-dark', height: 1400 },
];

const bottom = (b) => b.y + b.height;
const box = (x, y, width, height) => ({ x: Math.max(0, x), y: Math.max(0, y), width, height });
/** The page's full width between `top` and `end`. */
const rows = (page, top, end) => box(0, top, page.viewportSize().width, end - Math.max(0, top));
/** The first element matching `selector`, with a margin, at most `most` tall. */
async function element(page, selector, most = Infinity) {
  const b = await boxOf(page, selector);
  return box(b.x - 8, b.y - 8, b.width + 16, Math.min(b.height, most) + 16);
}

/**
 * The box of the first element matching `selector` (through shadow roots); with `text`, the
 * box of the block that holds the element inside it with that text (`nth`: which one, -1 the
 * last).
 */
async function boxOf(page, selector, text, nth = 0) {
  let target = page.locator(selector).first();
  if (text) {
    const found = target.getByText(text, { exact: true });
    target = (nth < 0 ? found.last() : found.nth(nth)).locator('xpath=..');
  }
  const b = await target.boundingBox();
  if (!b) throw new Error(`${selector}${text ? ` "${text}"` : ''} is not on the page`);
  return b;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = createServer();
    s.once('error', reject);
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

function run(cmd, argv, opts) {
  const r = spawnSync(cmd, argv, { stdio: 'inherit', ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${argv.join(' ')} exited with ${r.status}`);
}

async function waitFor(url, ms) {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${url} did not answer within ${ms} ms`);
}

const shots = SHOTS.filter((s) => sets.has(s.set));
const stops = [];
let workdir = args.runs;
let made = false;
const files = [];
try {
  let monitorBase;
  if (shots.some((s) => s.url)) {
    if (!workdir) {
      // At the demo agent's own pace (about a minute), so times and the timeline look real.
      workdir = mkdtempSync(join(tmpdir(), 'ca-showcase-'));
      made = true;
      run('uv', ['run', '--project', ROOT, 'python', join(WEB, 'scripts', 'showcase.py')], { cwd: workdir });
    }
    const port = await freePort();
    const monitor = spawn(
      'uv',
      ['run', '--project', ROOT, 'contraagent', 'monitor', '--runs-dir', join(workdir, 'demo-runs'), '--port', String(port), '--title', 'contraagent demo'],
      { stdio: 'ignore', cwd: ROOT },
    );
    stops.push(() => monitor.kill());
    monitorBase = `http://127.0.0.1:${port}`;
    await waitFor(`${monitorBase}/api/info`, 60_000);
  }
  let examplesBase;
  if (shots.some((s) => s.example)) {
    // Vite from the monitor app's dependencies; the workspace packages from their sources.
    const { createServer: vite } = await import(join(WEB, 'apps', 'monitor', 'node_modules', 'vite', 'dist', 'node', 'index.js'));
    const server = await vite({
      root: join(WEB, 'scripts', 'examples-page'),
      configFile: false,
      logLevel: 'error',
      resolve: { conditions: ['source'] },
      server: { port: await freePort(), strictPort: true, fs: { allow: [WEB] } },
    });
    await server.listen();
    stops.push(() => server.close());
    examplesBase = server.resolvedUrls.local[0];
  }

  const browser = await chromium.launch();
  stops.push(() => browser.close());
  for (const shot of shots) {
    const { dir } = SETS[shot.set];
    mkdirSync(dir, { recursive: true });
    const ctx = await browser.newContext({
      viewport: { width: shot.width ?? 900, height: shot.height ?? 900 },
      deviceScaleFactor: 2,
      reducedMotion: 'reduce',
      locale: 'en-US',
      timezoneId: 'UTC',
    });
    const theme = shot.theme ?? LIGHT;
    await ctx.addInitScript(
      ([t, css]) => {
        localStorage.setItem('contraagent:theme', t);
        localStorage.setItem('contraagent:locale', 'en');
        document.addEventListener('DOMContentLoaded', () => document.head.append(Object.assign(document.createElement('style'), { textContent: css })));
      },
      [theme, FONTS],
    );
    const page = await ctx.newPage();
    if (shot.url) {
      await page.goto(monitorBase + shot.url);
      await page.locator(shot.ready).first().waitFor();
    } else {
      await page.goto(`${examplesBase}?example=${shot.example}&theme=${theme}`);
      await page.locator('body[data-ready]').waitFor();
    }
    if (shot.prepare) await shot.prepare(page);
    await page.waitForTimeout(1500); // the live feeds settle and the graphs lay out
    const clip = shot.clip ? await shot.clip(page) : await hostBox(page);
    const path = join(dir, `${shot.name}.png`);
    await page.screenshot({ path, clip });
    files.push(path);
    await ctx.close();
  }
} finally {
  for (const stop of stops.reverse()) await stop();
  if (made) rmSync(workdir, { recursive: true, force: true });
}

/** An example's region: the page's host element, which holds what it mounted. */
async function hostBox(page) {
  const b = await page.evaluate(() => {
    const r = document.getElementById('host').getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  return box(b.x, b.y, b.width, b.height);
}

const asWebp = files.filter((f) => SETS[Object.keys(SETS).find((k) => f.startsWith(SETS[k].dir))].format === 'webp');
run('uv', ['run', '--project', ROOT, '--with', 'pyoxipng', '--with', 'pillow', 'python', join(WEB, 'scripts', 'optimize_images.py'), '--webp', ...asWebp, '--png', ...files.filter((f) => !asWebp.includes(f))]);
