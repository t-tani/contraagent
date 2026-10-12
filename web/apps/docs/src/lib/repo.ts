// Files of the repository, read when the site is built: pages quote and
// describe what is there, so they cannot drift from it.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Astro runs (dev and build) in web/apps/docs; module URLs move when it bundles.
export const REPO = resolve(process.cwd(), '../../..');

/** A repository file's text (path relative to the repository root). */
export function repoFile(path: string): string {
  return readFileSync(resolve(REPO, path), 'utf8');
}

/** A repository JSON file, parsed. */
export function repoJson<T>(path: string): T {
  return JSON.parse(repoFile(path)) as T;
}

/** A docstring as HTML: escaped, with `code` spans. */
export function inlineMd(s = ''): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n(?!\n)/g, ' ');
}
