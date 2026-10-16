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

/**
 * Lines of a repository file, as a `::code` line quotes them: from the first
 * line that holds `from` to the line before the next one that holds `to`
 * (the end of the file without it); a quote that matches nothing stops the build.
 */
export function repoQuote(path: string, from: string, to?: string): string {
  const lines = repoFile(path).split('\n');
  const start = lines.findIndex((l) => l.includes(from));
  if (start < 0) throw new Error(`${path}: no line holds ${JSON.stringify(from)}`);
  const end = to === undefined ? -1 : lines.findIndex((l, i) => i > start && l.includes(to));
  if (to !== undefined && end < 0) throw new Error(`${path}: no line after ${JSON.stringify(from)} holds ${JSON.stringify(to)}`);
  return lines.slice(start, end < 0 ? undefined : end).join('\n').trimEnd();
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
