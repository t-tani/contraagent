import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Workspace packages resolve to their TypeScript sources (`source` export condition), not dist/.
  resolve: { conditions: ['source'] },
  ssr: { resolve: { conditions: ['source'], externalConditions: ['source'] } },
  test: {
    include: ['packages/*/src/**/*.test.ts', 'scripts/**/*.test.mjs'],
    // DOM tests opt in per file with `// @vitest-environment happy-dom`.
    environment: 'node',
  },
});
