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
  paths,
} from './types.js';

/** A request the monitor answered with an error status. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
  ) {
    super(`${status} ${path}`);
    this.name = 'ApiError';
  }
}

export interface ClientOptions {
  /** Where the monitor is served; '' (the default) is the page's own origin. */
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
}

/** Typed calls for every JSON route of the monitor. Each throws `ApiError` on a non-2xx answer. */
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
  /** The JSON answer of GET `route`; `ApiError` on a non-2xx status or an empty answer. */
  async function get<P extends Route>(route: P, params?: Params<P>): Promise<Answer<P>> {
    const { path = {}, query = {} } = (params ?? {}) as { path?: Record<string, string>; query?: Record<string, number> };
    const url = origin + route.replace(/\{(\w+)\}/g, (part, name: string) => (name in path ? encodeURIComponent(path[name]!) : part));
    const search = Object.entries(query)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join('&');
    const response = await fetch(new Request(search ? `${url}?${search}` : url));
    if (!response.ok || response.status === 204 || response.headers.get('Content-Length') === '0')
      throw new ApiError(response.status, new URL(response.url, 'http://x').pathname);
    return (await response.json()) as Answer<P>;
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
  };
}
