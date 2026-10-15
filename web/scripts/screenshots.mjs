// The root README's screenshots (docs/assets/readme/*.png), taken from the real monitor:
// it runs the demo pipeline on its demo agent (no coding agent, nothing spent) into a
// temporary directory, serves `contraagent monitor` over those runs on a free port, and
// captures each view with Playwright at a fixed viewport and device scale. The PNGs are
// then reduced to a 256-colour palette (Pillow, through `uv run --with pillow`).
//
//   pnpm --dir web screenshots                 # all of them, into docs/assets/readme/
//   pnpm --dir web screenshots --runs DIR      # over demo runs already written (DIR/demo-runs)
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

/** Each screenshot: its file, the page, the theme, the viewport, and what it shows of the page. */
const SHOTS = [
  {
    // The run at a glance: state, problems, outputs, and the pipeline graph with its loop.
    name: 'overview',
    url: '/?run=docs&tab=overview',
    theme: 'contraagent-light',
    viewport: { width: 1280, height: 900 },
    ready: 'ca-pipeline-graph .dag',
  },
  {
    // A nested flow: functions drawn open, a loop inside a loop, and the legend.
    name: 'pipeline-graph',
    url: '/?run=analyse&tab=overview',
    theme: 'contraagent-light',
    viewport: { width: 1280, height: 900 },
    ready: 'ca-pipeline-graph .dag',
    clip: async (page) => box(page, 'ca-pipeline-graph', 12),
  },
  {
    // A task whose first output failed its checks, and the correction round that passed.
    name: 'task-detail',
    url: '/?run=docs&tab=stream&key=write_note-alpha&round=1',
    theme: 'contraagent-light',
    viewport: { width: 1280, height: 760 },
    ready: 'ca-task-view',
  },
  {
    // The history of attempts: outcome, coding agent, model, identity, tokens, cost, time.
    name: 'history',
    url: '/?run=docs&tab=journal',
    theme: 'contraagent-light',
    viewport: { width: 1280, height: 640 },
    ready: 'ca-journal-table, table',
  },
  {
    // The runs of a period added up.
    name: 'trends',
    url: '/?page=trends&days=7',
    theme: 'contraagent-light',
    viewport: { width: 1280, height: 900 },
    ready: 'ca-trends',
  },
  {
    // A model switch after a rate limit, in the dark theme (the monitor's default).
    name: 'model-switch-dark',
    url: '/?run=docs&tab=stream&key=summarize-beta',
    theme: 'contraagent-dark',
    viewport: { width: 1280, height: 760 },
    ready: 'ca-task-view',
  },
];

/** The bounding box of the first element matching `selector` (through shadow roots), with a margin. */
async function box(page, selector, margin) {
  const b = await page.locator(selector).first().boundingBox();
  if (!b) throw new Error(`${selector} is not on the page`);
  return { x: Math.max(0, b.x - margin), y: Math.max(0, b.y - margin), width: b.width + 2 * margin, height: b.height + 2 * margin };
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
  workdir = mkdtempSync(join(tmpdir(), 'ca-demo-'));
  made = true;
  run('uv', ['run', '--project', ROOT, 'python', '-m', 'contraagent.docs.examples.demo.run', '--no-serve'], { cwd: workdir });
}

const port = await freePort();
const monitor = spawn(
  'uv',
  [
    'run',
    '--project',
    ROOT,
    'contraagent',
    'monitor',
    '--runs-dir',
    join(workdir, 'demo-runs'),
    '--port',
    String(port),
    '--title',
    'contraagent demo',
    '--panels',
    'contraagent.docs.examples.demo.run:PANELS',
  ],
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
      viewport: shot.viewport,
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
    await page.screenshot({ path, ...(shot.clip ? { clip: await shot.clip(page) } : {}) });
    files.push(path);
    await ctx.close();
  }
  await browser.close();
} finally {
  monitor.kill();
  if (made) rmSync(workdir, { recursive: true, force: true });
}
run('uv', ['run', '--project', ROOT, '--with', 'pillow', 'python', join(ROOT, 'web', 'scripts', 'shrink_png.py'), ...files]);
