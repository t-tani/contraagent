// End-to-end tests of the documentation site (apps/docs) as built, under its base
// path, for its pages, links and live elements: the specs under e2e/site/
// (landing.spec.ts, mobile.spec.ts, fit.spec.ts, docs-links.spec.ts,
// code-tree.spec.ts). The site reads only its own files, so no monitor runs here.
// Run `pnpm build` first (`pnpm e2e:site` does both). The monitor's tests are
// playwright.config.ts's (`pnpm e2e`).
import { defineConfig } from '@playwright/test';
import { DOCS, DOCS_PORT } from './e2e/site/docs-site.js';

export default defineConfig({
  testDir: 'e2e/site',
  // A spec file runs on one worker, in order; three files at once against the same server,
  // which the specs only read.
  fullyParallel: false,
  workers: 3,
  timeout: 30_000,
  use: { viewport: { width: 1280, height: 800 } },
  webServer: [
    {
      // The documentation site as built (apps/docs/dist), under its base path and nothing
      // outside it (e2e/site/docs-site.ts).
      // --ignore-lock: another preview of the site may be running.
      command: `pnpm exec astro preview --host 127.0.0.1 --port ${DOCS_PORT} --ignore-lock`,
      cwd: 'apps/docs',
      url: `${DOCS}/elements/`,
      reuseExistingServer: false,
    },
  ],
});
