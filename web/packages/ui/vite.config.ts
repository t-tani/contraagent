// One self-contained ES module (Lit included) for pages without a build step:
// <script type="module" src=".../contraagent-ui.js"></script>. The npm entry
// (`dist/index.js`, built by tsc) leaves Lit to the consumer's bundler.
import { defineConfig } from 'vite';

export default defineConfig({
  resolve: { conditions: ['source'] },
  build: {
    outDir: 'dist',
    emptyOutDir: false, // tsc writes the module tree next to it
    target: 'es2022',
    lib: { entry: 'src/index.ts', formats: ['es'], fileName: () => 'contraagent-ui.js' },
  },
});
