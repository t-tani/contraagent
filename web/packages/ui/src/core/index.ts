// `@contraagent/ui/core`: the events the elements send, the monitor's view route and
// view router, and the languages. No element; nothing happens at import.
export * from './events.js';
export * from './view-route.js';
export { ViewRouter, type ViewRouteCause, type ViewRouterMode } from './view-router.js';
export { LOCALE_NAMES, allLocales, chooseLocale, configureLocales, getLocale, preferredLocale, setLocale, type Locale } from './i18n.js';
