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
      description: 'Run coding-agent CLIs as typed, supervised, observable tasks.',
      // A live demo can show @contraagent/ui's example of a theme of one's own.
      customCss: ['./src/styles/site.css', '../../packages/ui/docs/examples/theme.css'],
      // python/ and node/ are collected from the packages (scripts/collect.py).
      sidebar: [
        { label: 'Python', items: [{ autogenerate: { directory: 'python' } }] },
        {
          label: 'Node and the browser',
          items: [
            { label: '@contraagent/ui', items: [{ autogenerate: { directory: 'node/ui' } }] },
            { label: '@contraagent/api', items: [{ autogenerate: { directory: 'node/api' } }] },
          ],
        },
        { label: 'Live elements', slug: 'elements' },
        {
          label: 'Reference',
          items: [
            { label: 'Monitor HTTP API', slug: 'reference/http-api' },
            { label: 'Elements', slug: 'reference/elements' },
            { label: 'Theme properties', slug: 'reference/theme' },
          ],
        },
      ],
    }),
  ],
});
