// Durations, times and small text helpers shared by the views.
import { msg, str } from '@lit/localize';
import { getLocale } from '../core/i18n.js';
import { clockFormat } from './clock-format.js';

// The formats that read the same in every language are the generic package's.
export { esc, fmtDur } from '@contraagent/elements';

/**
 * An ISO time in the reader's time zone, as the UI locale writes it: `10:38:40`,
 * or with the date `Oct 12, 10:38:40` (the month as a word, so no reader takes
 * the day for the month). '' when there is no time.
 */
export function localTime(ts: string | null | undefined, withDate = false, locale: string = getLocale()): string {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return clockFormat(locale, withDate).format(d);
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

/** `s` as a sentence on its own: its first letter upper-cased (a phrase that also follows a colon starts lower case). */
export const sentence = (s: string): string => s.charAt(0).toLocaleUpperCase(getLocale()) + s.slice(1);

/** The facts of one row, chip or line, in order, without the empty ones (for `factLine`). */
export const factList = (...xs: (string | null | undefined | false)[]): string[] => xs.filter((x): x is string => !!x);

/** Facts of one row, chip or line, in order: `attempt 1 | done | 0.2s`. Empty facts are left out. */
export const facts = (...xs: (string | null | undefined | false)[]): string => factList(...xs).join(' | ');

const lists = new Map<string, Intl.ListFormat>();

/**
 * Words a reader reads as a list, as the UI locale writes one: `Pass 1, Pass 2, and Pass 3`
 * in English, `1 周目、2 周目、3 周目` in Japanese. Codes and identifiers are joined with `, ` instead.
 */
export function listText(items: readonly string[], locale: string = getLocale()): string {
  let f = lists.get(locale);
  if (!f) {
    f = new Intl.ListFormat(locale, { type: 'conjunction' });
    lists.set(locale, f);
  }
  return f.format(items);
}

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

/** What of the rows' tokens could not be read (`usage_unknown`): `tokens` when any row's,
 * else `calls` when any row's, else ''. */
export function usageUnknown(rows: readonly { usage_unknown?: string | null }[]): '' | 'calls' | 'tokens' {
  const all = new Set(rows.map((r) => r.usage_unknown ?? ''));
  return all.has('tokens') ? 'tokens' : all.has('calls') ? 'calls' : '';
}

/** The words for `usage_unknown` (`usageUnknown`): a short label and its tooltip; null when nothing is unknown. */
export function usageUnknownWords(unknown: '' | 'calls' | 'tokens'): { label: string; tip: string } | null {
  if (unknown === 'calls')
    return {
      label: msg('Tokens per API call unknown'),
      tip: msg('Only the token totals that the coding agent printed are known, not the tokens of each API call (usage_unknown)'),
    };
  if (unknown === 'tokens')
    return { label: msg('Tokens unknown'), tip: msg('The tokens of an agent session that ran are not known (usage_unknown)') };
  return null;
}

/** A row's unread event types with their counts (`session_settled ×2, x ×1`); '' when none. */
export function unreadEvents(rows: readonly { unread_events?: Record<string, number> | null }[]): string {
  const total = new Map<string, number>();
  for (const r of rows) for (const [k, n] of Object.entries(r.unread_events ?? {})) total.set(k, (total.get(k) ?? 0) + n);
  return [...total].map(([k, n]) => `${k} ×${n}`).join(', ');
}
