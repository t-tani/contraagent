// An export of the demo's runs (`contraagent monitor export`), served by a plain
// static server with no monitor behind it: the views read its files, the header
// says when it was written, and the views it does not hold say so.
import { expect, test } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Not the documentation site's port (playwright.config.ts, E2E_DOCS_PORT).
const PORT = Number(process.env['E2E_EXPORT_PORT'] ?? 18796);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const project = fileURLToPath(new URL('../..', import.meta.url));
const runs = fileURLToPath(new URL('./.runs/demo-runs', import.meta.url));
const out = fileURLToPath(new URL('./.runs/export', import.meta.url));
let server: ChildProcess | null = null;

test.beforeAll(async () => {
  rmSync(out, { recursive: true, force: true });
  execFileSync('uv', ['run', '--project', project, 'contraagent', 'monitor', 'export', '--runs-dir', runs, '--out', out, '--title', 'demo'], {
    stdio: 'inherit',
  });
  server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', out], { stdio: 'ignore' });
  for (let i = 0; i < 100; i++) {
    try {
      if ((await fetch(`${ORIGIN}/data/info.json`)).ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error('the static server did not start');
});

test.afterAll(() => {
  server?.kill();
});

test('an export opens with no server: its views, when it was written, and what it does not hold', async ({ page }) => {
  const asked: string[] = [];
  page.on('request', (r) => asked.push(new URL(r.url()).pathname));
  await page.goto(`${ORIGIN}/?run=docs&tab=journal`);
  // The header says it is an export and when it was written, where a live monitor shows its connection.
  const mark = page.locator('header .pill', { hasText: 'Exported' });
  await expect(mark).toBeVisible();
  await expect(mark).toHaveAttribute('title', 'Not in this export: transcripts and processes');
  // The history is the export's journal.
  const rows = page.locator('ca-journal-table tbody tr[data-key]');
  await expect(rows.first()).toBeVisible();
  // A task's detail: its attempts are there, its transcript is not.
  await page.locator('ca-journal-table tbody tr[data-key][data-executor="agent"]').first().click();
  await expect(page).toHaveURL(/tab=stream/);
  await expect(page.locator('ca-task-view')).toContainText('No transcript | not in this export');
  await page.goto(`${ORIGIN}/?run=docs&tab=procs`);
  await expect(page.locator('ca-procs-view')).toContainText('No processes | not in this export');
  await page.goto(`${ORIGIN}/?run=docs&tab=overview`);
  await expect(page.locator('ca-overview')).toBeVisible();
  // Nothing was asked of a monitor's API or its feeds.
  expect(asked.filter((p) => p.startsWith('/api/') || p.startsWith('/events'))).toEqual([]);
  expect(asked.some((p) => p.startsWith('/data/runs/docs/'))).toBe(true);
});
