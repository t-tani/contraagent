// @contraagent/ui: the monitor's web components. Importing this module
// registers every element; `ca-monitor` is the whole monitor. The generic parts
// they are built from (styles, themes, primitives, `cae-*` elements) are
// `@contraagent/elements`.
import { adoptThemes } from '@contraagent/elements/themes';

export * from './core/events.js';
export * from './core/route.js';
export { Router, type RouteCause, type RouterMode } from './core/router.js';
export { LOCALE_NAMES, allLocales, chooseLocale, getLocale, preferredLocale, setLocale, type Locale } from './core/i18n.js';
export * from './words/format.js';
export * from './adapters/index.js';

// `data-ca-theme` works anywhere in the page: the rules are in its document.
if (typeof document !== 'undefined') adoptThemes(document);

export * from './elements/shared/ca-definition.js';
export * from './elements/shell/ca-monitor.js';
export * from './elements/shell/ca-run-picker.js';
export * from './elements/shell/ca-toasts.js';
export * from './elements/overview/index.js';
export * from './elements/lists/index.js';
export * from './elements/task/index.js';
