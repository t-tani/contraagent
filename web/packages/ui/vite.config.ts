// One self-contained ES module (Lit and the translations included) for pages
// without a build step: <script type="module" src=".../contraagent-ui.js"></script>.
// The npm entries (`dist/**`, built by tsc) leave Lit to the consumer's bundler.
import { defineConfig } from 'vite';
import { minifyCss } from '../../scripts/minify-css.mjs';

export default defineConfig({
  plugins: [minifyCss()],
  resolve: { conditions: ['source'] },
  build: {
    outDir: 'dist',
    emptyOutDir: false, // tsc writes the module tree next to it
    target: 'es2022',
    lib: { entry: 'src/index.ts', formats: ['es'], fileName: () => 'contraagent-ui.js' },
    rolldownOptions: {
      // Minified whitespace too: a library build in ES format keeps it unless asked. One file: the
      // locales' modules are inlined.
      output: { minify: true, codeSplitting: false },
    },
  },
});
