// The root README's screenshots (docs/assets/readme/*.png), taken from the real monitor:
// it writes the showcase runs (showcase.py: the demo pipelines on the demo agent, every
// task done, no coding agent, nothing spent) into a temporary directory, serves
// `contraagent monitor` over them on a free port, and captures the region of each view
// that matters with Playwright, 1200 px wide at device scale 2. The PNGs keep their full
// colour and are optimized losslessly (oxipng, through `uv run --with pyoxipng`).
//
//   pnpm --dir web screenshots                 # all of them, into docs/assets/readme/
//   pnpm --dir web screenshots --runs DIR      # over showcase runs already written (DIR/demo-runs)
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
const { values: args } = parseArgs({
  options: {
    out: { type: 'string', default: join(ROOT, 'docs', 'assets', 'readme') },
    runs: { type: 'string' },
  },
});

const WIDTH = 1200;

/**
 * Each screenshot: its file, the page, the theme, the viewport's height, and the region it
 * keeps (`clip(page)`, in CSS pixels).
 */
const SHOTS = [
  {
    // The hero: a finished run, every task done, the review loop's layer, and the totals.
    name: 'overview',
    url: '/?run=docs&tab=overview&layer=contraagent.docs.examples.demo.tasks.review_loop',
    theme: 'contraagent-light',
    height: 1100,
    ready: 'ca-pipeline-graph .dag',
    clip: async (page) => rows(0, bottom(await boxOf(page, 'ca-kpis')) + 12),
  },
  {
    // A nested flow's inner layer: two loops, one inside the other.
    name: 'pipeline-graph',
    url: '/?run=analyse&tab=overview&layer=contraagent.docs.examples.analysis.flow.analyse_file',
    theme: 'contraagent-light',
    height: 1000,
    ready: 'ca-pipeline-graph .dag',
    clip: async (page) => {
      const g = await boxOf(page, 'ca-pipeline-graph');
      return rows(g.y - 64, bottom(g) + 12);
    },
  },
  {
    // An output checked, sent back with its failed checks, and corrected in the same session.
    name: 'task-detail',
    url: '/?run=docs&tab=stream&key=write_note-alpha&round=1',
    theme: 'contraagent-light',
    height: 1100,
    ready: 'ca-task-view',
    clip: async (page) => rows(104, bottom(await boxOf(page, 'ca-task-view', 'Output failed checks')) + 28),
  },
  {
    // The summaries' history: a correction, and the model switch after a rate limit.
    name: 'history',
    url: '/?run=docs&tab=journal&kind=summarize',
    theme: 'contraagent-light',
    height: 900,
    ready: 'ca-journal-table',
    clip: async (page) => rows(0, bottom(await boxOf(page, 'ca-journal-table')) + 8),
  },
  {
    // The model switch in the task's detail, in the dark theme (the monitor's default).
    name: 'model-switch-dark',
    url: '/?run=docs&tab=stream&key=summarize-beta',
    theme: 'contraagent-dark',
    height: 1100,
    ready: 'ca-task-view',
    clip: async (page) => rows(104, bottom(await boxOf(page, 'ca-task-view', 'Done.', -1)) + 28),
  },
  {
    // The runs of a period added up: totals, cost by day and kind, the kinds.
    name: 'trends',
    url: '/?page=trends&days=7',
    theme: 'contraagent-light',
    height: 1300,
    ready: 'ca-trends',
    clip: async () => rows(0, 990),
  },
];

/** The full width of the page between `top` and `end`. */
const rows = (top, end) => ({ x: 0, y: Math.max(0, top), width: WIDTH, height: end - Math.max(0, top) });
const bottom = (b) => b.y + b.height;

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

let workdir = args.runs;
let made = false;
if (!workdir) {
  // At the demo agent's own pace (about a minute), so times and the timeline look real.
  workdir = mkdtempSync(join(tmpdir(), 'ca-showcase-'));
  made = true;
  run('uv', ['run', '--project', ROOT, 'python', join(ROOT, 'web', 'scripts', 'showcase.py')], { cwd: workdir });
}

const port = await freePort();
const monitor = spawn(
  'uv',
  ['run', '--project', ROOT, 'contraagent', 'monitor', '--runs-dir', join(workdir, 'demo-runs'), '--port', String(port), '--title', 'contraagent demo'],
  { stdio: 'ignore', cwd: ROOT },
);
const files = [];
try {
  const base = `http://127.0.0.1:${port}`;
  await waitFor(`${base}/api/info`, 60_000);
  mkdirSync(args.out, { recursive: true });
  const browser = await chromium.launch();
  for (const shot of SHOTS) {
    const ctx = await browser.newContext({
      viewport: { width: WIDTH, height: shot.height },
      deviceScaleFactor: 2,
      reducedMotion: 'reduce',
      locale: 'en-US',
      timezoneId: 'UTC',
    });
    await ctx.addInitScript((theme) => {
      localStorage.setItem('contraagent:theme', theme);
      localStorage.setItem('contraagent:locale', 'en');
    }, shot.theme);
    const page = await ctx.newPage();
    await page.goto(base + shot.url);
    await page.locator(shot.ready).first().waitFor();
    await page.waitForTimeout(1500); // the live feeds settle and the graph lays out
    const path = join(args.out, `${shot.name}.png`);
    await page.screenshot({ path, clip: await shot.clip(page) });
    files.push(path);
    await ctx.close();
  }
  await browser.close();
} finally {
  monitor.kill();
  if (made) rmSync(workdir, { recursive: true, force: true });
}
run('uv', ['run', '--project', ROOT, '--with', 'pyoxipng', 'python', join(ROOT, 'web', 'scripts', 'optimize_png.py'), ...files]);
