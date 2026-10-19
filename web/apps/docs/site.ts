// Where the site is served: the repository's GitHub Pages, under its name
// (.github/workflows/pages.yml). astro.config.mjs builds the site for it, and the
// end-to-end tests serve the built site under the same base (playwright.config.ts).
export const SITE = 'https://t-tani.github.io';
export const BASE = '/contraagent';

/** The repository the site is built from: the header's GitHub link and the landing page's. */
export const REPOSITORY = 'https://github.com/t-tani/contraagent';
