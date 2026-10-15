// The view route, bound to the browser's history: navigating pushes an entry for a
// new place and replaces it for a refinement (a filter), Back and Forward
// restore it. In `memory` mode (an embedded monitor) the URL is left alone.
import { applyPatch, formatViewRoute, isNewPlace, parseViewRoute, type ViewRoute, type ViewRoutePatch } from './view-route.js';

export type ViewRouterMode = 'url' | 'memory';
/** Why the view route changed: the page loaded, the app navigated, or the reader went Back/Forward. */
export type ViewRouteCause = 'init' | 'push' | 'replace' | 'pop';

export class ViewRouter {
  private current: ViewRoute;

  constructor(
    private readonly mode: ViewRouterMode,
    private readonly onChange: (viewRoute: ViewRoute, cause: ViewRouteCause) => void,
    initial?: ViewRoutePatch,
    /** Called before a new history entry is pushed: what is kept per entry belongs to the one being left. */
    private readonly onLeave: () => void = () => {},
  ) {
    const base = mode === 'url' ? parseViewRoute(location.search) : parseViewRoute('');
    this.current = applyPatch(base, initial ?? {});
  }

  get viewRoute(): ViewRoute {
    return this.current;
  }

  start(): void {
    if (this.mode === 'url') {
      history.scrollRestoration = 'manual';
      addEventListener('popstate', this.onPop);
    }
    this.onChange(this.current, 'init');
  }

  stop(): void {
    if (this.mode === 'url') removeEventListener('popstate', this.onPop);
  }

  /**
   * Go to the view route with `patch` applied. A new place pushes a history entry,
   * a refinement replaces it; `replace` forces replacing (a default filled in,
   * not a step the reader took).
   */
  navigate(patch: ViewRoutePatch, opts: { replace?: boolean } = {}): void {
    const next = applyPatch(this.current, patch);
    if (formatViewRoute(next) === formatViewRoute(this.current)) return;
    const push = !opts.replace && isNewPlace(this.current, next);
    this.current = next;
    if (this.mode === 'url') {
      const url = `${location.pathname}${formatViewRoute(next)}${location.hash}`;
      if (push) {
        this.onLeave();
        history.pushState({}, '', url);
      } else {
        history.replaceState(history.state, '', url);
      }
    }
    this.onChange(next, push ? 'push' : 'replace');
  }

  private readonly onPop = (): void => {
    this.current = parseViewRoute(location.search);
    this.onChange(this.current, 'pop');
  };
}
