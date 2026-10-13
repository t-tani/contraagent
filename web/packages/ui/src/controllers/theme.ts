// The theme an element shows: the reader's choice, resolved against the
// system's colour scheme, reflected as `data-ca-theme`.
import type { ReactiveController, ReactiveControllerHost } from 'lit';
import { isThemeChoice, preferredTheme, prefersLight, resolveTheme, type ThemeChoice, type ThemeName } from '@contraagent/elements/themes';

export interface ThemeOptions {
  /** The element's `theme` property: a choice, or '' for the choice remembered from an earlier visit. */
  theme: () => ThemeChoice | '';
  /** The element is the page: the theme goes on `<html>` too. */
  pageWide: () => boolean;
}

/**
 * Shows the theme on its host (and on `<html>` when the host is the page),
 * after every update, and follows the system's colour scheme for `system`.
 */
export class ThemeController implements ReactiveController {
  /** Whether the system asks for a light colour scheme (what `system` follows). */
  light = prefersLight();
  private stop: (() => void) | null = null;

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly opts: ThemeOptions,
  ) {
    host.addController(this);
  }

  /** The reader's choice: the `theme` property, else the choice remembered from an earlier visit. */
  get choice(): ThemeChoice {
    const t = this.opts.theme();
    return isThemeChoice(t) ? t : preferredTheme();
  }

  /** The theme shown now. */
  get shown(): ThemeName {
    return resolveTheme(this.choice, this.light);
  }

  /** What `system` resolves to now. */
  get system(): ThemeName {
    return resolveTheme('system', this.light);
  }

  hostConnected(): void {
    this.apply();
    const scheme = globalThis.matchMedia?.('(prefers-color-scheme: light)');
    if (!scheme) return;
    const onScheme = (e: MediaQueryListEvent) => {
      this.light = e.matches;
      this.host.requestUpdate();
    };
    scheme.addEventListener('change', onScheme);
    this.stop = () => scheme.removeEventListener('change', onScheme);
  }

  hostDisconnected(): void {
    this.stop?.();
    this.stop = null;
  }

  hostUpdated(): void {
    this.apply();
  }

  /** Show the theme: on the host, and on the page when the host is the page. */
  private apply(): void {
    const name = this.shown;
    if (this.host.getAttribute('data-ca-theme') !== name) this.host.setAttribute('data-ca-theme', name);
    if (this.opts.pageWide() && document.documentElement.getAttribute('data-ca-theme') !== name)
      document.documentElement.setAttribute('data-ca-theme', name);
  }
}
