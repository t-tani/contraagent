// Rounds as the reader counts them, from each round's launch and the task's
// journal rows.
//
// Each round is one turn of the coding agent. A *try* starts a new session
// (the first one, or a retry after a failure); a *fix-up* continues the same
// session after the output failed its checks, with the errors in its prompt; a
// *model switch* starts a session on the next model of the failover chain
// within the same try (the journal row's `hops`), after a rate limit.
import type { LaunchEvent } from '@contraagent/api';
import type { RoundInfo, TryResult } from '../../core/events.js';

/** The start of the prompt the runner sends when an output failed its checks (contracts.py). */
const FIXUP_PROMPT = 'The output file(s) you wrote do not pass their checks.';

/** The check errors a fix-up's prompt lists (the lines under `Errors:`). */
export function fixupErrors(prompt: string | null | undefined): string[] {
  const out: string[] = [];
  let inErrors = false;
  for (const line of (prompt || '').split('\n')) {
    if (/^Errors:\s*$/.test(line)) inErrors = true;
    else if (inErrors && line.startsWith('- ')) out.push(line.slice(2));
    else if (inErrors && line.trim() && !line.startsWith('- ')) inErrors = false;
  }
  return out;
}

export const isFixup = (launch: Pick<LaunchEvent, 'prompt'> | null | undefined): boolean =>
  !!launch && (launch.prompt || '').startsWith(FIXUP_PROMPT);


/**
 * Classify each round (by its launch) as a try or a fix-up, and attach what is known of
 * its result. `rows` are the task's journal rows in order; the n-th that ran is the n-th try's.
 */
export function classifyRounds(launches: readonly (Pick<LaunchEvent, 'prompt'> | null)[], rows: readonly TryResult[]): RoundInfo[] {
  // The tries that ran, in order: a resumed run numbers a task's attempts from 0 again,
  // so a try's row is found by its place, not by its attempt number.
  const byTry = new Map(rows.filter((r) => r.stop !== 'invalid_input' && r.stop !== 'skipped').map((r, i) => [i + 1, r]));
  const out: RoundInfo[] = [];
  let tryNo = 0;
  let fixupNo = 0;
  let hopNo = 0;
  launches.forEach((l, i) => {
    const hops = byTry.get(tryNo)?.hops?.length ?? 1;
    if (i > 0 && isFixup(l)) fixupNo++;
    else if (i > 0 && hopNo + 1 < hops) {
      hopNo++; // a fresh session within the same try: the next model of its chain
      fixupNo = 0;
    } else {
      tryNo++;
      hopNo = 0;
      fixupNo = 0;
    }
    const hop = byTry.get(tryNo)?.hops?.[hopNo];
    const model = hop?.model || hop?.route || '';
    const kind = fixupNo ? 'fixup' : hopNo ? 'switch' : 'try';
    out.push({ kind, tryNo, fixupNo, hopNo, model, result: null, rejectedWith: [], switchedStop: '', switchedTo: '', row: null });
  });
  out.forEach((r, i) => {
    const next = out[i + 1];
    if (next && next.tryNo === r.tryNo && next.hopNo !== r.hopNo) {
      r.result = 'switched';
      r.switchedStop = byTry.get(r.tryNo)?.hops?.[r.hopNo]?.stop ?? '';
      r.switchedTo = next.model;
      return;
    }
    if (next && next.tryNo === r.tryNo) {
      r.result = 'rejected';
      r.rejectedWith = fixupErrors(launches[i + 1]?.prompt);
      return;
    }
    const row = byTry.get(r.tryNo) ?? null;
    r.row = row;
    r.result = row ? (row.ok ? 'ok' : 'failed') : null;
  });
  return out;
}

/** The check name in an error line (`.../delta.json: [three_points] points: ...` -> `three_points`). */
export const checkName = (error: string): string => /\[([\w.-]+)\]/.exec(error)?.[1] ?? '';

/** A check error as the reader reads it: `[three_points] points: ...` after a path -> `three_points: points: ...`. */
export function checkMessage(error: string): string {
  const m = /\[([\w.-]+)\]\s*(.*)$/.exec(error);
  return m ? `${m[1]}: ${m[2]}` : error;
}
