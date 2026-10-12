// A run's journal, live, with the store doing the data work: the store folds
// the run feed into one typed state, the element draws it.
import { MonitorStore, isBad } from '@contraagent/api';
import '@contraagent/ui';

export function showJournal(host: HTMLElement, run: string, openTask: (key: string) => void): () => void {
  const store = new MonitorStore({ baseUrl: 'http://127.0.0.1:8787' });
  const table = document.createElement('ca-journal-table');
  host.replaceChildren(table);

  // Every change: the newest state, already typed (`RunState`).
  const unsubscribe = store.subscribe((s) => {
    table.rows = s.state.journal;
    table.fresh = s.fresh;
  });
  // Rows that arrive after the replay: tasks that just finished.
  const unwatch = store.onNewRow((row) => {
    if (isBad(row)) console.warn(`${row.key} ended ${row.stop}: ${row.reason ?? ''}`);
  });
  // The element asks; the page answers.
  table.addEventListener('ca-filter', (e) => (table.stop = e.detail.stop ?? ''));
  table.addEventListener('ca-open-task', (e) => openTask(e.detail.key));

  void store.start();
  store.selectRun(run);
  return () => {
    unsubscribe();
    unwatch();
    store.stop();
  };
}
