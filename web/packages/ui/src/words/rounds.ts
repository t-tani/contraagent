import { runRelative } from '@contraagent/api';
// How a round is named and explained to the reader (render time: msg()).
import { msg, str } from '@lit/localize';
import { facts } from './format.js';
import { attemptLabel } from './attempts.js';
import { stopLabel } from './stop.js';
import type { RoundInfo } from '../core/events.js';

/**
 * "Attempt 1", "Correction 1", "Model switch"; with more than one attempt,
 * "Attempt 2 | correction 1" and "Attempt 2 | model switch". `name` is the name of
 * the round's attempt (`attemptNames`: "Attempt 1 | resumed run" in a resumed run).
 */
export function roundLabel(r: RoundInfo, tries: number, name = attemptLabel(r.tryNo - 1)): string {
  if (tries > 1) {
    if (r.fixupNo) return facts(name, msg(str`correction ${r.fixupNo}`));
    if (r.hopNo) return facts(name, msg('model switch'));
    return name;
  }
  if (r.fixupNo) return msg(str`Correction ${r.fixupNo}`);
  if (r.hopNo) return msg('Model switch');
  return attemptLabel(0);
}

/** One phrase on what this round was, for its prompt's heading; `resumed`: its attempt is the first of a resumed run. */
export function roundWhy(r: RoundInfo, resumed = false): string {
  if (r.fixupNo) return msg('same agent session, after failed checks');
  if (r.hopNo) return msg('new agent session on the next model');
  if (r.tryNo > 1 && resumed) return msg('new agent session in the resumed run');
  if (r.tryNo > 1) return msg(str`new agent session after attempt ${r.tryNo - 1} failed`);
  return msg('first agent session');
}

/** A switched round's model, and why it stopped: `primary-model: rate limited; switched to fallback-model`. */
export function switchText(r: RoundInfo): string {
  const from = r.model || msg('model');
  return r.switchedTo
    ? msg(str`${from}: ${stopLabel(r.switchedStop)}; switched to ${r.switchedTo}`)
    : msg(str`${from}: ${stopLabel(r.switchedStop)}; switched to the next model`);
}

/** The ✓ / ✕ mark, its word for screen readers and its tooltip. */
export function roundMark(r: RoundInfo, run: string): [mark: string, word: string, tip: string] {
  switch (r.result) {
    case 'ok':
      return ['✓', msg('passed'), msg('Output passed checks')];
    case 'rejected':
      return ['✕', msg('failed checks'), msg('Output failed checks')];
    case 'switched':
      return ['✕', stopLabel(r.switchedStop), switchText(r)];
    case 'failed':
      return ['✕', msg('failed'), runRelative(r.row?.reason, run) || stopLabel(r.row?.stop)];
    default:
      return ['', '', ''];
  }
}
