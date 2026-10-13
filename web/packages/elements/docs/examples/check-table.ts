// A check table: hand-written fields of a settings file, each checked against
// what it must be. The host judges the values; the table shows the verdicts.
import '@contraagent/elements/check-table/define';
import type { CheckRow } from '@contraagent/elements/check-table';

const rows: CheckRow[] = [
  { name: 'name', expected: 'string', hasValue: true, value: 'release-build', verdict: 'pass', verdictLabel: 'passed' },
  { name: 'retries', expected: 'integer', hasValue: true, value: '3', verdict: 'fail', verdictLabel: 'wrong type', tip: 'Expected integer' },
  { name: 'targets', expected: 'list[str]', hasValue: true, value: ['linux', 'macos', 'windows', 'wasm'], verdict: 'pass', verdictLabel: 'passed' },
  { name: 'cache', expected: 'object', optional: true, hasValue: false, verdict: 'none', verdictLabel: 'absent (optional)' },
  { name: 'colour', expected: 'not in the schema', extra: true, hasValue: true, value: 'blue', verdict: 'warn', verdictLabel: 'extra field' },
];

export function mount(host: HTMLElement): void {
  const table = document.createElement('cae-check-table');
  table.rows = rows;
  table.strings = { name: 'Field', actual: 'In the file' };
  host.replaceChildren(table);
}
