// The REST half of the monitor API, typed by the generated `paths`.
import type {
  Info,
  JournalPage,
  JsonObject,
  RunSummary,
  StreamPage,
  TaskDefinition,
  TaskDetail,
  paths,
} from './types.js';

/**
 * Why a request got no JSON answer: `network`, no response (a network error, a
 * refused connection, or a cross-origin response the browser blocked);
 * `status`, a status outside 2xx; `empty`, no body; `not-json`, a body that is
 * not JSON (such as the HTML page a development server answers every path with).
 */
export type ApiFailure = 'network' | 'status' | 'empty' | 'not-json';

/** A request to the monitor's API that got no JSON answer. Its message states the URL and the cause. */
export class ApiError extends Error {
  constructor(
    /** The URL requested. */
    readonly url: string,
    readonly failure: ApiFailure,
    /** The response's status; 0 with no response. */
    readonly status = 0,
    /** The response's media type, such as `text/html`; '' when it states none. */
    readonly type = '',
  ) {
    // A status other than 404 comes from a server that has the API.
    const lead = failure === 'status' && status !== 404 ? 'Monitor API error at' : 'No monitor API at';
    super(`${lead} ${url}: ${failureText(failure, status, type)}`);
    this.name = 'ApiError';
  }
}

/** The response is HTML: a page, not the API. */
export const isHtml = (type: string): boolean => type === 'text/html' || type === 'application/xhtml+xml';

/** The media type is JSON. */
export const isJson = (type: string): boolean => type === 'application/json' || type.endsWith('+json');

function failureText(failure: ApiFailure, status: number, type: string): string {
  switch (failure) {
    case 'network':
      return 'network error, no response';
    case 'status':
      return `the response status is ${status}`;
    case 'empty':
      return 'the response is empty';
    case 'not-json':
      return isHtml(type) ? 'the response is HTML, not JSON' : type && !isJson(type) ? `the response is ${type}, not JSON` : 'the response is not valid JSON';
  }
}

export interface ClientOptions {
  /** Where the monitor is served; '' (the default) is the page's own origin. */
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
}

/** Typed calls for every JSON route of the monitor. Each throws `ApiError` when it gets no JSON answer. */
export interface MonitorClient {
  readonly baseUrl: string;
  info(): Promise<Info>;
  runs(): Promise<RunSummary[]>;
  journal(run: string, since?: number): Promise<JournalPage>;
  definitions(run: string): Promise<TaskDefinition[]>;
  task(run: string, key: string): Promise<TaskDetail>;
  stream(run: string, key: string, since?: number): Promise<StreamPage>;
  panel(run: string, name: string): Promise<JsonObject>;
}

/** The monitor's GET routes. */
type Route = { [P in keyof paths]: paths[P] extends { get: object } ? P : never }[keyof paths];
type Operation<P extends Route> = paths[P] extends { get: infer O } ? O : never;
/** A route's parameters: `path` fills its `{name}` parts, `query` is its query string. */
type Params<P extends Route> = Operation<P> extends { parameters: infer X } ? X : never;
/** A route's JSON answer (status 200). */
type Answer<P extends Route> =
  Operation<P> extends { responses: { 200: { content: { 'application/json': infer T } } } } ? T : never;

export function createMonitorClient(options: ClientOptions = {}): MonitorClient {
  const baseUrl = (options.baseUrl ?? '').replace(/\/$/, '');
  const origin = (baseUrl || globalThis.location?.origin || '').replace(/\/$/, '');
  const fetch = options.fetch ?? globalThis.fetch;
  /** The JSON answer of GET `route`; `ApiError` when there is none. */
  async function get<P extends Route>(route: P, params?: Params<P>): Promise<Answer<P>> {
    const { path = {}, query = {} } = (params ?? {}) as { path?: Record<string, string>; query?: Record<string, number> };
    const url = origin + route.replace(/\{(\w+)\}/g, (part, name: string) => (name in path ? encodeURIComponent(path[name]!) : part));
    const search = Object.entries(query)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join('&');
    const target = search ? `${url}?${search}` : url;
    let response: Response;
    try {
      response = await fetch(new Request(target));
    } catch {
      throw new ApiError(target, 'network');
    }
    const { status } = response;
    const type = (response.headers.get('Content-Type') ?? '').split(';')[0]!.trim().toLowerCase();
    if (!response.ok) throw new ApiError(target, 'status', status, type);
    if (status === 204 || response.headers.get('Content-Length') === '0') throw new ApiError(target, 'empty', status, type);
    if (type && !isJson(type)) throw new ApiError(target, 'not-json', status, type);
    try {
      return (await response.json()) as Answer<P>;
    } catch {
      throw new ApiError(target, 'not-json', status, type);
    }
  }
  return {
    baseUrl,
    info: () => get('/api/info'),
    runs: () => get('/api/runs'),
    journal: (run, since = 0) => get('/api/runs/{run}/journal', { path: { run }, query: { since } }),
    definitions: (run) => get('/api/runs/{run}/definitions', { path: { run } }),
    task: (run, key) => get('/api/runs/{run}/task/{key}', { path: { run, key } }),
    stream: (run, key, since = 0) => get('/api/runs/{run}/stream/{key}', { path: { run, key }, query: { since } }),
    panel: (run, name) => get('/api/runs/{run}/panels/{name}', { path: { run, name } }),
  };
}
