// One task's detail (`MonitorClient.task`), fetched for the element that shows
// it: again whenever the run, the task or the client changes, and only the
// latest request's answer is kept.
import type { MonitorClient, TaskDetail } from '@contraagent/api';
import type { ReactiveControllerHost } from 'lit';

/** The detail of a task the server could not return: no attempts, no files, no definition. */
export const emptyDetail = (key: string): TaskDetail => ({
  key,
  rows: [],
  launches: [],
  definition: null,
  io: { params: {}, inputs: [], outputs: [], executor: 'agent', upstream: [], downstream: [] },
  stream: null,
});

/**
 * Holds `value`, the detail of the task `load` named last: null until it
 * arrives, `emptyDetail` (and `error`) when the request failed. The host
 * re-renders when it arrives.
 */
export class TaskDetailController {
  /** The detail; null while it loads, or when there is no task to load. */
  value: TaskDetail | null = null;
  /** Why the last request failed; null when it did not. */
  error: unknown = null;
  private token = 0;

  constructor(private readonly host: ReactiveControllerHost) {}

  /** Load the detail of `key` in `run`; an earlier request still on its way is dropped. */
  load(client: MonitorClient | undefined, run: string, key: string | null): void {
    const token = ++this.token;
    this.value = null;
    this.error = null;
    if (!run || !key || !client) return;
    void this.fetch(token, client, run, key);
  }

  private async fetch(token: number, client: MonitorClient, run: string, key: string): Promise<void> {
    let d: TaskDetail;
    let error: unknown = null;
    try {
      d = await client.task(run, key);
    } catch (e) {
      d = emptyDetail(key);
      error = e;
    }
    if (token !== this.token) return;
    this.value = d;
    this.error = error;
    this.host.requestUpdate();
  }
}
