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
      // The wordmark carries the name; the brand assets live with the root README's (docs/assets/brand).
      logo: {
        light: '../../../docs/assets/brand/contraagent-logo-light.svg',
        dark: '../../../docs/assets/brand/contraagent-logo-dark.svg',
        alt: 'contraagent',
        replacesTitle: true,
      },
      // favicon.svg follows the reader's colour scheme; the PNGs are for browsers and home screens without SVG icons.
      favicon: '/favicon.svg',
      head: [
        { tag: 'link', attrs: { rel: 'icon', href: '/favicon-32.png', type: 'image/png', sizes: '32x32' } },
        { tag: 'link', attrs: { rel: 'apple-touch-icon', href: '/apple-touch-icon.png', sizes: '180x180' } },
      ],
      // A live demo can show @contraagent/elements' example of a theme of one's own.
      // The landing page's first screen (the only page with a `hero`).
      components: { Hero: './src/components/home/Hero.astro' },
      customCss: ['./src/styles/site.css', '../../packages/elements/docs/examples/theme.css'],
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
