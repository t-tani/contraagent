// How an attempt ended (a journal row's `stop`), in words.
import { inputProblems, type Stop } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { isStop } from '../lib/tone.js';

/**
 * How one attempt ended (a journal row's `stop`), in words. A value contraagent does not write is shown as it is.
 * With the row's `reason`, a refused input names its problem (missing, or failed checks).
 */
export function stopLabel(stop: string | null | undefined, reason?: string | null): string {
  if (!stop) return '—';
  return isStop(stop) ? knownStopLabel(stop, reason) : msg(str`unknown (${stop})`);
}

/** A stop contraagent writes, in words: every `Stop` has a case, or this fails type-checking. */
function knownStopLabel(stop: Stop, reason?: string | null): string {
  switch (stop) {
    case 'completed':
      return msg('done', { id: 'stop-completed', desc: 'How an attempt ended: completed' });
    case 'skipped':
      return msg('skipped');
    case 'partial':
      return msg('partly done', { id: 'stop-partial', desc: 'How an attempt ended: partial, its output a placeholder' });
    case 'invalid_input': {
      const kinds = new Set(inputProblems(reason).map((p) => p.problem));
      if (kinds.size === 1 && kinds.has('missing')) return msg('not started (input missing)');
      if (kinds.size === 1 && kinds.has('checks')) return msg('not started (input failed checks)');
      if (kinds.size === 1 && kinds.has('failed')) return msg('not started (earlier task failed)');
      if (kinds.size === 2 && kinds.has('missing') && kinds.has('checks')) return msg('not started (input missing and input failed checks)');
      return msg('not started', { id: 'stop-invalid-input', desc: 'How an attempt ended: invalid_input, with no input named' });
    }
    case 'invalid_output':
      return msg('failed checks');
    case 'timeout':
      return msg('timed out');
    case 'max_turns':
      return msg('turn limit reached');
    case 'budget':
      return msg('cost limit reached');
    case 'context_budget':
      return msg('context limit reached');
    case 'stalled':
      return msg('stalled (no events)');
    case 'auth_failed':
      return msg('authentication failed');
    case 'api_error':
      return msg('API error');
    case 'rate_limited':
      return msg('rate limited');
    case 'refused':
      return msg('refused by the model');
    case 'aborted':
      return msg('aborted');
    case 'denied':
      return msg('permission denied');
    case 'error':
      return msg('error');
    case 'no_output':
      return msg('ended without a result');
    case 'launch_failed':
      return msg('agent session did not start');
    case 'credential_mismatch':
      return msg('wrong identity used');
  }
}
