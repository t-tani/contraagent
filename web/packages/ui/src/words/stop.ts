// How an attempt ended (a journal row's `stop`), in words.
import { inputProblems } from '@contraagent/api';
import { msg, str } from '@lit/localize';

/**
 * How one attempt ended (a journal row's `stop`), in words. Unknown values are shown as they are.
 * With the row's `reason`, a refused input names its problem (missing, or failed checks).
 */
export function stopLabel(stop: string | null | undefined, reason?: string | null): string {
  switch (stop) {
    case 'completed':
      return msg('done', { id: 'stop-completed', desc: 'How an attempt ended: completed' });
    case 'skipped':
      return msg('skipped');
    case 'invalid_input': {
      const kinds = new Set(inputProblems(reason).map((p) => p.problem));
      if (kinds.size === 1 && kinds.has('missing')) return msg('not started (input missing)');
      if (kinds.size === 1 && kinds.has('checks')) return msg('not started (input failed checks)');
      return msg('not started (input missing or failed checks)');
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
      return msg('stalled (no output)');
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
      return msg('could not start the agent');
    case 'credential_mismatch':
      return msg('wrong identity used');
    case null:
    case undefined:
    case '':
      return '—';
    default:
      return msg(str`unknown (${stop})`);
  }
}
