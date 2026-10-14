// Words for a subscription's utilization readings (see @contraagent/api quota.ts).
import type { QuotaReading } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, localTime, sentence } from './format.js';
import { credentialLabel } from './credential.js';

/** A utilization as a whole percent: `14%`; '—' when not reported. */
export const pct = (v: number | null | undefined): string => (v === null || v === undefined ? '—' : `${Math.round(v)}%`);

/** A reading's `status` in words, with the window it is about when known (`near the limit | weekly`); '' for `allowed` (the usual case) or none. */
export function quotaStatusLabel(status: string | null | undefined, window?: string | null): string {
  if (!status || status === 'allowed') return '';
  const s = status.split(',');
  const word = s.some((x) => ['rejected', 'exhausted', 'quota', 'blocked'].includes(x))
    ? msg('limit reached')
    : s.every((x) => ['allowed_warning', 'warning'].includes(x))
      ? msg('near the limit')
      : msg(str`unknown (${status})`);
  return window ? facts(word, windowName(window)) : word;
}

/**
 * A usage window's name: `5-hour`, `weekly`, and a model's own window by its model
 * (`seven_day_opus`: `weekly (opus)`); an unknown window as it is named.
 */
export function windowName(window: string): string {
  if (window === 'five_hour') return msg('5-hour');
  if (window === 'seven_day') return msg('weekly');
  const own = /^(five_hour|seven_day)_(.+)$/.exec(window);
  if (own) return own[1] === 'five_hour' ? msg(str`5-hour (${own[2]})`) : msg(str`weekly (${own[2]})`);
  return window;
}

/** An account's digest, short, as a label: `account 3f9c2a`. */
export const accountLabel = (account: string): string => msg(str`account ${account.slice(0, 6)}`);

/** When a window resets, relative to now: `resets in 2h 58m`; '' when unknown. */
export function resetsIn(iso: string | null | undefined, now = Date.now()): string {
  const t = Date.parse(iso ?? '');
  if (Number.isNaN(t)) return '';
  if (t <= now) return msg('reset');
  const h = (t - now) / 3_600_000;
  // A weekly window is days away: days and hours read better than 121h.
  const left = h >= 48 ? msg(str`${Math.floor(h / 24)}d ${Math.floor(h % 24)}h`) : fmtDur((t - now) / 1000);
  return msg(str`resets in ${left}`);
}

/** A reading in one line, the weekly window first (the one that runs out first in practice): `weekly 41% | 5-hour 14%`. */
export const readingShort = (r: QuotaReading): string =>
  facts(msg(str`weekly ${pct(r.seven_day_pct)}`), msg(str`5-hour ${pct(r.five_hour_pct)}`));

/** A reading in full, for a tooltip: both windows, their resets, when it arrived. */
export function readingTip(r: QuotaReading): string {
  const parts = [
    r.seven_day_resets_at
      ? msg(str`Weekly usage ${pct(r.seven_day_pct)} (resets ${localTime(r.seven_day_resets_at, true)})`)
      : msg(str`Weekly usage ${pct(r.seven_day_pct)}`),
    r.five_hour_resets_at
      ? msg(str`5-hour usage ${pct(r.five_hour_pct)} (resets ${localTime(r.five_hour_resets_at, true)})`)
      : msg(str`5-hour usage ${pct(r.five_hour_pct)}`),
    // The windows beyond the two: a model's own (`weekly (opus)`).
    ...Object.entries(r.windows ?? {})
      .filter(([name]) => name !== 'five_hour' && name !== 'seven_day')
      .map(([name, w]) => msg(str`${sentence(windowName(name))} usage ${pct(w.pct)}`)),
    msg(str`Reported ${localTime(r.observed_at, true)}`),
  ];
  const status = quotaStatusLabel(r.status, r.status_window);
  if (status) parts.push(msg(str`Status: ${status}`));
  if (r.threshold_pct != null) parts.push(msg(str`Warning threshold: ${pct(r.threshold_pct)}`));
  if (r.overage_status) parts.push(msg(str`Extra usage: ${extraUsage(r.overage_status)}`));
  if (r.account) parts.push(msg(str`Account: ${r.account}`));
  return parts.join('\n');
}

/** Whether usage past the limit is allowed (`overage_status`): `allowed`, `not allowed`, else as reported. */
function extraUsage(status: string): string {
  if (status === 'allowed' || status === 'allowed_warning') return msg('allowed');
  if (status === 'rejected') return msg('not allowed');
  return status;
}

/** A reading with its account: `weekly 41% | 5-hour 14% | default`. */
export const accountReading = (r: QuotaReading): string => facts(readingShort(r), credentialLabel(r.credential));

/** One account's latest reading (`credential` + `last`). */
interface AccountLast {
  credential: string;
  last: QuotaReading;
}

/**
 * The busiest account's latest reading, for a one-line summary:
 * `weekly 43% | 5-hour 33%`; with more accounts, the busiest one's name and `1 more account`.
 * `accounts` comes sorted, the highest weekly use first.
 */
export function accountsLine(accounts: readonly AccountLast[]): string {
  const top = accounts[0];
  if (!top) return '';
  const more = accounts.length - 1;
  // One account: its name is in the tooltip; with more, the line names the busiest.
  if (!more) return readingShort(top.last);
  const line = accountReading(top.last);
  return facts(line, more === 1 ? msg('1 more account') : msg(str`${more} more accounts`));
}

/** Every account's latest reading, one per line, for a tooltip. */
export const accountsTip = (accounts: readonly AccountLast[]): string =>
  accounts.map((a) => (a.credential ? `${credentialLabel(a.credential)}\n${readingTip(a.last)}` : readingTip(a.last))).join('\n\n');
