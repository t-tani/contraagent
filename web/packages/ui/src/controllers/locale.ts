// The language an element shows: its `locale` property, else the reader's
// earlier choice or the browser's language; and the `lang` its text is in.
import type { ReactiveController, ReactiveControllerHost } from 'lit';
import { getLocale, isLocale, preferredLocale, setLocale, type Locale } from '../core/i18n.js';

export interface LocaleOptions {
  /** The element's `locale` property; '' for the reader's earlier choice, else the browser's language. */
  locale: () => Locale | '';
  /** The element is the page: `<html lang>` follows the language too. */
  pageWide: () => boolean;
}

/**
 * Sets the language when the host connects and when its `locale` changes, and
 * sets `lang` on the host (and on `<html>` when the host is the page) after
 * every update.
 */
export class LocaleController implements ReactiveController {
  /** The `locale` the last update saw; undefined before the first. */
  private seen: Locale | '' | undefined;
  /** Settles when the language chosen at connect is loaded (a locale's module loads when first chosen). */
  ready: Promise<void> = Promise.resolve();

  constructor(
    private readonly host: ReactiveControllerHost & HTMLElement,
    private readonly opts: LocaleOptions,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    const l = this.opts.locale();
    this.ready = setLocale(isLocale(l) ? l : preferredLocale()).catch(() => {});
  }

  hostUpdated(): void {
    const l = this.opts.locale();
    if (l !== this.seen) {
      this.seen = l;
      if (isLocale(l) && l !== getLocale()) void setLocale(l);
    }
    // A page that is the monitor speaks its language; an embedded monitor leaves the host's <html lang> alone.
    if (this.opts.pageWide()) document.documentElement.lang = getLocale();
    // Its own text is in its language either way (line breaking between Japanese phrases reads it).
    this.host.lang = getLocale();
  }
}
