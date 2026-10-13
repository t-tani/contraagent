// A task's transcript as it arrives: a saved one folded at once, or one tailed
// from the monitor's stream feed (`openStreamFeed`), page by page, with "load
// earlier" through the client. The host re-renders on every page.
import {
  openStreamFeed,
  type MonitorClient,
  type StreamPage,
  type TranscriptEvent,
  type Unsubscribe,
} from '@contraagent/api';
import type { ReactiveController, ReactiveControllerHost } from 'lit';
import { applyEvents, emptyTranscript, type Transcript } from '../adapters/transcript/model.js';

/** How far back "load earlier" reaches, in transcript lines. */
const EARLIER_LINES = 3000;

/** What to load: a saved transcript, or the transcript of task `stream` in `run`, tailed from `baseUrl`. */
export type StreamSource = { events: readonly TranscriptEvent[] } | { run: string; stream: string; baseUrl: string };

export class StreamController implements ReactiveController {
  model: Transcript = emptyTranscript();
  /** Transcript lines before the first page that are not loaded. */
  behind = 0;
  /** The events shown so far: the pages' events that showed something. */
  count = 0;
  /** The first page has arrived (a saved transcript: at once). */
  ready = false;
  /** Changes with every page, and with every load. */
  version = 0;
  /** Changes with every load: a new transcript, or the same one after the host was attached again. */
  generation = 0;
  /** The key of what is loaded (`load`); '' after the host was detached. */
  loaded = '';
  private close: Unsubscribe | null = null;

  constructor(private readonly host: ReactiveControllerHost) {
    host.addController(this);
  }

  /** The feed is open: the transcript is being tailed. */
  get tailing(): boolean {
    return this.close !== null;
  }

  hostDisconnected(): void {
    this.stop();
    this.loaded = '';
  }

  private stop(): void {
    this.close?.();
    this.close = null;
  }

  /** Start over with `source` (none: an empty transcript); `key` names it for `loaded`. */
  load(key: string, source: StreamSource | null): void {
    this.stop();
    this.loaded = key;
    this.generation++;
    this.version++;
    this.model = emptyTranscript();
    this.behind = 0;
    this.count = 0;
    this.ready = false;
    if (source && 'events' in source) {
      this.count = applyEvents(this.model, source.events);
      this.ready = true;
    } else if (source) {
      const generation = this.generation;
      this.close = openStreamFeed(source.run, source.stream, { message: (page) => this.onPage(page, generation) }, { baseUrl: source.baseUrl });
    }
  }

  private onPage(page: StreamPage, generation: number): void {
    if (generation !== this.generation) return;
    if (!this.ready && page.behind) this.behind = page.behind;
    this.count += applyEvents(this.model, page.events);
    this.ready = true;
    this.version++;
    this.host.requestUpdate();
  }

  /** Load the transcript again from further back: the lines `behind` the first page, up to 3000. */
  async loadEarlier(client: MonitorClient, run: string, stream: string): Promise<void> {
    const generation = this.generation;
    const back = Math.max(0, this.behind - EARLIER_LINES);
    this.behind = 0;
    this.host.requestUpdate();
    const page = await client.stream(run, stream, back);
    if (generation !== this.generation) return;
    this.model = emptyTranscript();
    applyEvents(this.model, page.events);
    this.version++;
    this.host.requestUpdate();
  }
}
