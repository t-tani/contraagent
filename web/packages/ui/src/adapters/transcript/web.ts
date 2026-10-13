// The pages a web search returned, read from its output.

/** One page a web search returned. */
export interface WebResult {
  title: string;
  url: string;
}

const RESULTS_MAX = 20;
const JSON_LINK = /\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"url"\s*:\s*"(https?:\/\/[^"\s]+)"/g;
const NUMBERED = /^\s*\[\d+\]\s+(.+)\n\s*(https?:\/\/\S+)/gm;
const BARE_URL = /https?:\/\/[^\s"'<>)\]]+/g;

/**
 * The pages a web search's output lists, in order, at most 20: Claude Code's
 * `{"title", "url"}` links, omp's `[n] title` lines followed by a URL, else every
 * http(s) URL in the text (titled by itself).
 */
export function webResults(out: string | null | undefined): WebResult[] {
  const text = out ?? '';
  const found: WebResult[] = [];
  const seen = new Set<string>();
  const add = (title: string, url: string): void => {
    if (seen.has(url) || found.length >= RESULTS_MAX) return;
    seen.add(url);
    found.push({ title: title.trim() || url, url });
  };
  for (const m of text.matchAll(JSON_LINK)) {
    let title = m[1] ?? '';
    try {
      title = JSON.parse(`"${title}"`) as string;
    } catch {
      // an escape JSON does not take: the raw text is still a title
    }
    add(title, m[2] ?? '');
  }
  if (!found.length) for (const m of text.matchAll(NUMBERED)) add(m[1] ?? '', m[2] ?? '');
  if (!found.length) for (const m of text.matchAll(BARE_URL)) add('', m[0].replace(/[.,;:!?]+$/, '')); // a sentence's own punctuation
  return found;
}
