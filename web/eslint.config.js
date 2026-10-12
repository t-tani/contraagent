// @ts-check
import tseslint from 'typescript-eslint';
import lit from 'eslint-plugin-lit';

export default tseslint.config(
  { ignores: ['**/dist/**', '**/node_modules/**', '**/.astro/**', 'packages/ui/src/locales/**', 'packages/api/src/schema.ts', 'packages/ui/custom-elements.json'] },
  ...tseslint.configs.recommendedTypeChecked,
  lit.configs['flat/recommended'],
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  { files: ['**/*.js', '**/*.mjs'], ...tseslint.configs.disableTypeChecked },
);
