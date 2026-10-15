// @ts-check
import { fileURLToPath } from 'node:url';
import starlight from '@astrojs/starlight';
import { defineConfig, passthroughImageService } from 'astro/config';

const repo = fileURLToPath(new URL('../../..', import.meta.url));

export default defineConfig({
  // No raster images to optimise: skip sharp and its install script.
  image: { service: passthroughImageService() },
  vite: {
    // Workspace packages from their TypeScript sources; pages quote files across the repository.
    resolve: { conditions: ['source'] },
    server: { fs: { allow: [repo] } },
  },
  integrations: [
    starlight({
      title: 'contraagent',
      description: 'Run coding agents as typed, checked, supervised tasks.',
      // A live demo can show @contraagent/elements' example of a theme of one's own.
      customCss: ['./src/styles/site.css', '../../packages/elements/docs/examples/theme.css'],
      // An element topic's live elements come first in its content (its `live` front matter).
      components: { MarkdownContent: './src/components/MarkdownContent.astro' },
      // python/ and node/ are collected from the packages (scripts/collect.py).
      sidebar: [
        { label: 'Python package: contraagent', collapsed: true, items: [{ autogenerate: { directory: 'python' } }] },
        {
          label: 'Web packages',
          items: [
            { label: 'Element gallery', slug: 'elements' },
            { label: '@contraagent/ui', collapsed: true, items: [{ autogenerate: { directory: 'node/ui' } }] },
            { label: '@contraagent/elements', collapsed: true, items: [{ autogenerate: { directory: 'node/elements' } }] },
            { label: '@contraagent/api', collapsed: true, items: [{ autogenerate: { directory: 'node/api' } }] },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Monitor HTTP API', slug: 'reference/http-api' },
            { label: 'Elements of @contraagent/ui', slug: 'reference/ui' },
            { label: 'Elements of @contraagent/elements', slug: 'reference/elements' },
            { label: 'Theme properties', slug: 'reference/theme' },
          ],
        },
      ],
    }),
  ],
});
