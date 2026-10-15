// The REST half of the monitor API, typed by the generated `paths`.
import type {
  Hosts,
  Info,
  JournalPage,
  JsonObject,
  RunSummary,
  StreamPage,
  TaskDefinition,
  TaskDetail,
  Trends,
  TrendsQuery,
  paths,
} from './types.js';

/**
 * Why a request got no JSON answer: `network`, no response (a network error, a
 * refused connection, or a cross-origin response the browser blocked);
 * `status`, a status outside 2xx; `not-json`, a body that is not JSON (empty,
 * or the HTML page a development server answers every path with).
 */
export type ApiFailure = 'network' | 'status' | 'not-json';

/**
 * A request to the monitor's API that got no JSON answer. Its message states
 * the URL, the failure, the status and the media type
 * ("No JSON answer from http://host/api/runs: not-json 200 text/html");
 * `@contraagent/ui` words it for the reader.
 */
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
    super(`No JSON answer from ${url}: ${failure} ${status} ${type}`.trim());
    this.name = 'ApiError';
  }
}

export interface ClientOptions {
  /** Where the monitor is served; '' (the default) is the page's own origin. */
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
}

/** Typed calls for every JSON endpoint of the monitor. Each throws `ApiError` when it gets no JSON answer. */
export interface MonitorClient {
  readonly baseUrl: string;
  info(): Promise<Info>;
  runs(): Promise<RunSummary[]>;
  /** The hosts behind the runs (a hub: `Info.hosts`). */
  hosts(): Promise<Hosts>;
  journal(run: string, since?: number): Promise<JournalPage>;
  definitions(run: string): Promise<TaskDefinition[]>;
  task(run: string, key: string): Promise<TaskDetail>;
  stream(run: string, key: string, since?: number): Promise<StreamPage>;
  panel(run: string, name: string): Promise<JsonObject>;
  /** What the runs of a period add up to. */
  trends(query?: TrendsQuery): Promise<Trends>;
  /** A trend panel's body over the runs of a period (`Panel(scope="trends")`). */
  trendsPanel(name: string, query?: TrendsQuery): Promise<JsonObject>;
}

/** The monitor's GET endpoints. */
type Endpoint = { [P in keyof paths]: paths[P] extends { get: object } ? P : never }[keyof paths];
type Operation<P extends Endpoint> = paths[P] extends { get: infer O } ? O : never;
/** An endpoint's parameters: `path` fills its `{name}` parts, `query` is its query string. */
type Params<P extends Endpoint> = Operation<P> extends { parameters: infer X } ? X : never;
/** An endpoint's JSON answer (status 200). */
type Answer<P extends Endpoint> =
  Operation<P> extends { responses: { 200: { content: { 'application/json': infer T } } } } ? T : never;

export function createMonitorClient(options: ClientOptions = {}): MonitorClient {
  const baseUrl = (options.baseUrl ?? '').replace(/\/$/, '');
  const origin = (baseUrl || globalThis.location?.origin || '').replace(/\/$/, '');
  const fetch = options.fetch ?? globalThis.fetch;
  /** The JSON answer of GET `endpoint`; `ApiError` when there is none. */
  async function get<P extends Endpoint>(endpoint: P, params?: Params<P>): Promise<Answer<P>> {
    const { path = {}, query = {} } = (params ?? {}) as { path?: Record<string, string>; query?: Record<string, number> };
    const url = origin + endpoint.replace(/\{(\w+)\}/g, (part, name: string) => (name in path ? encodeURIComponent(path[name]!) : part));
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
    const { status, ok } = response;
    const type = (response.headers.get('Content-Type') ?? '').split(';')[0]!.trim().toLowerCase();
    try {
      if (ok) return (await response.json()) as Answer<P>;
    } catch {
      // An empty body, an HTML page, or text that is not JSON.
    }
    throw new ApiError(target, ok ? 'not-json' : 'status', status, type);
  }
  return {
    baseUrl,
    info: () => get('/api/info'),
    runs: () => get('/api/runs'),
    hosts: () => get('/api/hosts'),
    journal: (run, since = 0) => get('/api/runs/{run}/journal', { path: { run }, query: { since } }),
    definitions: (run) => get('/api/runs/{run}/definitions', { path: { run } }),
    task: (run, key) => get('/api/runs/{run}/task/{key}', { path: { run, key } }),
    stream: (run, key, since = 0) => get('/api/runs/{run}/stream/{key}', { path: { run, key }, query: { since } }),
    panel: (run, name) => get('/api/runs/{run}/panels/{name}', { path: { run, name } }),
    trends: (query = {}) => get('/api/trends', { query: { ...query } }),
    trendsPanel: (name, query = {}) => get('/api/trends/panels/{name}', { path: { name }, query: { ...query } }),
  };
}
