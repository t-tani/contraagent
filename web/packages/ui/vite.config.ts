// One self-contained ES module (Lit and the translations included) for pages
// without a build step: <script type="module" src=".../contraagent-ui.js"></script>.
// The npm entries (`dist/**`, built by tsc) leave Lit to the consumer's bundler.
import { defineConfig } from 'vite';
import { compactLocales, staticLocales } from '../../scripts/compact-locale.mjs';
import { minifyCss } from '../../scripts/minify-css.mjs';
import { minifyHtml } from '../../scripts/minify-html.mjs';

export default defineConfig({
  // One file: the locales are imported with the page rather than loaded when chosen.
  plugins: [minifyCss(), minifyHtml(), compactLocales(), staticLocales()],
  resolve: { conditions: ['source'] },
  build: {
    outDir: 'dist',
    emptyOutDir: false, // tsc writes the module tree next to it
    target: 'es2022',
    // Terser (three passes) on each chunk, then the bundler's own minifier: smaller than either alone.
    minify: 'terser',
    terserOptions: { module: true, ecma: 2020, compress: { passes: 3 } },
    lib: { entry: 'src/index.ts', formats: ['es'], fileName: () => 'contraagent-ui.js' },
    rolldownOptions: {
      // Minified whitespace too: a library build in ES format keeps it unless asked, and its
      // `@__PURE__` marks, which a page without a build step has no use for. One file: no chunks.
      output: { minify: true, comments: { annotation: false }, codeSplitting: false },
    },
  },
});
