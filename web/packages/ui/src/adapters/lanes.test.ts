import type { JournalRow } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { lanesFromJournal } from './lanes.js';

const row = (key: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T10:00:00Z', key, kind: 'k', stop: 'completed', ok: true, ...extra,
});
const none = new Map();

describe('lanesFromJournal', () => {
  const end = Date.parse('2026-10-11T10:00:00Z');

  it('lays finished tasks on lanes by kind, in order of first start', () => {
    const tl = lanesFromJournal(
      [row('a', { kind: 'late', wall_s: 10 }), row('b', { kind: 'early', wall_s: 60, executor: 'python' }), row('c', { kind: 'late', stop: 'error', ok: false })],
      [],
      none,
      '',
    );
    expect(tl?.lanes.map((l) => [l.label, l.bars.map((b) => b.style)])).toEqual([
      ['early', ['py']],
      ['late', ['llm', 'bad']],
    ]);
    expect(tl?.lanes[0]?.bars[0]).toMatchObject({ start: end - 60e3, end });
    expect(tl?.omitted).toBe(0);
  });

  it('leaves out what ended more than six hours before the newest', () => {
    const tl = lanesFromJournal([row('old', { ts: '2026-10-11T03:00:00Z' }), row('new')], [], none, '');
    expect(tl?.omitted).toBe(1);
    expect(tl?.lanes.flatMap((l) => l.bars)).toHaveLength(1);
  });

  it('draws running tasks with no end, named in their tooltip', () => {
    const tl = lanesFromJournal([], [{ kind: 'k', cls: 'llm', t0: end }], none, '');
    expect(tl?.lanes[0]?.bars).toEqual([{ id: 'live0', style: 'run', start: end, end: null, label: 'k\nrunning' }]);
  });

  it('greys a task that never started, and names it with its stop in the tooltip', () => {
    const tl = lanesFromJournal([row('z', { kind: 'k', unit: 'u', stop: 'invalid_input', ok: false })], [], none, '');
    const bar = tl?.lanes[0]?.bars[0];
    expect(bar?.style).toBe('idle');
    expect(bar?.label.split('\n')[0]).toBe('k · u');
  });

  it('is null with nothing to draw', () => {
    expect(lanesFromJournal([], [], none, '')).toBeNull();
  });
});
