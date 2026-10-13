// A data table: hand-written rows, one sortable column, a row's action. The
// host holds the rows and the order, and answers the events.
import '@contraagent/elements/data-table/define';
import { sortRows, type CaeDataTable, type DataColumn } from '@contraagent/elements/data-table';
import { pill } from '@contraagent/elements';

interface Job {
  id: string;
  name: string;
  minutes: number;
  state: 'done' | 'failed' | 'running';
}

const jobs: Job[] = [
  { id: 'j1', name: 'Build', minutes: 4, state: 'done' },
  { id: 'j2', name: 'Unit tests', minutes: 11, state: 'failed' },
  { id: 'j3', name: 'Deploy preview', minutes: 2, state: 'running' },
];

const columns: DataColumn<Job>[] = [
  { id: 'name', header: 'Job', rowHeader: true, cell: (j) => j.name },
  { id: 'minutes', header: 'Minutes', align: 'end', width: '96px', cell: (j) => j.minutes, compare: (a, b) => a.minutes - b.minutes },
  { id: 'state', header: 'State', width: '120px', cell: (j) => pill({ text: j.state, tone: j.state }) },
];

export function mount(host: HTMLElement): void {
  const table = document.createElement('cae-data-table') as CaeDataTable<Job>;
  table.caption = 'Jobs';
  table.columns = columns;
  table.rowKey = (j) => j.id;
  table.rows = jobs;
  table.addEventListener('cae-sort', (e) => {
    table.sort = e.detail;
    table.rows = sortRows(jobs, columns, e.detail);
  });
  const shown = document.createElement('p');
  table.addEventListener('cae-activate', (e) => (shown.textContent = `Opened: ${e.detail.id}`));
  host.replaceChildren(table, shown);
}
