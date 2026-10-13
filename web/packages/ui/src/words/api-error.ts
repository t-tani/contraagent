// A request to the monitor's API that got no JSON answer, in words: the URL and
// the cause (render time: msg()).
import type { ApiError } from '@contraagent/api';
import { msg, str } from '@lit/localize';

/** "No monitor API at http://host/api/runs: the response is HTML, not JSON". */
export function apiErrorLine({ url, failure, status, type }: ApiError): string {
  const why =
    failure === 'network'
      ? msg('network error, no response')
      : failure === 'status'
        ? msg(str`the response status is ${status}`)
        : type.includes('html')
          ? msg('the response is HTML, not JSON')
          : msg('the response is not JSON');
  return msg(str`No monitor API at ${url}: ${why}`);
}
