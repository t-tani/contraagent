// @contraagent/ui: the monitor's web components. Importing this module
// registers every element (define/all.ts); `ca-monitor` is the whole monitor.
// One view alone is a subpath (`@contraagent/ui/transcript`, define/). Nothing
// else happens at import: the page sets up the languages (`configureLocales`)
// and the themes (`adoptThemes`, `@contraagent/elements/themes`), or
// `<ca-monitor>` does when it connects. The generic parts the elements are
// built from (styles, themes, primitives, `cae-*` elements) are
// `@contraagent/elements`.
import './define/all.js';

export * from './core/index.js';
export * from './words/format.js';
export * from './adapters/index.js';

export * from './elements/shared/ca-definition.js';
export * from './elements/shell/ca-monitor.js';
export * from './elements/shell/ca-clock.js';
export * from './elements/shell/ca-run-picker.js';
export * from './elements/shell/ca-hosts.js';
export * from './elements/shell/ca-toasts.js';
export * from './elements/overview/index.js';
export * from './elements/lists/index.js';
export * from './elements/task/index.js';
