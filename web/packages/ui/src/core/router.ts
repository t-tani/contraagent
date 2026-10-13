// The route, bound to the browser's history: navigating pushes an entry for a
// new place and replaces it for a refinement (a filter), Back and Forward
// restore it. In `memory` mode (an embedded monitor) the URL is left alone.
import { applyPatch, formatRoute, isNewPlace, parseRoute, type Route, type RoutePatch } from './route.js';

export type RouterMode = 'url' | 'memory';
/** Why the route changed: the page loaded, the app navigated, or the reader went Back/Forward. */
export type RouteCause = 'init' | 'push' | 'replace' | 'pop';

export class Router {
  private current: Route;

  constructor(
    private readonly mode: RouterMode,
    private readonly onChange: (route: Route, cause: RouteCause) => void,
    initial?: RoutePatch,
    /** Called before a new history entry is pushed: what is kept per entry belongs to the one being left. */
    private readonly onLeave: () => void = () => {},
  ) {
    const base = mode === 'url' ? parseRoute(location.search) : parseRoute('');
    this.current = applyPatch(base, initial ?? {});
  }

  get route(): Route {
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
   * Go to the route with `patch` applied. A new place pushes a history entry,
   * a refinement replaces it; `replace` forces replacing (a default filled in,
   * not a step the reader took).
   */
  navigate(patch: RoutePatch, opts: { replace?: boolean } = {}): void {
    const next = applyPatch(this.current, patch);
    if (formatRoute(next) === formatRoute(this.current)) return;
    const push = !opts.replace && isNewPlace(this.current, next);
    this.current = next;
    if (this.mode === 'url') {
      const url = `${location.pathname}${formatRoute(next)}${location.hash}`;
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
    this.current = parseRoute(location.search);
    this.onChange(this.current, 'pop');
  };
}
