// `@contraagent/ui/core`: the events the elements send, the monitor's route and
// router, and the languages. No element; nothing happens at import.
export * from './events.js';
export * from './route.js';
export { Router, type RouteCause, type RouterMode } from './router.js';
export { LOCALE_NAMES, allLocales, chooseLocale, configureLocales, getLocale, preferredLocale, setLocale, type Locale } from './i18n.js';
