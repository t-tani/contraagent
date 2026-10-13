// Durations, times and small text helpers shared by the views.
import { msg, str } from '@lit/localize';
import { getLocale } from '../i18n.js';

/**
 * A duration in seconds, the one format every view uses: `<0.1s`, `4.2s`,
 * `37s`, `2m 05s`, `1h 02m`; '—' when unknown.
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

const formats = new Map<string, Intl.DateTimeFormat>();
function formatter(locale: string, withDate: boolean): Intl.DateTimeFormat {
  const id = `${locale}|${withDate}`;
  let f = formats.get(id);
  if (!f) {
    f = new Intl.DateTimeFormat(locale, {
      ...(withDate ? { month: 'short', day: 'numeric' } : {}),
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    });
    formats.set(id, f);
  }
  return f;
}

/**
 * An ISO time in the reader's time zone, as the UI locale writes it: `10:38:40`,
 * or with the date `Oct 12, 10:38:40` (the month as a word, so no reader takes
 * the day for the month). '' when there is no time.
 */
export function localTime(ts: string | null | undefined, withDate = false, locale: string = getLocale()): string {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return formatter(locale, withDate).format(d);
}

/** An ISO time as `just now`, `5m ago`, `3h ago`, `2d ago` (the run picker only; rows and chips show `localTime`). */
export function relAgo(iso: string | null | undefined, now = Date.now()): string {
  const t = Date.parse(iso || '');
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, (now - t) / 1000);
  if (s < 60) return msg('just now');
  if (s < 3600) return msg(str`${Math.floor(s / 60)}m ago`);
  if (s < 86400) return msg(str`${Math.floor(s / 3600)}h ago`);
  return msg(str`${Math.floor(s / 86400)}d ago`);
}

/** Facts of one row, chip or line, in order: `attempt 1 | done | 0.2s`. Empty facts are left out. */
/** `s` as a sentence on its own: its first letter upper-cased (a phrase that also follows a colon starts lower case). */
export const sentence = (s: string): string => s.charAt(0).toLocaleUpperCase(getLocale()) + s.slice(1);

export const facts = (...xs: (string | null | undefined | false)[]): string => xs.filter(Boolean).join(' | ');

/** `kind · unit`, or the bare kind for a run-scope task. */
export const kindUnit = (x: { kind?: string | null | undefined; unit?: string | null | undefined }, sep = ' · '): string =>
  `${x.kind ?? ''}${x.unit ? sep + x.unit : ''}`;

/** The first line of a text, cut at 100 characters. */
export function firstLine(s: string | null | undefined): string {
  const t = (s || '').trim();
  if (!t) return '';
  const l = (t.split('\n')[0] || '').trim();
  return l.length > 100 ? `${l.slice(0, 100)}…` : l;
}

/** HTML-escape a text for the few places that build markup as a string (markdown, highlighting). */
export const esc = (s: string | number | null | undefined): string =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

/** A token count, compact: `950`, `1.2k`, `34k`, `1.3M`. */
export function tokenCount(n: number | null | undefined): string {
  const v = n ?? 0;
  if (v < 1000) return String(Math.round(v));
  if (v < 10_000) return `${(v / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  if (v < 1_000_000) return `${Math.round(v / 1000)}k`;
  return `${(v / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
}

/** A cost in USD: `$0.041`, `$1.23`, `<$0.001`; '—' when none was reported. */
export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  if (v === 0) return '$0';
  if (v < 0.001) return '<$0.001';
  if (v < 1) return `$${v.toFixed(3)}`; // fixed decimals, so columns of costs line up
  return `$${v.toFixed(2)}`;
}

/** A row's unread event types with their counts (`session_settled ×2, x ×1`); '' when none. */
export function unreadEvents(rows: readonly { unread_events?: Record<string, number> | null }[]): string {
  const total = new Map<string, number>();
  for (const r of rows) for (const [k, n] of Object.entries(r.unread_events ?? {})) total.set(k, (total.get(k) ?? 0) + n);
  return [...total].map(([k, n]) => `${k} ×${n}`).join(', ');
}
