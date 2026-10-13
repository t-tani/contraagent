// The events the elements send up. Each crosses shadow roots (`composed`) and
// all but `ca-rounds` bubble, so a host listens on any ancestor. An element
// states what the reader asked for; whoever hosts it decides what happens (the
// monitor changes its route; another page may open its own view).
import type { LaunchEvent } from '@contraagent/api';
import type { RoutePatch, TaskView } from './route.js';
import type { ThemeChoice } from './themes/index.js';

export interface OpenTaskDetail {
  /** A task key. */
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

/** Where to go; `replace`: in place of where the reader is (a link that named nothing, set right), not a step back can return to. */
export type NavigateDetail = RoutePatch & { replace?: boolean };

export interface ChooseThemeDetail {
  /** The reader's choice: a theme, or `system`. */
  theme: ThemeChoice;
}

/** What a journal row says about a try (the fields this needs). */
export interface TryResult {
  attempt?: number | null;
  ok: boolean;
  stop: string;
  reason?: string | null;
  /** The models this try went through, one per hop of the failover chain. */
  hops?: readonly { model?: string | null; route?: string | null; stop?: string | null }[] | null;
}

export interface RoundInfo {
  kind: 'try' | 'fixup' | 'switch';
  /** 1-based try number. */
  tryNo: number;
  /** 0 for a try's first answer, else the fix-up's number within its try. */
  fixupNo: number;
  /** 0 for the try's first model, else the model switch's number within the try. */
  hopNo: number;
  /** The model of this round's hop, when the journal names it. */
  model: string;
  /**
   * `ok`: this round's output passed (the try's last round, the try succeeded);
   * `rejected`: a later fix-up in the same try followed it (its output failed its checks);
   * `failed`: the try's last round, and the try failed;
   * `switched`: a model switch followed it (its model stopped, e.g. rate limited);
   * null: not known yet (running).
   */
  result: 'ok' | 'rejected' | 'failed' | 'switched' | null;
  /** For a switched round: how its model's session ended (a stop value). */
  switchedStop: string;
  /** For a switched round: the model the next session ran on ('' when the journal names none). */
  switchedTo: string;
  /** For a rejected round: the errors the next round was sent back with. */
  rejectedWith: string[];
  /** For a failed round: the journal row of its try. */
  row: TryResult | null;
}

export interface RoundsChangedDetail {
  /** Each round's launch event (null for events before any launch). */
  launches: (LaunchEvent | null)[];
  /** The round shown, 0-based; -1 while there is none. */
  shown: number;
  /** Each round as a try or a fix-up, with its result when known. */
  rounds: RoundInfo[];
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
  'ca-navigate': NavigateDetail;
  /** Show another theme (the theme control). */
  'ca-choose-theme': ChooseThemeDetail;
  /** Close the element (the run picker). */
  'ca-close': Record<string, never>;
  /** A transcript's rounds or its shown round changed; does not bubble (`ca-transcript`). */
  'ca-rounds': RoundsChangedDetail;
}

declare global {
  interface HTMLElementEventMap {
    'ca-open-task': CustomEvent<OpenTaskDetail>;
    'ca-select-run': CustomEvent<SelectRunDetail>;
    'ca-filter': CustomEvent<FilterDetail>;
    'ca-navigate': CustomEvent<NavigateDetail>;
    'ca-choose-theme': CustomEvent<ChooseThemeDetail>;
    'ca-close': CustomEvent<Record<string, never>>;
    'ca-rounds': CustomEvent<RoundsChangedDetail>;
  }
}

/** Sends `name` from `from`; it bubbles unless `bubbles: false`. */
export function emit<K extends keyof CaEventMap>(
  from: EventTarget,
  name: K,
  detail: CaEventMap[K],
  { bubbles = true }: { bubbles?: boolean } = {},
): void {
  from.dispatchEvent(new CustomEvent(name, { detail, bubbles, composed: true }));
}
