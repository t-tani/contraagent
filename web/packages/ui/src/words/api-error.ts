// A request to the monitor's API that got no JSON answer, in words: the URL and
// the cause (render time: msg()).
import { isHtml, isJson, type ApiError } from '@contraagent/api';
import { msg, str } from '@lit/localize';

/** Why the request got no JSON answer. */
function cause(e: ApiError): string {
  switch (e.failure) {
    case 'network':
      return msg('network error, no response');
    case 'status':
      return msg(str`the response status is ${e.status}`);
    case 'empty':
      return msg('the response is empty');
    case 'not-json':
      if (isHtml(e.type)) return msg('the response is HTML, not JSON');
      if (e.type && !isJson(e.type)) return msg(str`the response is ${e.type}, not JSON`);
      return msg('the response is not valid JSON');
  }
}

/**
 * "No monitor API at http://host/api/runs: the response is HTML, not JSON". A
 * status other than 404 comes from a server that has the API:
 * "Monitor API error at http://host/api/runs: the response status is 500".
 */
export function apiErrorLine(e: ApiError): string {
  const url = e.url;
  const why = cause(e);
  return e.failure === 'status' && e.status !== 404
    ? msg(str`Monitor API error at ${url}: ${why}`)
    : msg(str`No monitor API at ${url}: ${why}`);
}
