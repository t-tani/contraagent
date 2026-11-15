// One shared once-a-second tick for every element that shows a running clock.
// A tick draws nothing while the page is hidden; the first one after it shows
// again does. It asks the page at each tick and listens for nothing: an element
// on a host's page adds no listener to its document.
import type { ReactiveController, ReactiveControllerHost } from 'lit';

const hosts = new Set<ReactiveControllerHost>();
let timer: ReturnType<typeof setInterval> | null = null;

/** Whether nobody sees the page (a tab in the background, a window minimized): nothing is drawn for it. */
export const pageHidden = (): boolean => typeof document !== 'undefined' && document.hidden;

function tick(): void {
  if (pageHidden()) return;
  for (const h of hosts) h.requestUpdate();
}

/** Re-renders its host every second while it is connected. */
export class ClockController implements ReactiveController {
  constructor(private readonly host: ReactiveControllerHost) {
    host.addController(this);
  }
  hostConnected(): void {
    hosts.add(this.host);
    timer ??= setInterval(tick, 1000);
  }
  hostDisconnected(): void {
    hosts.delete(this.host);
    if (!hosts.size && timer) {
      clearInterval(timer);
      timer = null;
    }
  }
}

/**
 * Start times that stay put. A process reports its age in whole seconds, so
 * `now - age` jitters by a second between updates; the first value seen for an
 * id is kept while later ones stay within a few seconds of it.
 */
export class StableStarts {
  private readonly seen = new Map<string, number>();
  at(id: string, ageS: number, now = Date.now()): number {
    const t0 = Math.round(now - ageS * 1000);
    const prev = this.seen.get(id);
    if (prev !== undefined && Math.abs(prev - t0) < 5000) return prev;
    this.seen.set(id, t0);
    return t0;
  }
}

/** Shared by every view, so the same process shows the same start everywhere. */
export const starts = new StableStarts();
