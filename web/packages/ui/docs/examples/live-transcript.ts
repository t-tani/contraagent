// One task's transcript, tailed live, in a page of your own.
//
// The element renders; the page decides what a reader's request means. Here a
// round picked in the transcript is simply shown.
import { createMonitorClient } from '@contraagent/api';
import '@contraagent/ui/transcript';

/** Where `contraagent-monitor` runs (start it with `--cors-origin <this page's origin>`). */
const MONITOR = 'http://127.0.0.1:8787';

export function showTranscript(host: HTMLElement, run: string, key: string): void {
  const t = document.createElement('ca-transcript');
  t.client = createMonitorClient({ baseUrl: MONITOR }); // for "load earlier"
  t.baseUrl = MONITOR; // the live feed
  t.run = run;
  t.stream = key;
  t.live = true;
  t.addEventListener('ca-navigate', (e) => {
    if (e.detail.round !== undefined) t.round = e.detail.round;
  });
  host.replaceChildren(t);
}
