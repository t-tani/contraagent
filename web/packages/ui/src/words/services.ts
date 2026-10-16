// A service (the long-lived helper a claim name stands for, `Plan.services`) in words:
// its state, when it started and stopped, and why it stopped.
import type { ServiceSpan } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, localTime } from './format.js';

/** The state of one start of a service: it runs, it stopped, its start failed, or its stop is not recorded. */
export type ServiceState = 'running' | 'stopped' | 'failed' | 'unknown';

/** The state of one start of a service; `live`: whether its run still runs. */
export function serviceState(s: ServiceSpan, live: boolean): ServiceState {
  if (s.start_error) return 'failed';
  if (s.stopped_at) return 'stopped';
  return live ? 'running' : 'unknown';
}

/** The state in words: `running`, `stopped`, `did not start`, `stop not recorded`. */
export function serviceStateLabel(state: ServiceState): string {
  switch (state) {
    case 'running':
      return msg('running', { id: 'service-running', desc: 'A service that is running' });
    case 'stopped':
      return msg('stopped', { desc: 'A service that stopped' });
    case 'failed':
      return msg('did not start', { desc: 'A service whose start failed' });
    default:
      return msg('stop not recorded', { desc: 'A service of a finished run whose stop is not in services.jsonl' });
  }
}

/** Why a service stopped, in words; '' while it runs. */
export function stopCauseLabel(cause: ServiceSpan['stop_cause']): string {
  switch (cause) {
    case 'run_end':
      return msg('The run ended');
    case 'interrupted':
      return msg('The run was stopped by a signal');
    default:
      return '';
  }
}

/**
 * The facts of one start of a service, in one line:
 * `Started 10:02:03 in 1.2s | Stopped 10:05:10 | The run ended`, or `10:02:03 | OSError: port 9000 in use`
 * for a start that failed (the error is the value, so the line holds no label of its own).
 */
export function serviceFacts(s: ServiceSpan): string {
  if (s.start_error) return facts(localTime(s.started_at), s.start_error);
  return facts(
    msg(str`Started ${localTime(s.started_at)} in ${fmtDur(s.start_s ?? 0)}`),
    s.stopped_at ? msg(str`Stopped ${localTime(s.stopped_at)}`) : '',
    stopCauseLabel(s.stop_cause),
    s.stop_error ? msg('Stop failed') : '',
    s.stop_error,
  );
}
