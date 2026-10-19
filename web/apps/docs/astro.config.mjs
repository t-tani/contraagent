// @ts-check
import { fileURLToPath } from 'node:url';
import starlight from '@astrojs/starlight';
import { defineConfig, passthroughImageService } from 'astro/config';
import { satteri } from '@astrojs/markdown-satteri';
import { tableCards } from './src/lib/table-cards.mjs';
import { BASE, REPOSITORY, SITE } from './site.ts';

const repo = fileURLToPath(new URL('../../..', import.meta.url));

export default defineConfig({
  // The repository's GitHub Pages (site.ts); a page links through src/lib/base.ts.
  site: SITE,
  base: BASE,
  // No raster images to optimise: skip sharp and its install script.
  image: { service: passthroughImageService() },
  // A Markdown table of three columns or more: one card per row on a phone (src/styles/pages.css).
  markdown: { processor: satteri({ hastPlugins: [tableCards] }) },
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
      // The repository, by its icon at the end of the header on every page (in the menu on a phone).
      social: [{ icon: 'github', label: 'GitHub', href: REPOSITORY }],
      // favicon.svg follows the reader's colour scheme; the PNGs are for browsers and home screens without SVG icons.
      // Starlight adds the base to `favicon`, not to the links in `head`.
      favicon: '/favicon.svg',
      head: [
        { tag: 'link', attrs: { rel: 'icon', href: `${BASE}/favicon-32.png`, type: 'image/png', sizes: '32x32' } },
        { tag: 'link', attrs: { rel: 'apple-touch-icon', href: `${BASE}/apple-touch-icon.png`, sizes: '180x180' } },
      ],
      // A live demo can show @contraagent/elements' example of a theme of one's own.
      // The landing page's first screen (the only page with a `hero`).
      components: { Hero: './src/components/home/Hero.astro', PageTitle: './src/components/PageTitle.astro' },
      customCss: ['./src/styles/site.css', './src/styles/pages.css', '../../packages/elements/docs/examples/theme.css'],
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
