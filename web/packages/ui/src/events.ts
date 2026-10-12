// The events the elements send up. Each bubbles and crosses shadow roots
// (`composed`), so a host listens on any ancestor. An element states what the
// reader asked for; whoever hosts it decides what happens (the monitor changes
// its route; another page may open its own view).
import type { RoutePatch, TaskView } from './route.js';

export interface OpenTaskDetail {
  /** A task key or a slot (`<kind>-<unit>`). */
  key: string;
  /** What to show of it; the host's choice when absent. */
  view?: TaskView;
}

export interface SelectRunDetail {
  run: string;
}

export interface FilterDetail {
  kind?: string;
  /** A journal stop, or 'bad' for every attempt that did not complete. */
  stop?: string;
  q?: string;
}

/** Every event an element sends, by name. */
export interface CaEventMap {
  /** Open a task: its transcript, or `view` of it. */
  'ca-open-task': OpenTaskDetail;
  /** Switch to another run. */
  'ca-select-run': SelectRunDetail;
  /** Change a list filter. */
  'ca-filter': FilterDetail;
  /** Go elsewhere in the monitor (its own views use this). */
  'ca-navigate': RoutePatch;
}

declare global {
  interface HTMLElementEventMap {
    'ca-open-task': CustomEvent<OpenTaskDetail>;
    'ca-select-run': CustomEvent<SelectRunDetail>;
    'ca-filter': CustomEvent<FilterDetail>;
    'ca-navigate': CustomEvent<RoutePatch>;
  }
}

export function emit<K extends keyof CaEventMap>(from: EventTarget, name: K, detail: CaEventMap[K]): void {
  from.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
}
