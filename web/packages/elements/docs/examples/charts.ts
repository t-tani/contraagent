// Charts: a CI pipeline's minutes by day and stage (stacked columns), its queue
// time (lines), its builds by weekday and hour (a heatmap), how its nightly builds
// ended (a state grid) and its test funnel (horizontal bars). The host gives each
// chart its unit's format.
import '@contraagent/elements/charts/define';
import type { ChartSeries } from '@contraagent/elements/charts';

const days = ['10-08', '10-09', '10-10', '10-11', '10-12', '10-13', '10-14'];
const minutes: ChartSeries[] = [
  { name: 'build', values: [42, 38, 51, 12, 9, 47, 44] },
  { name: 'test', values: [65, 70, 58, 20, null, 61, 66] },
  { name: 'deploy', values: [8, 8, 9, 2, 2, 10, 8] },
];

export function mount(host: HTMLElement): void {
  const columns = document.createElement('cae-column-chart');
  columns.label = 'Minutes by day';
  columns.x = days;
  columns.series = minutes;
  columns.stacked = true;
  columns.format = (v) => `${v} min`;

  const lines = document.createElement('cae-line-chart');
  lines.label = 'Queue time';
  lines.x = days;
  lines.series = [
    { name: 'median', values: [1.2, 1.4, 0.9, 0.3, 0.2, 1.8, 1.1] },
    { name: 'slowest', values: [6, 9, 4, 1, 1, 12, 7] },
  ];
  lines.format = (v) => `${v} min`;

  const heat = document.createElement('cae-heatmap');
  heat.label = 'Builds by weekday and hour';
  heat.x = ['9', '10', '11', '12', '13', '14', '15', '16', '17'];
  heat.y = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  // A count per weekday and hour; Wednesday at 13 has no record (null: an empty cell).
  heat.values = heat.y.map((_, r) => heat.x.map((_, c) => (r === 2 && c === 4 ? null : (r * 7 + c * 3) % 9)));
  heat.strings = { scale: (low, high) => `${low} to ${high} builds` };

  const bars = document.createElement('cae-bar-chart');
  bars.label = 'Tests this week';
  bars.bars = [
    { label: 'written', value: 1240 },
    { label: 'run', value: 1180 },
    { label: 'passed', value: 1162 },
    { label: 'flaky', value: 18, tone: 'attention' },
  ];

  const nightly = document.createElement('cae-state-grid');
  nightly.label = 'Nightly builds by weekday and hour';
  nightly.x = ['0', '1', '2', '3'];
  nightly.y = ['Mon', 'Tue'];
  const passed = { label: 'passed', tone: 'done' as const };
  // A state per weekday and hour: its word, its tone, and a fact for the tooltip; null: no build.
  nightly.cells = [
    [passed, { label: 'failed', tone: 'failed', tip: 'build 4127' }, passed, null],
    [passed, passed, { label: 'skipped', tone: 'muted' }, passed],
  ];

  host.replaceChildren(columns, lines, heat, nightly, bars);
}
