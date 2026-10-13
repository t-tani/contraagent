// Formats that read the same in every language: a duration, and HTML escaping
// for the few places that build markup as a string.

/**
 * A duration in seconds, in one format: `<0.1s`, `4.2s`, `37s`, `2m 05s`,
 * `1h 02m`; '—' when unknown.
 */
export function fmtDur(s: number | null | undefined): string {
  if (s === null || s === undefined || Number.isNaN(s)) return '—';
  const v = Math.max(0, s);
  if (v < 0.05) return '<0.1s';
  if (v < 9.95) return `${v.toFixed(1)}s`;
  const r = Math.round(v);
  if (r < 60) return `${r}s`;
  if (r < 3600) return `${Math.floor(r / 60)}m ${String(r % 60).padStart(2, '0')}s`;
  return `${Math.floor(r / 3600)}h ${String(Math.floor((r % 3600) / 60)).padStart(2, '0')}m`;
}

/** HTML-escape a text for the few places that build markup as a string (markdown, highlighting). */
export const esc = (s: string | number | null | undefined): string =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
