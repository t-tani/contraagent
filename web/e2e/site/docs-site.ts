// The documentation site as the end-to-end tests serve it (playwright.site.config.ts):
// apps/docs/dist under the base path it is built for (apps/docs/site.ts), and
// nothing outside it, so that a link or a file that misses the base is not found.
import { BASE } from '../../apps/docs/site.js';

export { BASE };
/** The port of the documentation site; `E2E_DOCS_PORT` sets it. */
export const DOCS_PORT = Number(process.env['E2E_DOCS_PORT'] ?? 18795);
/** The site's root, with no `/` at the end: a page's path from the site's root (`/elements/`) follows it. */
export const DOCS = `http://127.0.0.1:${DOCS_PORT}${BASE}`;
