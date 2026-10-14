// A credential's quota rest (the reader's "paused identity") and why the queue
// deferred a task, in words. The data says it (`QuotaRest`, `DeferralCause`);
// the recorded English sentence (`PlanNode.deferred`) is only the fallback for a
// cause these words do not know.
import type { CredentialRest, DeferralCause, QuotaCap, QuotaRest, SkippedHop } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { credentialLabel } from './credential.js';
import { facts, fmtDur, localTime } from './format.js';
import { pct } from './quota.js';

/** A window's usage in words: `5-hour usage 93%`, `Weekly usage 96%`. */
function usage(window: string, value: number | null | undefined): string {
  return window === 'seven_day' ? msg(str`Weekly usage ${pct(value)}`) : msg(str`5-hour usage ${pct(value)}`);
}

/** A cap as written in the config: `90%`, `0.5%` (a cap is not rounded: 0.5 is not 1). */
const capPct = (cap: number | null | undefined): string => (cap == null ? '—' : `${Number(cap.toFixed(2))}%`);

/** A cap in words: `limit 90%`. */
export const capLabel = (cap: number | null | undefined): string => msg(str`limit ${capPct(cap)}`);

/**
 * Why an identity is paused, its facts after its name:
 * `5-hour usage 93% | limit 90% | until 10/14 14:30`, or `Usage rule: over the pace`.
 */
export function restFacts(r: QuotaRest): string {
  if (r.rule) return msg(str`Usage rule: ${r.rule}`);
  return facts(usage(r.window ?? '', r.pct), capLabel(r.cap), r.until ? msg(str`until ${localTime(r.until, true)}`) : '');
}

/** A paused identity in one line: `Identity personal paused | 5-hour usage 93% | limit 90% | until 10/14 14:30`. */
export const restLine = (r: QuotaRest): string => facts(msg(str`Identity ${credentialLabel(r.credential)} paused`), restFacts(r));

/** The rests of a cause, one per identity (a pool's members, the hops of one identity). */
function byIdentity<T extends QuotaRest>(rests: readonly T[]): T[] {
  const seen = new Set<string>();
  return rests.filter((r) => !seen.has(r.credential) && seen.add(r.credential));
}

/**
 * Why the queue deferred a task, in words: `Past the deadline`, `Identity personal paused | ...`.
 * `recorded`: the run's own sentence, for a cause these words do not name. '' for none.
 */
export function deferredText(cause: DeferralCause | null | undefined, recorded = ''): string {
  switch (cause?.cause) {
    case 'deadline':
      return msg('Past the deadline');
    case 'grace_window':
      return msg('Past the deadline and its finishing time');
    case 'cannot_finish':
      return facts(
        msg('Cannot finish before the deadline'),
        cause.need_s != null ? msg(str`needs ${fmtDur(cause.need_s)}`) : '',
        cause.left_s != null ? msg(str`${fmtDur(cause.left_s)} left`) : '',
      );
    case 'dependency_not_queued':
      return msg('An earlier task was never scheduled');
    case 'rest': {
      const rests = byIdentity(cause.rests ?? []);
      if (!rests.length) return recorded;
      return rests.length === 1 ? restLine(rests[0]!) : facts(restLine(rests[0]!), msg(str`+${rests.length - 1} paused identities`));
    }
    default:
      return recorded;
  }
}

/** The tooltip of a deferral: every paused identity, one per line; '' when there is nothing more to say. */
export function deferredTip(cause: DeferralCause | null | undefined): string {
  const rests = cause?.cause === 'rest' ? byIdentity(cause.rests ?? []) : [];
  return rests.length > 1 ? rests.map(restLine).join('\n') : '';
}

/** A hop passed over without an agent session, in a model switch: `claude-haiku-5-5 (identity paused)`. */
export const skippedHopStep = (h: SkippedHop): string => msg(str`${h.model || h.route || '—'} (identity paused)`);

/** One rest of an identity over a run: `Paused 10:31 → 10:45 | 5-hour usage 93% | limit 90%`; still paused: `Paused since 10:31 | ...`. */
export function restSpan(r: CredentialRest): string {
  const when = r.ended ? msg(str`Paused ${localTime(r.since)} → ${localTime(r.ended)}`) : msg(str`Paused since ${localTime(r.since)}`);
  return facts(when, r.rule ? msg(str`Usage rule: ${r.rule}`) : facts(usage(r.window ?? '', r.pct), capLabel(r.cap)));
}

/** An identity's caps in one line: `Limits: 5-hour 90% | weekly 95%`; '' for none. */
export function capsLine(c: QuotaCap | undefined): string {
  if (!c || (c.five_hour_pct == null && c.seven_day_pct == null)) return '';
  const parts = facts(
    c.seven_day_pct != null ? msg(str`weekly ${capPct(c.seven_day_pct)}`) : '',
    c.five_hour_pct != null ? msg(str`5-hour ${capPct(c.five_hour_pct)}`) : '',
  );
  return msg(str`Limits: ${parts}`);
}
