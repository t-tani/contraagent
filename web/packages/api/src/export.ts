// An export (`contraagent monitor export`): the monitor's views of some runs,
// written as files and read with no server. The client maps each route to its
// file; the feed replays a run's files once and ends with `ready`.
import { ApiError, type MonitorClient } from './client.js';
import type { FeedHandlers, Unsubscribe } from './feed.js';
import type {
  CursorView,
  Info,
  JournalPage,
  JsonObject,
  Outputs,
  Plan,
  RunFeedMessage,
  RunSummary,
  TaskDefinition,
  TaskDetail,
} from './types.js';

/** A client of an export: the monitor's client, and the files the server sends over its feed instead. */
export interface ExportClient extends MonitorClient {
  /** A file of the export, `data/<path>` (cached): the routes' answers, and `plan`, `outputs`, `cursor`. */
  file<T>(path: string): Promise<T>;
}

export interface ExportClientOptions {
  fetch?: typeof globalThis.fetch;
}

const seg = encodeURIComponent;

/**
 * A `MonitorClient` over an export at `baseUrl` (its `data/`, relative to the page or
 * absolute). A route is a file: `info.json`, `runs.json`, `runs/<run>/journal.json`,
 * `runs/<run>/tasks/<key>.json` ... A task's file leaves out its rows and its
 * definition, which the run's journal and definitions hold: the client puts them back.
 * A view the export does not hold (a transcript, the hosts) answers `ApiError` 404.
 * A route of no run is a file under `data/` (`trends.json`, `trends/panels/<name>.json`):
 * a new route is one method here, `file<T>('<its file>')`, beside its entry in the
 * Python `ROUTES` or `SITE_ROUTES` (`contraagent/monitor/export.py`).
 */
export function createExportClient(baseUrl: string, options: ExportClientOptions = {}): ExportClient {
  const base = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
  const fetch = options.fetch ?? globalThis.fetch;
  const cache = new Map<string, Promise<unknown>>();

  function file<T>(path: string): Promise<T> {
    let p = cache.get(path);
    if (!p) {
      p = load(base + path);
      // A failed read is tried again next time.
      p.catch(() => cache.delete(path));
      cache.set(path, p);
    }
    return p as Promise<T>;
  }

  async function load(url: string): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(new Request(url));
    } catch {
      throw new ApiError(url, 'network');
    }
    const type = (response.headers.get('Content-Type') ?? '').split(';')[0]!.trim().toLowerCase();
    if (!response.ok) throw new ApiError(url, 'status', response.status, type);
    try {
      return (await response.json()) as unknown;
    } catch {
      throw new ApiError(url, 'not-json', response.status, type);
    }
  }

  const run = (r: string, path: string): string => `runs/${seg(r)}/${path}`;
  const absent = (path: string): Promise<never> => Promise.reject(new ApiError(base + path, 'status', 404));

  return {
    baseUrl: base.replace(/\/$/, ''),
    file,
    info: () => file<Info>('info.json'),
    runs: () => file<RunSummary[]>('runs.json'),
    hosts: () => absent('hosts.json'),
    async journal(r, since = 0): Promise<JournalPage> {
      const page = await file<JournalPage>(run(r, 'journal.json'));
      return since > 0 ? { entries: page.entries.slice(since), total: page.total } : page;
    },
    definitions: (r) => file<TaskDefinition[]>(run(r, 'definitions.json')),
    async task(r, key): Promise<TaskDetail> {
      const [detail, journal, definitions, plan] = await Promise.all([
        file<TaskDetail>(run(r, `tasks/${seg(key)}.json`)),
        file<JournalPage>(run(r, 'journal.json')),
        file<TaskDefinition[]>(run(r, 'definitions.json')),
        file<Plan>(run(r, 'plan.json')),
      ]);
      const rows = journal.entries.filter((e) => e.key === key);
      const kind = rows.at(-1)?.kind ?? plan.nodes.find((n) => n.key === key)?.kind;
      return { ...detail, rows, definition: definitions.find((d) => d.kind === kind) ?? null };
    },
    stream: (r, key) => absent(run(r, `streams/${seg(key)}.json`)),
    panel: (r, name) => file<JsonObject>(run(r, `panels/${seg(name)}.json`)),
  };
}

/** A cursor file: `{}` when the run keeps no cursor. */
const isCursor = (c: CursorView | Record<string, never>): c is CursorView => Object.keys(c).length > 0;

/** A run feed opener, as `openRunFeed` is: what `MonitorStore` opens a run's feed with. */
export type RunFeedOpener = (run: string, panels: readonly string[], on: FeedHandlers<RunFeedMessage>) => Unsubscribe;

/**
 * The run feed of an export: the run's journal rows, plan, outputs, cursor and panels,
 * each once, then `ready`; nothing after. A file it cannot read stops it with `error`.
 */
export function openExportFeed(client: ExportClient): RunFeedOpener {
  return (r, panels, on) => {
    let closed = false;
    void (async () => {
      try {
        const [journal, plan, outputs, cursor, bodies] = await Promise.all([
          client.journal(r),
          client.file<Plan>(`runs/${seg(r)}/plan.json`),
          client.file<Outputs>(`runs/${seg(r)}/outputs.json`),
          client.file<CursorView | Record<string, never>>(`runs/${seg(r)}/cursor.json`),
          Promise.all(panels.map((p) => client.panel(r, p).catch((e: unknown): JsonObject => ({ error: String(e) })))),
        ]);
        if (closed) return;
        on.open?.();
        const send = (m: RunFeedMessage) => !closed && on.message(m);
        for (const row of journal.entries) send({ event: 'journal', data: row });
        send({ event: 'plan', data: plan });
        send({ event: 'outputs', data: outputs });
        send({ event: 'cursor', data: isCursor(cursor) ? cursor : null });
        panels.forEach((p, i) => send({ event: `panel:${p}`, data: bodies[i] ?? {} }));
        send({ event: 'ready', data: { journal: journal.total } });
      } catch {
        if (!closed) on.error?.();
      }
    })();
    return () => {
      closed = true;
    };
  };
}
