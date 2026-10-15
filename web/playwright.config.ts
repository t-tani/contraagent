// End-to-end: the built page (src/contraagent/_internal/monitor/static), served by the
// real Python monitor over the demo pipeline's runs, and by a hub over the same
// runs shipped from two hosts (e2e/hub.py; hub.spec.ts); and the documentation
// site as built, for its live elements (fit.spec.ts). Run `pnpm build` first
// (`pnpm e2e` does both).
import { defineConfig } from '@playwright/test';

const PORT = Number(process.env["E2E_PORT"] ?? 18793);
/** The hub's port; hub.spec.ts reads it from `E2E_HUB_PORT` too. */
const HUB_PORT = Number(process.env["E2E_HUB_PORT"] ?? 18794);
/** The documentation site's port; fit.spec.ts reads it from `E2E_DOCS_PORT` too. */
const DOCS_PORT = Number(process.env["E2E_DOCS_PORT"] ?? 18795);

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
      // The documentation site as built (apps/docs/dist), for its live elements (fit.spec.ts).
      command: `uv run python -m http.server ${DOCS_PORT} --bind 127.0.0.1 --directory web/apps/docs/dist`,
      cwd: '..',
      url: `http://127.0.0.1:${DOCS_PORT}/elements/`,
      reuseExistingServer: false,
      // http.server logs each request on stderr.
      stderr: 'ignore',
    },
  ],
});
