// The site is served under a base path (site.ts). A link or a file reference that
// a component or a page of src/ writes is a path from the site's root
// (`/python/tutorial/`) passed through `withBase()`; the pages that scripts/collect.py
// writes link to each other with relative URLs.

/** The URL of the site's page or file at `path`, a path from the site's root that starts with `/`. */
export const withBase = (path: string): string => `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`;
