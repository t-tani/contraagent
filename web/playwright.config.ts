// End-to-end tests of the monitor and what ships with it: the built page
// (src/contraagent/_internal/monitor/static), served by the real Python monitor over
// the demo pipeline's runs, and by a hub over the same runs shipped from two hosts
// (e2e/hub.py; hub.spec.ts), and by a monitor served under a base path behind a proxy
// (base-path.spec.ts); the elements on a host page (embed.spec.ts, connection.spec.ts)
// and an export of the runs (export.spec.ts). Every spec under e2e/ but e2e/site/.
// Run `pnpm build` first (`pnpm e2e` does both). The documentation site's tests are
// playwright.site.config.ts's (`pnpm e2e:site`).
import { defineConfig } from '@playwright/test';

const PORT = Number(process.env["E2E_PORT"] ?? 18793);
/** The hub's port; hub.spec.ts reads it from `E2E_HUB_PORT` too. */
const HUB_PORT = Number(process.env["E2E_HUB_PORT"] ?? 18794);
/** The port of the monitor under a base path; base-path.spec.ts reads it from `E2E_BASE_PATH_PORT` too. */
const BASE_PATH_PORT = Number(process.env["E2E_BASE_PATH_PORT"] ?? 18797);

export default defineConfig({
  testDir: 'e2e',
  testIgnore: 'site/**',
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
      // The same runs under /monitor, reached through the proxy base-path.spec.ts starts.
      command: `uv run contraagent monitor --runs-dir web/e2e/.runs/demo-runs --port ${BASE_PATH_PORT} --base-path /monitor`,
      cwd: '..',
      url: `http://127.0.0.1:${BASE_PATH_PORT}/api/info`,
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
  ],
});
