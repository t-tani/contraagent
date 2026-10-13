// Stat tiles: hand-written figures, one with a tone and a link. The host holds
// the figures and answers `cae-action`.
import '@contraagent/elements/tiles/define';
import type { StatTile } from '@contraagent/elements/tiles';

const tiles: StatTile[] = [
  { id: 'jobs', label: 'Jobs', value: 24, sub: [[{ text: '22 passed' }, { text: '2 failed', tone: 'failed' }]] },
  {
    id: 'failed',
    label: 'Failed jobs',
    value: 2,
    tone: 'failed',
    sub: [['Unit tests', 'Lint']],
    action: { id: 'list', label: 'Failed jobs in the log' },
  },
  { id: 'time', label: 'Build time', value: '14m 05s', sub: [['Longest: Unit tests']], tip: 'Sum over all jobs' },
  { id: 'queued', label: 'Queued', value: 0, sub: [['No jobs waiting']] },
];

export function mount(host: HTMLElement): void {
  const grid = document.createElement('cae-stat-tiles');
  grid.columns = 4;
  grid.tiles = tiles;
  const shown = document.createElement('p');
  grid.addEventListener('cae-action', (e) => (shown.textContent = `Action: ${e.detail.action} of ${e.detail.id}`));
  host.replaceChildren(grid, shown);
}
