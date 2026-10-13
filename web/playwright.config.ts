// End-to-end: the built page (src/contraagent/monitor/static), served by the
// real Python monitor over the demo pipeline's runs. Run `pnpm build` first
// (`pnpm e2e` does both).
import { defineConfig } from '@playwright/test';

const PORT = Number(process.env["E2E_PORT"] ?? 18793);

export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1280, height: 800 } },
  webServer: {
    command: `uv run contraagent monitor --runs-dir web/e2e/.runs/demo-runs --port ${PORT}`,
    cwd: '..',
    url: `http://127.0.0.1:${PORT}/api/info`,
    reuseExistingServer: false,
  },
});
