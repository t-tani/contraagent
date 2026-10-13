// Lanes: hand-written jobs on a time axis, a lane per stage, one job running.
// The host names the looks of the bars; their labels are the legend.
import '@contraagent/elements/lanes/define';
import type { Lane, LaneStyle } from '@contraagent/elements/lanes';

const barStyles: Record<string, LaneStyle> = {
  passed: { label: 'passed', color: 'var(--ca-status-done)' },
  failed: { label: 'failed', color: 'var(--ca-status-failed)', pattern: 'hatched' },
  running: { label: 'running', color: 'var(--ca-status-running)', pattern: 'striped' },
};

export function mount(host: HTMLElement): void {
  const now = Date.now();
  const min = 60e3;
  const lanes: Lane[] = [
    {
      id: 'build',
      label: 'Build',
      bars: [
        { id: 'b1', start: now - 9 * min, end: now - 6 * min, style: 'failed', label: 'Build #1\nfailed' },
        { id: 'b2', start: now - 6 * min, end: now - 3 * min, style: 'passed', label: 'Build #2\npassed' },
      ],
    },
    {
      id: 'test',
      label: 'Test',
      bars: [
        { id: 't1', start: now - 3 * min, end: null, style: 'running', label: 'Unit tests\nrunning' },
        { id: 't2', start: now - 2.5 * min, end: now - 1 * min, style: 'passed', label: 'Lint\npassed' },
      ],
    },
  ];
  const el = document.createElement('cae-lanes');
  el.lanes = lanes;
  el.barStyles = barStyles;
  el.live = true;
  el.omitted = 3;
  el.strings = { omitted: (n) => `${n} older jobs not shown` };
  host.replaceChildren(el);
}
