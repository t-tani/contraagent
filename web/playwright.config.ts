// End-to-end: the built page (src/contraagent/_internal/monitor/static), served by the
// real Python monitor over the demo pipeline's runs, and by a hub over the same
// runs shipped from two hosts (e2e/hub.py; hub.spec.ts); and the documentation
// site as built, under its base path, for its pages, links and live elements
// (landing.spec.ts, mobile.spec.ts, fit.spec.ts, docs-links.spec.ts). Run `pnpm build` first
// (`pnpm e2e` does both).
import { defineConfig } from '@playwright/test';
import { DOCS, DOCS_PORT } from './e2e/docs-site.js';

const PORT = Number(process.env["E2E_PORT"] ?? 18793);
/** The hub's port; hub.spec.ts reads it from `E2E_HUB_PORT` too. */
const HUB_PORT = Number(process.env["E2E_HUB_PORT"] ?? 18794);

export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.ts',
  // A spec file runs on one worker, in order; three files at once against the same servers,
  // which the specs only read.
  fullyParallel: false,
  workers: 3,
  timeout: 30_000,
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1280, height: 800 } },
  webServer: [
    {
      command: `uv run contraagent monitor --runs-dir web/e2e/.runs/demo-runs --port ${PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${PORT}/api/info`,
      reuseExistingServer: false,
    },
    {
      // Runs the demo pipeline into a temporary directory of its own, then serves the hub.
      command: `uv run python web/e2e/hub.py --port ${HUB_PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${HUB_PORT}/api/info`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // The documentation site as built (apps/docs/dist), under its base path and nothing
      // outside it (e2e/docs-site.ts), for its pages and live elements.
      // --ignore-lock: another preview of the site may be running.
      command: `pnpm exec astro preview --host 127.0.0.1 --port ${DOCS_PORT} --ignore-lock`,
      cwd: 'apps/docs',
      url: `${DOCS}/elements/`,
      reuseExistingServer: false,
    },
  ],
});
