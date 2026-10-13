// The monitor inside a Vite application, as src/main.ts. Its dependencies:
// @contraagent/ui, and its peers lit and @lit/localize.
//
// The monitor runs on another origin and lets this page read its API:
//
//   contraagent monitor --runs-dir runs --cors-origin http://localhost:5173
//   pnpm vite   # http://localhost:5173
//
// The import registers <ca-monitor> (and every element it renders). Its
// properties take effect whenever they are set, before or after the import.
import '@contraagent/ui/monitor';
import type { CaMonitor } from '@contraagent/ui/monitor';

/** Where the monitor serves its API: another origin, named with `--cors-origin`. */
const MONITOR = 'http://127.0.0.1:8787';

const monitor = document.querySelector('ca-monitor')!;
monitor.baseUrl = MONITOR; // the `base-url` attribute

// `locale` changes the monitor's language in place.
const language = document.querySelector<HTMLSelectElement>('#language')!;
language.value = monitor.locale;
language.addEventListener('change', () => (monitor.locale = language.value as CaMonitor['locale']));
