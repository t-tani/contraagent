import { describe, expect, it } from 'vitest';
import { monitorTabs } from './tabs.js';

describe('the tab list', () => {
  it('has a tab per run panel, after the built-in ones; a trends panel is not a run\'s tab', () => {
    const tabs = monitorTabs([
      { name: 'findings', title: 'Findings', description: '', icon: '◆', scope: 'run' },
      { name: 'trend', title: 'Trend', description: '', icon: '▤', scope: 'trends' },
      { name: 'old', title: 'Old', description: '', icon: '▤' },
    ]);
    expect(tabs.filter((t) => t.panel).map((t) => t.id)).toEqual(['panel:findings', 'panel:old']);
    expect(tabs[0]!.id).toBe('overview');
  });
});
