// An export in words: when it was written, and what it does not hold.
import type { ExportInfo } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { exportTip, exportedLabel, notInExport } from './export.js';
import { localTime } from './format.js';

const EXPORT: ExportInfo = {
  exported_at: '2026-10-14T21:30:00+09:00',
  runs: ['r1'],
  left_out: ['transcripts', 'processes'],
  redacted: ['host', 'paths'],
};

describe('export words', () => {
  it('state when the export was written and what it leaves out', () => {
    expect(exportedLabel(EXPORT)).toBe(`Exported ${localTime(EXPORT.exported_at, true)}`);
    expect(exportTip(EXPORT)).toBe('Not in this export: transcripts and processes');
    expect(notInExport()).toBe('not in this export');
  });
});
