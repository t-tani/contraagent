// A mark matrix: a hand-written week of nightly checks, a row per service, a column
// per check under a group per night. The host sorts the rows and keeps the selection.
import '@contraagent/elements/matrix/define';
import type { MarkMatrixInput, MatrixRowInput } from '@contraagent/elements/matrix';
import type { StateStyles } from '@contraagent/elements/primitives';

const states: StateStyles = {
  pass: { label: 'pass', tone: 'done', shape: 'round', rank: 0 },
  fail: { label: 'fail', tone: 'failed', shape: 'square', rank: 2 },
  skip: { label: 'skip', tone: 'muted', shape: 'round', rank: 1 },
};

const nights = ['Mon', 'Tue'];
const checks = ['lint', 'unit'];
const results: Record<string, string[]> = { api: ['pass', 'pass', 'pass', 'fail'], web: ['pass', 'skip', 'pass', 'pass'], worker: ['fail', 'fail', 'pass', 'pass'] };

const rows: MatrixRowInput[] = Object.entries(results).map(([service, rs]) => ({
  id: service,
  label: service,
  value: rs.filter((r) => r === 'fail').length,
  strong: rs.includes('fail'),
  cells: rs.map((state, i) => {
    const at = `${nights[Math.floor(i / 2)]} ${checks[i % 2]}`;
    return { id: `${service}|${i}`, state, label: `${service} | ${at} | ${state}`, tip: `${service}, ${at}` };
  }),
}));

const byFailures = (rs: readonly MatrixRowInput[]) => [...rs].sort((a, b) => Number(b.value) - Number(a.value));

const matrix = (sort: string): MarkMatrixInput => ({
  caption: 'Nightly checks',
  label: 'Nightly checks by service',
  facts: ['2 nights', '3 services'],
  head: [
    nights.map((n) => ({ id: n, label: n, span: 2, rows: 1, type: 'group' as const })),
    nights.flatMap((n) => checks.map((c) => ({ id: `${n}|${c}`, label: c, span: 1, rows: 1, type: 'column' as const }))),
  ],
  columns: nights.flatMap((n) => checks.map((c) => ({ id: `${n}|${c}`, groups: [n] }))),
  rows: sort === 'failures' ? byFailures(rows) : rows,
  value: { label: 'Failures' },
  sorts: [
    { id: 'name', label: 'Name' },
    { id: 'failures', label: 'Failures' },
  ],
  sort,
});

export function mount(host: HTMLElement): void {
  const el = document.createElement('cae-mark-matrix');
  el.matrix = matrix('name');
  el.states = states;
  el.strings = { rowsHeader: 'Service' };
  el.addEventListener('cae-sort', (e) => (el.matrix = matrix(e.detail.id)));
  el.addEventListener('cae-select', (e) => (el.selected = e.detail.id));
  host.replaceChildren(el);
}
