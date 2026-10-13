// The monitor inside a Vite application, as src/main.ts. Its dependencies:
// @contraagent/ui, and its peers lit and @lit/localize.
//
// The monitor runs on another origin and lets this page read its API:
//
//   contraagent monitor --runs-dir runs --cors-origin http://localhost:5173
//   pnpm vite   # http://localhost:5173
//
// The import registers <ca-monitor> (and every element it renders). An element
// in the page is upgraded at once, and it reads `base-url` when it connects:
// so the page sets `base-url` before the element is in the page, here by
// creating it from script after the import.
import '@contraagent/ui/monitor';
import type { CaMonitor } from '@contraagent/ui/monitor';

/** Where the monitor serves its API: another origin, named with `--cors-origin`. */
const MONITOR = 'http://127.0.0.1:8787';

const monitor = document.createElement('ca-monitor');
monitor.baseUrl = MONITOR; // the `base-url` attribute
// `memory`: the route stays in the element; the page's URL, title and <html> stay the application's.
monitor.history = 'memory';
monitor.locale = 'en';
document.querySelector('#monitor')!.append(monitor); // it connects, and fetches from MONITOR

// `locale` changes the monitor's language in place.
const language = document.querySelector<HTMLSelectElement>('#language')!;
language.value = monitor.locale;
language.addEventListener('change', () => (monitor.locale = language.value as CaMonitor['locale']));
