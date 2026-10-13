// The live half of the monitor API: Server-Sent Events, parsed into typed messages.
import type { RunEventName, RunFeedMessage, StreamPage } from './types.js';

/** Every SSE event name of `/events` with a fixed meaning; panels add `panel:<name>`. */
export const RUN_EVENT_NAMES = [
  'journal',
  'procs',
  'plan',
  'outputs',
  'cursor',
  'ready',
] as const satisfies readonly RunEventName[];

// A name missing from the list above fails to compile here.
type Missing = Exclude<RunEventName, (typeof RUN_EVENT_NAMES)[number]>;
const _exhaustive: [Missing] extends [never] ? true : never = true;
void _exhaustive;

export interface FeedHandlers<M> {
  message(msg: M): void;
  /** The connection opened, or re-opened after a drop (the server then starts over). */
  open?(): void;
  /** The connection dropped; the browser retries on its own. */
  error?(): void;
}

export interface FeedOptions {
  baseUrl?: string;
  /** For tests and non-browser hosts. */
  EventSource?: typeof globalThis.EventSource;
}

/** A feed to stop. */
export type Unsubscribe = () => void;

function connect(url: string, names: readonly string[], on: FeedHandlers<{ event: string; data: unknown }>, opts: FeedOptions): Unsubscribe {
  const ES = opts.EventSource ?? globalThis.EventSource;
  const es = new ES(url);
  es.onopen = () => on.open?.();
  es.onerror = () => on.error?.();
  for (const name of names) {
    es.addEventListener(name, (ev) => {
      on.message({ event: name, data: JSON.parse((ev as globalThis.MessageEvent<string>).data) as unknown });
    });
  }
  return () => es.close();
}

const q = encodeURIComponent;

/**
 * `/events?run=`: the run, live. The server replays the whole journal on every
 * (re)connect and then sends `ready`; `panels` are the panel names from
 * `/api/info` to listen for.
 */
export function openRunFeed(
  run: string,
  panels: readonly string[],
  on: FeedHandlers<RunFeedMessage>,
  opts: FeedOptions = {},
): Unsubscribe {
  const names = [...RUN_EVENT_NAMES, ...panels.map((p) => `panel:${p}`)];
  return connect(`${opts.baseUrl ?? ''}/events?run=${q(run)}`, names, on, opts);
}

/** `/events/stream`: one transcript, tailed. The first page is the tail; each later one only what is new. */
export function openStreamFeed(
  run: string,
  key: string,
  on: FeedHandlers<StreamPage>,
  opts: FeedOptions = {},
): Unsubscribe {
  return connect(
    `${opts.baseUrl ?? ''}/events/stream?run=${q(run)}&key=${q(key)}`,
    ['stream'],
    { ...on, message: (m) => on.message(m.data as StreamPage) },
    opts,
  );
}
