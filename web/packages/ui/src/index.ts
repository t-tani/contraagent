// @contraagent/ui: the monitor's web components. Importing this module
// registers every element; `ca-monitor` is the whole monitor.
import { adoptThemes } from './styles/theme-sheet.js';

export * from './events.js';
export * from './route.js';
export { Router, type RouteCause, type RouterMode } from './router.js';
export { LOCALE_NAMES, allLocales, chooseLocale, getLocale, preferredLocale, setLocale, type Locale } from './i18n.js';
export * from './lib/format.js';
export { md, mdFile } from './lib/markdown.js';
export { highlight } from './lib/highlight.js';
export { tokens, base, prose } from './styles/base.js';
export * from './styles/themes.js';
export { themeStyles, hostThemeStyles, adoptThemes } from './styles/theme-sheet.js';

// `data-ca-theme` works anywhere in the page: the rules are in its document.
if (typeof document !== 'undefined') adoptThemes(document);

export * from './elements/shared/ca-json-tree.js';
export * from './elements/shared/ca-elapsed.js';
export * from './elements/shared/ca-count.js';
export * from './elements/shared/ca-markdown.js';
export * from './elements/shared/ca-definition.js';
export * from './elements/shell/ca-monitor.js';
export * from './elements/shell/ca-run-picker.js';
export * from './elements/shell/ca-toasts.js';
export * from './elements/overview/index.js';
export * from './elements/lists/index.js';
export * from './elements/task/index.js';
