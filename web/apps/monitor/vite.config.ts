import { fileURLToPath } from 'node:url';
import { defineConfig, type Plugin } from 'vite';
import { themeBootScript, themeRules } from '../../packages/ui/src/styles/themes.ts';

/** Where `contraagent-monitor` runs during `pnpm dev` (override with CONTRAAGENT_MONITOR). */
const API = process.env['CONTRAAGENT_MONITOR'] ?? 'http://127.0.0.1:8787';

/** The page opens in the reader's theme: `data-ca-theme` on <html> and the themes' rules, before the first paint. */
const theme = (): Plugin => ({
  name: 'contraagent-theme',
  transformIndexHtml: () => [
    { tag: 'script', children: themeBootScript, injectTo: 'head-prepend' },
    { tag: 'style', children: themeRules((n) => `[data-ca-theme="${n}"]`), injectTo: 'head' },
  ],
});

export default defineConfig({
  plugins: [theme()],
  // Relative asset URLs: the monitor may be served under a path prefix.
  base: './',
  resolve: { conditions: ['source'] },
  server: {
    proxy: { '/api': API, '/events': API },
  },
  build: {
    // The Python package serves this directory; the build output is committed.
    outDir: fileURLToPath(new URL('../../../src/contraagent/monitor/static', import.meta.url)),
    emptyOutDir: true,
    target: 'es2022',
    // Flat, stable names: the server answers only `/<name>.<js|css>`.
    assetsDir: '',
    modulePreload: false,
    rolldownOptions: {
      output: { entryFileNames: 'app.js', chunkFileNames: '[name].js', assetFileNames: '[name][extname]', codeSplitting: false },
    },
  },
});
