// The REST half of the monitor API, typed by the generated `paths`.
import createClient from 'openapi-fetch';
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
  journal(run: string, since?: number): Promise<JournalPage>;
  definitions(run: string): Promise<TaskDefinition[]>;
  task(run: string, slotOrKey: string): Promise<TaskDetail>;
  stream(run: string, key: string, since?: number): Promise<StreamPage>;
  panel(run: string, name: string): Promise<JsonObject>;
}

async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, response } = await call;
  if (!response.ok || data === undefined) throw new ApiError(response.status, new URL(response.url, 'http://x').pathname);
  return data;
}

export function createMonitorClient(options: ClientOptions = {}): MonitorClient {
  const baseUrl = (options.baseUrl ?? '').replace(/\/$/, '');
  const c = createClient<paths>({
    baseUrl: baseUrl || globalThis.location?.origin || '',
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  return {
    baseUrl,
    info: () => unwrap(c.GET('/api/info')),
    runs: () => unwrap(c.GET('/api/runs')),
    journal: (run, since = 0) => unwrap(c.GET('/api/runs/{run}/journal', { params: { path: { run }, query: { since } } })),
    definitions: (run) => unwrap(c.GET('/api/runs/{run}/definitions', { params: { path: { run } } })),
    task: (run, slotOrKey) =>
      unwrap(c.GET('/api/runs/{run}/task/{slot_or_key}', { params: { path: { run, slot_or_key: slotOrKey } } })),
    stream: (run, key, since = 0) =>
      unwrap(c.GET('/api/runs/{run}/stream/{key}', { params: { path: { run, key }, query: { since } } })),
    panel: (run, name) => unwrap(c.GET('/api/runs/{run}/panels/{name}', { params: { path: { run, name } } })),
  };
}
