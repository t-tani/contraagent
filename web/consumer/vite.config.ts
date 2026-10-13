// The page as an npm consumer builds it: the packages from their `dist/` (no
// `source` condition), Lit bundled, minified, one module.
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    modulePreload: false,
    rolldownOptions: {
      input: 'src/main.ts',
      output: { entryFileNames: 'main.js', codeSplitting: false },
    },
  },
});
